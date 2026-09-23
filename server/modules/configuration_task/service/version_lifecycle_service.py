"""任务版本生命周期服务：复制、删除、废弃、撤销发布。

版本快照不可变原则的配套出口：
- 已发布版本不允许编辑（update_version 锁定 DRAFT），运行消息下发时步骤
  实时读取版本 steps_json，因此已发布版本绝不允许内容变更；
- 需要修改时通过"复制为新草稿"派生可编辑副本（步骤保留原 stepId，阶段
  切分一并复制，复制件与源版本解耦）；
- 草稿可物理删除（阶段定义一并清理）；已发布版本只能废弃（DEPRECATED），
  废弃与撤销发布都会处理任务"当前发布版本"指针的回退；
- 撤销发布仅允许从未运行过的版本（有运行记录时回退会破坏运行可追溯性，
  应改用"废弃 + 复制"路径）。
"""

from datetime import datetime

from loguru import logger
from sqlalchemy.orm import Session

from modules.configuration_task.dao.stage_artifact_dao import ConfigurationTaskStageDao
from modules.configuration_task.dao.task_dao import (
    ConfigurationTaskDao,
    ConfigurationTaskRunDao,
    ConfigurationTaskVersionDao,
)
from modules.configuration_task.service.task_service import (
    ConfigurationTaskService,
    ConfigurationTaskServiceResult,
)

_OPERATOR_EMPTY = ""


