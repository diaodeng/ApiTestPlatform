from sqlalchemy.orm import Session

from modules.credential.dao.credential_dao import CredentialDao
from modules.credential.entity.vo.credential_vo import CredentialLeaseModel, CredentialOperationLogModel


class CredentialAuditService:
    """统一凭证审计日志和租约查询服务。"""

    @classmethod
    def list_operation_logs(cls, db: Session, credential_id: int | None, limit: int) -> list[CredentialOperationLogModel]:
        """查询不包含密文、请求体和认证值的操作日志。"""
        return [
            CredentialOperationLogModel(
                operationId=str(row.operation_id), credentialId=str(row.credential_id), bindingId=str(row.binding_id) if row.binding_id else None,
                operationType=row.operation_type, status=row.status, revision=row.revision, message=row.message,
                operator=row.operator, createTime=row.create_time,
            )
            for row in CredentialDao.list_operation_logs(db, credential_id, limit)
        ]

    @classmethod
    def list_active_leases(cls, db: Session, credential_id: int | None) -> list[CredentialLeaseModel]:
        """查询当前有效租约，只返回持有者和过期时间等运行摘要。"""
        return [
            CredentialLeaseModel(
                leaseId=str(row.lease_id), credentialId=str(row.credential_id), leaseType=row.lease_type,
                holder=row.holder, expiresAt=row.expires_at, createTime=row.create_time,
            )
            for row in CredentialDao.list_active_leases(db, credential_id)
        ]
