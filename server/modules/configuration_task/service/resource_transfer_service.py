"""配置任务资源传输业务编排。"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from loguru import logger
from sqlalchemy.orm import Session

from module_admin.entity.vo.user_vo import CurrentUserModel
from module_hrm.dao.agent_dao import AgentDao
from module_qtr.service.agent_file_transfer_service import AgentFileTransferService
from module_qtr.service.agent_service import agent_sessions, agents
from modules.configuration_task.dao.resource_dao import ResourceDao
from modules.configuration_task.dao.resource_transfer_dao import ResourceTransferDao
from modules.configuration_task.entity.do.resource_object_do import ResourceObject
from modules.configuration_task.entity.do.resource_transfer_do import ResourceTransfer
from modules.configuration_task.entity.vo.resource_vo import (
    ResourceTransferBeginModel,
    ResourceTransferChunkModel,
    ResourceTransferCommitModel,
    ResourceTransferResponseModel,
)


@dataclass
class ResourceTransferServiceResult:
    """资源传输操作结果。"""

    is_success: bool
    message: str
    result: ResourceTransferResponseModel | None = None


class ResourceTransferService:
    """编排资源传输状态，不直接读写文件。"""

    TRANSFER_TTL_MINUTES = 30

    @staticmethod
    def _operator_scope(current_user: CurrentUserModel) -> tuple[str, bool]:
        """提取当前用户名称和管理员范围。"""
        user = current_user.user
        return user.user_name if user else "system", bool(user and getattr(user, "admin", False))

    @classmethod
    def _visible_resource(cls, db: Session, resource_id: int, current_user: CurrentUserModel) -> ResourceObject | None:
        """按用户范围获取资源实体。"""
        operator, is_admin = cls._operator_scope(current_user)
        return ResourceDao.get_visible_resource(db, resource_id, operator, is_admin)

    @staticmethod
    def _agent_online(db: Session, agent_code: str) -> bool:
        """确认 Agent 已登记、状态在线且存在当前 WebSocket 连接。"""
        agent = AgentDao.get_agent_by_code(db, agent_code)
        return bool(agent and agent.status == 2 and agent_code in agents)

    @staticmethod
    def _session_id(agent_code: str) -> str:
        """读取当前 Agent 连接会话标识。"""
        return str(agent_sessions.get(agent_code) or "")

    @staticmethod
    def _response(row: ResourceTransfer) -> ResourceTransferResponseModel:
        """将传输 ORM 转换成对外响应，避免 BIGINT 资源 ID泄露为数字。"""
        return ResourceTransferResponseModel(
            transferId=row.transfer_id,
            resourceId=str(row.resource_id),
            agentCode=row.agent_code,
            status=row.status,
            receivedBytes=row.received_bytes,
            receivedChunks=row.received_chunks,
            errorCode=row.error_code or "",
            errorMessage=row.error_message or "",
            sessionId=row.session_id or "",
        )

    @classmethod
    def begin(
        cls,
        db: Session,
        resource_id: int,
        model: ResourceTransferBeginModel,
        current_user: CurrentUserModel,
    ) -> ResourceTransferServiceResult:
        """创建或复用传输，并向当前 Agent 发送 begin。"""
        resource = cls._visible_resource(db, resource_id, current_user)
        if not resource:
            return ResourceTransferServiceResult(False, "资源不存在")
        if resource.status in {"DELETED", "DELETING", "EXPIRED", "READY"}:
            return ResourceTransferServiceResult(False, f"资源当前状态不允许传输：{resource.status}")
        if resource.expires_at and resource.expires_at <= datetime.now():
            ResourceDao.update_resource(
                db,
                resource_id,
                {"status": "EXPIRED", "last_audit_at": datetime.now(), "audit_message": "传输开始前资源已过期"},
            )
            db.commit()
            return ResourceTransferServiceResult(False, "资源已过期")
        if not cls._agent_online(db, resource.agent_code):
            return ResourceTransferServiceResult(False, "目标 Agent 未在线")
        session_id = cls._session_id(resource.agent_code)
        if not session_id:
            return ResourceTransferServiceResult(False, "目标 Agent 连接会话不可用")

        transfer_id = model.transfer_id or f"transfer-{uuid.uuid4().hex}"
        existing = ResourceTransferDao.get_transfer(db, transfer_id)
        if existing:
            if existing.resource_id != resource_id or existing.agent_code != resource.agent_code:
                return ResourceTransferServiceResult(False, "传输标识已被其他资源占用")
            if existing.status in {"COMPLETED", "READY"}:
                return ResourceTransferServiceResult(True, "传输已完成", cls._response(existing))
            if existing.status in {"FAILED", "EXPIRED"}:
                return ResourceTransferServiceResult(False, "传输已结束，请使用新的传输标识", cls._response(existing))
            if existing.session_id != session_id:
                return ResourceTransferServiceResult(False, "传输连接会话已变更")
            return ResourceTransferServiceResult(True, "传输已存在", cls._response(existing))

        active = ResourceTransferDao.get_active_by_resource(db, resource_id)
        if active:
            if active.session_id == session_id:
                return ResourceTransferServiceResult(True, "传输已存在", cls._response(active))
            return ResourceTransferServiceResult(False, "资源已有其他活动传输")

        operator, _ = cls._operator_scope(current_user)
        now = datetime.now()
        row = ResourceTransferDao.add_transfer(
            db,
            {
                "transfer_id": transfer_id,
                "resource_id": resource_id,
                "agent_code": resource.agent_code,
                "session_id": session_id,
                "status": "PENDING",
                "expected_size": resource.file_size,
                "expected_sha256": resource.sha256,
                "version": resource.version,
                "expires_at": now + timedelta(minutes=cls.TRANSFER_TTL_MINUTES),
                "create_by": operator,
                "create_time": now,
                "update_by": operator,
                "update_time": now,
                "last_audit_at": now,
                "audit_message": "等待 Agent 接收资源发布",
            },
        )
        db.commit()
        command_result = AgentFileTransferService.send_command(
            resource.agent_code,
            "file_publish_begin",
            {
                "resource_id": str(resource.resource_id),
                "transfer_id": row.transfer_id,
                "original_file_name": resource.original_file_name,
                "mime_type": resource.mime_type,
                "size": resource.file_size,
                "sha256": resource.sha256,
                "version": resource.version,
                "expires": resource.expires_at.isoformat() if resource.expires_at else "",
            },
        )
        if not command_result.success:
            return cls._fail(
                db, row, resource, command_result.error_code or "AGENT_BEGIN_FAILED", command_result.error_message
            )
        ResourceTransferDao.update_transfer(
            db,
            row.transfer_id,
            {"status": "UPLOADING", "last_audit_at": datetime.now(), "audit_message": "Agent 已接收资源发布"},
        )
        ResourceDao.update_resource(
            db,
            resource.resource_id,
            {"status": "UPLOADING", "last_audit_at": datetime.now(), "audit_message": "资源已开始向 Agent 传输"},
        )
        db.commit()
        refreshed = ResourceTransferDao.get_transfer(db, row.transfer_id)
        logger.info(
            f"资源传输开始: transfer_id={row.transfer_id}, resource_id={resource_id}, agent_code={resource.agent_code}"
        )
        return ResourceTransferServiceResult(True, "资源传输已开始", cls._response(refreshed))

    @classmethod
    def chunk(
        cls,
        db: Session,
        resource_id: int,
        transfer_id: str,
        model: ResourceTransferChunkModel,
        current_user: CurrentUserModel,
    ) -> ResourceTransferServiceResult:
        """校验当前分片并转发到同一 Agent 会话。"""
        resource = cls._visible_resource(db, resource_id, current_user)
        row = ResourceTransferDao.get_transfer(db, transfer_id)
        if not resource or not row or row.resource_id != resource_id:
            return ResourceTransferServiceResult(False, "资源传输不存在")
        if row.expires_at and row.expires_at <= datetime.now() and row.status in {"PENDING", "UPLOADING"}:
            return cls._expire(db, row, resource)
        if row.status == "COMPLETED":
            return ResourceTransferServiceResult(True, "传输已完成", cls._response(row))
        if row.status != "UPLOADING":
            return ResourceTransferServiceResult(False, f"传输当前状态不允许分片：{row.status}")
        session_id = cls._session_id(resource.agent_code)
        if row.session_id != session_id or not session_id:
            return cls._fail(db, row, resource, "AGENT_SESSION_CHANGED", "Agent 连接会话已变更")
        if model.total_bytes != resource.file_size:
            return cls._fail(db, row, resource, "TOTAL_SIZE_MISMATCH", "分片声明总大小与资源不一致")
        command_result = AgentFileTransferService.send_command(
            resource.agent_code,
            "file_chunk",
            {
                "resource_id": str(resource.resource_id),
                "transfer_id": row.transfer_id,
                "index": model.index,
                "offset": model.offset,
                "totalBytes": model.total_bytes,
                "chunkBytes": model.chunk_bytes,
                "data": model.data,
                "chunkSha256": model.chunk_sha256,
            },
        )
        if not command_result.success:
            return cls._fail(
                db, row, resource, command_result.error_code or "AGENT_CHUNK_FAILED", command_result.error_message
            )
        data = command_result.data
        received_bytes = int(data.get("received") or row.received_bytes)
        received_chunks = row.received_chunks + (0 if data.get("idempotent") else 1)
        ResourceTransferDao.update_transfer(
            db,
            row.transfer_id,
            {
                "received_bytes": received_bytes,
                "received_chunks": received_chunks,
                "last_audit_at": datetime.now(),
                "audit_message": "Agent 已确认资源分片",
            },
        )
        db.commit()
        refreshed = ResourceTransferDao.get_transfer(db, row.transfer_id)
        logger.info(
            f"资源分片已确认: transfer_id={row.transfer_id}, index={model.index}, bytes={model.chunk_bytes or 0}"
        )
        return ResourceTransferServiceResult(True, "资源分片已接收", cls._response(refreshed))

    @classmethod
    def commit(
        cls,
        db: Session,
        resource_id: int,
        transfer_id: str,
        model: ResourceTransferCommitModel,
        current_user: CurrentUserModel,
    ) -> ResourceTransferServiceResult:
        """要求 Agent 完成最终校验后，将资源和传输置为完成。"""
        del model
        resource = cls._visible_resource(db, resource_id, current_user)
        row = ResourceTransferDao.get_transfer(db, transfer_id)
        if not resource or not row or row.resource_id != resource_id:
            return ResourceTransferServiceResult(False, "资源传输不存在")
        if row.expires_at and row.expires_at <= datetime.now() and row.status in {"PENDING", "UPLOADING"}:
            return cls._expire(db, row, resource)
        if row.status == "COMPLETED":
            return ResourceTransferServiceResult(True, "传输已完成", cls._response(row))
        if row.status != "UPLOADING":
            return ResourceTransferServiceResult(False, f"传输当前状态不允许提交：{row.status}")
        session_id = cls._session_id(resource.agent_code)
        if row.session_id != session_id or not session_id:
            return cls._fail(db, row, resource, "AGENT_SESSION_CHANGED", "Agent 连接会话已变更")
        command_result = AgentFileTransferService.send_command(
            resource.agent_code,
            "file_publish_commit",
            {"resource_id": str(resource.resource_id), "transfer_id": row.transfer_id},
        )
        if not command_result.success:
            return cls._fail(
                db, row, resource, command_result.error_code or "AGENT_COMMIT_FAILED", command_result.error_message
            )
        data = command_result.data
        actual_size = int(data.get("size") or data.get("file_size") or 0)
        actual_sha256 = str(data.get("sha256") or "").lower()
        if actual_size != resource.file_size or actual_sha256 != resource.sha256:
            return cls._fail(db, row, resource, "RESOURCE_METADATA_MISMATCH", "Agent 提交的文件元数据不一致")
        now = datetime.now()
        ResourceTransferDao.update_transfer(
            db,
            row.transfer_id,
            {
                "status": "COMPLETED",
                "received_bytes": actual_size,
                "completed_at": now,
                "last_audit_at": now,
                "audit_message": "Agent 已完成资源校验",
            },
        )
        ResourceDao.update_resource(
            db,
            resource.resource_id,
            {
                "status": "READY",
                "error_code": "",
                "error_message": "",
                "update_by": cls._operator_scope(current_user)[0],
                "last_audit_at": now,
                "audit_message": "Agent commit 校验通过",
            },
        )
        db.commit()
        refreshed = ResourceTransferDao.get_transfer(db, row.transfer_id)
        logger.info(f"资源传输完成: transfer_id={row.transfer_id}, resource_id={resource_id}, status=READY")
        return ResourceTransferServiceResult(True, "资源已就绪", cls._response(refreshed))

    @classmethod
    def _expire(
        cls,
        db: Session,
        row: ResourceTransfer,
        resource: ResourceObject,
    ) -> ResourceTransferServiceResult:
        """将超过传输 TTL 的活动记录收敛为 EXPIRED，禁止继续提交分片。"""
        now = datetime.now()
        ResourceTransferDao.update_transfer(
            db,
            row.transfer_id,
            {
                "status": "EXPIRED",
                "error_code": "TRANSFER_EXPIRED",
                "error_message": "资源传输已超时",
                "last_audit_at": now,
                "audit_message": "资源传输超过 TTL",
            },
        )
        if resource.status not in {"READY", "DELETED", "EXPIRED"}:
            ResourceDao.update_resource(
                db,
                resource.resource_id,
                {
                    "status": "FAILED",
                    "error_code": "TRANSFER_EXPIRED",
                    "error_message": "资源传输已超时",
                    "last_audit_at": now,
                    "audit_message": "资源传输超过 TTL",
                },
            )
        db.commit()
        logger.warning(f"资源传输已过期: transfer_id={row.transfer_id}, resource_id={resource.resource_id}")
        refreshed = ResourceTransferDao.get_transfer(db, row.transfer_id)
        return ResourceTransferServiceResult(False, "资源传输已过期", cls._response(refreshed))

    @classmethod
    def _fail(
        cls, db: Session, row: ResourceTransfer, resource: ResourceObject, error_code: str, error_message: str
    ) -> ResourceTransferServiceResult:
        """记录稳定错误并将活动传输及资源置为失败。"""
        safe_message = error_message or "资源传输失败"
        now = datetime.now()
        ResourceTransferDao.update_transfer(
            db,
            row.transfer_id,
            {
                "status": "FAILED",
                "error_code": error_code,
                "error_message": safe_message[:500],
                "last_audit_at": now,
                "audit_message": "资源传输失败",
            },
        )
        if resource.status not in {"READY", "DELETED", "EXPIRED"}:
            ResourceDao.update_resource(
                db,
                resource.resource_id,
                {
                    "status": "FAILED",
                    "error_code": error_code,
                    "error_message": safe_message[:500],
                    "last_audit_at": now,
                    "audit_message": "Agent 资源传输失败",
                },
            )
        db.commit()
        logger.warning(
            f"资源传输失败: transfer_id={row.transfer_id}, resource_id={resource.resource_id}, error_code={error_code}"
        )
        refreshed = ResourceTransferDao.get_transfer(db, row.transfer_id)
        return ResourceTransferServiceResult(False, safe_message, cls._response(refreshed))


def self_operator(current_user: CurrentUserModel) -> str:
    """获取资源状态更新所需的审计操作者。"""
    return current_user.user.user_name if current_user.user else "system"
