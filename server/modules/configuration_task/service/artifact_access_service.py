"""配置任务运行产物受控访问服务。"""

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from loguru import logger
from sqlalchemy.orm import Session

from module_admin.entity.vo.user_vo import CurrentUserModel
from modules.configuration_task.dao.artifact_access_audit_dao import (
    ConfigurationTaskArtifactAccessAuditDao,
)
from modules.configuration_task.dao.resource_dao import ResourceDao
from modules.configuration_task.dao.stage_artifact_dao import TaskArtifactDao
from modules.configuration_task.dao.task_dao import ConfigurationTaskDao, ConfigurationTaskRunDao
from modules.configuration_task.entity.do.resource_object_do import ResourceObject
from modules.configuration_task.entity.vo.task_vo import ArtifactModel
from modules.configuration_task.service.artifact_service import ConfigurationTaskArtifactService
from modules.configuration_task.service.resource_extended_service import (
    ResourceDownloadError,
    ResourceExtendedService,
)

SAFE_PREVIEW_MIME_TYPES = {
    "image/png",
    "image/jpeg",
    "image/webp",
    "text/plain",
    "application/json",
}
_SAFE_FILE_NAME = re.compile(r"[^A-Za-z0-9._\-\u4e00-\u9fff ]+")


@dataclass
class ArtifactContent:
    """已完成权限和摘要校验的产物正文。"""

    artifact_id: int
    file_name: str
    mime_type: str
    file_size: int
    sha256: str
    content: bytes
    disposition: str


@dataclass
class ArtifactAccessResult:
    """产物访问结果；失败时不携带文件正文。"""

    is_success: bool
    message: str
    result: ArtifactContent | None = None
    error_code: str = ""


