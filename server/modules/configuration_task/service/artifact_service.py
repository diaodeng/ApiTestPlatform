"""配置任务产物服务：Agent 截图/日志登记为 Agent 本地资源并建立产物引用。

链路：Agent 在步骤完成/失败时通过资源传输协议上报截图（HTTP 接口走既有
begin/chunk/commit 或单接口直传），本服务负责：
1. 在资源表登记 `agent_local` 资源（状态 READY，由 Agent 本地 manifest 保证存在）；
2. 建立 `task_artifact` 产物引用（只追加，不覆盖）。
报告归档只读取产物引用，不接触文件正文。
"""

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from loguru import logger
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from module_qtr.service.agent_file_transfer_service import AgentFileTransferService
from modules.configuration_task.dao.resource_dao import ResourceDao
from modules.configuration_task.dao.stage_artifact_dao import (
    ConfigurationTaskStageDao,
    TaskArtifactDao,
)
from modules.configuration_task.dao.task_dao import ConfigurationTaskRunDao, load_json_list
from modules.configuration_task.entity.do.resource_object_do import ResourceObject
from modules.configuration_task.entity.vo.task_vo import AgentStepScreenshotModel, ArtifactModel
from modules.configuration_task.service.evidence_status_service import (
    ConfigurationTaskEvidenceStatusService,
)

ARTIFACT_TYPES = {"step_screenshot", "failure_screenshot", "execution_log", "report"}
_EVIDENCE_TYPES = {
    "checkpoint_screenshot",
    "before_screenshot",
    "after_screenshot",
    "failure_screenshot",
    "execution_log",
    "report",
}
_SHA256_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")
_ALLOWED_MIME_TYPES = {"image/png", "image/jpeg", "image/webp", "text/plain", "application/json"}


@dataclass
class ArtifactServiceResult:
    """产物操作结果。"""

    is_success: bool
    message: str
    result: Any = None


def _dumps(value) -> str:
    """序列化为紧凑 JSON。"""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


