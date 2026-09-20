"""阶段与产物数据访问层；只封装查询和持久化。"""

import json
from datetime import datetime

from sqlalchemy.orm import Session

from modules.configuration_task.entity.do.stage_artifact_do import (
    ConfigurationTaskStage,
    TaskArtifact,
    TaskRunStage,
)


def load_json_list(raw: str | None) -> list:
    """安全解析 JSON 数组，解析失败返回空列表。"""
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        return []
    return value if isinstance(value, list) else []


class ConfigurationTaskStageDao:
    """版本阶段与运行阶段数据访问。"""

    @classmethod
    def list_version_stages(cls, db: Session, version_id: int) -> list[ConfigurationTaskStage]:
        """按版本查询阶段定义，阶段顺序升序。"""
        return (
            db.query(ConfigurationTaskStage)
            .filter(ConfigurationTaskStage.version_id == version_id)
            .order_by(ConfigurationTaskStage.stage_order.asc())
            .all()
        )

    @classmethod
    def replace_version_stages(cls, db: Session, version_id: int, stages: list[dict]) -> list[ConfigurationTaskStage]:
        """删除并重建版本阶段定义；仅在版本草稿阶段由服务层调用。"""
        db.query(ConfigurationTaskStage).filter(ConfigurationTaskStage.version_id == version_id).delete()
        rows = [ConfigurationTaskStage(**stage) for stage in stages]
        db.add_all(rows)
        db.flush()
        return rows

    @classmethod
    def delete_version_stages(cls, db: Session, version_id: int) -> None:
        """按版本删除阶段定义。"""
        db.query(ConfigurationTaskStage).filter(ConfigurationTaskStage.version_id == version_id).delete()

    @classmethod
    def list_run_stages(cls, db: Session, task_run_id: int) -> list[TaskRunStage]:
        """按运行查询阶段实例，阶段顺序升序。"""
        return (
            db.query(TaskRunStage)
            .filter(TaskRunStage.task_run_id == task_run_id)
            .order_by(TaskRunStage.stage_order.asc())
            .all()
        )

    @classmethod
    def get_run_stage(cls, db: Session, run_stage_id: int) -> TaskRunStage | None:
        """按运行阶段 ID 查询实体。"""
        return db.query(TaskRunStage).filter(TaskRunStage.run_stage_id == run_stage_id).first()

    @classmethod
    def get_run_stage_by_run_and_key(cls, db: Session, task_run_id: int, stage_key: str) -> TaskRunStage | None:
        """按运行和阶段标识查询实体。"""
        return (
            db.query(TaskRunStage)
            .filter(TaskRunStage.task_run_id == task_run_id, TaskRunStage.stage_key == stage_key)
            .first()
        )

    @classmethod
    def add_run_stages(cls, db: Session, stages: list[dict]) -> list[TaskRunStage]:
        """批量写入运行阶段快照。"""
        rows = [TaskRunStage(**stage) for stage in stages]
        db.add_all(rows)
        db.flush()
        return rows

    @classmethod
    def update_run_stage(cls, db: Session, run_stage_id: int, values: dict) -> bool:
        """按运行阶段 ID 更新实体。"""
        update_values = {**values, "update_time": datetime.now()}
        return (
            db.query(TaskRunStage).filter(TaskRunStage.run_stage_id == run_stage_id).update(update_values) == 1
        )


class TaskArtifactDao:
    """运行产物数据访问。"""

    @classmethod
    def add_artifact(cls, db: Session, values: dict) -> TaskArtifact:
        """新增产物引用并刷新数据库状态。"""
        row = TaskArtifact(**values)
        db.add(row)
        db.flush()
        return row

    @classmethod
    def list_artifacts(cls, db: Session, task_run_id: int) -> list[TaskArtifact]:
        """按运行查询产物列表，创建时间升序。"""
        return (
            db.query(TaskArtifact)
            .filter(TaskArtifact.task_run_id == task_run_id)
            .order_by(TaskArtifact.create_time.asc())
            .all()
        )

    @classmethod
    def list_artifacts_by_resource(
        cls, db: Session, resource_id: int, limit: int = 200
    ) -> list[TaskArtifact]:
        """按资源查询引用它的产物，用于删除引用保护。"""
        return (
            db.query(TaskArtifact)
            .filter(TaskArtifact.resource_id == resource_id)
            .limit(limit)
            .all()
        )

    @classmethod
    def get_artifact_by_evidence_identity(
        cls,
        db: Session,
        task_run_id: int,
        run_stage_id: int | None,
        step_id: str,
        evidence_key: str,
        sequence_no: int,
        sha256: str,
    ) -> TaskArtifact | None:
        """按运行阶段、稳定步骤、证据键、序号和摘要查询产物引用。"""
        query = db.query(TaskArtifact).filter(
            TaskArtifact.task_run_id == task_run_id,
            TaskArtifact.step_id == (step_id or ""),
            TaskArtifact.evidence_key == (evidence_key or ""),
            TaskArtifact.sequence_no == sequence_no,
            TaskArtifact.sha256 == (sha256 or ""),
        )
        if run_stage_id is None:
            query = query.filter(TaskArtifact.run_stage_id.is_(None))
        else:
            query = query.filter(TaskArtifact.run_stage_id == run_stage_id)
        return query.first()

    @classmethod
    def get_artifact(cls, db: Session, artifact_id: int) -> TaskArtifact | None:
        """按产物 ID 查询实体。"""
        return db.query(TaskArtifact).filter(TaskArtifact.artifact_id == artifact_id).first()
