"""配置任务产物服务：Agent 截图/日志登记为 Agent 本地资源并建立产物引用。

链路：Agent 在步骤完成/失败时通过资源传输协议上报截图（HTTP 接口走既有
begin/chunk/commit 或单接口直传），本服务负责：
1. 在资源表登记 `agent_local` 资源（状态 READY，由 Agent 本地 manifest 保证存在）；
2. 建立 `task_artifact` 产物引用（只追加，不覆盖）。
报告归档只读取产物引用，不接触文件正文。
"""

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from loguru import logger
from sqlalchemy.orm import Session

from modules.configuration_task.dao.resource_dao import ResourceDao
from modules.configuration_task.dao.stage_artifact_dao import TaskArtifactDao
from modules.configuration_task.dao.task_dao import ConfigurationTaskRunDao
from modules.configuration_task.entity.do.resource_object_do import ResourceObject
from modules.configuration_task.entity.vo.task_vo import AgentStepScreenshotModel, ArtifactModel

ARTIFACT_TYPES = {"step_screenshot", "failure_screenshot", "execution_log", "report"}


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
        """登记 Agent 上报的截图/日志产物：资源表 + 产物引用一次写入。

        资源状态直接置 READY：Agent 上报即代表本地 manifest 已写入该文件
        （Agent 端在截图后通过本地文件服务落盘），服务端仅追踪元数据。
        """
        user = getattr(current_user, "user", None)
        operator = user.user_name if user else "system"
        try:
            task_run_id = int(model.task_run_id)
        except (TypeError, ValueError):
            return ArtifactServiceResult(False, "taskRunId 不合法")
        run = ConfigurationTaskRunDao.get_run(db, task_run_id)
        if not run:
            return ArtifactServiceResult(False, "运行记录不存在")

        data_text = model.data
        try:
            import base64

            content = base64.b64decode(data_text.encode("ascii"), validate=True)
        except Exception:
            return ArtifactServiceResult(False, "data 必须是合法 Base64")
        if not content:
            return ArtifactServiceResult(False, "截图内容不能为空")
        sha256 = hashlib.sha256(content).hexdigest()
        size = len(content)

        # 资源身份：agent_code + object_key + version；同一运行同一步骤重复上报幂等返回。
        object_key = f"artifacts/{task_run_id}/{model.artifact_type}/{model.step_index}_{sha256[:16]}"
        existing = ResourceDao.get_by_identity(db, run.agent_code, object_key, 1)
        if existing:
            resource = existing
        else:
            now = datetime.now()
            try:
                resource = ResourceDao.add_resource(
                    db,
                    {
                        "provider_type": "agent_local",
                        "provider_execution_side": "agent",
                        "agent_code": run.agent_code,
                        "object_key": object_key,
                        "original_file_name": model.file_name or "screenshot.png",
                        "mime_type": model.mime_type or "image/png",
                        "file_size": size,
                        "checksum_algorithm": "sha256",
                        "sha256": sha256,
                        "version": 1,
                        "status": "READY",
                        "create_by": operator,
                        "create_time": now,
                        "update_by": operator,
                        "update_time": now,
                        "last_audit_at": now,
                        "audit_message": "Agent 步骤产物上报登记",
                        "remark": f"task_run_id={task_run_id} step_index={model.step_index}",
                    },
                )
                db.commit()
            except Exception as exc:
                db.rollback()
                logger.warning(f"产物资源登记冲突，回查已有记录: task_run_id={task_run_id}, error={exc}")
                resource = ResourceDao.get_by_identity(db, run.agent_code, object_key, 1)
                if not resource:
                    return ArtifactServiceResult(False, "产物资源登记失败")

        artifact = TaskArtifactDao.add_artifact(
            db,
            {
                "task_run_id": task_run_id,
                "run_stage_id": None,
                "artifact_type": model.artifact_type,
                "step_key": f"step-{model.step_index}",
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
        logger.info(
            f"登记运行产物: artifact_id={artifact.artifact_id}, task_run_id={task_run_id}, "
            f"type={model.artifact_type}, size={size}, operator={operator}"
        )
        return ArtifactServiceResult(True, "产物登记成功", cls.to_artifact_model(artifact))

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
            resourceId=str(row.resource_id),
            originalFileName=row.original_file_name or "",
            fileSize=row.file_size,
            sha256=row.sha256 or "",
            note=row.note or "",
            createTime=row.create_time,
        )