class ConfigurationTaskArtifactService:
    """产物登记与查询。"""

    @classmethod
    def register_agent_screenshot(
        cls,
        db: Session,
        model: AgentStepScreenshotModel,
        current_user,
    ) -> ArtifactServiceResult:
        """登记 Agent 截图产物，兼容旧 Base64 并优先支持 metadata-only。"""
        user = getattr(current_user, "user", None)
        operator = user.user_name if user else "system"
        try:
            task_run_id = int(model.task_run_id)
        except (TypeError, ValueError):
            return ArtifactServiceResult(False, "taskRunId 不合法")
        run = ConfigurationTaskRunDao.get_run(db, task_run_id)
        if not run:
            return ArtifactServiceResult(False, "运行记录不存在")
        if model.agent_code and model.agent_code != run.agent_code:
            return ArtifactServiceResult(False, "产物不属于当前运行 Agent")
        if model.artifact_type not in ARTIFACT_TYPES:
            return ArtifactServiceResult(False, "产物类型不支持")

        artifact_type = model.artifact_type
        evidence_type = model.evidence_type or (
            "checkpoint_screenshot" if artifact_type == "step_screenshot" else
            "failure_screenshot" if artifact_type == "failure_screenshot" else None
        )
        if evidence_type and evidence_type not in _EVIDENCE_TYPES:
            return ArtifactServiceResult(False, "证据类型不支持")
        if model.mime_type not in _ALLOWED_MIME_TYPES:
            return ArtifactServiceResult(False, "MIME 类型不支持")

        run_stage_id = None
        if model.stage_key:
            stage = ConfigurationTaskStageDao.get_run_stage_by_run_and_key(
                db, task_run_id, model.stage_key
            )
            if not stage:
                return ArtifactServiceResult(False, "阶段不存在或不属于当前运行")
            run_stage_id = stage.run_stage_id
            stage_step_ids = load_json_list(stage.step_ids_json)
            if model.step_id and stage_step_ids and model.step_id not in stage_step_ids:
                return ArtifactServiceResult(False, "步骤不属于上报阶段")

        data_text = model.data
        resource_probe = ("ONLINE", "", "")
        if data_text:
            # 旧版事件只在兼容分支解码，正文不写入运行 JSON、日志或资源索引。
            try:
                import base64

                content = base64.b64decode(data_text.encode("ascii"), validate=True)
            except Exception:
                return ArtifactServiceResult(False, "data 必须是合法 Base64")
            if not content:
                return ArtifactServiceResult(False, "截图内容不能为空")
            sha256 = hashlib.sha256(content).hexdigest()
            size = len(content)
            object_key = (
                f"artifacts/{task_run_id}/{artifact_type}/"
                f"{model.step_index}_{sha256[:16]}"
            )
            agent_code = run.agent_code
        else:
            if model.provider_type != "agent_local":
                return ArtifactServiceResult(False, "metadata-only 只支持 agent_local Provider")
            object_key = str(model.object_key or "").strip()
            parts = object_key.split("/")
            if (
                not object_key
                or object_key.startswith("/")
                or "\\" in object_key
                or ".." in parts
                or len(parts) != 2
                or parts[0] != "resources"
                or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", parts[1])
            ):
                return ArtifactServiceResult(False, "objectKey 不是受控相对定位键")
            if model.file_size is None or model.file_size <= 0:
                return ArtifactServiceResult(False, "metadata-only 必须提供 fileSize")
            if not _SHA256_PATTERN.fullmatch(model.sha256 or ""):
                return ArtifactServiceResult(False, "metadata-only 必须提供合法 SHA-256")
            sha256 = model.sha256.lower()
            size = model.file_size
            agent_code = model.agent_code or run.agent_code
            resource_probe = cls._probe_agent_resource(agent_code, object_key, size, sha256)
        existing_resource = ResourceDao.get_by_identity(db, agent_code, object_key, 1)
        if existing_resource:
            if existing_resource.sha256 != sha256 or existing_resource.file_size != size:
                return ArtifactServiceResult(False, "资源元数据与已有资源不一致")
            resource = existing_resource
            if data_text is None:
                resource_status, resource_error_code, resource_error_message = cls._resource_state_from_probe(
                    resource_probe
                )
                ResourceDao.update_resource(
                    db,
                    resource.resource_id,
                    {
                        "status": resource_status,
                        "error_code": resource_error_code,
                        "error_message": resource_error_message,
                        "last_audit_at": datetime.now(),
                        "audit_message": "Agent metadata-only 资源状态复核",
                        "update_by": operator,
                    },
                )
                db.flush()
        else:
            now = datetime.now()
            resource_status, resource_error_code, resource_error_message = cls._resource_state_from_probe(
                resource_probe
            )
            try:
                resource = ResourceDao.add_resource(
                    db,
                    {
                        "provider_type": model.provider_type or "agent_local",
                        "provider_execution_side": "agent",
                        "agent_code": agent_code,
                        "object_key": object_key,
                        "original_file_name": model.file_name or "screenshot.png",
                        "mime_type": model.mime_type or "image/png",
                        "file_size": size,
                        "checksum_algorithm": "sha256",
                        "sha256": sha256,
                        "version": 1,
                        "status": resource_status,
                        "error_code": resource_error_code,
                        "error_message": resource_error_message,
                        "create_by": operator,
                        "create_time": now,
                        "update_by": operator,
                        "update_time": now,
                        "last_audit_at": now,
                        "audit_message": "Agent 步骤产物 metadata-only 登记",
                        "remark": f"task_run_id={task_run_id} step_id={model.step_id or model.step_index}",
                    },
                )
            except Exception as exc:
                db.rollback()
                logger.warning(
                    f"产物资源登记冲突，回查已有记录: task_run_id={task_run_id}, error={exc}"
                )
                resource = ResourceDao.get_by_identity(db, agent_code, object_key, 1)
                if not resource:
                    return ArtifactServiceResult(False, "产物资源登记失败")

        artifact_availability = resource_probe[0]

        step_id = model.step_id or f"step-{model.step_index}"
        evidence_key = model.evidence_key or (step_id if data_text is None else "")
        existing_artifact = TaskArtifactDao.get_artifact_by_evidence_identity(
            db,
            task_run_id,
            run_stage_id,
            step_id,
            evidence_key,
            model.sequence_no,
            sha256,
        )
        if existing_artifact:
            db.rollback()
            ConfigurationTaskEvidenceStatusService.refresh_run_and_stages(db, task_run_id)
            return ArtifactServiceResult(True, "产物已登记", cls.to_artifact_model(existing_artifact))

        try:
            artifact = TaskArtifactDao.add_artifact(
                db,
                {
                    "task_run_id": task_run_id,
                    "run_stage_id": run_stage_id,
                    "artifact_type": artifact_type,
                    "step_key": step_id,
                    "step_id": step_id,
                    "evidence_type": evidence_type or "",
                    "evidence_key": evidence_key,
                    "sequence_no": model.sequence_no,
                    "captured_at": model.captured_at,
                    "mask_applied": model.mask_applied,
                    "availability_status": artifact_availability,
                    "provider_type": model.provider_type or "agent_local",
                    "agent_code": agent_code,
                    "object_key": object_key,
                    "mime_type": model.mime_type or "image/png",
                    "resource_id": resource.resource_id,
                    "original_file_name": model.file_name or "screenshot.png",
                    "file_size": size,
                    "sha256": sha256,
                    "note": model.step_name or "",
                    "create_by": operator,
                    "create_time": datetime.now(),
                },
            )
            db.commit()
        except IntegrityError as exc:
            # 并发请求可能同时通过插入前查询，唯一键由数据库完成最终裁决；
            # 回滚后按同一引用身份回查，向调用方返回已提交的记录而不重复创建。
            db.rollback()
            existing_artifact = TaskArtifactDao.get_artifact_by_evidence_identity(
                db,
                task_run_id,
                run_stage_id,
                step_id,
                evidence_key,
                model.sequence_no,
                sha256,
            )
            if not existing_artifact:
                logger.warning(
                    f"产物引用登记唯一约束冲突且无法回查: task_run_id={task_run_id}, "
                    f"run_stage_id={run_stage_id}, step_id={step_id}, error={exc}"
                )
                return ArtifactServiceResult(False, "产物引用登记冲突")
            ConfigurationTaskEvidenceStatusService.refresh_run_and_stages(db, task_run_id)
            return ArtifactServiceResult(
                True,
                "产物已登记",
                cls.to_artifact_model(existing_artifact),
            )
        logger.info(
            f"登记运行产物: artifact_id={artifact.artifact_id}, task_run_id={task_run_id}, "
            f"type={artifact_type}, evidence_type={evidence_type}, size={size}, operator={operator}"
        )
        return ArtifactServiceResult(True, "产物登记成功", cls.to_artifact_model(artifact))

    @staticmethod
    def _probe_agent_resource(
        agent_code: str,
        object_key: str,
        expected_size: int,
        expected_sha256: str,
    ) -> tuple[str, str, str]:
        """登记 metadata-only 产物前探测 Agent 本地文件，不读取文件正文。"""
        parts = object_key.split("/")
        agent_resource_id = parts[1] if len(parts) == 2 else ""
        command_result = AgentFileTransferService.send_command(
            agent_code,
            "file_stat",
            {
                "resource_id": agent_resource_id,
                "expected_size": expected_size,
                "expected_sha256": expected_sha256,
            },
            timeout_seconds=30,
        )
        if not command_result.success:
            error_code = command_result.error_code or "AGENT_STAT_FAILED"
            availability = {
                "AGENT_OFFLINE": "AGENT_OFFLINE",
                "RESOURCE_NOT_FOUND": "NOT_FOUND",
                "RESOURCE_EXPIRED": "NOT_FOUND",
                "CHECKSUM_MISMATCH": "CHECKSUM_MISMATCH",
                "SIZE_MISMATCH": "CHECKSUM_MISMATCH",
            }.get(error_code, "ACCESS_DENIED")
            return availability, error_code, command_result.error_message or "Agent 文件状态不可用"
        actual_size = int(command_result.data.get("size") or 0)
        actual_sha256 = str(command_result.data.get("sha256") or "").lower()
        if actual_size != expected_size:
            return "CHECKSUM_MISMATCH", "SIZE_MISMATCH", "Agent 文件大小与上报元数据不一致"
        if actual_sha256 != expected_sha256:
            return "CHECKSUM_MISMATCH", "CHECKSUM_MISMATCH", "Agent 文件摘要与上报元数据不一致"
        return "ONLINE", "", ""

    @staticmethod
    def _resource_state_from_probe(probe: tuple[str, str, str]) -> tuple[str, str, str]:
        """把 Agent 探测结果转换为资源表状态和脱敏错误摘要。"""
        availability, error_code, error_message = probe
        status = "READY" if availability == "ONLINE" else "FAILED"
        return status, error_code, error_message

    @classmethod
    def register_report_artifact(
        cls,
        db: Session,
        task_run_id: int,
        resource: ResourceObject,
        operator: str,
    ) -> Any:
        """报告生成后登记产物引用。"""
        artifact = TaskArtifactDao.add_artifact(
            db,
            {
                "task_run_id": task_run_id,
                "run_stage_id": None,
                "artifact_type": "report",
                "step_key": "",
                "step_id": "",
                "evidence_type": "report",
                "evidence_key": f"report-{task_run_id}",
                "sequence_no": 1,
                "availability_status": "ONLINE" if resource.status == "READY" else "NOT_FOUND",
                "provider_type": resource.provider_type,
                "agent_code": resource.agent_code,
                "object_key": resource.object_key,
                "mime_type": resource.mime_type,
                "resource_id": resource.resource_id,
                "original_file_name": resource.original_file_name,
                "file_size": resource.file_size,
                "sha256": resource.sha256,
                "note": "任务运行报告归档",
                "create_by": operator,
                "create_time": datetime.now(),
            },
        )
        db.commit()
        return artifact

    @classmethod
    def list_artifacts(cls, db: Session, task_run_id: int) -> list[ArtifactModel]:
        """查询运行产物列表。"""
        rows = TaskArtifactDao.list_artifacts(db, task_run_id)
        return [cls.to_artifact_model(row) for row in rows]

    @staticmethod
    def to_artifact_model(row) -> ArtifactModel:
        """产物 ORM 转响应模型，BIGINT ID 字符串化。"""
        return ArtifactModel(
            artifactId=str(row.artifact_id),
            taskRunId=str(row.task_run_id),
            runStageId=str(row.run_stage_id) if row.run_stage_id else None,
            artifactType=row.artifact_type,
            stepKey=row.step_key or "",
            stepId=row.step_id or "",
            evidenceType=row.evidence_type or None,
            evidenceKey=row.evidence_key or "",
            sequenceNo=row.sequence_no or 1,
            capturedAt=row.captured_at,
            maskApplied=bool(row.mask_applied),
            availabilityStatus=row.availability_status or "ONLINE",
            providerType=row.provider_type or "agent_local",
            agentCode=row.agent_code or "",
            objectKey=row.object_key or "",
            mimeType=row.mime_type or "",
            resourceId=str(row.resource_id),
            originalFileName=row.original_file_name or "",
            fileSize=row.file_size,
            sha256=row.sha256 or "",
            note=row.note or "",
            createTime=row.create_time,
        )
