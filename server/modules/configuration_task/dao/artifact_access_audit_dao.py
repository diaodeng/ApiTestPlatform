"""配置任务产物访问审计 DAO。"""

from sqlalchemy.orm import Session

from modules.configuration_task.entity.do.artifact_access_audit_do import (
    ConfigurationTaskArtifactAccessAudit,
)


class ConfigurationTaskArtifactAccessAuditDao:
    """只负责产物访问审计记录的持久化。"""

    @classmethod
    def add_audit(cls, db: Session, values: dict) -> ConfigurationTaskArtifactAccessAudit:
        """新增一条不含文件正文的访问审计。"""
        row = ConfigurationTaskArtifactAccessAudit(**values)
        db.add(row)
        db.flush()
        return row
