from fastapi import APIRouter, Depends, Request
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from config.get_db import get_db
from module_admin.annotation.log_annotation import log_decorator
from module_admin.aspect.interface_auth import CheckUserInterfaceAuth
from module_admin.entity.vo.user_vo import CurrentUserModel
from module_admin.service.login_service import LoginService
from modules.credential.entity.vo.credential_vo import CredentialBindingOptionQueryModel, CredentialBindingQueryModel, CredentialBindingSaveModel, CredentialOperationLogQueryModel, CredentialQueryModel, CredentialRefreshRequestModel, CredentialSaveModel, CredentialUpdateModel, CredentialWritebackModel
from modules.credential.service.credential_binding_service import CredentialBindingService
from modules.credential.service.credential_audit_service import CredentialAuditService
from modules.credential.service.credential_refresh_service import CredentialRefreshService
from modules.credential.service.credential_service import CredentialService
from modules.credential.service.credential_writeback_service import CredentialWritebackService
from utils.response_util import ResponseUtil


credentialController = APIRouter(prefix="/system/credentials", dependencies=[Depends(LoginService.get_current_user)])


@credentialController.get("/operation-logs", dependencies=[Depends(CheckUserInterfaceAuth("system:credential:query"))])
async def list_credential_operation_logs(request: Request, query: CredentialOperationLogQueryModel = Depends(CredentialOperationLogQueryModel.as_query), query_db: Session = Depends(get_db)):
    """查询凭证操作审计摘要。"""
    return ResponseUtil.success(data=await run_in_threadpool(CredentialAuditService.list_operation_logs, query_db, query.credential_id, query.limit))


@credentialController.get("/leases", dependencies=[Depends(CheckUserInterfaceAuth("system:credential:query"))])
async def list_credential_leases(request: Request, query: CredentialOperationLogQueryModel = Depends(CredentialOperationLogQueryModel.as_query), query_db: Session = Depends(get_db)):
    """查询当前有效凭证租约摘要。"""
    return ResponseUtil.success(data=await run_in_threadpool(CredentialAuditService.list_active_leases, query_db, query.credential_id))


@credentialController.get("", dependencies=[Depends(CheckUserInterfaceAuth("system:credential:list"))])
async def list_credentials(request: Request, query: CredentialQueryModel = Depends(CredentialQueryModel.as_query), query_db: Session = Depends(get_db)):
    """获取统一凭证列表，返回值不包含任何明文或密文。"""
    return ResponseUtil.success(data=await run_in_threadpool(CredentialService.list_credentials, query_db, query.keyword, query.enabled))


@credentialController.get("/bindings", dependencies=[Depends(CheckUserInterfaceAuth("system:credential:list"))])
async def list_bindings(request: Request, query: CredentialBindingQueryModel = Depends(CredentialBindingQueryModel.as_query), query_db: Session = Depends(get_db)):
    """获取凭证绑定列表。"""
    return ResponseUtil.success(data=await run_in_threadpool(CredentialBindingService.list_bindings, query_db, query.business_type))


@credentialController.get("/binding-options", dependencies=[Depends(CheckUserInterfaceAuth("system:credential:list"))])
async def list_binding_options(request: Request, query: CredentialBindingOptionQueryModel = Depends(CredentialBindingOptionQueryModel.as_query), query_db: Session = Depends(get_db)):
    """获取业务配置可选择的凭证绑定。"""
    return ResponseUtil.success(data=await run_in_threadpool(CredentialBindingService.list_options, query_db, query.business_type))


@credentialController.get("/{credential_id}", dependencies=[Depends(CheckUserInterfaceAuth("system:credential:query"))])
async def get_credential(request: Request, credential_id: int, query_db: Session = Depends(get_db)):
    """获取指定凭证的脱敏详情。"""
    result = await run_in_threadpool(CredentialService.get_credential, query_db, credential_id)
    return ResponseUtil.success(data=result) if result else ResponseUtil.failure(msg="凭证不存在")
@credentialController.get("/{credential_id}/secret", dependencies=[Depends(CheckUserInterfaceAuth("system:credential:edit"))])
async def get_credential_secret(request: Request, credential_id: int, query_db: Session = Depends(get_db)):
    """获取指定凭证的解密后明文内容，用于编辑时回显。权限等同于编辑操作。"""
    result = await run_in_threadpool(CredentialService.get_credential_secret, query_db, credential_id)
    return ResponseUtil.success(data=result) if result else ResponseUtil.failure(msg="凭证不存在")



@credentialController.post("", dependencies=[Depends(CheckUserInterfaceAuth("system:credential:add"))])
@log_decorator(title="统一凭证管理", business_type=1)
async def create_credential(request: Request, model: CredentialSaveModel, query_db: Session = Depends(get_db), current_user: CurrentUserModel = Depends(LoginService.get_current_user)):
    """新增统一凭证。"""
    result = await run_in_threadpool(CredentialService.create_credential, query_db, model, current_user)
    return ResponseUtil.success(msg=result.message, data=result.result) if result.is_success else ResponseUtil.failure(msg=result.message)


