"""配置任务资源维护服务：资源/传输过期收敛与孤儿运行恢复。

供定时任务周期调用；方法均为同步实现，由调用方决定线程池边界。
"""

from datetime import datetime

from loguru import logger
from sqlalchemy.orm import Session

from modules.configuration_task.dao.resource_dao import ResourceDao
from modules.configuration_task.dao.resource_transfer_dao import ResourceTransferDao


class ConfigurationTaskMaintenanceService:
    """资源过期、传输过期与孤儿运行的周期维护。"""

    @classmethod
    def cleanup_expired_resources(cls, db: Session, limit: int = 200) -> dict[str, int]:
        """把已到期资源收敛为 EXPIRED，同时收敛其活动传输为 EXPIRED。

        资源在传输进行中到期时同样过期；READY 资源过期后不允许被新版本引用，
        已引用它的历史运行按运行快照不受影响。
        :return: {scanned, expired, transfers} 摘要。
        """
        now = datetime.now()
        rows = ResourceDao.list_expired_resources(db, limit=limit)
        expired = 0
        transfers = 0
        for resource in rows:
            ResourceDao.update_resource(
                db,
                resource.resource_id,
                {
                    "status": "EXPIRED",
                    "error_code": "RESOURCE_EXPIRED",
                    "error_message": "资源已超过保留期",
                    "last_audit_at": now,
                    "audit_message": "过期清理任务收敛",
                    "update_by": "system",
                },
            )
            expired += 1
            transfer = ResourceTransferDao.get_active_by_resource(db, resource.resource_id)
            if transfer:
                ResourceTransferDao.update_transfer(
                    db,
                    transfer.transfer_id,
                    {
                        "status": "EXPIRED",
                        "error_code": "TRANSFER_EXPIRED",
                        "error_message": "资源已超过保留期，传输终止",
                        "last_audit_at": now,
                        "audit_message": "资源过期联动收敛",
                        "update_by": "system",
                    },
                )
                transfers += 1
        if expired:
            db.commit()
            logger.info(f"配置任务资源过期清理完成: expired={expired}, transfers={transfers}")
        return {"scanned": len(rows), "expired": expired, "transfers": transfers}

    @classmethod
    def cleanup_expired_transfers(cls, db: Session, limit: int = 200) -> dict[str, int]:
        """把超过 TTL 的活动传输收敛为 EXPIRED，并联动资源进入 FAILED。

        与 begin/chunk/commit 内的即时过期检查互补：覆盖没有再被访问、
        不会触发状态机的静默传输。
        :return: {scanned, expired, resources} 摘要。
        """
        now = datetime.now()
        rows = ResourceTransferDao.list_expired_active_transfers(db, limit=limit)
        expired = 0
        resources = 0
        for transfer in rows:
            ResourceTransferDao.update_transfer(
                db,
                transfer.transfer_id,
                {
                    "status": "EXPIRED",
                    "error_code": "TRANSFER_EXPIRED",
                    "error_message": "资源传输已超时",
                    "last_audit_at": now,
                    "audit_message": "传输过期清理任务收敛",
                    "update_by": "system",
                },
            )
            expired += 1
            resource = ResourceDao.get_resource(db, transfer.resource_id)
            if resource and resource.status in {"PENDING", "UPLOADING"}:
                ResourceDao.update_resource(
                    db,
                    resource.resource_id,
                    {
                        "status": "FAILED",
                        "error_code": "TRANSFER_EXPIRED",
                        "error_message": "资源传输已超时",
                        "last_audit_at": now,
                        "audit_message": "传输过期联动收敛",
                        "update_by": "system",
                    },
                )
                resources += 1
        if expired:
            db.commit()
            logger.info(f"配置任务传输过期清理完成: expired={expired}, resources={resources}")
        return {"scanned": len(rows), "expired": expired, "resources": resources}

    @classmethod
    def recover_orphan_runs(cls, db: Session, timeout_minutes: int = 60) -> dict[str, int]:
        """收敛超时无进展的 RUNNING 孤儿运行，委托运行服务实现。"""
        from modules.configuration_task.service.task_run_service import ConfigurationTaskRunService

        return ConfigurationTaskRunService.recover_orphan_running(db, timeout_minutes=timeout_minutes)
