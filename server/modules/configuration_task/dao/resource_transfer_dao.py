"""配置任务资源传输数据访问层。"""

from datetime import datetime

from sqlalchemy.orm import Session

from modules.configuration_task.entity.do.resource_transfer_do import ResourceTransfer


class ResourceTransferDao:
    """只封装资源传输实体的查询、创建和更新。"""

    @classmethod
    def get_transfer(cls, db: Session, transfer_id: str) -> ResourceTransfer | None:
        """按传输 ID 查询传输实体。"""
        return db.query(ResourceTransfer).filter(ResourceTransfer.transfer_id == transfer_id).first()

    @classmethod
    def list_expired_active_transfers(cls, db: Session, limit: int = 200) -> list[ResourceTransfer]:
        """查询已超过 TTL 的活动传输，供过期清理任务收敛。"""
        return (
            db.query(ResourceTransfer)
            .filter(
                ResourceTransfer.status.in_(["PENDING", "UPLOADING"]),
                ResourceTransfer.expires_at.isnot(None),
                ResourceTransfer.expires_at <= datetime.now(),
            )
            .limit(limit)
            .all()
        )

    @classmethod
    def get_active_by_resource(cls, db: Session, resource_id: int) -> ResourceTransfer | None:
        """查询资源当前仍在进行中的传输。"""
        return (
            db.query(ResourceTransfer)
            .filter(
                ResourceTransfer.resource_id == resource_id,
                ResourceTransfer.status.in_(["PENDING", "UPLOADING"]),
            )
            .order_by(ResourceTransfer.create_time.desc())
            .first()
        )

    @classmethod
    def add_transfer(cls, db: Session, values: dict) -> ResourceTransfer:
        """新增传输实体并刷新数据库状态。"""
        row = ResourceTransfer(**values)
        db.add(row)
        db.flush()
        return row

    @classmethod
    def update_transfer(cls, db: Session, transfer_id: str, values: dict) -> bool:
        """按传输 ID更新传输实体。"""
        update_values = {**values, "update_time": datetime.now()}
        return (
            db.query(ResourceTransfer)
            .filter(ResourceTransfer.transfer_id == transfer_id)
            .update(update_values, synchronize_session="fetch")
            == 1
        )
