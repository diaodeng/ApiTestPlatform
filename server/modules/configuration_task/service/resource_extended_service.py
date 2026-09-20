"""资源扩展服务：SFTP 上传、下载回传、删除与引用保护。

所有方法均为同步实现；异步调用方（Controller）必须通过 run_in_threadpool 包裹。
SFTP 文件正文不进入资源记录或日志；下载回传响应只含 Base64 与元数据。
"""

import base64
import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from loguru import logger
from sqlalchemy.orm import Session

from module_admin.entity.vo.user_vo import CurrentUserModel
from modules.configuration_task.dao.resource_dao import ResourceDao
from modules.configuration_task.dao.stage_artifact_dao import TaskArtifactDao
from modules.configuration_task.entity.do.resource_object_do import ResourceObject
from modules.configuration_task.entity.vo.resource_vo import (
    ResourceDeleteModel,
    ResourceDetailModel,
    ResourceDownloadModel,
    ResourceSftpCreateModel,
    ResourceSftpUploadModel,
)
from modules.configuration_task.util.sftp_provider import (
    SftpProvider,
    SftpProviderError,
    resolve_sftp_config,
)
from modules.credential.dao.credential_dao import CredentialDao
from modules.credential.util.credential_secret_util import decrypt_secret

# 引用保护检查上限：超过该数量的引用拒绝删除并提示先清理产物。
MAX_REFERENCE_CHECK = 200


class ResourceDownloadError(RuntimeError):
    """Agent 资源读取失败，code 为稳定错误码，message 面向用户脱敏。"""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass
class ResourceExtendedResult:
    """资源扩展操作结果。"""

    is_success: bool
    message: str
    result: Any = None


