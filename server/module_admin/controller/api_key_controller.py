from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from config.get_db import get_db
from module_admin.annotation.log_annotation import log_decorator
from module_admin.aspect.interface_auth import CheckUserInterfaceAuth
from module_admin.entity.vo.api_key_vo import ApiKeyPageQueryModel, CreateApiKeyModel, ViewApiKeyModel
from module_admin.service.api_key_service import ApiKeyService
from module_admin.service.login_service import CurrentUserModel, LoginService
from utils.log_util import logger
from utils.page_util import PageResponseModel
from utils.response_util import ResponseUtil

apiKeyController = APIRouter(prefix="/system/apikey", dependencies=[Depends(LoginService.get_current_user)])


def _check_api_key_manage_access(current_user: CurrentUserModel):
    """
    校验当前鉴权方式是否允许管理API Key
    :param current_user: 当前登录用户对象
    :return: 不允许时返回禁止访问响应，允许时返回None
    """
    if current_user.auth_type == "api_key":
        logger.warning("API Key鉴权不支持管理API Key")
        return ResponseUtil.forbidden(msg="API Key鉴权不支持管理API Key")
    return None


@apiKeyController.get(
    "/list",
    response_model=PageResponseModel,
    dependencies=[Depends(CheckUserInterfaceAuth("system:apikey:list"))],
)
async def get_api_key_list(
    request: Request,
    api_key_page_query: ApiKeyPageQueryModel = Depends(ApiKeyPageQueryModel.as_query),
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """
    获取当前登录用户的API Key分页列表
    :param request: Request对象
    :param api_key_page_query: API Key分页查询对象
    :param query_db: orm对象
    :param current_user: 当前登录用户对象
    :return: 当前用户API Key分页列表
    """
    deny_response = _check_api_key_manage_access(current_user)
    if deny_response:
        return deny_response

    try:
        api_key_list = ApiKeyService.get_api_key_list_services(query_db, current_user, api_key_page_query)
        logger.info("获取成功")
        return ResponseUtil.success(model_content=api_key_list)
    except Exception as exc:
        logger.exception(exc)
        return ResponseUtil.error(msg=str(exc))


@apiKeyController.get(
    "/permissionOptions",
    dependencies=[Depends(CheckUserInterfaceAuth("system:apikey:list"))],
)
async def get_api_key_permission_options(
    request: Request,
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """
    获取当前登录用户可分配给API Key的权限选项
    :param request: Request对象
    :param current_user: 当前登录用户对象
    :return: 当前用户可授权的权限选项列表
    """
    deny_response = _check_api_key_manage_access(current_user)
    if deny_response:
        return deny_response

    try:
        permission_options = ApiKeyService.get_api_key_permission_options_services(current_user)
        logger.info("获取成功")
        return ResponseUtil.success(data=permission_options)
    except Exception as exc:
        logger.exception(exc)
        return ResponseUtil.error(msg=str(exc))


@apiKeyController.post("", dependencies=[Depends(CheckUserInterfaceAuth("system:apikey:add"))])
async def add_api_key(
    request: Request,
    add_api_key_model: CreateApiKeyModel,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """
    新增当前登录用户的API Key
    :param request: Request对象
    :param add_api_key_model: 新增API Key请求对象
    :param query_db: orm对象
    :param current_user: 当前登录用户对象
    :return: 新增结果，成功时返回API Key明文
    """
    deny_response = _check_api_key_manage_access(current_user)
    if deny_response:
        return deny_response

    try:
        add_result = ApiKeyService.add_api_key_services(query_db, current_user, add_api_key_model)
        if add_result.is_success:
            logger.info(add_result.message)
            return ResponseUtil.success(msg=add_result.message, data=add_result.result)
        logger.warning(add_result.message)
        return ResponseUtil.failure(msg=add_result.message)
    except Exception as exc:
        logger.exception(exc)
        return ResponseUtil.error(msg=str(exc))


@apiKeyController.get("/{api_key_id}", dependencies=[Depends(CheckUserInterfaceAuth("system:apikey:query"))])
async def get_api_key_detail(
    request: Request,
    api_key_id: int,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """
    获取当前登录用户指定API Key的详情
    :param request: Request对象
    :param api_key_id: API Key主键
    :param query_db: orm对象
    :param current_user: 当前登录用户对象
    :return: API Key详情
    """
    deny_response = _check_api_key_manage_access(current_user)
    if deny_response:
        return deny_response

    try:
        api_key_detail = ApiKeyService.get_api_key_detail_services(query_db, current_user, api_key_id)
        if not api_key_detail:
            logger.warning(f"API Key不存在，api_key_id={api_key_id}")
            return ResponseUtil.failure(msg="API Key不存在")
        logger.info(f"获取api_key_id为{api_key_id}的信息成功")
        return ResponseUtil.success(data=api_key_detail)
    except Exception as exc:
        logger.exception(exc)
        return ResponseUtil.error(msg=str(exc))


@apiKeyController.post("/{api_key_id}/view", dependencies=[Depends(CheckUserInterfaceAuth("system:apikey:view"))])
async def view_api_key(
    request: Request,
    api_key_id: int,
    view_api_key_model: ViewApiKeyModel,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """
    校验当前账号密码后查看指定API Key明文
    :param request: Request对象
    :param api_key_id: API Key主键
    :param view_api_key_model: 查看API Key请求对象
    :param query_db: orm对象
    :param current_user: 当前登录用户对象
    :return: 查看结果，成功时返回API Key明文
    """
    deny_response = _check_api_key_manage_access(current_user)
    if deny_response:
        return deny_response

    try:
        view_result = ApiKeyService.view_api_key_services(query_db, current_user, api_key_id, view_api_key_model)
        if view_result.is_success:
            logger.info(view_result.message)
            return ResponseUtil.success(msg=view_result.message, data=view_result.result)
        logger.warning(view_result.message)
        return ResponseUtil.failure(msg=view_result.message)
    except Exception as exc:
        logger.exception(exc)
        return ResponseUtil.error(msg=str(exc))


@apiKeyController.post(
    "/{api_key_id}/expire",
    dependencies=[Depends(CheckUserInterfaceAuth("system:apikey:expire"))],
)
@log_decorator(title="API Key管理", business_type=2)
async def expire_api_key(
    request: Request,
    api_key_id: int,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """
    手动过期当前登录用户指定的API Key
    :param request: Request对象
    :param api_key_id: API Key主键
    :param query_db: orm对象
    :param current_user: 当前登录用户对象
    :return: 手动过期结果
    """
    deny_response = _check_api_key_manage_access(current_user)
    if deny_response:
        return deny_response

    try:
        expire_result = ApiKeyService.expire_api_key_services(query_db, current_user, api_key_id)
        if expire_result.is_success:
            logger.info(expire_result.message)
            return ResponseUtil.success(msg=expire_result.message)
        logger.warning(expire_result.message)
        return ResponseUtil.failure(msg=expire_result.message)
    except Exception as exc:
        logger.exception(exc)
        return ResponseUtil.error(msg=str(exc))


@apiKeyController.delete("/{api_key_id}", dependencies=[Depends(CheckUserInterfaceAuth("system:apikey:remove"))])
@log_decorator(title="API Key管理", business_type=3)
async def delete_api_key(
    request: Request,
    api_key_id: int,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """
    删除当前登录用户指定的API Key
    :param request: Request对象
    :param api_key_id: API Key主键
    :param query_db: orm对象
    :param current_user: 当前登录用户对象
    :return: 删除结果
    """
    deny_response = _check_api_key_manage_access(current_user)
    if deny_response:
        return deny_response

    try:
        delete_result = ApiKeyService.delete_api_key_services(query_db, current_user, api_key_id)
        if delete_result.is_success:
            logger.info(delete_result.message)
            return ResponseUtil.success(msg=delete_result.message)
        logger.warning(delete_result.message)
        return ResponseUtil.failure(msg=delete_result.message)
    except Exception as exc:
        logger.exception(exc)
        return ResponseUtil.error(msg=str(exc))
