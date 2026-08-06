from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from modules.credential.dao.credential_dao import CredentialDao
from modules.credential.entity.vo.credential_vo import CredentialWritebackModel
from modules.credential.util.credential_secret_util import decrypt_secret, encrypt_secret, mask_secret


class CredentialWritebackService:
    """浏览器状态回写服务，默认不参与普通 Web 执行。"""

    @classmethod
    def writeback_storage_state(
        cls,
        db: Session,
        binding_id: int,
        model: CredentialWritebackModel,
        operator: str,
    ) -> dict[str, Any]:
        """按绑定和版本安全写回最终 storageState，冲突时保留服务端较新版本。"""
        binding = CredentialDao.get_binding(db, binding_id)
        if not binding or not binding.enabled:
            return {"success": False, "message": "凭证绑定不存在或未启用", "status": "not_found"}
        if binding.business_type != "web_case" or binding.projection_type != "playwright_storage":
            return {"success": False, "message": "当前绑定不允许写回浏览器状态", "status": "invalid_binding"}
        if not binding.writeback_enabled:
            return {"success": False, "message": "当前绑定未开启凭证回写", "status": "writeback_disabled"}
        if not model.local_cache_enabled:
            return {"success": False, "message": "仅在启用本地浏览器状态缓存时允许回写", "status": "local_cache_required"}
        if not cls.is_valid_storage_state(model.storage_state):
            return {"success": False, "message": "浏览器状态不完整，未写回凭证", "status": "invalid_state"}

        credential = CredentialDao.get_credential(db, binding.credential_id)
        if not credential or not credential.enabled:
            return {"success": False, "message": "绑定的凭证不存在或未启用", "status": "not_found"}
        if credential.credential_type != "browser_storage":
            return {"success": False, "message": "只有浏览器状态凭证允许回写", "status": "invalid_credential"}
        if credential.revision != model.expected_revision:
            cls.add_log(db, credential.credential_id, binding_id, "writeback", "conflict", model.expected_revision, "浏览器状态回写版本冲突", operator)
            db.commit()
            return {"success": False, "message": "凭证版本冲突，服务端保留较新状态", "status": "conflict"}

        secret = decrypt_secret(credential.secret_cipher_text)
        next_secret = {**secret, "storageState": model.storage_state}
        now = datetime.now()
        updated = CredentialDao.update_credential(
            db,
            credential.credential_id,
            {
                "secret_cipher_text": encrypt_secret(next_secret),
                "secret_mask": mask_secret(next_secret),
                "revision": credential.revision + 1,
                "update_by": operator,
                "update_time": now,
            },
            model.expected_revision,
        )
        if not updated:
            cls.add_log(db, credential.credential_id, binding_id, "writeback", "conflict", model.expected_revision, "浏览器状态回写版本冲突", operator)
            db.commit()
            return {"success": False, "message": "凭证版本冲突，服务端保留较新状态", "status": "conflict"}
        cls.add_log(db, credential.credential_id, binding_id, "writeback", "success", credential.revision + 1, "浏览器状态已安全回写", operator)
        db.commit()
        return {"success": True, "message": "浏览器状态已回写", "status": "success", "revision": credential.revision + 1}

    @staticmethod
    def is_valid_storage_state(storage_state: dict[str, Any]) -> bool:
        """校验 Playwright storageState 基础结构，拒绝空状态覆盖有效凭证。"""
        if not isinstance(storage_state, dict):
            return False
        cookies = storage_state.get("cookies")
        origins = storage_state.get("origins")
        if not isinstance(cookies, list) or not isinstance(origins, list):
            return False
        return bool(cookies or origins)

    @staticmethod
    def add_log(
        db: Session,
        credential_id: int,
        binding_id: int,
        operation_type: str,
        status: str,
        revision: int,
        message: str,
        operator: str,
    ) -> None:
        """记录不含敏感值的浏览器状态回写审计日志。"""
        CredentialDao.add_operation_log(
            db,
            {
                "credential_id": credential_id,
                "binding_id": binding_id,
                "operation_type": operation_type,
                "status": status,
                "revision": revision,
                "message": message,
                "operator": operator,
            },
        )