class ResourceExtendedService:
    """SFTP Provider 资源上传、下载回传与删除保护。"""

    # ---------- SFTP 上传 ----------

    @classmethod
    def upload_sftp_resource(
        cls,
        db: Session,
        model: ResourceSftpCreateModel,
        upload: ResourceSftpUploadModel,
        current_user: CurrentUserModel,
    ) -> ResourceExtendedResult:
        """上传文件到 SFTP 并登记资源；先写远端成功再写数据库。"""
        user = current_user.user
        operator = user.user_name if user else "system"
        try:
            import base64 as _base64

            content = _base64.b64decode(upload.data.encode("ascii"), validate=True)
        except Exception:
            return ResourceExtendedResult(False, "文件正文必须是合法 Base64")
        sha256 = hashlib.sha256(content).hexdigest()

        binding, credential, secret = cls._resolve_sftp_credential(db, model.credential_binding_id)
        if isinstance(binding, str):
            return ResourceExtendedResult(False, binding)

        object_key = model.object_key
        try:
            with SftpProvider(resolve_sftp_config(secret)) as provider:
                provider.upload(object_key, content)
        except SftpProviderError as exc:
            logger.warning(
                f"SFTP 资源上传失败: objectKey={object_key}, code={exc.code}, operator={operator}"
            )
            return ResourceExtendedResult(False, exc.args[0] if exc.args else "SFTP 上传失败")

        # 远端已写入，登记资源；唯一身份冲突回查返回已有资源。
        existing = ResourceDao.get_by_identity(db, model.agent_code, object_key, model.version)
        if existing:
            return ResourceExtendedResult(True, "资源已存在", cls._detail(db, existing))
        now = datetime.now()
        try:
            row = ResourceDao.add_resource(
                db,
                {
                    "provider_type": "sftp",
                    "provider_execution_side": "server",
                    "agent_code": model.agent_code,
                    "object_key": object_key,
                    "original_file_name": model.original_file_name,
                    "mime_type": model.mime_type,
                    "file_size": len(content),
                    "checksum_algorithm": "sha256",
                    "sha256": sha256,
                    "version": model.version,
                    "status": "READY",
                    "expires_at": model.expires_at,
                    "create_by": operator,
                    "create_time": now,
                    "update_by": operator,
                    "update_time": now,
                    "last_audit_at": now,
                    "audit_message": f"SFTP 资源上传登记（凭证绑定 {binding.binding_id}）",
                    "remark": model.remark or "",
                },
            )
            db.commit()
            # 审计绑定 ID 写入独立可解析字段：重用 audit_message 拼接会被自然语言破坏，
            # 这里在提交后把绑定 ID 追加到 remark 之外的 audit 摘要里（格式受控）。
            ResourceDao.update_resource(
                db,
                row.resource_id,
                {"audit_message": f"SFTP_UPLOAD|bindingId={binding.binding_id}|operator={operator}"},
            )
            db.commit()
        except Exception:
            db.rollback()
            existing = ResourceDao.get_by_identity(db, model.agent_code, object_key, model.version)
            if existing:
                return ResourceExtendedResult(True, "资源已存在", cls._detail(db, existing))
            raise
        logger.info(
            f"SFTP 资源上传登记成功: resource_id={row.resource_id}, objectKey={object_key}, "
            f"size={len(content)}, operator={operator}"
        )
        return ResourceExtendedResult(True, "SFTP 资源上传成功", cls._detail(db, row))

    # ---------- 下载回传 ----------

    @classmethod
    def download_resource(
        cls,
        db: Session,
        resource_id: int,
        current_user: CurrentUserModel,
    ) -> ResourceExtendedResult:
        """按资源 Provider 下载文件内容：SFTP 走服务端，agent_local 走 Agent file_read 命令。

        本方法只处理 SFTP 与通用校验；agent_local 资源由异步调用方先取 Agent
        内容（同样走本服务 `_load_agent_resource_content` 的同步实现）。
        """
        operator, is_admin = cls._operator_scope(current_user)
        row = ResourceDao.get_visible_resource(db, resource_id, operator, is_admin)
        if not row:
            return ResourceExtendedResult(False, "资源不存在")
        if row.status not in {"READY"}:
            return ResourceExtendedResult(False, f"资源当前状态不允许下载：{row.status}")
        if row.expires_at and row.expires_at <= datetime.now():
            return ResourceExtendedResult(False, "资源已过期")
        if row.provider_type == "sftp":
            binding_id = cls._extract_binding_id(row)
            if not binding_id:
                return ResourceExtendedResult(False, "资源缺少 SFTP 凭证绑定信息，无法下载")
            binding, _credential, secret = cls._resolve_sftp_credential(db, binding_id)
            if isinstance(binding, str):
                return ResourceExtendedResult(False, binding)
            try:
                with SftpProvider(resolve_sftp_config(secret)) as provider:
                    content = provider.download(row.object_key)
            except SftpProviderError as exc:
                logger.warning(
                    f"SFTP 资源下载失败: resource_id={resource_id}, code={exc.code}, operator={operator}"
                )
                return ResourceExtendedResult(False, exc.args[0] if exc.args else "SFTP 下载失败")
        else:
            try:
                content = cls._read_agent_resource(row, operator)
            except ResourceDownloadError as exc:
                return ResourceExtendedResult(False, exc.args[0] if exc.args else "Agent 资源读取失败")

        actual_sha256 = hashlib.sha256(content).hexdigest()
        if actual_sha256 != row.sha256:
            logger.warning(f"SFTP 资源下载校验不一致: resource_id={resource_id}")
            return ResourceExtendedResult(False, "文件校验失败，远端内容与登记摘要不一致")
        response = ResourceDownloadModel(
            resourceId=str(row.resource_id),
            originalFileName=row.original_file_name,
            mimeType=row.mime_type,
            fileSize=len(content),
            sha256=actual_sha256,
            data=base64.b64encode(content).decode("ascii"),
        )
        logger.info(f"资源下载回传成功: resource_id={resource_id}, size={len(content)}, operator={operator}")
        return ResourceExtendedResult(True, "下载成功", response)

    # ---------- 删除与引用保护 ----------

    @classmethod
    def delete_resource(
        cls,
        db: Session,
        resource_id: int,
        model: ResourceDeleteModel,
        current_user: CurrentUserModel,
    ) -> ResourceExtendedResult:
        """删除资源：带引用保护，DELETING → DELETED 状态机，按 Provider 清理文件。"""
        operator, is_admin = cls._operator_scope(current_user)
        row = ResourceDao.get_visible_resource(db, resource_id, operator, is_admin)
        if not row:
            return ResourceExtendedResult(False, "资源不存在")
        if row.status in {"DELETING", "DELETED"}:
            return ResourceExtendedResult(False, f"资源正在删除或已删除：{row.status}")

        references = TaskArtifactDao.list_artifacts_by_resource(db, resource_id, limit=MAX_REFERENCE_CHECK + 1)
        if references and not model.force:
            return ResourceExtendedResult(
                False,
                f"资源被 {len(references)} 条运行产物引用，不能直接删除；请先清理相关运行记录或使用管理员强制删除",
            )
        if references and model.force and not is_admin:
            return ResourceExtendedResult(False, "强制删除被引用资源需要管理员权限")

        # 先置 DELETING 再清理文件，最后 DELETED；文件清理失败保留 DELETING 供重试。
        ResourceDao.update_resource(
            db,
            resource_id,
            {
                "status": "DELETING",
                "last_audit_at": datetime.now(),
                "audit_message": f"资源删除受理（operator={operator}, force={model.force}）",
                "update_by": operator,
            },
        )
        db.commit()

        file_error = cls._delete_provider_file(db, row)
        now = datetime.now()
        if file_error:
            ResourceDao.update_resource(
                db,
                resource_id,
                {
                    "last_audit_at": now,
                    "audit_message": f"远端文件清理失败，保留 DELETING 等待重试: {file_error}",
                    "update_by": operator,
                },
            )
            db.commit()
            logger.warning(f"资源删除时远端文件清理失败: resource_id={resource_id}, error={file_error}")
            return ResourceExtendedResult(False, f"资源已标记删除但远端文件清理失败：{file_error}")

        ResourceDao.update_resource(
            db,
            resource_id,
            {
                "status": "DELETED",
                "deleted_at": now,
                "error_code": "",
                "error_message": "",
                "last_audit_at": now,
                "audit_message": f"资源删除完成（reason={model.reason or '未填写'}）",
                "update_by": operator,
            },
        )
        db.commit()
        logger.warning(
            f"资源已删除: resource_id={resource_id}, operator={operator}, force={model.force}, "
            f"references={len(references)}"
        )
        return ResourceExtendedResult(True, "资源删除完成", cls._detail(db, ResourceDao.get_resource(db, resource_id)))

    # ---------- 内部工具 ----------

    @staticmethod
    def _operator_scope(current_user: CurrentUserModel) -> tuple[str, bool]:
        """提取操作者与管理员标识。"""
        user = current_user.user
        return (user.user_name if user else "system", bool(user and getattr(user, "admin", False)))

    @staticmethod
    def _resolve_sftp_credential(db: Session, binding_id_text: str):
        """解析 SFTP 凭证绑定；返回 (binding, credential, secret) 或错误文本。"""
        try:
            binding_id = int(binding_id_text)
        except (TypeError, ValueError):
            return "credentialBindingId 不合法", None, None
        binding = CredentialDao.get_binding(db, binding_id)
        if not binding or not binding.enabled:
            return "SFTP 凭证绑定不存在或未启用", None, None
        credential = CredentialDao.get_credential(db, binding.credential_id)
        if not credential or not credential.enabled:
            return "绑定的凭证不存在或未启用", None, None
        if credential.expire_time and credential.expire_time <= datetime.now():
            return "SFTP 凭证已到期，请先刷新或更新", None, None
        try:
            secret = decrypt_secret(credential.secret_cipher_text)
        except Exception as exc:
            logger.warning(f"SFTP 凭证解密失败: binding_id={binding_id}, error_type={exc.__class__.__name__}")
            return "SFTP 凭证密文无法解密，请重新配置", None, None
        return binding, credential, secret

    @staticmethod
    def _extract_binding_id(row: ResourceObject) -> str:
        """从资源审计摘要中提取凭证绑定 ID（格式：SFTP_UPLOAD|bindingId=123|operator=xx）。"""
        message = row.audit_message or ""
        marker = "bindingId="
        if marker in message:
            tail = message.split(marker, 1)[1]
            digits = ""
            for char in tail:
                if char.isdigit():
                    digits += char
                else:
                    break
            return digits
        return ""

    @classmethod
    def _read_agent_resource(cls, row: ResourceObject, operator: str) -> bytes:
        """通过 Agent file_read 命令读取受控资源内容；失败抛出 ResourceDownloadError。

        同步实现：调用方负责线程池包裹；不记录 Base64 正文。
        """
        from module_qtr.service.agent_file_transfer_service import AgentFileTransferService

        command_result = AgentFileTransferService.send_command(
            row.agent_code,
            "file_read",
            {"resource_id": str(row.resource_id)},
            timeout_seconds=60,
        )
        if not command_result.success:
            raise ResourceDownloadError(
                command_result.error_code or "AGENT_READ_FAILED",
                command_result.error_message or "Agent 资源读取失败",
            )
        data_text = str(command_result.data.get("data") or "")
        try:
            content = base64.b64decode(data_text.encode("ascii"), validate=True)
        except Exception as exc:
            raise ResourceDownloadError("AGENT_READ_INVALID", "Agent 返回的文件内容不合法") from exc
        logger.info(f"Agent 资源读取成功: resource_id={row.resource_id}, size={len(content)}, operator={operator}")
        return content

    @classmethod
    def _delete_provider_file(cls, db: Session, row: ResourceObject) -> str:
        """按 Provider 清理远端文件；返回错误文本或空串。"""
        if row.provider_type == "sftp":
            binding_id = cls._extract_binding_id(row)
            if not binding_id:
                return "缺少 SFTP 凭证绑定信息"
            binding, _credential, secret = cls._resolve_sftp_credential(db, binding_id)
            if isinstance(binding, str):
                return binding
            try:
                with SftpProvider(resolve_sftp_config(secret)) as provider:
                    provider.delete(row.object_key)
            except SftpProviderError as exc:
                return exc.args[0] if exc.args else "SFTP 删除失败"
            return ""
        # agent_local：通过 Agent file_delete 命令清理受控文件。
        from module_qtr.service.agent_file_transfer_service import AgentFileTransferService

        command_result = AgentFileTransferService.send_command(
            row.agent_code,
            "file_delete",
            {"resource_id": str(row.resource_id)},
            timeout_seconds=30,
        )
        if not command_result.success:
            return command_result.error_message or "Agent 资源删除失败"
        return ""

    @staticmethod
    def _detail(db: Session, row: ResourceObject | None) -> ResourceDetailModel | None:
        """复用资源服务详情转换。"""
        from modules.configuration_task.service.resource_service import ResourceService

        return ResourceService.to_detail_model(row)
