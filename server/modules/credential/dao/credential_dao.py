from datetime import datetime

from sqlalchemy.orm import Session

from modules.credential.entity.do.credential_do import AuthCredential, AuthCredentialAuthConfig, AuthCredentialBinding, AuthCredentialLease, AuthCredentialOperationLog


class CredentialDao:
    """凭证管理数据访问层，只承担 ORM 查询与持久化。"""

    @classmethod
    def get_credential(cls, db: Session, credential_id: int):
        return db.query(AuthCredential).filter(AuthCredential.credential_id == credential_id, AuthCredential.del_flag == "0").first()

    @classmethod
    def list_credentials(cls, db: Session, keyword: str = "", enabled: bool | None = None):
        query = db.query(AuthCredential).filter(AuthCredential.del_flag == "0")
        if keyword:
            query = query.filter(AuthCredential.credential_name.like(f"%{keyword}%"))
        if enabled is not None:
            query = query.filter(AuthCredential.enabled == enabled)
        return query.order_by(AuthCredential.credential_id.desc()).all()

    @classmethod
    def add_credential(cls, db: Session, values: dict) -> AuthCredential:
        row = AuthCredential(**values)
        db.add(row)
        db.flush()
        return row

    @classmethod
    def update_credential(cls, db: Session, credential_id: int, values: dict, expected_revision: int | None = None) -> bool:
        query = db.query(AuthCredential).filter(AuthCredential.credential_id == credential_id, AuthCredential.del_flag == "0")
        if expected_revision is not None:
            query = query.filter(AuthCredential.revision == expected_revision)
        return query.update(values) == 1

    @classmethod
    def get_auth_config(cls, db: Session, credential_id: int):
        return db.query(AuthCredentialAuthConfig).filter(AuthCredentialAuthConfig.credential_id == credential_id).first()

    @classmethod
    def save_auth_config(cls, db: Session, credential_id: int, values: dict) -> None:
        row = cls.get_auth_config(db, credential_id)
        if row:
            db.query(AuthCredentialAuthConfig).filter(AuthCredentialAuthConfig.auth_config_id == row.auth_config_id).update({**values, "update_time": datetime.now()})
        else:
            db.add(AuthCredentialAuthConfig(credential_id=credential_id, **values))

    @classmethod
    def get_binding(cls, db: Session, binding_id: int):
        return db.query(AuthCredentialBinding).filter(AuthCredentialBinding.binding_id == binding_id, AuthCredentialBinding.del_flag == "0").first()

    @classmethod
    def list_bindings(cls, db: Session, business_type: str | None = None):
        query = db.query(AuthCredentialBinding).filter(AuthCredentialBinding.del_flag == "0")
        if business_type:
            query = query.filter(AuthCredentialBinding.business_type == business_type)
        return query.order_by(AuthCredentialBinding.binding_id.desc()).all()

    @classmethod
    def add_binding(cls, db: Session, values: dict) -> AuthCredentialBinding:
        row = AuthCredentialBinding(**values)
        db.add(row)
        db.flush()
        return row

    @classmethod
    def update_binding(cls, db: Session, binding_id: int, values: dict) -> bool:
        return db.query(AuthCredentialBinding).filter(AuthCredentialBinding.binding_id == binding_id, AuthCredentialBinding.del_flag == "0").update(values) == 1

    @classmethod
    def add_operation_log(cls, db: Session, values: dict) -> None:
        db.add(AuthCredentialOperationLog(**values))

    @classmethod
    def list_operation_logs(cls, db: Session, credential_id: int | None = None, limit: int = 100):
        """查询脱敏审计日志，DAO 不返回凭证明文。"""
        query = db.query(AuthCredentialOperationLog)
        if credential_id is not None:
            query = query.filter(AuthCredentialOperationLog.credential_id == credential_id)
        return query.order_by(AuthCredentialOperationLog.create_time.desc(), AuthCredentialOperationLog.operation_id.desc()).limit(limit).all()

    @classmethod
    def list_active_leases(cls, db: Session, credential_id: int | None = None):
        """查询当前未过期租约。"""
        query = db.query(AuthCredentialLease).filter(AuthCredentialLease.expires_at > datetime.now())
        if credential_id is not None:
            query = query.filter(AuthCredentialLease.credential_id == credential_id)
        return query.order_by(AuthCredentialLease.expires_at.asc()).all()
