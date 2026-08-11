from datetime import datetime, timedelta
import secrets

from sqlalchemy.orm import Session

from modules.credential.entity.do.credential_do import AuthCredential, AuthCredentialLease


class CredentialLeaseService:
    """凭证独占租约服务，供会使旧会话失效的登录/刷新流程使用。"""

    @classmethod
    def acquire(cls, db: Session, credential_id: int, lease_type: str, holder: str, ttl_sec: int = 300) -> str:
        """获取独占租约；先锁定凭证行，保证同一凭证的获取操作串行化。"""
        now = datetime.now()
        # 锁定聚合根行而非仅检查租约记录，避免无历史租约时两个事务同时插入。
        db.query(AuthCredential).filter(AuthCredential.credential_id == credential_id).with_for_update().one_or_none()
        db.query(AuthCredentialLease).filter(AuthCredentialLease.expires_at <= now).delete()
        occupied = db.query(AuthCredentialLease).filter(AuthCredentialLease.credential_id == credential_id, AuthCredentialLease.lease_type == lease_type, AuthCredentialLease.expires_at > now).first()
        if occupied:
            raise ValueError("凭证正在被独占使用或刷新，请稍后重试")
        token = secrets.token_urlsafe(24)
        db.add(AuthCredentialLease(credential_id=credential_id, lease_token=token, lease_type=lease_type, holder=holder, expires_at=now + timedelta(seconds=max(ttl_sec, 30))))
        db.flush()
        return token

    @classmethod
    def release(cls, db: Session, lease_token: str) -> None:
        """释放已持有的独占租约。"""
        db.query(AuthCredentialLease).filter(AuthCredentialLease.lease_token == lease_token).delete()
