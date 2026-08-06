from datetime import datetime

from sqlalchemy.orm import Session

from module_admin.entity.vo.common_vo import CrudResponseModel
from module_admin.entity.vo.user_vo import CurrentUserModel
from modules.credential.dao.credential_dao import CredentialDao
from modules.credential.entity.vo.credential_vo import CredentialBindingModel, CredentialBindingSaveModel, CredentialOptionModel


class CredentialBindingService:
    """业务凭证绑定服务，业务侧只保存 binding_id，不保存凭证内容。"""

    @classmethod
    def list_bindings(cls, db: Session, business_type: str | None = None) -> list[CredentialBindingModel]:
        """获取绑定清单及其对应凭证的非敏感摘要。"""
        return [cls.to_model(db, row) for row in CredentialDao.list_bindings(db, business_type)]

    @classmethod
    def list_options(cls, db: Session, business_type: str) -> list[CredentialOptionModel]:
        """返回业务配置可选择的已启用绑定。"""
        result = []
        for binding in CredentialDao.list_bindings(db, business_type):
            credential = CredentialDao.get_credential(db, binding.credential_id)
            if credential and credential.enabled and binding.enabled:
                result.append(CredentialOptionModel(bindingId=str(binding.binding_id), bindingName=binding.binding_name, credentialName=credential.credential_name, credentialType=credential.credential_type, projectionType=binding.projection_type, businessType=binding.business_type))
        return result

    @classmethod
    def create_binding(cls, db: Session, model: CredentialBindingSaveModel, current_user: CurrentUserModel) -> CrudResponseModel:
        """创建绑定并校验被引用凭证存在。"""
        credential_id = int(model.credential_id)
        credential = CredentialDao.get_credential(db, credential_id)
        if not credential:
            return CrudResponseModel(is_success=False, message="绑定的凭证不存在")
        validation_error = cls.validate_binding(model, credential)
        if validation_error:
            return CrudResponseModel(is_success=False, message=validation_error)
        now = datetime.now()
        try:
            row = CredentialDao.add_binding(db, {**model.model_dump(by_alias=False, exclude={"credential_id"}), "credential_id": credential_id, "create_by": current_user.user.user_name, "create_time": now, "update_by": current_user.user.user_name, "update_time": now})
            db.commit()
            return CrudResponseModel(is_success=True, message="新增成功", result={"bindingId": str(row.binding_id)})
        except Exception:
            db.rollback()
            raise

    @classmethod
    def update_binding(cls, db: Session, binding_id: int, model: CredentialBindingSaveModel, current_user: CurrentUserModel) -> CrudResponseModel:
        """更新业务绑定。"""
        credential = CredentialDao.get_credential(db, int(model.credential_id))
        if not credential:
            return CrudResponseModel(is_success=False, message="绑定的凭证不存在")
        validation_error = cls.validate_binding(model, credential)
        if validation_error:
            return CrudResponseModel(is_success=False, message=validation_error)
        try:
            updated = CredentialDao.update_binding(db, binding_id, {**model.model_dump(by_alias=False, exclude={"credential_id"}), "credential_id": int(model.credential_id), "update_by": current_user.user.user_name, "update_time": datetime.now()})
            if not updated:
                return CrudResponseModel(is_success=False, message="凭证绑定不存在")
            db.commit()
            return CrudResponseModel(is_success=True, message="修改成功")
        except Exception:
            db.rollback()
            raise

    @classmethod
    def delete_binding(cls, db: Session, binding_id: int, current_user: CurrentUserModel) -> CrudResponseModel:
        """逻辑删除业务绑定。"""
        try:
            updated = CredentialDao.update_binding(db, binding_id, {"del_flag": "2", "update_by": current_user.user.user_name, "update_time": datetime.now()})
            if not updated:
                return CrudResponseModel(is_success=False, message="凭证绑定不存在")
            db.commit()
            return CrudResponseModel(is_success=True, message="删除成功")
        except Exception:
            db.rollback()
            raise

    @classmethod
    def to_model(cls, db: Session, binding) -> CredentialBindingModel:
        """组合绑定和凭证非敏感摘要。"""
        credential = CredentialDao.get_credential(db, binding.credential_id)
        return CredentialBindingModel(bindingId=str(binding.binding_id), bindingName=binding.binding_name, credentialId=str(binding.credential_id), businessType=binding.business_type, projectionType=binding.projection_type, targetUrl=binding.target_url, targetHostPatterns=binding.target_host_patterns or [], sharingMode=binding.sharing_mode, writebackEnabled=binding.writeback_enabled, enabled=binding.enabled, remark=binding.remark, credentialName=credential.credential_name if credential else "已删除凭证", credentialType=credential.credential_type if credential else "", createTime=binding.create_time, updateTime=binding.update_time)

    @staticmethod
    def validate_binding(model: CredentialBindingSaveModel, credential) -> str | None:
        """校验业务绑定的投影契约，避免运行时才发现无法投影。"""
        if model.business_type == "web_case":
            if model.projection_type != "playwright_storage":
                return "Web 用例绑定必须使用 playwright_storage 投影"
            if credential.credential_type != "browser_storage":
                return "Web 用例绑定必须引用 browser_storage 凭证"
        elif model.business_type in {"ticket_log_pull", "ticket_remote_sync"}:
            if model.projection_type not in {"http_header", "http_cookie"}:
                return "工单业务绑定必须使用 HTTP Header 或 Cookie 投影"
        if model.writeback_enabled and model.business_type != "web_case":
            return "只有 Web 用例绑定允许回写凭证"
        if model.writeback_enabled and model.sharing_mode == "shared_read":
            return "允许回写的绑定不能使用 shared_read 并发策略"
        return None
