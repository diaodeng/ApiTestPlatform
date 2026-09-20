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
from modules.configuration_task.dao.task_dao import (
    ConfigurationTaskRunDao,
    ConfigurationTaskVersionDao,
    load_json_object,
)
from modules.configuration_task.dao.task_dao import (
    load_json_list as load_run_list,
)
from modules.configuration_task.entity.do.task_do import ConfigurationTaskVersion
from modules.configuration_task.entity.do.task_run_do import ConfigurationTaskRun
from modules.configuration_task.entity.vo.task_vo import (
    EvidencePolicyModel,
    StageApproveModel,
    StageSplitRuleModel,
    TaskRunStageModel,
)
from modules.configuration_task.service.evidence_status_service import (
    ConfigurationTaskEvidenceStatusService,
)
from modules.configuration_task.util.step_identity_util import (
    ensure_step_ids,
    step_id_map,
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
        """保存版本阶段切分，并把旧步骤索引转换为稳定步骤 ID。"""
        if version.status != "DRAFT":
            return StageServiceResult(False, f"版本当前状态不允许修改阶段：{version.status}")
        if not rules:
            return StageServiceResult(False, "至少需要一个阶段")
        if len(rules) > MAX_STAGES_PER_VERSION:
            return StageServiceResult(False, f"阶段数量不能超过 {MAX_STAGES_PER_VERSION}")

        steps = ensure_step_ids(load_json_list(version.steps_json))
        id_to_index = step_id_map(steps)
        covered_indexes: set[int] = set()
        keys: set[str] = set()
        stage_rows: list[dict[str, Any]] = []
        for order, rule in enumerate(rules, start=1):
            if rule.stage_key in keys:
                return StageServiceResult(False, f"阶段标识重复：{rule.stage_key}")
            keys.add(rule.stage_key)
            indexes = list(rule.step_indexes)
            step_ids = list(rule.step_ids)
            if step_ids:
                unknown_ids = [step_id for step_id in step_ids if step_id not in id_to_index]
                if unknown_ids:
                    return StageServiceResult(
                        False,
                        f"阶段 {rule.stage_key} 包含不存在的 stepId：{', '.join(unknown_ids[:3])}",
                    )
                mapped_indexes = [id_to_index[step_id] for step_id in step_ids]
                if indexes and set(indexes) != set(mapped_indexes):
                    return StageServiceResult(False, f"阶段 {rule.stage_key} 的 stepIds 与 stepIndexes 不一致")
                indexes = mapped_indexes
            else:
                if not indexes:
                    return StageServiceResult(False, f"阶段 {rule.stage_key} 至少包含一个步骤索引或 stepId")
                invalid_indexes = [index for index in indexes if index < 0 or index >= len(steps)]
                if invalid_indexes:
                    return StageServiceResult(
                        False,
                        f"阶段 {rule.stage_key} 包含不存在的步骤索引：{invalid_indexes[0]}",
                    )
                step_ids = [str(steps[index].get("stepId") or "") for index in indexes]
            if len(set(indexes)) != len(indexes):
                return StageServiceResult(False, f"阶段 {rule.stage_key} 的步骤不能重复")
            for index in indexes:
                if index in covered_indexes:
                    return StageServiceResult(False, f"步骤索引 {index} 被多个阶段重复覆盖")
                covered_indexes.add(index)
            policy = rule.evidence_policy.model_dump(mode="json", by_alias=False)
            stage_rows.append(
                {
                    "version_id": version.version_id,
                    "stage_key": rule.stage_key,
                    "stage_name": rule.stage_name or rule.stage_key,
                    "mode": rule.mode,
                    "stage_order": order,
                    "step_range_json": _dumps(sorted(indexes)),
                    "step_ids_json": _dumps(step_ids),
                    "evidence_policy_json": _dumps(policy),
                    "create_time": datetime.now(),
                }
            )
        if not covered_indexes:
            return StageServiceResult(False, "阶段未覆盖任何步骤")

        rows = ConfigurationTaskStageDao.replace_version_stages(db, version.version_id, stage_rows)
        if steps != load_json_list(version.steps_json):
            version.steps_json = _dumps(steps)
        db.commit()
        logger.info(
            f"保存版本阶段切分: version_id={version.version_id}, stages={len(rows)}, "
            f"covered_steps={len(covered_indexes)}, operator={operator}"
        )
        return StageServiceResult(True, "阶段保存成功", [cls.to_stage_def_model(row) for row in rows])

    @classmethod
    def validate_version_stages_for_publish(cls, db: Session, version_id: int) -> str:
        """发布前校验阶段引用和证据策略，拒绝无法映射的旧索引。"""
        version = ConfigurationTaskVersionDao.get_version(db, version_id)
        if not version:
            return "版本不存在"
        steps = ensure_step_ids(load_json_list(version.steps_json))
        id_to_index = step_id_map(steps)
        definitions = ConfigurationTaskStageDao.list_version_stages(db, version_id)
        if not definitions:
            return ""
        covered: set[int] = set()
        for definition in definitions:
            indexes = load_json_list(definition.step_range_json)
            step_ids = load_json_list(definition.step_ids_json)
            if not step_ids:
                invalid = [index for index in indexes if index < 0 or index >= len(steps)]
                if invalid:
                    return f"阶段 {definition.stage_key} 包含不存在的步骤索引：{invalid[0]}"
                step_ids = [str(steps[index].get("stepId") or "") for index in indexes]
            unknown = [step_id for step_id in step_ids if step_id not in id_to_index]
            if unknown:
                return f"阶段 {definition.stage_key} 包含不存在的 stepId：{unknown[0]}"
            mapped_indexes = [id_to_index[step_id] for step_id in step_ids]
            if indexes and set(indexes) != set(mapped_indexes):
                return f"阶段 {definition.stage_key} 的步骤映射不一致"
            for index in mapped_indexes:
                if index in covered:
                    return f"步骤索引 {index} 被多个阶段重复覆盖"
                covered.add(index)
            try:
                policy = EvidencePolicyModel(**load_json_object(definition.evidence_policy_json))
            except Exception as exc:
                return f"阶段 {definition.stage_key} 的证据策略不合法：{exc}"
            if policy.mode == "NONE" and (policy.required_types or policy.required_evidence_keys):
                return f"阶段 {definition.stage_key} 为 NONE 时不能声明必需证据"
            candidates = []
            for index in mapped_indexes:
                step = steps[index]
                if step.get("actionType") != "capture_screenshot":
                    continue
                params = step.get("params") if isinstance(step.get("params"), dict) else {}
                candidates.append(
                    (
                        str(params.get("evidenceType") or "checkpoint_screenshot"),
                        str(params.get("evidenceKey") or step.get("stepId") or "").strip(),
                    )
                )
            if policy.mode in {"REQUIRED", "BEFORE_AFTER"} and not candidates:
                return f"阶段 {definition.stage_key} 要求证据，但未配置 capture_screenshot 步骤"
            candidate_types = {item[0] for item in candidates}
            if policy.mode == "BEFORE_AFTER":
                if not {"before_screenshot", "after_screenshot"}.issubset(candidate_types):
                    return f"阶段 {definition.stage_key} 的 BEFORE_AFTER 必须同时配置 before/after 截图"
            missing_types = [
                item for item in policy.required_types if item not in candidate_types
            ]
            if missing_types:
                return f"阶段 {definition.stage_key} 缺少证据类型：{', '.join(missing_types)}"
            candidate_keys = {candidate[1] for candidate in candidates}
            missing_keys = [
                item for item in policy.required_evidence_keys if item not in candidate_keys
            ]
            if missing_keys:
                return f"阶段 {definition.stage_key} 缺少证据键：{', '.join(missing_keys[:3])}"
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
            "stepIds": load_json_list(row.step_ids_json),
            "evidencePolicy": EvidencePolicyModel(**(load_json_object(row.evidence_policy_json) or {})).model_dump(
                by_alias=True
            ),
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
        steps = ensure_step_ids(load_json_list(getattr(version, "steps_json", "[]")))
        all_step_ids = [str(step.get("stepId") or "") for step in steps if isinstance(step, dict)]
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
                    "step_range_json": _dumps(list(range(len(steps)))),
                    "step_ids_json": _dumps(all_step_ids),
                    "evidence_policy_json": _dumps(EvidencePolicyModel().model_dump(mode="json")),
                    "evidence_status": "NOT_REQUIRED",
                    "evidence_missing_json": "[]",
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
                    "step_ids_json": definition.step_ids_json or "[]",
                    "evidence_policy_json": definition.evidence_policy_json or "{}",
                    "evidence_status": "NOT_REQUIRED",
                    "evidence_missing_json": "[]",
                    # WRITE 阶段创建即挂起审批，其余阶段等待顺序执行。
                    "status": "WAITING_APPROVAL" if definition.mode == "WRITE" else "PENDING",
                    "create_time": now,
                    "update_time": now,
                }
                for definition in definitions
            ]
        return ConfigurationTaskStageDao.add_run_stages(db, snapshots)

    @classmethod
    def list_run_stage_entities(cls, db: Session, task_run_id: int) -> list:
        """返回运行阶段 ORM 快照，供运行消息和证据状态服务编排使用。"""
        return ConfigurationTaskStageDao.list_run_stages(db, task_run_id)

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
            stepIds=load_json_list(row.step_ids_json),
            evidencePolicy=EvidencePolicyModel(**(load_json_object(row.evidence_policy_json) or {})),
            evidenceStatus=row.evidence_status or "NOT_REQUIRED",
            evidenceMissing=load_json_list(row.evidence_missing_json),
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
        row = ConfigurationTaskStageDao.get_run_stage(db, run_stage_id)
        if not row:
            logger.warning(f"阶段终态更新失败，运行阶段不存在: run_stage_id={run_stage_id}")
            return
        if row.status in {"SUCCESS", "FAILED", "SKIPPED", "CANCELLED"}:
            # 迟到或重复事件不能覆盖已经确定的阶段终态，避免 SUCCESS/FAILED 逆向回写。
            logger.debug(
                f"忽略已终态阶段的重复更新: run_stage_id={run_stage_id}, status={row.status}"
            )
            return

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
            for later in ConfigurationTaskStageDao.list_run_stages(db, row.task_run_id):
                if later.stage_order > row.stage_order and later.status in {"PENDING", "WAITING_APPROVAL"}:
                    ConfigurationTaskStageDao.update_run_stage(
                        db,
                        later.run_stage_id,
                        {
                            "status": "SKIPPED",
                            "error_code": "PREVIOUS_STAGE_FAILED",
                            "error_message": "前置阶段执行失败，已跳过",
                        },
                    )

        # 阶段终态与证据状态在同一事务中刷新，避免阶段已经结束但
        # 运行详情仍显示旧的 PENDING/NOT_REQUIRED 证据状态。
        ConfigurationTaskEvidenceStatusService.refresh_run_and_stages(
            db,
            row.task_run_id,
            commit=False,
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
        run = ConfigurationTaskRunDao.get_run(db, row.task_run_id)
        if not run:
            return StageServiceResult(False, "所属运行不存在")
        if run.status in {"SUCCESS", "FAILED", "CANCELLED"}:
            return StageServiceResult(False, f"运行已结束，不允许重试阶段：{run.status}")

        reset_values = {
            "retry_count": row.retry_count + 1,
            "error_code": "",
            "error_message": "",
            "evidence_status": "PENDING",
            "evidence_missing_json": "[]",
            "result_json": "{}",
            "started_at": None,
            "ended_at": None,
        }
        if row.mode == "WRITE":
            # WRITE 重试必须重新走审批闸门，不允许复用上一轮审批结果。
            ConfigurationTaskStageDao.update_run_stage(
                db,
                run_stage_id,
                {
                    **reset_values,
                    "status": "WAITING_APPROVAL",
                    "approved_by": "",
                    "approved_at": None,
                },
            )
        else:
            ConfigurationTaskStageDao.update_run_stage(
                db,
                run_stage_id,
                {
                    **reset_values,
                    "status": "PENDING",
                },
            )
        db.commit()
        logger.info(f"阶段重试已受理: run_stage_id={run_stage_id}, operator={operator}")
        refreshed = ConfigurationTaskStageDao.get_run_stage(db, run_stage_id)
        return StageServiceResult(True, "阶段已重置，等待执行", cls.to_run_stage_model(refreshed))