class ConfigurationTaskArtifactAccessService:
    """按 artifact_id 提供预览和下载，禁止以 resource_id 或 object_key 授权。"""

    @classmethod
    def access_artifact(
        cls,
        db: Session,
        artifact_id: int,
        current_user: CurrentUserModel,
        action: str,
    ) -> ArtifactAccessResult:
        """读取产物正文并记录访问审计；action 只允许 preview/download。"""
        operator, is_admin = cls._operator_scope(current_user)
        if action not in {"preview", "download"}:
            return ArtifactAccessResult(False, "产物访问动作不支持", error_code="ACTION_INVALID")

        artifact = TaskArtifactDao.get_artifact(db, artifact_id)
        if not artifact:
            result = ArtifactAccessResult(False, "产物不存在", error_code="ARTIFACT_NOT_FOUND")
            cls._audit(db, artifact_id, None, None, action, operator, result)
            return result
        run = ConfigurationTaskRunDao.get_run(db, artifact.task_run_id)
        task = ConfigurationTaskDao.get_task(db, run.task_id) if run else None
        resource = ResourceDao.get_resource(db, artifact.resource_id)
        if not run or not task:
            result = ArtifactAccessResult(False, "产物所属运行不存在", error_code="RUN_NOT_FOUND")
            cls._audit(db, artifact_id, artifact.task_run_id, artifact.resource_id, action, operator, result)
            return result
        if not cls._can_access(operator, is_admin, task, run, artifact, resource):
            result = ArtifactAccessResult(False, "无权访问该运行产物", error_code="ACCESS_DENIED")
            cls._audit(db, artifact_id, artifact.task_run_id, artifact.resource_id, action, operator, result)
            return result
        if not resource or resource.resource_id != artifact.resource_id:
            result = ArtifactAccessResult(False, "产物资源不存在", error_code="RESOURCE_NOT_FOUND")
            cls._audit(db, artifact_id, artifact.task_run_id, artifact.resource_id, action, operator, result)
            return result
        consistency_error = cls._validate_consistency(artifact, resource)
        if consistency_error:
            result = ArtifactAccessResult(False, consistency_error[1], error_code=consistency_error[0])
            cls._audit(db, artifact_id, artifact.task_run_id, artifact.resource_id, action, operator, result)
            return result
        if action == "preview" and artifact.mime_type not in SAFE_PREVIEW_MIME_TYPES:
            result = ArtifactAccessResult(
                False,
                "该 MIME 类型不支持在线预览，请使用下载",
                error_code="PREVIEW_UNSUPPORTED",
            )
            cls._audit(db, artifact_id, artifact.task_run_id, artifact.resource_id, action, operator, result)
            return result
        if artifact.availability_status != "ONLINE" or resource.status != "READY":
            result = ArtifactAccessResult(False, "产物当前不可取回", error_code="ARTIFACT_UNAVAILABLE")
            cls._audit(db, artifact_id, artifact.task_run_id, artifact.resource_id, action, operator, result)
            return result
        if resource.expires_at and resource.expires_at <= datetime.now():
            result = ArtifactAccessResult(False, "产物资源已过期", error_code="RESOURCE_EXPIRED")
            cls._audit(db, artifact_id, artifact.task_run_id, artifact.resource_id, action, operator, result)
            return result

        try:
            content = cls._read_content(db, resource, operator)
        except ResourceDownloadError as exc:
            result = ArtifactAccessResult(False, str(exc), error_code=exc.code)
            cls._audit(db, artifact_id, artifact.task_run_id, artifact.resource_id, action, operator, result)
            return result
        actual_sha256 = hashlib.sha256(content).hexdigest()
        if len(content) != artifact.file_size or actual_sha256 != artifact.sha256:
            result = ArtifactAccessResult(
                False,
                "文件校验失败，正文与产物登记摘要不一致",
                error_code="CHECKSUM_MISMATCH",
            )
            cls._audit(db, artifact_id, artifact.task_run_id, artifact.resource_id, action, operator, result)
            return result
        file_name = cls._safe_file_name(artifact.original_file_name, artifact.artifact_id)
        result = ArtifactAccessResult(
            True,
            "产物读取成功",
            ArtifactContent(
                artifact_id=artifact.artifact_id,
                file_name=file_name,
                mime_type=artifact.mime_type or resource.mime_type or "application/octet-stream",
                file_size=len(content),
                sha256=actual_sha256,
                content=content,
                disposition="inline" if action == "preview" else "attachment",
            ),
        )
        cls._audit(db, artifact_id, artifact.task_run_id, artifact.resource_id, action, operator, result)
        logger.info(f"配置任务产物访问成功: artifact_id={artifact_id}, action={action}, operator={operator}")
        return result

    @classmethod
    def list_artifacts(
        cls,
        db: Session,
        task_run_id: int,
        current_user: CurrentUserModel,
    ) -> tuple[bool, str, list[ArtifactModel]]:
        """按任务/运行归属查询产物，避免仅凭 taskRunId 泄露元数据。"""
        operator, is_admin = cls._operator_scope(current_user)
        run = ConfigurationTaskRunDao.get_run(db, task_run_id)
        task = ConfigurationTaskDao.get_task(db, run.task_id) if run else None
        if not run or not task:
            return False, "运行记录不存在", []
        if not cls._can_access(operator, is_admin, task, run, None, None):
            return False, "无权查询该运行产物", []
        rows = TaskArtifactDao.list_artifacts(db, task_run_id)
        return True, "产物查询成功", [ConfigurationTaskArtifactService.to_artifact_model(row) for row in rows]

    @staticmethod
    def _operator_scope(current_user: CurrentUserModel) -> tuple[str, bool]:
        """提取操作者和管理员范围。"""
        user = current_user.user
        return user.user_name if user else "system", bool(user and getattr(user, "admin", False))

    @staticmethod
    def _can_access(operator: str, is_admin: bool, task, run, artifact, resource) -> bool:
        """按任务/运行/产物/资源归属判断访问范围，管理员可跨范围访问。"""
        if is_admin:
            return True
        owners = {
            str(getattr(task, "create_by", "") or ""),
            str(getattr(run, "create_by", "") or ""),
            str(getattr(artifact, "create_by", "") or ""),
            str(getattr(resource, "create_by", "") or "") if resource else "",
        }
        owners.discard("")
        return bool(operator and operator in owners)

    @staticmethod
    def _validate_consistency(artifact, resource) -> tuple[str, str] | None:
        """确认产物引用和资源索引的关键元数据一致。"""
        checks = (
            (artifact.file_size, resource.file_size, "SIZE_MISMATCH", "产物与资源大小不一致"),
            (artifact.sha256.lower(), resource.sha256.lower(), "CHECKSUM_MISMATCH", "产物与资源摘要不一致"),
            (artifact.mime_type, resource.mime_type, "METADATA_MISMATCH", "产物与资源 MIME 不一致"),
            (artifact.agent_code, resource.agent_code, "METADATA_MISMATCH", "产物与资源 Agent 归属不一致"),
            (artifact.object_key, resource.object_key, "METADATA_MISMATCH", "产物与资源定位键不一致"),
        )
        for actual, expected, code, message in checks:
            if actual != expected:
                return code, message
        return None

    @staticmethod
    def _read_content(db: Session, resource: ResourceObject, operator: str) -> bytes:
        """按资源执行侧分流读取正文，不向调用方暴露本地路径。"""
        return ResourceExtendedService.read_resource_content(db, resource, operator)

    @staticmethod
    def _safe_file_name(file_name: str, artifact_id: int) -> str:
        """生成不含路径分隔符和控制字符的下载文件名。"""
        name = Path(file_name or "").name
        name = _SAFE_FILE_NAME.sub("_", name).strip(" .")
        return name[:180] or f"artifact-{artifact_id}"

    @staticmethod
    def _audit(
        db: Session,
        artifact_id: int,
        task_run_id: int | None,
        resource_id: int | None,
        action: str,
        operator: str,
        result: ArtifactAccessResult,
    ) -> None:
        """写入脱敏访问审计，失败不覆盖原始访问结果。"""
        try:
            ConfigurationTaskArtifactAccessAuditDao.add_audit(
                db,
                {
                    "artifact_id": artifact_id,
                    "task_run_id": task_run_id,
                    "resource_id": resource_id,
                    "action": action,
                    "operator": operator,
                    "success": result.is_success,
                    "error_code": result.error_code,
                    "audit_message": result.message[:500],
                },
            )
            db.commit()
        except Exception as exc:
            db.rollback()
            logger.warning(f"产物访问审计写入失败: artifact_id={artifact_id}, action={action}, error={exc}")

