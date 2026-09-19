"""配置任务资源业务服务，负责元数据登记、状态确认和响应模型转换。"""

from dataclasses import dataclass
from datetime import datetime

from loguru import logger
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from module_admin.entity.vo.user_vo import CurrentUserModel
from module_hrm.dao.agent_dao import AgentDao
from modules.configuration_task.dao.resource_dao import ResourceDao
from modules.configuration_task.entity.do.resource_object_do import ResourceObject
from modules.configuration_task.entity.vo.resource_vo import (
    ResourceCreateModel,
    ResourceDetailModel,
    ResourceQueryModel,
    ResourceReadyModel,
)


@dataclass
class ResourceServiceResult:
    """资源操作结果，供 Controller 转换为统一 HTTP 响应。"""

    is_success: bool
    message: str
    result: ResourceDetailModel | None = None


class ResourceService:
    """资源对象元数据服务；首期不执行文件读写和 Agent 传输。"""

    @staticmethod
    def _operator_scope(current_user: CurrentUserModel) -> tuple[str, bool]:
        """提取当前用户名称和管理员范围标识。"""
        user = current_user.user
        return (user.user_name if user else "system", bool(user and getattr(user, "admin", False)))

    @classmethod
    def list_resources(
        cls, db: Session, query: ResourceQueryModel, current_user: CurrentUserModel
    ) -> list[ResourceDetailModel]:
        """按用户范围查询资源，并将 BIGINT resource_id 序列化为字符串。"""
        operator, is_admin = cls._operator_scope(current_user)
        rows = ResourceDao.list_resources(
            db,
            resource_id=query.resource_id,
            agent_code=query.agent_code,
            status=query.status,
            keyword=query.keyword,
            limit=query.limit,
            operator=operator,
            is_admin=is_admin,
        )
        return [cls.to_detail_model(row) for row in rows]

    @classmethod
    def get_resource(cls, db: Session, resource_id: int, current_user: CurrentUserModel) -> ResourceDetailModel | None:
        """按用户范围查询资源详情，不返回 Agent 绝对路径或传输内容。"""
        operator, is_admin = cls._operator_scope(current_user)
        row = ResourceDao.get_visible_resource(db, resource_id, operator, is_admin)
        return cls.to_detail_model(row) if row else None

    @classmethod
    def create_resource(
        cls,
        db: Session,
        model: ResourceCreateModel,
        current_user: CurrentUserModel,
    ) -> ResourceServiceResult:
        """登记 Agent 本地资源元数据，初始状态固定为 PENDING。"""
        operator, _ = cls._operator_scope(current_user)
        agent = AgentDao.get_agent_by_code(db, model.agent_code)
        if not agent:
            return ResourceServiceResult(False, "Agent 未登记")
        existing = ResourceDao.get_by_identity(db, model.agent_code, model.object_key, model.version)
        if existing and existing.status != "DELETED":
            logger.info(f"资源登记幂等命中，resource_id={existing.resource_id}，agent_code={model.agent_code}")
            return ResourceServiceResult(True, "资源已存在", cls.to_detail_model(existing))

        now = datetime.now()
        try:
            row = ResourceDao.add_resource(
                db,
                {
                    "provider_type": model.provider_type,
                    "provider_execution_side": model.provider_execution_side,
                    "agent_code": model.agent_code,
                    "object_key": model.object_key,
                    "original_file_name": model.original_file_name,
                    "mime_type": model.mime_type,
                    "file_size": model.file_size,
                    "checksum_algorithm": "sha256",
                    "sha256": model.sha256,
                    "version": model.version,
                    "status": "PENDING",
                    "expires_at": model.expires_at,
                    "create_by": operator,
                    "create_time": now,
                    "update_by": operator,
                    "update_time": now,
                    "last_audit_at": now,
                    "audit_message": "资源元数据已登记，等待 Agent 传输确认",
                    "remark": model.remark,
                },
            )
            db.commit()
        except IntegrityError:
            db.rollback()
            existing = ResourceDao.get_by_identity(db, model.agent_code, model.object_key, model.version)
            if existing and existing.status != "DELETED":
                logger.info(f"资源并发登记命中唯一身份，resource_id={existing.resource_id}")
                return ResourceServiceResult(True, "资源已存在", cls.to_detail_model(existing))
            raise
        logger.info(
            f"登记配置任务资源，resource_id={row.resource_id}，agent_code={row.agent_code}，"
            f"file_size={row.file_size}，status={row.status}，operator={operator}"
        )
        return ResourceServiceResult(True, "资源登记成功", cls.to_detail_model(row))

    @classmethod
    def mark_ready(
        cls,
        db: Session,
        resource_id: int,
        model: ResourceReadyModel,
        current_user: CurrentUserModel,
    ) -> ResourceServiceResult:
        """确认 Agent 侧资源大小和 SHA-256，匹配后才转为 READY。"""
        operator, is_admin = cls._operator_scope(current_user)
        row = ResourceDao.get_visible_resource(db, resource_id, operator, is_admin)
        if not row:
            return ResourceServiceResult(False, "资源不存在")
        if row.status in {"DELETED", "DELETING", "EXPIRED"}:
            return ResourceServiceResult(False, f"资源当前状态不允许 ready：{row.status}")
        if row.expires_at and row.expires_at <= datetime.now():
            ResourceDao.update_resource(
                db,
                resource_id,
                {
                    "status": "EXPIRED",
                    "last_audit_at": datetime.now(),
                    "audit_message": "资源已过期",
                },
            )
            db.commit()
            logger.warning(f"资源 ready 被拒绝，资源已过期，resource_id={resource_id}")
            return ResourceServiceResult(False, "资源已过期")
        if model.file_size != row.file_size or model.sha256 != row.sha256:
            ResourceDao.update_resource(
                db,
                resource_id,
                {
                    "status": "FAILED",
                    "error_code": "RESOURCE_METADATA_MISMATCH",
                    "error_message": "Agent 确认的文件大小或 SHA-256 与登记值不一致",
                    "last_audit_at": datetime.now(),
                    "audit_message": "旧 ready 校验失败",
                    "update_by": operator,
                },
            )
            db.commit()
            logger.warning(f"资源 ready 校验失败，resource_id={resource_id}，status=FAILED")
            return ResourceServiceResult(False, "资源大小或 SHA-256 校验失败")

        logger.warning(f"拒绝绕过传输的 ready 请求，resource_id={resource_id}，operator={operator}")
        return ResourceServiceResult(False, "资源必须通过 Agent 传输 commit 确认就绪")

    @staticmethod
    def to_detail_model(row: ResourceObject | None) -> ResourceDetailModel | None:
        """将 ORM 实体转成响应模型，显式字符串化 BIGINT 资源 ID。"""
        if row is None:
            return None
        return ResourceDetailModel(
            resourceId=str(row.resource_id),
            providerType=row.provider_type,
            providerExecutionSide=row.provider_execution_side,
            agentCode=row.agent_code,
            objectKey=row.object_key,
            originalFileName=row.original_file_name,
            mimeType=row.mime_type,
            fileSize=row.file_size,
            checksumAlgorithm=row.checksum_algorithm,
            sha256=row.sha256,
            version=row.version,
            status=row.status,
            expiresAt=row.expires_at,
            deletedAt=row.deleted_at,
            errorCode=row.error_code or "",
            errorMessage=row.error_message or "",
            createBy=row.create_by or "",
            createTime=row.create_time,
            updateBy=row.update_by or "",
            updateTime=row.update_time,
            lastAuditAt=row.last_audit_at,
            auditMessage=row.audit_message or "",
            remark=row.remark or "",
        )
