"""配置任务、版本和运行数据访问层；只封装查询和持久化。"""

import json
from datetime import datetime

from sqlalchemy.orm import Session

from modules.configuration_task.entity.do.task_do import ConfigurationTask, ConfigurationTaskVersion
from modules.configuration_task.entity.do.task_run_do import ConfigurationTaskRun


class ConfigurationTaskDao:
    """配置任务定义数据访问。"""

    @classmethod
    def get_task(cls, db: Session, task_id: int) -> ConfigurationTask | None:
        """按任务 ID 查询任务实体。"""
        return db.query(ConfigurationTask).filter(ConfigurationTask.task_id == task_id).first()

    @classmethod
    def list_tasks(cls, db: Session, keyword: str = "", limit: int = 50) -> list[ConfigurationTask]:
        """按关键词查询任务列表，倒序返回。"""
        query = db.query(ConfigurationTask)
        if keyword:
            query = query.filter(ConfigurationTask.task_name.like(f"%{keyword}%"))
        return query.order_by(ConfigurationTask.create_time.desc()).limit(limit).all()

    @classmethod
    def add_task(cls, db: Session, values: dict) -> ConfigurationTask:
        """新增任务实体并刷新数据库状态。"""
        row = ConfigurationTask(**values)
        db.add(row)
        db.flush()
        return row

    @classmethod
    def update_task(cls, db: Session, task_id: int, values: dict) -> bool:
        """按任务 ID 更新任务实体。"""
        update_values = {**values, "update_time": datetime.now()}
        return (
            db.query(ConfigurationTask).filter(ConfigurationTask.task_id == task_id).update(update_values) == 1
        )


class ConfigurationTaskVersionDao:
    """配置任务版本数据访问。"""

    @classmethod
    def get_version(cls, db: Session, version_id: int) -> ConfigurationTaskVersion | None:
        """按版本 ID 查询版本实体。"""
        return db.query(ConfigurationTaskVersion).filter(ConfigurationTaskVersion.version_id == version_id).first()

    @classmethod
    def get_by_task_and_no(cls, db: Session, task_id: int, version_no: int) -> ConfigurationTaskVersion | None:
        """按任务和版本号精确查询版本。"""
        return (
            db.query(ConfigurationTaskVersion)
            .filter(ConfigurationTaskVersion.task_id == task_id, ConfigurationTaskVersion.version_no == version_no)
            .first()
        )

    @classmethod
    def list_versions(cls, db: Session, task_id: int, limit: int = 50) -> list[ConfigurationTaskVersion]:
        """按任务查询版本列表，版本号倒序。"""
        return (
            db.query(ConfigurationTaskVersion)
            .filter(ConfigurationTaskVersion.task_id == task_id)
            .order_by(ConfigurationTaskVersion.version_no.desc())
            .limit(limit)
            .all()
        )

    @classmethod
    def get_max_version_no(cls, db: Session, task_id: int) -> int:
        """查询任务当前最大版本号，无版本时返回 0。"""
        max_no = (
            db.query(ConfigurationTaskVersion)
            .filter(ConfigurationTaskVersion.task_id == task_id)
            .order_by(ConfigurationTaskVersion.version_no.desc())
            .first()
        )
        return int(max_no.version_no) if max_no else 0

    @classmethod
    def add_version(cls, db: Session, values: dict) -> ConfigurationTaskVersion:
        """新增版本实体并刷新数据库状态。"""
        row = ConfigurationTaskVersion(**values)
        db.add(row)
        db.flush()
        return row

    @classmethod
    def update_version(cls, db: Session, version_id: int, values: dict) -> bool:
        """按版本 ID 更新版本实体。"""
        update_values = {**values, "update_time": datetime.now()}
        return (
            db.query(ConfigurationTaskVersion)
            .filter(ConfigurationTaskVersion.version_id == version_id)
            .update(update_values)
            == 1
        )


class ConfigurationTaskRunDao:
    """配置任务运行数据访问。"""

    @classmethod
    def get_run(cls, db: Session, task_run_id: int) -> ConfigurationTaskRun | None:
        """按运行 ID 查询运行实体。"""
        return db.query(ConfigurationTaskRun).filter(ConfigurationTaskRun.task_run_id == task_run_id).first()

    @classmethod
    def list_runs(
        cls,
        db: Session,
        task_id: int | None = None,
        agent_code: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[ConfigurationTaskRun]:
        """按任务、Agent 和状态查询运行列表，创建时间倒序。"""
        query = db.query(ConfigurationTaskRun)
        if task_id:
            query = query.filter(ConfigurationTaskRun.task_id == task_id)
        if agent_code:
            query = query.filter(ConfigurationTaskRun.agent_code == agent_code)
        if status:
            query = query.filter(ConfigurationTaskRun.status == status)
        return query.order_by(ConfigurationTaskRun.create_time.desc()).limit(limit).all()

    @classmethod
    def add_run(cls, db: Session, values: dict) -> ConfigurationTaskRun:
        """新增运行实体并刷新数据库状态。"""
        row = ConfigurationTaskRun(**values)
        db.add(row)
        db.flush()
        return row

    @classmethod
    def update_run(cls, db: Session, task_run_id: int, values: dict) -> bool:
        """按运行 ID 更新运行实体。"""
        update_values = {**values, "update_time": datetime.now()}
        return (
            db.query(ConfigurationTaskRun).filter(ConfigurationTaskRun.task_run_id == task_run_id).update(update_values)
            == 1
        )


def load_json_object(raw: str | None) -> dict:
    """安全解析 JSON 对象，解析失败返回空字典。"""
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def load_json_list(raw: str | None) -> list:
    """安全解析 JSON 数组，解析失败返回空列表。"""
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        return []
    return value if isinstance(value, list) else []
