from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from config.get_db import get_db
from module_admin.aspect.interface_auth import CheckUserInterfaceAuth
from module_admin.entity.vo.ai_provider_vo import (
    AiProviderPageQueryModel,
    CreateAiProviderModel,
    UpdateAiProviderModel,
)
from module_admin.service.ai_provider_service import AiProviderService
from module_admin.service.login_service import CurrentUserModel, LoginService
from utils.response_util import ResponseUtil
from utils.page_util import PageResponseModel

aiProviderController = APIRouter(prefix="/system/aiprovider", dependencies=[Depends(LoginService.get_current_user)])


@aiProviderController.get(
    "/list",
    response_model=PageResponseModel,
    dependencies=[Depends(CheckUserInterfaceAuth("system:aiprovider:list"))],
)
async def get_ai_provider_list(
    request: Request,
    ai_provider_page_query: AiProviderPageQueryModel = Depends(AiProviderPageQueryModel.as_query),
    query_db: Session = Depends(get_db),
):
    """
    获取 AI Provider 分页列表。
    :param request: Request对象
    :param ai_provider_page_query: AI Provider分页查询对象
    :param query_db: orm对象
    :return: AI Provider分页列表
    """
    try:
        ai_provider_list = AiProviderService.get_ai_provider_list_services(query_db, ai_provider_page_query)
        return ResponseUtil.success(model_content=ai_provider_list)
    except Exception as exc:
        return ResponseUtil.error(msg=str(exc))


@aiProviderController.get(
    "/options",
    dependencies=[Depends(CheckUserInterfaceAuth("system:aiprovider:list"))],
)
async def get_ai_provider_options(
    request: Request,
    query_db: Session = Depends(get_db),
):
    """
    获取可用于节点选择的 AI Provider 选项。
    :param request: Request对象
    :param query_db: orm对象
    :return: Provider选项列表
    """
    try:
        provider_options = AiProviderService.get_ai_provider_options_services(query_db)
        return ResponseUtil.success(data=provider_options)
    except Exception as exc:
        return ResponseUtil.error(msg=str(exc))


@aiProviderController.get("/{provider_id}", dependencies=[Depends(CheckUserInterfaceAuth("system:aiprovider:query"))])
async def get_ai_provider_detail(
    request: Request,
    provider_id: int,
    query_db: Session = Depends(get_db),
):
    """
    获取 AI Provider 详情。
    :param request: Request对象
    :param provider_id: Provider主键
    :param query_db: orm对象
    :return: Provider详情
    """
    try:
        provider_detail = AiProviderService.get_ai_provider_detail_services(query_db, provider_id)
        if not provider_detail:
            return ResponseUtil.failure(msg="Provider不存在")
        return ResponseUtil.success(data=provider_detail)
    except Exception as exc:
        return ResponseUtil.error(msg=str(exc))


@aiProviderController.post("", dependencies=[Depends(CheckUserInterfaceAuth("system:aiprovider:add"))])
async def add_ai_provider(
    request: Request,
    add_ai_provider_model: CreateAiProviderModel,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """
    新增 AI Provider。
    :param request: Request对象
    :param add_ai_provider_model: 新增请求对象
    :param query_db: orm对象
    :param current_user: 当前登录用户对象
    :return: 新增结果
    """
    try:
        add_result = AiProviderService.add_ai_provider_services(
            query_db, add_ai_provider_model, current_user.user.user_name
        )
        if add_result.is_success:
            return ResponseUtil.success(msg=add_result.message, data=add_result.result)
        return ResponseUtil.failure(msg=add_result.message)
    except Exception as exc:
        return ResponseUtil.error(msg=str(exc))


@aiProviderController.put("", dependencies=[Depends(CheckUserInterfaceAuth("system:aiprovider:edit"))])
async def update_ai_provider(
    request: Request,
    update_ai_provider_model: UpdateAiProviderModel,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """
    编辑 AI Provider。
    :param request: Request对象
    :param update_ai_provider_model: 编辑请求对象
    :param query_db: orm对象
    :param current_user: 当前登录用户对象
    :return: 修改结果
    """
    try:
        update_result = AiProviderService.update_ai_provider_services(
            query_db, update_ai_provider_model, current_user.user.user_name
        )
        if update_result.is_success:
            return ResponseUtil.success(msg=update_result.message, data=update_result.result)
        return ResponseUtil.failure(msg=update_result.message)
    except Exception as exc:
        return ResponseUtil.error(msg=str(exc))


@aiProviderController.delete("/{provider_id}", dependencies=[Depends(CheckUserInterfaceAuth("system:aiprovider:remove"))])
async def delete_ai_provider(
    request: Request,
    provider_id: int,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """
    删除 AI Provider。
    :param request: Request对象
    :param provider_id: Provider主键
    :param query_db: orm对象
    :param current_user: 当前登录用户对象
    :return: 删除结果
    """
    try:
        delete_result = AiProviderService.delete_ai_provider_services(query_db, provider_id, current_user.user.user_name)
        if delete_result.is_success:
            return ResponseUtil.success(msg=delete_result.message)
        return ResponseUtil.failure(msg=delete_result.message)
    except Exception as exc:
        return ResponseUtil.error(msg=str(exc))
