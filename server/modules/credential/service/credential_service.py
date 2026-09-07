from datetime import datetime

from sqlalchemy.orm import Session

from module_admin.entity.vo.common_vo import CrudResponseModel
from module_admin.entity.vo.user_vo import CurrentUserModel
from modules.credential.dao.credential_dao import CredentialDao
from modules.credential.entity.vo.credential_vo import (
    CredentialAuthConfigModel,
    CredentialModel,
    CredentialSaveModel,
    CredentialUpdateModel,
)
from modules.credential.util.credential_secret_util import decrypt_secret, encrypt_secret, mask_secret
from utils.log_util import logger


class CredentialService:
    """凭证聚合根服务，负责密文快照、版本控制和安全审计。"""

    @classmethod
    def get_credential_secret(cls, db: Session, credential_id: int) -> dict | None:
        """获取解密后的凭证明文，仅用于编辑回显。调用方需自行控制权限。"""
        row = CredentialDao.get_credential(db, credential_id)
        if not row or not row.secret_cipher_text:
            return None
        try:
            return decrypt_secret(row.secret_cipher_text)
        except Exception:
            logger.warning(f"解密凭证失败，credential_id={credential_id}")
            return None

    @classmethod
    def list_credentials(cls, db: Session, keyword: str, enabled: bool | None) -> list[CredentialModel]:
        """获取不含明文的凭证列表。"""
        return [cls.to_model(db, row) for row in CredentialDao.list_credentials(db, keyword, enabled)]

    @classmethod
    def get_credential(cls, db: Session, credential_id: int) -> CredentialModel | None:
        """获取不含明文的凭证详情。"""
        row = CredentialDao.get_credential(db, credential_id)
        return cls.to_model(db, row) if row else None

    @classmethod
    def create_credential(cls, db: Session, model: CredentialSaveModel, current_user: CurrentUserModel) -> CrudResponseModel:
        """创建凭证和认证配置，凭证明文仅在本次请求内存在。"""
        now = datetime.now()
        user_name = current_user.user.user_name
        try:
            row = CredentialDao.add_credential(
                db,
                {
                    "credential_name": model.credential_name.strip(),
                    "credential_type": model.credential_type,
                    "auth_mode": model.auth_mode,
                    "enabled": model.enabled,
                    "auto_refresh_enabled": model.auto_refresh_enabled,
                    "refresh_interval_sec": model.refresh_interval_sec,
                    "sharing_mode": model.sharing_mode,
                    "secret_cipher_text": encrypt_secret(model.secret),
                    "secret_mask": mask_secret(model.secret),
                    "expire_time": model.expire_time,
                    "create_by": user_name,
                    "create_time": now,
                    "update_by": user_name,
                    "update_time": now,
                    "remark": model.remark,
                },
            )
            CredentialDao.save_auth_config(db, row.credential_id, model.auth_config.model_dump(by_alias=False))
            CredentialDao.add_operation_log(db, {"credential_id": row.credential_id, "operation_type": "create", "status": "success", "revision": 1, "message": "已创建凭证", "operator": user_name})
            db.commit()
            logger.info(f"已创建统一凭证，credential_id={row.credential_id}，credential_name={row.credential_name}")
            return CrudResponseModel(is_success=True, message="新增成功", result={"credentialId": str(row.credential_id)})
        except Exception:
            db.rollback()
            raise

    @classmethod
    def update_credential(cls, db: Session, credential_id: int, model: CredentialUpdateModel, current_user: CurrentUserModel) -> CrudResponseModel:
        """乐观锁更新凭证；冲突不会覆盖刷新后的有效凭证。"""
        current = CredentialDao.get_credential(db, credential_id)
        if not current:
            return CrudResponseModel(is_success=False, message="凭证不存在")
        now = datetime.now()
        values = model.model_dump(exclude={"expected_revision", "secret", "auth_config"}, by_alias=False)
        values.update({
            "credential_name": model.credential_name.strip(),
            "revision": model.expected_revision + 1,
            "update_by": current_user.user.user_name,
            "update_time": now,
        })
        # 详情接口不会返回密文，编辑普通字段时必须保留原快照，避免空 JSON 覆盖有效凭证。
        # 但凭证类型变化时，旧类型的主凭证不能继续被刷新请求携带。
        if model.secret or current.credential_type != model.credential_type:
            merged_secret = decrypt_secret(current.secret_cipher_text)
            if current.credential_type != model.credential_type:
                cls._clear_primary_secret_fields(merged_secret)
            # 编辑页已回填明文，显式传空串的字段表示用户清空了该敏感项，合并前删除而不是保留旧值。
            cls._drop_empty_secret_fields(model.secret)
            merged_secret.update(model.secret)
            values["secret_cipher_text"] = encrypt_secret(merged_secret)
            values["secret_mask"] = mask_secret(merged_secret)
        try:
            updated = CredentialDao.update_credential(db, credential_id, values, model.expected_revision)
            if not updated:
                CredentialDao.add_operation_log(db, {"credential_id": credential_id, "operation_type": "update_conflict", "status": "conflict", "revision": model.expected_revision, "message": "凭证已被其他刷新或编辑操作更新", "operator": current_user.user.user_name})
                db.commit()
                return CrudResponseModel(is_success=False, message="凭证版本冲突，请刷新页面后重试")
            CredentialDao.save_auth_config(db, credential_id, model.auth_config.model_dump(by_alias=False))
            CredentialDao.add_operation_log(db, {"credential_id": credential_id, "operation_type": "update", "status": "success", "revision": model.expected_revision + 1, "message": "已更新凭证", "operator": current_user.user.user_name})
            db.commit()
            return CrudResponseModel(is_success=True, message="修改成功")
        except Exception:
            db.rollback()
            raise

    @staticmethod
    def _drop_empty_secret_fields(secret: dict) -> None:
        """更新时剔除显式传空串的主字段，使"清空输入框保存"等价于删除该敏感字段。

        仅处理顶层字符串键；headers/cookies 等对象字段由编辑页整体覆盖，不走该逻辑。
        """
        for key in [key for key, value in secret.items() if value == ""]:
            secret.pop(key, None)

    @staticmethod
    def _clear_primary_secret_fields(secret: dict) -> None:
        """切换凭证类型时删除旧类型主字段，保留附加 Header、Cookie 和登录账号等共享字段。"""
        primary_fields = {
            "cookie",
            "cookieHeader",
            "headerName",
            "header_name",
            "headerValue",
            "header_value",
            "valuePrefix",
            "value_prefix",
            "token",
            "apiKey",
            "storageState",
            "storage_state",
        }
        for field in primary_fields:
            secret.pop(field, None)

    @classmethod
    def delete_credential(cls, db: Session, credential_id: int, current_user: CurrentUserModel) -> CrudResponseModel:
        """逻辑删除凭证，已绑定业务在下次解析时会明确失败，避免静默降级。"""
        row = CredentialDao.get_credential(db, credential_id)
        if not row:
            return CrudResponseModel(is_success=False, message="凭证不存在")
        try:
            CredentialDao.update_credential(db, credential_id, {"del_flag": "2", "update_by": current_user.user.user_name, "update_time": datetime.now()})
            CredentialDao.add_operation_log(db, {"credential_id": credential_id, "operation_type": "delete", "status": "success", "revision": row.revision, "message": "已逻辑删除凭证", "operator": current_user.user.user_name})
            db.commit()
            return CrudResponseModel(is_success=True, message="删除成功")
        except Exception:
            db.rollback()
            raise

    @classmethod
    def to_model(cls, db: Session, row) -> CredentialModel:
        """将 ORM 凭证转换为安全响应模型。"""
        config = CredentialDao.get_auth_config(db, row.credential_id)
        auth_config = CredentialAuthConfigModel.model_validate(config) if config else CredentialAuthConfigModel()
        auth_config_data = auth_config.model_dump(by_alias=False)
        for key in ("request_template", "login_request_template", "refresh_request_template"):
            auth_config_data[key] = cls._redact_config_value(auth_config_data.get(key) or {})
        auth_config = CredentialAuthConfigModel.model_validate(auth_config_data)
        return CredentialModel(
            credentialId=str(row.credential_id), credentialName=row.credential_name, credentialType=row.credential_type,
            authMode=row.auth_mode, enabled=row.enabled, autoRefreshEnabled=row.auto_refresh_enabled,
            refreshIntervalSec=row.refresh_interval_sec, sharingMode=row.sharing_mode, secretMask=row.secret_mask,
            revision=row.revision, expireTime=row.expire_time, lastRefreshTime=row.last_refresh_time,
            lastRefreshStatus=row.last_refresh_status, lastRefreshMessage=row.last_refresh_message,
            authConfig=auth_config, remark=row.remark, createBy=row.create_by, createTime=row.create_time,
            updateBy=row.update_by, updateTime=row.update_time,
        )

    @staticmethod
    def _redact_config_value(value):
        """隐藏请求模板中的常见敏感字段，防止编辑详情接口泄露固定密码或密钥。"""
        sensitive_names = {"password", "passwd", "secret", "token", "authorization", "cookie", "api_key", "apikey"}
        if isinstance(value, dict):
            return {
                key: "******" if str(key).lower().replace("-", "_") in sensitive_names else CredentialService._redact_config_value(item)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [CredentialService._redact_config_value(item) for item in value]
        return value
