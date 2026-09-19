"""配置任务定义与版本服务：任务 CRUD、版本草稿、发布校验和响应转换。"""

import json
from dataclasses import dataclass
from datetime import datetime

from loguru import logger
from sqlalchemy.orm import Session

from module_admin.entity.vo.user_vo import CurrentUserModel
from module_hrm.dao.agent_dao import AgentDao
from modules.configuration_task.dao.resource_dao import ResourceDao
from modules.configuration_task.dao.task_dao import (
    ConfigurationTaskDao,
    ConfigurationTaskVersionDao,
    load_json_list,
    load_json_object,
)
from modules.configuration_task.entity.do.task_do import ConfigurationTask, ConfigurationTaskVersion
from modules.configuration_task.entity.vo.task_vo import (
    TASK_BINDINGS_MAX_BYTES,
    TASK_STEPS_MAX_BYTES,
    TASK_VARIABLES_MAX_BYTES,
    ConfigurationTaskCreateModel,
    ConfigurationTaskDetailModel,
    ConfigurationTaskUpdateModel,
    TaskVersionCreateModel,
    TaskVersionDetailModel,
    TaskVersionUpdateModel,
)


@dataclass
class ConfigurationTaskServiceResult:
    """任务与版本操作结果，供 Controller 转换为统一 HTTP 响应。"""

    is_success: bool
    message: str
    result: ConfigurationTaskDetailModel | TaskVersionDetailModel | None = None


def _dumps(value) -> str:
    """序列化为紧凑 JSON，供 ORM 文本列保存。"""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


