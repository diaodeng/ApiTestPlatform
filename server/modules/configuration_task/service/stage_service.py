"""配置任务阶段服务：版本阶段切分、运行阶段快照、审批闸门和阶段重试。

阶段模式语义：
- READ / VERIFY：查询与验证，自动执行；
- PREPARE_WRITE：自动执行，但版本发布校验要求其后的 WRITE 阶段存在审批闸门；
- WRITE：执行前进入 WAITING_APPROVAL，审批通过才下发对应步骤。
"""

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from loguru import logger
from sqlalchemy.orm import Session

from module_admin.entity.vo.user_vo import CurrentUserModel
from modules.configuration_task.dao.stage_artifact_dao import (
    ConfigurationTaskStageDao,
    load_json_list,
)
from modules.configuration_task.dao.task_dao import ConfigurationTaskRunDao
from modules.configuration_task.dao.task_dao import load_json_list as load_run_list
from modules.configuration_task.entity.do.task_do import ConfigurationTaskVersion
from modules.configuration_task.entity.do.task_run_do import ConfigurationTaskRun
from modules.configuration_task.entity.vo.task_vo import (
    StageApproveModel,
    StageSplitRuleModel,
    TaskRunStageModel,
)

MAX_STAGES_PER_VERSION = 20


@dataclass
class StageServiceResult:
    """阶段操作结果，供 Controller 转换为统一 HTTP 响应。"""

    is_success: bool
    message: str
    result: Any = None


def _dumps(value) -> str:
    """序列化为紧凑 JSON。"""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


