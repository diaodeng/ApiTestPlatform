from fastapi import APIRouter, Depends, Request
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from config.get_db import get_db
from module_admin.aspect.interface_auth import CheckUserInterfaceAuth
from module_admin.entity.vo.ai_provider_vo import (
    AiProviderPageQueryModel,
    CreateAiProviderModel,
    PreviewAiProviderModelCatalogRequest,
    TestAiProviderConnectionRequest,
    UpdateAiProviderModel,
    ViewAiProviderSecretModel,
)
from module_admin.service.ai_provider_capability_service import AiProviderCapabilityService
from module_admin.service.ai_provider_connection_service import AiProviderConnectionService
from module_admin.service.ai_provider_model_catalog_service import AiProviderModelCatalogService
from module_admin.service.ai_provider_service import AiProviderService
from module_admin.service.login_service import CurrentUserModel, LoginService
from utils.page_util import PageResponseModel
from utils.response_util import ResponseUtil

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
    usage: str | None = None,
    executor: str | None = None,
    query_db: Session = Depends(get_db),
):
    """
    获取可用于节点选择的 AI Provider 选项。
    :param request: Request对象
    :param usage: 可选业务用途过滤
    :param executor: 可选执行器过滤
    :param query_db: orm对象
    :return: Provider选项列表
    """
    try:
        provider_options = AiProviderService.get_ai_provider_options_services(query_db, usage, executor)
        return ResponseUtil.success(data=provider_options)
    except Exception as exc:
        return ResponseUtil.error(msg=str(exc))


@aiProviderController.get(
    "/metadata/options",
    dependencies=[Depends(CheckUserInterfaceAuth("system:aiprovider:list"))],
)
async def get_ai_provider_metadata_options(request: Request):
    """
    获取Provider平台、协议、用途和执行器的元数据选项。
    :param request: 请求对象
    :return: Provider配置元数据
    """
    return ResponseUtil.success(
        data={
            "platforms": AiProviderCapabilityService.PLATFORM_OPTIONS,
            "protocols": AiProviderCapabilityService.PROTOCOL_OPTIONS,
            "usages": AiProviderCapabilityService.USAGE_OPTIONS,
            "executors": AiProviderCapabilityService.EXECUTOR_OPTIONS,
        }
    )


@aiProviderController.post(
    "/model-catalog/preview",
    dependencies=[Depends(CheckUserInterfaceAuth("system:aiprovider:edit"))],
)
async def preview_ai_provider_models(
    request: Request,
    preview_object: PreviewAiProviderModelCatalogRequest,
    query_db: Session = Depends(get_db),
):
    """
    使用未保存的Provider表单草稿探测上游模型目录，不写入数据库。
    :param request: 请求对象
    :param preview_object: Provider连接草稿
    :param query_db: 数据库会话
    :return: 上游模型目录
    """
    try:
        models = await run_in_threadpool(AiProviderConnectionService.preview_models, query_db, preview_object)
        return ResponseUtil.success(data=models)
    except Exception as exc:
        return ResponseUtil.error(msg=str(exc))


@aiProviderController.get(
    "/{provider_id}/model-catalog",
    dependencies=[Depends(CheckUserInterfaceAuth("system:aiprovider:query"))],
)
async def get_ai_provider_model_catalog(request: Request, provider_id: int, query_db: Session = Depends(get_db)):
    """
    获取已保存Provider的模型目录缓存。
    :param request: 请求对象
    :param provider_id: Provider主键
    :param query_db: 数据库会话
    :return: 模型目录列表
    """
    try:
        models = AiProviderModelCatalogService.list_models(query_db, provider_id)
        return ResponseUtil.success(data=models)
    except Exception as exc:
        return ResponseUtil.error(msg=str(exc))


@aiProviderController.post(
    "/connection/test",
    dependencies=[Depends(CheckUserInterfaceAuth("system:aiprovider:edit"))],
)
async def test_ai_provider_connection(
    request: Request,
    test_object: TestAiProviderConnectionRequest,
    query_db: Session = Depends(get_db),
):
    """
    使用当前Provider表单草稿测试默认模型是否可调用。
    :param request: 请求对象
    :param test_object: Provider连接测试草稿
    :param query_db: 数据库会话
    :return: 模型测试结果
    """
    try:
        result = await run_in_threadpool(AiProviderConnectionService.test_connection, query_db, test_object)
        return ResponseUtil.success(data=result)
    except Exception as exc:
        return ResponseUtil.error(msg=str(exc))


@aiProviderController.post(
    "/{provider_id}/secret/view",
    dependencies=[Depends(CheckUserInterfaceAuth("system:aiprovider:view-secret"))],
)
async def view_ai_provider_secret(
    request: Request,
    provider_id: int,
    view_object: ViewAiProviderSecretModel,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """
    校验当前登录用户密码后查看指定Provider密钥明文。
    :param request: 请求对象
    :param provider_id: Provider主键
    :param view_object: 当前用户密码
    :param query_db: 数据库会话
    :param current_user: 当前登录用户
    :return: Provider密钥明文
    """
    try:
        result = AiProviderService.view_ai_provider_secret_services(
            query_db, current_user, provider_id, view_object.password
        )
        if result.is_success:
            return ResponseUtil.success(msg=result.message, data=result.result)
        return ResponseUtil.failure(msg=result.message)
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


@aiProviderController.delete(
    "/{provider_id}",
    dependencies=[Depends(CheckUserInterfaceAuth("system:aiprovider:remove"))],
)
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
        delete_result = AiProviderService.delete_ai_provider_services(
            query_db,
            provider_id,
            current_user.user.user_name,
        )
        if delete_result.is_success:
            return ResponseUtil.success(msg=delete_result.message)
        return ResponseUtil.failure(msg=delete_result.message)
    except Exception as exc:
        return ResponseUtil.error(msg=str(exc))