class ConfigurationTaskService:
    """配置任务与版本服务；运行执行独立在 Execution 服务中实现。"""

    @staticmethod
    def _operator(current_user: CurrentUserModel) -> str:
        """提取当前用户名，用于审计字段。"""
        user = current_user.user
        return user.user_name if user else "system"

    @classmethod
    def create_task(
        cls,
        db: Session,
        model: ConfigurationTaskCreateModel,
        current_user: CurrentUserModel,
    ) -> ConfigurationTaskServiceResult:
        """创建配置任务，要求 Agent 已登记；初始无发布版本。"""
        operator = cls._operator(current_user)
        agent = AgentDao.get_agent_by_code(db, model.agent_code)
        if not agent:
            return ConfigurationTaskServiceResult(False, "Agent 未登记")
        variables_json = _dumps(model.variables or {})
        if len(variables_json.encode("utf-8")) > TASK_VARIABLES_MAX_BYTES:
            return ConfigurationTaskServiceResult(False, "variables 超过大小限制")
        now = datetime.now()
        row = ConfigurationTaskDao.add_task(
            db,
            {
                "task_name": model.task_name,
                "description": model.description or "",
                "agent_code": model.agent_code,
                "variables_json": variables_json,
                "status": "ACTIVE",
                "create_by": operator,
                "create_time": now,
                "update_by": operator,
                "update_time": now,
                "remark": model.remark or "",
            },
        )
        db.commit()
        logger.info(f"创建配置任务，task_id={row.task_id}，agent_code={row.agent_code}，operator={operator}")
        return ConfigurationTaskServiceResult(True, "任务创建成功", cls.to_task_model(row))

    @classmethod
    def update_task(
        cls,
        db: Session,
        task_id: int,
        model: ConfigurationTaskUpdateModel,
        current_user: CurrentUserModel,
    ) -> ConfigurationTaskServiceResult:
        """更新任务基础信息；不改变已发布版本。"""
        operator = cls._operator(current_user)
        row = ConfigurationTaskDao.get_task(db, task_id)
        if not row:
            return ConfigurationTaskServiceResult(False, "任务不存在")
        values: dict = {}
        if model.task_name is not None:
            values["task_name"] = model.task_name
        if model.description is not None:
            values["description"] = model.description
        if model.agent_code is not None and model.agent_code != row.agent_code:
            agent = AgentDao.get_agent_by_code(db, model.agent_code)
            if not agent:
                return ConfigurationTaskServiceResult(False, "Agent 未登记")
            values["agent_code"] = model.agent_code
        if model.variables is not None:
            variables_json = _dumps(model.variables)
            if len(variables_json.encode("utf-8")) > TASK_VARIABLES_MAX_BYTES:
                return ConfigurationTaskServiceResult(False, "variables 超过大小限制")
            values["variables_json"] = variables_json
        if model.status is not None:
            values["status"] = model.status
        if model.remark is not None:
            values["remark"] = model.remark
        if not values:
            return ConfigurationTaskServiceResult(True, "无变更", cls.to_task_model(row))
        values["update_by"] = operator
        ConfigurationTaskDao.update_task(db, task_id, values)
        db.commit()
        logger.info(f"更新配置任务，task_id={task_id}，operator={operator}，fields={sorted(values)}")
        refreshed = ConfigurationTaskDao.get_task(db, task_id)
        return ConfigurationTaskServiceResult(True, "任务更新成功", cls.to_task_model(refreshed))

    @classmethod
    def get_task(cls, db: Session, task_id: int) -> ConfigurationTaskDetailModel | None:
        """查询任务详情。"""
        row = ConfigurationTaskDao.get_task(db, task_id)
        return cls.to_task_model(row) if row else None

    @classmethod
    def list_tasks(cls, db: Session, keyword: str = "", limit: int = 50) -> list[ConfigurationTaskDetailModel]:
        """查询任务列表。"""
        rows = ConfigurationTaskDao.list_tasks(db, keyword=keyword, limit=limit)
        return [cls.to_task_model(row) for row in rows]

    @classmethod
    def create_version(
        cls,
        db: Session,
        task_id: int,
        model: TaskVersionCreateModel,
        current_user: CurrentUserModel,
    ) -> ConfigurationTaskServiceResult:
        """创建版本草稿；不校验资源 READY，发布时统一校验。"""
        operator = cls._operator(current_user)
        task = ConfigurationTaskDao.get_task(db, task_id)
        if not task:
            return ConfigurationTaskServiceResult(False, "任务不存在")
        steps_json = _dumps(model.steps or [])
        if len(steps_json.encode("utf-8")) > TASK_STEPS_MAX_BYTES:
            return ConfigurationTaskServiceResult(False, "steps 超过大小限制")
        bindings_json = _dumps(model.input_bindings or {})
        if len(bindings_json.encode("utf-8")) > TASK_BINDINGS_MAX_BYTES:
            return ConfigurationTaskServiceResult(False, "inputBindings 超过大小限制")
        variables_json = _dumps(model.variables or {})
        if len(variables_json.encode("utf-8")) > TASK_VARIABLES_MAX_BYTES:
            return ConfigurationTaskServiceResult(False, "variables 超过大小限制")
        version_no = ConfigurationTaskVersionDao.get_max_version_no(db, task_id) + 1
        now = datetime.now()
        row = ConfigurationTaskVersionDao.add_version(
            db,
            {
                "task_id": task_id,
                "version_no": version_no,
                "status": "DRAFT",
                "start_url": model.start_url,
                "browser_name": model.browser_name or "chromium",
                "headless": bool(model.headless),
                "credential_binding_id": model.credential_binding_id or "",
                "variables_json": variables_json,
                "steps_json": steps_json,
                "input_bindings_json": bindings_json,
                "create_by": operator,
                "create_time": now,
                "update_by": operator,
                "update_time": now,
            },
        )
        db.commit()
        logger.info(f"创建任务版本草稿，task_id={task_id}，version_no={version_no}，operator={operator}")
        return ConfigurationTaskServiceResult(True, "版本草稿创建成功", cls.to_version_model(row))

    @classmethod
    def update_version(
        cls,
        db: Session,
        version_id: int,
        model: TaskVersionUpdateModel,
        current_user: CurrentUserModel,
    ) -> ConfigurationTaskServiceResult:
        """更新版本草稿；已发布版本不允许修改，保持快照不可变。"""
        operator = cls._operator(current_user)
        row = ConfigurationTaskVersionDao.get_version(db, version_id)
        if not row:
            return ConfigurationTaskServiceResult(False, "版本不存在")
        if row.status != "DRAFT":
            return ConfigurationTaskServiceResult(False, f"版本当前状态不允许修改：{row.status}")
        values: dict = {}
        if model.start_url is not None:
            values["start_url"] = model.start_url
        if model.browser_name is not None:
            values["browser_name"] = model.browser_name.strip().lower()
        if model.headless is not None:
            values["headless"] = bool(model.headless)
        if model.credential_binding_id is not None:
            values["credential_binding_id"] = model.credential_binding_id.strip()
        if model.variables is not None:
            variables_json = _dumps(model.variables)
            if len(variables_json.encode("utf-8")) > TASK_VARIABLES_MAX_BYTES:
                return ConfigurationTaskServiceResult(False, "variables 超过大小限制")
            values["variables_json"] = variables_json
        if model.steps is not None:
            steps_json = _dumps(model.steps)
            if len(steps_json.encode("utf-8")) > TASK_STEPS_MAX_BYTES:
                return ConfigurationTaskServiceResult(False, "steps 超过大小限制")
            values["steps_json"] = steps_json
        if model.input_bindings is not None:
            bindings = model.input_bindings or {}
            bindings_json = _dumps(bindings)
            if len(bindings_json.encode("utf-8")) > TASK_BINDINGS_MAX_BYTES:
                return ConfigurationTaskServiceResult(False, "inputBindings 超过大小限制")
            for file_key, resource_ids in bindings.items():
                key = str(file_key or "").strip()
                ids = [str(item).strip() for item in (resource_ids or []) if str(item or "").strip()]
                if not key or not ids:
                    return ConfigurationTaskServiceResult(False, "fileKey 和资源ID不能为空")
                if not all(item.isdigit() for item in ids):
                    return ConfigurationTaskServiceResult(False, "资源ID必须是数字字符串")
            values["input_bindings_json"] = bindings_json
        if not values:
            return ConfigurationTaskServiceResult(True, "无变更", cls.to_version_model(row))
        values["update_by"] = operator
        ConfigurationTaskVersionDao.update_version(db, version_id, values)
        db.commit()
        logger.info(f"更新任务版本草稿，version_id={version_id}，operator={operator}，fields={sorted(values)}")
        refreshed = ConfigurationTaskVersionDao.get_version(db, version_id)
        return ConfigurationTaskServiceResult(True, "版本草稿更新成功", cls.to_version_model(refreshed))

    @classmethod
    def publish_version(
        cls,
        db: Session,
        version_id: int,
        current_user: CurrentUserModel,
    ) -> ConfigurationTaskServiceResult:
        """发布版本：校验步骤、绑定资源 READY 且归属正确，成功后成为任务当前版本。"""
        operator = cls._operator(current_user)
        row = ConfigurationTaskVersionDao.get_version(db, version_id)
        if not row:
            return ConfigurationTaskServiceResult(False, "版本不存在")
        if row.status not in {"DRAFT", "PUBLISHED"}:
            return ConfigurationTaskServiceResult(False, f"版本当前状态不允许发布：{row.status}")
        steps = load_json_list(row.steps_json)
        enabled_steps = [step for step in steps if isinstance(step, dict) and step.get("enabled", True)]
        if not enabled_steps:
            return ConfigurationTaskServiceResult(False, "发布失败：版本必须包含至少一个启用的步骤")
        bindings = load_json_object(row.input_bindings_json)
        for file_key, resource_ids in bindings.items():
            for resource_id_text in resource_ids:
                try:
                    resource_id_int = int(resource_id_text)
                except (TypeError, ValueError):
                    return ConfigurationTaskServiceResult(False, f"fileKey {file_key} 的资源ID不合法")
                resource = ResourceDao.get_resource(db, resource_id_int)
                if not resource:
                    return ConfigurationTaskServiceResult(False, f"fileKey {file_key} 绑定的资源不存在")
                task_for_resource = ConfigurationTaskDao.get_task(db, row.task_id)
                if not task_for_resource or resource.agent_code != task_for_resource.agent_code:
                    return ConfigurationTaskServiceResult(False, f"fileKey {file_key} 绑定的资源不属于执行Agent")
                if resource.status != "READY":
                    return ConfigurationTaskServiceResult(
                        False,
                        f"fileKey {file_key} 绑定的资源未就绪：{resource.status}",
                    )
        now = datetime.now()
        ConfigurationTaskVersionDao.update_version(
            db,
            version_id,
            {
                "status": "PUBLISHED",
                "publish_by": operator,
                "publish_time": now,
                "update_by": operator,
            },
        )
        task = ConfigurationTaskDao.get_task(db, row.task_id)
        if task:
            ConfigurationTaskDao.update_task(
                db,
                row.task_id,
                {
                    "current_version_id": row.version_id,
                    "current_version_no": row.version_no,
                    "update_by": operator,
                },
            )
        db.commit()
        logger.info(
            f"发布任务版本，version_id={version_id}，task_id={row.task_id}，version_no={row.version_no}，"
            f"operator={operator}"
        )
        refreshed = ConfigurationTaskVersionDao.get_version(db, version_id)
        return ConfigurationTaskServiceResult(True, "版本发布成功", cls.to_version_model(refreshed))

    @classmethod
    def list_versions(cls, db: Session, task_id: int, limit: int = 50) -> list[TaskVersionDetailModel]:
        """查询任务版本列表。"""
        rows = ConfigurationTaskVersionDao.list_versions(db, task_id, limit=limit)
        return [cls.to_version_model(row) for row in rows]

    @classmethod
    def get_version(cls, db: Session, version_id: int) -> TaskVersionDetailModel | None:
        """查询版本详情。"""
        row = ConfigurationTaskVersionDao.get_version(db, version_id)
        return cls.to_version_model(row) if row else None

    @staticmethod
    def to_task_model(row: ConfigurationTask | None) -> ConfigurationTaskDetailModel | None:
        """将任务 ORM 转为响应模型，BIGINT ID 字符串化。"""
        if row is None:
            return None
        return ConfigurationTaskDetailModel(
            taskId=str(row.task_id),
            taskName=row.task_name,
            description=row.description or "",
            agentCode=row.agent_code,
            variables=load_json_object(row.variables_json),
            status=row.status,
            currentVersionId=str(row.current_version_id) if row.current_version_id else None,
            currentVersionNo=row.current_version_no,
            createBy=row.create_by or "",
            createTime=row.create_time,
            updateBy=row.update_by or "",
            updateTime=row.update_time,
            remark=row.remark or "",
        )

    @staticmethod
    def to_version_model(row: ConfigurationTaskVersion | None) -> TaskVersionDetailModel | None:
        """将版本 ORM 转为响应模型，BIGINT ID 字符串化。"""
        if row is None:
            return None
        return TaskVersionDetailModel(
            versionId=str(row.version_id),
            taskId=str(row.task_id),
            versionNo=row.version_no,
            status=row.status,
            startUrl=row.start_url,
            browserName=row.browser_name,
            headless=bool(row.headless),
            credentialBindingId=row.credential_binding_id or "",
            variables=load_json_object(row.variables_json),
            steps=load_json_list(row.steps_json),
            inputBindings={key: list(value) for key, value in load_json_object(row.input_bindings_json).items()},
            publishBy=row.publish_by or "",
            publishTime=row.publish_time,
            createBy=row.create_by or "",
            createTime=row.create_time,
            updateBy=row.update_by or "",
            updateTime=row.update_time,
        )