class ConfigurationTaskVersionLifecycleService:
    """版本生命周期操作：只做状态迁移与派生，不承接步骤内容编辑。"""

    @staticmethod
    def _operator(current_user) -> str:
        """取操作人名称，用于审计字段。"""
        return current_user.user.user_name if current_user and current_user.user else "system"

    @staticmethod
    def _repoint_current_version(db, task_id: int, excluded_version_id: int, operator: str) -> None:
        """任务当前发布版本指针回退：指向 version_no 最大的其他已发布版本，无则置空。

        废弃/撤销发布后调用；excluded_version_id 是刚被废弃或撤销的版本。
        """
        versions = ConfigurationTaskVersionDao.list_versions(db, task_id, limit=200)
        fallback = next(
            (
                row
                for row in versions
                if row.version_id != excluded_version_id and row.status == "PUBLISHED"
            ),
            None,
        )
        if fallback:
            values = {
                "current_version_id": fallback.version_id,
                "current_version_no": fallback.version_no,
            }
        else:
            values = {"current_version_id": None, "current_version_no": None}
        ConfigurationTaskDao.update_task(db, task_id, {**values, "update_by": operator})
        logger.info(
            f"任务当前版本指针回退: task_id={task_id}, "
            f"current_version_id={values['current_version_id']}, operator={operator}"
        )

    @classmethod
    def copy_version(cls, db: Session, version_id: int, current_user) -> ConfigurationTaskServiceResult:
        """复制任意版本为新草稿：步骤/绑定/变量原样保留（stepId 不变），阶段切分一并复制。"""
        operator = cls._operator(current_user)
        row = ConfigurationTaskVersionDao.get_version(db, version_id)
        if not row:
            return ConfigurationTaskServiceResult(False, "版本不存在")
        version_no = ConfigurationTaskVersionDao.get_max_version_no(db, row.task_id) + 1
        now = datetime.now()
        new_row = ConfigurationTaskVersionDao.add_version(
            db,
            {
                "task_id": row.task_id,
                "version_no": version_no,
                "status": "DRAFT",
                "start_url": row.start_url,
                "browser_name": row.browser_name,
                "headless": bool(row.headless),
                "credential_binding_id": row.credential_binding_id or "",
                "variables_json": row.variables_json,
                "steps_json": row.steps_json,
                "input_bindings_json": row.input_bindings_json,
                "publish_by": _OPERATOR_EMPTY,
                "publish_time": None,
                "create_by": operator,
                "create_time": now,
                "update_by": operator,
                "update_time": now,
            },
        )
        # 阶段切分一并复制：stepId 未变，step_ids_json 可直接沿用原值。
        stage_rows = ConfigurationTaskStageDao.list_version_stages(db, version_id)
        if stage_rows:
            ConfigurationTaskStageDao.replace_version_stages(
                db,
                new_row.version_id,
                [
                    {
                        "version_id": new_row.version_id,
                        "stage_key": stage.stage_key,
                        "stage_name": stage.stage_name,
                        "mode": stage.mode,
                        "stage_order": stage.stage_order,
                        "step_range_json": stage.step_range_json,
                        "step_ids_json": stage.step_ids_json,
                        "evidence_policy_json": stage.evidence_policy_json,
                    }
                    for stage in stage_rows
                ],
            )
        db.commit()
        logger.info(
            f"复制任务版本为新草稿: source_version_id={version_id}, "
            f"new_version_id={new_row.version_id}, version_no={version_no}, operator={operator}"
        )
        refreshed = ConfigurationTaskVersionDao.get_version(db, new_row.version_id)
        return ConfigurationTaskServiceResult(
            True,
            f"已复制为新草稿 v{version_no}",
            ConfigurationTaskService.to_version_model(refreshed),
        )

    @classmethod
    def delete_version(cls, db: Session, version_id: int, current_user) -> ConfigurationTaskServiceResult:
        """删除草稿版本：仅草稿可删除，且不允许存在运行记录引用。"""
        operator = cls._operator(current_user)
        row = ConfigurationTaskVersionDao.get_version(db, version_id)
        if not row:
            return ConfigurationTaskServiceResult(False, "版本不存在")
        if row.status != "DRAFT":
            return ConfigurationTaskServiceResult(False, f"仅草稿版本可删除，当前状态：{row.status}")
        run_count = ConfigurationTaskRunDao.count_runs_by_version(db, version_id)
        if run_count > 0:
            return ConfigurationTaskServiceResult(False, f"版本存在 {run_count} 条运行记录，不能删除")
        task = ConfigurationTaskDao.get_task(db, row.task_id)
        if task and task.current_version_id == row.version_id:
            # 草稿正常不会成为当前版本，此处为防御性清理。
            ConfigurationTaskDao.update_task(
                db,
                row.task_id,
                {"current_version_id": None, "current_version_no": None, "update_by": operator},
            )
        ConfigurationTaskStageDao.delete_version_stages(db, version_id)
        ConfigurationTaskVersionDao.delete_version(db, version_id)
        db.commit()
        logger.info(
            f"删除任务版本草稿: version_id={version_id}, task_id={row.task_id}, "
            f"version_no={row.version_no}, operator={operator}"
        )
        return ConfigurationTaskServiceResult(True, f"草稿 v{row.version_no} 已删除")

    @classmethod
    def deprecate_version(cls, db: Session, version_id: int, current_user) -> ConfigurationTaskServiceResult:
        """废弃已发布版本：不可再发起运行，保留记录供追溯，可复制派生新草稿。"""
        operator = cls._operator(current_user)
        row = ConfigurationTaskVersionDao.get_version(db, version_id)
        if not row:
            return ConfigurationTaskServiceResult(False, "版本不存在")
        if row.status != "PUBLISHED":
            return ConfigurationTaskServiceResult(False, f"仅已发布版本可废弃，当前状态：{row.status}")
        ConfigurationTaskVersionDao.update_version(
            db,
            version_id,
            {"status": "DEPRECATED", "update_by": operator},
        )
        task = ConfigurationTaskDao.get_task(db, row.task_id)
        if task and task.current_version_id == row.version_id:
            cls._repoint_current_version(db, row.task_id, row.version_id, operator)
        db.commit()
        logger.info(
            f"废弃任务版本: version_id={version_id}, task_id={row.task_id}, "
            f"version_no={row.version_no}, operator={operator}"
        )
        refreshed = ConfigurationTaskVersionDao.get_version(db, version_id)
        return ConfigurationTaskServiceResult(
            True,
            f"版本 v{row.version_no} 已废弃",
            ConfigurationTaskService.to_version_model(refreshed),
        )

    @classmethod
    def unpublish_version(cls, db: Session, version_id: int, current_user) -> ConfigurationTaskServiceResult:
        """撤销发布：回退为草稿以便编辑；仅允许从未运行过的版本。"""
        operator = cls._operator(current_user)
        row = ConfigurationTaskVersionDao.get_version(db, version_id)
        if not row:
            return ConfigurationTaskServiceResult(False, "版本不存在")
        if row.status != "PUBLISHED":
            return ConfigurationTaskServiceResult(False, f"仅已发布版本可撤销发布，当前状态：{row.status}")
        run_count = ConfigurationTaskRunDao.count_runs_by_version(db, version_id)
        if run_count > 0:
            return ConfigurationTaskServiceResult(
                False,
                f"版本已有 {run_count} 条运行记录，不能撤销发布；请改用废弃后复制新草稿",
            )
        ConfigurationTaskVersionDao.update_version(
            db,
            version_id,
            {
                "status": "DRAFT",
                "publish_by": _OPERATOR_EMPTY,
                "publish_time": None,
                "update_by": operator,
            },
        )
        task = ConfigurationTaskDao.get_task(db, row.task_id)
        if task and task.current_version_id == row.version_id:
            cls._repoint_current_version(db, row.task_id, row.version_id, operator)
        db.commit()
        logger.info(
            f"撤销任务版本发布: version_id={version_id}, task_id={row.task_id}, "
            f"version_no={row.version_no}, operator={operator}"
        )
        refreshed = ConfigurationTaskVersionDao.get_version(db, version_id)
        return ConfigurationTaskServiceResult(
            True,
            f"版本 v{row.version_no} 已撤销发布，可继续编辑",
            ConfigurationTaskService.to_version_model(refreshed),
        )