class ConfigurationTaskStageService:
    """阶段切分、快照、审批与重试。"""

    @staticmethod
    def _operator(current_user: CurrentUserModel) -> str:
        """提取当前用户名。"""
        user = current_user.user
        return user.user_name if user else "system"

    # ---------- 版本阶段切分 ----------

    @classmethod
    def save_version_stages(
        cls,
        db: Session,
        version: ConfigurationTaskVersion,
        rules: list[StageSplitRuleModel],
        operator: str,
    ) -> StageServiceResult:
        """保存版本阶段切分；仅草稿可改，WRITE 阶段校验版本声明了审批要求。"""
        if version.status != "DRAFT":
            return StageServiceResult(False, f"版本当前状态不允许修改阶段：{version.status}")
        if not rules:
            return StageServiceResult(False, "至少需要一个阶段")
        if len(rules) > MAX_STAGES_PER_VERSION:
            return StageServiceResult(False, f"阶段数量不能超过 {MAX_STAGES_PER_VERSION}")
        covered: set[int] = set()
        keys: set[str] = set()
        for rule in rules:
            if rule.stage_key in keys:
                return StageServiceResult(False, f"阶段标识重复：{rule.stage_key}")
            keys.add(rule.stage_key)
            if not rule.step_indexes:
                return StageServiceResult(False, f"阶段 {rule.stage_key} 至少包含一个步骤索引")
            for index in rule.step_indexes:
                if index in covered:
                    return StageServiceResult(False, f"步骤索引 {index} 被多个阶段重复覆盖")
                covered.add(index)
        if not covered:
            return StageServiceResult(False, "阶段未覆盖任何步骤")

        now = datetime.now()
        rows = ConfigurationTaskStageDao.replace_version_stages(
            db,
            version.version_id,
            [
                {
                    "version_id": version.version_id,
                    "stage_key": rule.stage_key,
                    "stage_name": rule.stage_name or rule.stage_key,
                    "mode": rule.mode,
                    "stage_order": order + 1,
                    "step_range_json": _dumps(sorted(rule.step_indexes)),
                    "create_time": now,
                }
                for order, rule in enumerate(rules)
            ],
        )
        db.commit()
        logger.info(
            f"保存版本阶段切分: version_id={version.version_id}, stages={len(rows)}, operator={operator}"
        )
        return StageServiceResult(True, "阶段保存成功", [cls.to_stage_def_model(row) for row in rows])

    @classmethod
    def validate_version_stages_for_publish(cls, db: Session, version_id: int) -> str:
        """发布校验：阶段切分为可选能力，未声明阶段时按单阶段全量执行处理。

        保留独立入口便于后续扩展发布期阶段约束；当前总是返回空串表示通过。
        """
        del db, version_id
        return ""

    @classmethod
    def to_stage_def_model(cls, row) -> dict[str, Any]:
        """版本阶段定义转响应字典。"""
        return {
            "stageId": str(row.stage_id),
            "versionId": str(row.version_id),
            "stageKey": row.stage_key,
            "stageName": row.stage_name,
            "mode": row.mode,
            "stageOrder": row.stage_order,
            "stepIndexes": load_json_list(row.step_range_json),
        }

    # ---------- 运行阶段快照 ----------

    @classmethod
    def snapshot_run_stages(
        cls,
        db: Session,
        run: ConfigurationTaskRun,
        version: ConfigurationTaskVersion,
    ) -> list:
        """运行创建时从版本阶段复制快照；未声明阶段时生成单一全量阶段。"""
        definitions = ConfigurationTaskStageDao.list_version_stages(db, version.version_id)
        now = datetime.now()
        if not definitions:
            # 未声明阶段：单阶段全量步骤，模式 READ，保持既有同步执行语义。
            snapshots = [
                {
                    "task_run_id": run.task_run_id,
                    "stage_id": version.version_id,
                    "stage_key": "all",
                    "stage_name": "全部步骤",
                    "mode": "READ",
                    "stage_order": 1,
                    "step_range_json": "[]",
                    "status": "PENDING",
                    "create_time": now,
                    "update_time": now,
                }
            ]
        else:
            snapshots = [
                {
                    "task_run_id": run.task_run_id,
                    "stage_id": definition.stage_id,
                    "stage_key": definition.stage_key,
                    "stage_name": definition.stage_name,
                    "mode": definition.mode,
                    "stage_order": definition.stage_order,
                    "step_range_json": definition.step_range_json,
                    # WRITE 阶段创建即挂起审批，其余阶段等待顺序执行。
                    "status": "WAITING_APPROVAL" if definition.mode == "WRITE" else "PENDING",
                    "create_time": now,
                    "update_time": now,
                }
                for definition in definitions
            ]
        return ConfigurationTaskStageDao.add_run_stages(db, snapshots)

    @classmethod
    def list_run_stages(cls, db: Session, task_run_id: int) -> list[TaskRunStageModel]:
        """查询运行阶段列表。"""
        rows = ConfigurationTaskStageDao.list_run_stages(db, task_run_id)
        return [cls.to_run_stage_model(row) for row in rows]

    @classmethod
    def to_run_stage_model(cls, row) -> TaskRunStageModel:
        """运行阶段 ORM 转响应模型，BIGINT ID 字符串化。"""
        return TaskRunStageModel(
            runStageId=str(row.run_stage_id),
            taskRunId=str(row.task_run_id),
            stageId=str(row.stage_id),
            stageKey=row.stage_key,
            stageName=row.stage_name,
            mode=row.mode,
            stageOrder=row.stage_order,
            stepIndexes=load_json_list(row.step_range_json),
            status=row.status,
            result=load_run_list(row.result_json) if isinstance(row.result_json, list) else {},
            errorCode=row.error_code or "",
            errorMessage=row.error_message or "",
            retryCount=row.retry_count,
            approvedBy=row.approved_by or "",
            approvedAt=row.approved_at,
            startedAt=row.started_at,
            endedAt=row.ended_at,
        )

    # ---------- 审批闸门 ----------

    @classmethod
    def approve_stage(
        cls,
        db: Session,
        run_stage_id: int,
        model: StageApproveModel,
        current_user: CurrentUserModel,
    ) -> StageServiceResult:
        """审批 WRITE 阶段：通过后置 PENDING 等待执行，拒绝则阶段与运行收敛 FAILED/CANCELLED。"""
        operator = cls._operator(current_user)
        row = ConfigurationTaskStageDao.get_run_stage(db, run_stage_id)
        if not row:
            return StageServiceResult(False, "运行阶段不存在")
        if row.mode != "WRITE":
            return StageServiceResult(False, "只有 WRITE 阶段需要审批")
        if row.status != "WAITING_APPROVAL":
            return StageServiceResult(False, f"阶段当前状态不允许审批：{row.status}")

        now = datetime.now()
        if not model.approved:
            ConfigurationTaskStageDao.update_run_stage(
                db,
                run_stage_id,
                {
                    "status": "CANCELLED",
                    "error_code": "STAGE_REJECTED",
                    "error_message": (model.comment or "阶段审批被拒绝")[:500],
                    "approved_by": operator,
                    "approved_at": now,
                },
            )
            ConfigurationTaskRunDao.update_run(
                db,
                row.task_run_id,
                {
                    "status": "CANCELLED",
                    "error_code": "STAGE_REJECTED",
                    "error_message": (model.comment or "WRITE 阶段审批被拒绝")[:2000],
                    "ended_at": now,
                    "update_by": operator,
                },
            )
            db.commit()
            logger.warning(
                f"WRITE 阶段审批被拒绝: run_stage_id={run_stage_id}, task_run_id={row.task_run_id}, operator={operator}"
            )
            return StageServiceResult(False, "阶段审批被拒绝，运行已取消")

        ConfigurationTaskStageDao.update_run_stage(
            db,
            run_stage_id,
            {
                "status": "PENDING",
                "approved_by": operator,
                "approved_at": now,
                "error_code": "",
                "error_message": "",
            },
        )
        db.commit()
        logger.info(
            f"WRITE 阶段审批通过: run_stage_id={run_stage_id}, task_run_id={row.task_run_id}, operator={operator}"
        )
        refreshed = ConfigurationTaskStageDao.get_run_stage(db, run_stage_id)
        return StageServiceResult(True, "审批通过，阶段等待执行", cls.to_run_stage_model(refreshed))

    # ---------- 阶段执行推进 ----------

    @classmethod
    def mark_stage_running(cls, db: Session, run_stage_id: int) -> None:
        """阶段开始执行。"""
        ConfigurationTaskStageDao.update_run_stage(
            db,
            run_stage_id,
            {"status": "RUNNING", "started_at": datetime.now()},
        )
        db.commit()

    @classmethod
    def mark_stage_finished(
        cls,
        db: Session,
        run_stage_id: int,
        success: bool,
        result: dict[str, Any] | None,
        error_code: str = "",
        error_message: str = "",
    ) -> None:
        """阶段终态落库；失败时把同一运行的后续阶段全部跳过。"""
        now = datetime.now()
        ConfigurationTaskStageDao.update_run_stage(
            db,
            run_stage_id,
            {
                "status": "SUCCESS" if success else "FAILED",
                "result_json": _dumps(result or {}),
                "error_code": error_code,
                "error_message": (error_message or "")[:2000],
                "ended_at": now,
            },
        )
        if not success:
            row = ConfigurationTaskStageDao.get_run_stage(db, run_stage_id)
            if row:
                for later in ConfigurationTaskStageDao.list_run_stages(db, row.task_run_id):
                    if later.stage_order > row.stage_order and later.status in {"PENDING", "WAITING_APPROVAL"}:
                        ConfigurationTaskStageDao.update_run_stage(
                            db,
                            later.run_stage_id,
                            {"status": "SKIPPED", "error_code": "PREVIOUS_STAGE_FAILED"},
                        )
        db.commit()

    @classmethod
    def retry_stage(
        cls,
        db: Session,
        run_stage_id: int,
        current_user: CurrentUserModel,
    ) -> StageServiceResult:
        """重试失败阶段：仅 FAILED 阶段可重试，重试后回到等待执行状态。"""
        operator = cls._operator(current_user)
        row = ConfigurationTaskStageDao.get_run_stage(db, run_stage_id)
        if not row:
            return StageServiceResult(False, "运行阶段不存在")
        if row.status != "FAILED":
            return StageServiceResult(False, f"只有失败阶段允许重试：{row.status}")
        if row.mode == "WRITE":
            # WRITE 重试必须重新走审批闸门，不允许绕过。
            ConfigurationTaskStageDao.update_run_stage(
                db,
                run_stage_id,
                {
                    "status": "WAITING_APPROVAL",
                    "retry_count": row.retry_count + 1,
                    "error_code": "",
                    "error_message": "",
                },
            )
        else:
            ConfigurationTaskStageDao.update_run_stage(
                db,
                run_stage_id,
                {
                    "status": "PENDING",
                    "retry_count": row.retry_count + 1,
                    "error_code": "",
                    "error_message": "",
                },
            )
        db.commit()
        logger.info(f"阶段重试已受理: run_stage_id={run_stage_id}, operator={operator}")
        refreshed = ConfigurationTaskStageDao.get_run_stage(db, run_stage_id)
        return StageServiceResult(True, "阶段已重置，等待执行", cls.to_run_stage_model(refreshed))
