"""任务系统凭证映射服务：任务级"系统标识 → 凭证绑定"的环境配置。

设计要点：
- 映射独立于版本快照，发布后仍可修改（凭证属于环境配置，不冻结）；
- 阶段/阶段模板（二期）通过 system_key 声明目标系统，任务级映射统一维护绑定；
- 保存为批量替换式：一次提交完整映射清单，服务端整体重建，避免增量同步的
  一致性问题；映射量小（单任务最多 50 条），重建成本可忽略。
"""

from datetime import datetime

from loguru import logger
from sqlalchemy.orm import Session

from modules.configuration_task.dao.task_dao import (
    ConfigurationTaskCredentialMappingDao,
    ConfigurationTaskDao,
)
from modules.configuration_task.entity.vo.task_vo import (
    TaskCredentialMappingModel,
    TaskCredentialMappingSaveModel,
)
from modules.configuration_task.service.task_service import ConfigurationTaskServiceResult


class ConfigurationTaskCredentialMappingService:
    """系统凭证映射的查询与批量保存。"""

    @staticmethod
    def _operator(current_user) -> str:
        """取操作人名称，用于审计字段。"""
        return current_user.user.user_name if current_user and current_user.user else "system"

    @classmethod
    def list_mappings(cls, db: Session, task_id: int) -> list[TaskCredentialMappingModel]:
        """查询任务的全部映射。"""
        rows = ConfigurationTaskCredentialMappingDao.list_by_task(db, task_id)
        return [
            TaskCredentialMappingModel(
                system_key=row.system_key,
                credential_binding_id=row.credential_binding_id or "",
                remark=row.remark or "",
            )
            for row in rows
        ]

    @classmethod
    def save_mappings(
        cls,
        db: Session,
        task_id: int,
        model: TaskCredentialMappingSaveModel,
        current_user,
    ) -> ConfigurationTaskServiceResult:
        """批量替换式保存映射：整表重建，校验 system_key 唯一与绑定格式。"""
        operator = cls._operator(current_user)
        task = ConfigurationTaskDao.get_task(db, task_id)
        if not task:
            return ConfigurationTaskServiceResult(False, "任务不存在")

        seen_keys: set[str] = set()
        rows: list[dict] = []
        now = datetime.now()
        for item in model.mappings:
            key = (item.system_key or "").strip()
            if not key:
                return ConfigurationTaskServiceResult(False, "系统标识不能为空")
            if key in seen_keys:
                return ConfigurationTaskServiceResult(False, f"系统标识重复：{key}")
            seen_keys.add(key)
            binding_id = (item.credential_binding_id or "").strip()
            if binding_id and not binding_id.isdigit():
                return ConfigurationTaskServiceResult(False, f"系统 {key} 的凭证绑定ID必须是数字字符串")
            rows.append(
                {
                    "task_id": task_id,
                    "system_key": key,
                    "credential_binding_id": binding_id,
                    "remark": (item.remark or "").strip(),
                    "create_by": operator,
                    "create_time": now,
                    "update_by": operator,
                    "update_time": now,
                }
            )
        ConfigurationTaskCredentialMappingDao.delete_by_task(db, task_id)
        if rows:
            ConfigurationTaskCredentialMappingDao.add_mappings(db, rows)
        db.commit()
        logger.info(
            f"保存任务系统凭证映射: task_id={task_id}, count={len(rows)}, operator={operator}"
        )
        return ConfigurationTaskServiceResult(True, "凭证映射已保存", cls.list_mappings(db, task_id))