@credentialController.put("/{credential_id}", dependencies=[Depends(CheckUserInterfaceAuth("system:credential:edit"))])
@log_decorator(title="统一凭证管理", business_type=2)
async def update_credential(request: Request, credential_id: int, model: CredentialUpdateModel, query_db: Session = Depends(get_db), current_user: CurrentUserModel = Depends(LoginService.get_current_user)):
    """更新统一凭证。"""
    result = await run_in_threadpool(CredentialService.update_credential, query_db, credential_id, model, current_user)
    return ResponseUtil.success(msg=result.message) if result.is_success else ResponseUtil.failure(msg=result.message)


@credentialController.delete("/{credential_id}", dependencies=[Depends(CheckUserInterfaceAuth("system:credential:remove"))])
@log_decorator(title="统一凭证管理", business_type=3)
async def delete_credential(request: Request, credential_id: int, query_db: Session = Depends(get_db), current_user: CurrentUserModel = Depends(LoginService.get_current_user)):
    """删除统一凭证。"""
    result = await run_in_threadpool(CredentialService.delete_credential, query_db, credential_id, current_user)
    return ResponseUtil.success(msg=result.message) if result.is_success else ResponseUtil.failure(msg=result.message)


@credentialController.post("/{credential_id}/refresh", dependencies=[Depends(CheckUserInterfaceAuth("system:credential:refresh"))])
@log_decorator(title="统一凭证刷新", business_type=2)
async def refresh_credential(request: Request, credential_id: int, model: CredentialRefreshRequestModel, query_db: Session = Depends(get_db), current_user: CurrentUserModel = Depends(LoginService.get_current_user)):
    """手工触发 HTTP 凭证刷新。"""
    result = await run_in_threadpool(
        CredentialRefreshService.refresh_credential,
        query_db,
        credential_id,
        model.expected_revision,
        current_user.user.user_name,
        model.otp_code,
    )
    return ResponseUtil.success(msg=result["message"], data=result) if result["success"] else ResponseUtil.failure(msg=result["message"], data=result)


@credentialController.post("/bindings", dependencies=[Depends(CheckUserInterfaceAuth("system:credential:add"))])
@log_decorator(title="统一凭证绑定", business_type=1)
async def create_binding(request: Request, model: CredentialBindingSaveModel, query_db: Session = Depends(get_db), current_user: CurrentUserModel = Depends(LoginService.get_current_user)):
    """新增业务凭证绑定。"""
    result = await run_in_threadpool(CredentialBindingService.create_binding, query_db, model, current_user)
    return ResponseUtil.success(msg=result.message, data=result.result) if result.is_success else ResponseUtil.failure(msg=result.message)


@credentialController.put("/bindings/{binding_id}", dependencies=[Depends(CheckUserInterfaceAuth("system:credential:edit"))])
@log_decorator(title="统一凭证绑定", business_type=2)
async def update_binding(request: Request, binding_id: int, model: CredentialBindingSaveModel, query_db: Session = Depends(get_db), current_user: CurrentUserModel = Depends(LoginService.get_current_user)):
    """修改业务凭证绑定。"""
    result = await run_in_threadpool(CredentialBindingService.update_binding, query_db, binding_id, model, current_user)
    return ResponseUtil.success(msg=result.message) if result.is_success else ResponseUtil.failure(msg=result.message)


@credentialController.delete("/bindings/{binding_id}", dependencies=[Depends(CheckUserInterfaceAuth("system:credential:remove"))])
@log_decorator(title="统一凭证绑定", business_type=3)
async def delete_binding(request: Request, binding_id: int, query_db: Session = Depends(get_db), current_user: CurrentUserModel = Depends(LoginService.get_current_user)):
    """删除业务凭证绑定。"""
    result = await run_in_threadpool(CredentialBindingService.delete_binding, query_db, binding_id, current_user)
    return ResponseUtil.success(msg=result.message) if result.is_success else ResponseUtil.failure(msg=result.message)


@credentialController.post("/bindings/{binding_id}/writeback", dependencies=[Depends(CheckUserInterfaceAuth("system:credential:edit"))])
@log_decorator(title="统一凭证浏览器状态回写", business_type=2)
async def writeback_browser_storage_state(request: Request, binding_id: int, model: CredentialWritebackModel, query_db: Session = Depends(get_db), current_user: CurrentUserModel = Depends(LoginService.get_current_user)):
    """在显式允许且本地缓存已启用时，回写浏览器最终状态。"""
    result = await run_in_threadpool(CredentialWritebackService.writeback_storage_state, query_db, binding_id, model, current_user.user.user_name)
    return ResponseUtil.success(msg=result["message"], data=result) if result["success"] else ResponseUtil.failure(msg=result["message"], data=result)
