from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from config.get_db import get_db
from module_admin.annotation.log_annotation import log_decorator
from module_admin.aspect.interface_auth import CheckUserInterfaceAuth
from module_hrm.entity.vo.module_common_prompt_vo import (
    CreateModuleCommonPromptModel,
    ModuleCommonPromptPageQueryModel,
    UpdateModuleCommonPromptModel,
)
from module_hrm.service.module_common_prompt_service import ModuleCommonPromptService
from module_admin.service.login_service import CurrentUserModel, LoginService
from utils.page_util import PageResponseModel
from utils.response_util import ResponseUtil


moduleCommonPromptController = APIRouter(
    prefix="/hrm/module-common-prompt",
    dependencies=[Depends(LoginService.get_current_user)],
)


@moduleCommonPromptController.get(
    "/list",
    response_model=PageResponseModel,
    dependencies=[Depends(CheckUserInterfaceAuth("hrm:moduleCommonPrompt:list"))],
)
async def get_module_common_prompt_list(
    request: Request,
    query: ModuleCommonPromptPageQueryModel = Depends(ModuleCommonPromptPageQueryModel.as_query),
    query_db: Session = Depends(get_db),
):
    """分页查询模块通用提示词。"""
    try:
        result = await run_in_threadpool(ModuleCommonPromptService.get_page_services, query_db, query)
        return ResponseUtil.success(model_content=result)
    except Exception as exc:
        return ResponseUtil.error(msg=str(exc))


@moduleCommonPromptController.get(
    "/options",
    dependencies=[Depends(CheckUserInterfaceAuth("hrm:moduleCommonPrompt:list"))],
)
async def get_module_common_prompt_options(
    request: Request,
    keyword: str | None = None,
    query_db: Session = Depends(get_db),
):
    """查询模块通用提示词可用编码选项。"""
    try:
        result = await run_in_threadpool(ModuleCommonPromptService.get_options_services, query_db, keyword)
        return ResponseUtil.success(data=result)
    except Exception as exc:
        return ResponseUtil.error(msg=str(exc))


@moduleCommonPromptController.get(
    "/{prompt_id}",
    dependencies=[Depends(CheckUserInterfaceAuth("hrm:moduleCommonPrompt:query"))],
)
async def get_module_common_prompt_detail(
    request: Request,
    prompt_id: int,
    query_db: Session = Depends(get_db),
):
    """查询模块通用提示词详情。"""
    try:
        result = await run_in_threadpool(ModuleCommonPromptService.get_detail_services, query_db, prompt_id)
        if not result:
            return ResponseUtil.failure(msg="模块通用提示词不存在")
        return ResponseUtil.success(data=result)
    except Exception as exc:
        return ResponseUtil.error(msg=str(exc))


@moduleCommonPromptController.post(
    "",
    dependencies=[Depends(CheckUserInterfaceAuth("hrm:moduleCommonPrompt:add"))],
)
@log_decorator(title="模块通用提示词", business_type=1)
async def add_module_common_prompt(
    request: Request,
    payload: CreateModuleCommonPromptModel,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """新增模块通用提示词。"""
    try:
        result = await run_in_threadpool(
            ModuleCommonPromptService.add_services,
            query_db,
            payload,
            current_user.user.user_name,
        )
        if result.is_success:
            return ResponseUtil.success(msg=result.message, data=result.result)
        return ResponseUtil.failure(msg=result.message)
    except Exception as exc:
        return ResponseUtil.error(msg=str(exc))


@moduleCommonPromptController.put(
    "",
    dependencies=[Depends(CheckUserInterfaceAuth("hrm:moduleCommonPrompt:edit"))],
)
@log_decorator(title="模块通用提示词", business_type=2)
async def update_module_common_prompt(
    request: Request,
    payload: UpdateModuleCommonPromptModel,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """修改模块通用提示词。"""
    try:
        result = await run_in_threadpool(
            ModuleCommonPromptService.update_services,
            query_db,
            payload,
            current_user.user.user_name,
        )
        if result.is_success:
            return ResponseUtil.success(msg=result.message, data=result.result)
        return ResponseUtil.failure(msg=result.message)
    except Exception as exc:
        return ResponseUtil.error(msg=str(exc))


@moduleCommonPromptController.delete(
    "/{prompt_id}",
    dependencies=[Depends(CheckUserInterfaceAuth("hrm:moduleCommonPrompt:remove"))],
)
@log_decorator(title="模块通用提示词", business_type=3)
async def delete_module_common_prompt(
    request: Request,
    prompt_id: int,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """逻辑删除模块通用提示词。"""
    try:
        result = await run_in_threadpool(
            ModuleCommonPromptService.delete_services,
            query_db,
            prompt_id,
            current_user.user.user_name,
        )
        if result.is_success:
            return ResponseUtil.success(msg=result.message)
        return ResponseUtil.failure(msg=result.message)
    except Exception as exc:
        return ResponseUtil.error(msg=str(exc))
