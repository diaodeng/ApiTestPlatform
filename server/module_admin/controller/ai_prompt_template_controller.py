from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from config.get_db import get_db
from module_admin.aspect.interface_auth import CheckUserInterfaceAuth
from module_admin.entity.vo.ai_prompt_template_vo import (
    AiPromptTemplatePageQueryModel,
    CreateAiPromptTemplateModel,
    UpdateAiPromptTemplateModel,
)
from module_admin.service.ai_prompt_template_service import AiPromptTemplateService
from module_admin.service.login_service import CurrentUserModel, LoginService
from utils.page_util import PageResponseModel
from utils.response_util import ResponseUtil

aiPromptTemplateController = APIRouter(prefix="/system/aiprompt", dependencies=[Depends(LoginService.get_current_user)])


@aiPromptTemplateController.get(
    "/list",
    response_model=PageResponseModel,
    dependencies=[Depends(CheckUserInterfaceAuth("system:aiprompt:list"))],
)
async def get_ai_prompt_template_list(
    request: Request,
    ai_prompt_template_page_query: AiPromptTemplatePageQueryModel = Depends(AiPromptTemplatePageQueryModel.as_query),
    query_db: Session = Depends(get_db),
):
    """
    获取 AI 提示词模板分页列表。
    :param request: Request对象
    :param ai_prompt_template_page_query: AI提示词模板分页查询对象
    :param query_db: orm对象
    :return: AI提示词模板分页列表
    """
    try:
        template_list = AiPromptTemplateService.get_prompt_template_list_services(query_db, ai_prompt_template_page_query)
        return ResponseUtil.success(model_content=template_list)
    except Exception as exc:
        return ResponseUtil.error(msg=str(exc))


@aiPromptTemplateController.get(
    "/options",
    dependencies=[Depends(CheckUserInterfaceAuth("system:aiprompt:list"))],
)
async def get_ai_prompt_template_options(
    request: Request,
    template_category: str | None = None,
    enabled_only: bool = True,
    query_db: Session = Depends(get_db),
):
    """
    获取 AI 提示词模板下拉选项。
    :param request: Request对象
    :param template_category: 模板分类，支持逗号分隔
    :param enabled_only: 是否只返回启用模板
    :param query_db: orm对象
    :return: AI提示词模板选项
    """
    try:
        template_options = AiPromptTemplateService.get_prompt_template_options_services(
            query_db, template_category=template_category, enabled_only=enabled_only
        )
        return ResponseUtil.success(data=template_options)
    except Exception as exc:
        return ResponseUtil.error(msg=str(exc))


@aiPromptTemplateController.get(
    "/{template_id}",
    dependencies=[Depends(CheckUserInterfaceAuth("system:aiprompt:query"))],
)
async def get_ai_prompt_template_detail(
    request: Request,
    template_id: int,
    query_db: Session = Depends(get_db),
):
    """
    获取 AI 提示词模板详情。
    :param request: Request对象
    :param template_id: 模板主键
    :param query_db: orm对象
    :return: 模板详情
    """
    try:
        template_detail = AiPromptTemplateService.get_prompt_template_detail_services(query_db, template_id)
        if not template_detail:
            return ResponseUtil.failure(msg="模板不存在")
        return ResponseUtil.success(data=template_detail)
    except Exception as exc:
        return ResponseUtil.error(msg=str(exc))


@aiPromptTemplateController.post("", dependencies=[Depends(CheckUserInterfaceAuth("system:aiprompt:add"))])
async def add_ai_prompt_template(
    request: Request,
    add_ai_prompt_template_model: CreateAiPromptTemplateModel,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """
    新增 AI 提示词模板。
    :param request: Request对象
    :param add_ai_prompt_template_model: 新增请求对象
    :param query_db: orm对象
    :param current_user: 当前登录用户对象
    :return: 新增结果
    """
    try:
        add_result = AiPromptTemplateService.add_prompt_template_services(
            query_db, add_ai_prompt_template_model, current_user.user.user_name
        )
        if add_result.is_success:
            return ResponseUtil.success(msg=add_result.message, data=add_result.result)
        return ResponseUtil.failure(msg=add_result.message)
    except Exception as exc:
        return ResponseUtil.error(msg=str(exc))


@aiPromptTemplateController.put("", dependencies=[Depends(CheckUserInterfaceAuth("system:aiprompt:edit"))])
async def update_ai_prompt_template(
    request: Request,
    update_ai_prompt_template_model: UpdateAiPromptTemplateModel,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """
    编辑 AI 提示词模板。
    :param request: Request对象
    :param update_ai_prompt_template_model: 编辑请求对象
    :param query_db: orm对象
    :param current_user: 当前登录用户对象
    :return: 修改结果
    """
    try:
        update_result = AiPromptTemplateService.update_prompt_template_services(
            query_db, update_ai_prompt_template_model, current_user.user.user_name
        )
        if update_result.is_success:
            return ResponseUtil.success(msg=update_result.message, data=update_result.result)
        return ResponseUtil.failure(msg=update_result.message)
    except Exception as exc:
        return ResponseUtil.error(msg=str(exc))


@aiPromptTemplateController.delete(
    "/{template_id}", dependencies=[Depends(CheckUserInterfaceAuth("system:aiprompt:remove"))]
)
async def delete_ai_prompt_template(
    request: Request,
    template_id: int,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """
    删除 AI 提示词模板。
    :param request: Request对象
    :param template_id: 模板主键
    :param query_db: orm对象
    :param current_user: 当前登录用户对象
    :return: 删除结果
    """
    try:
        delete_result = AiPromptTemplateService.delete_prompt_template_services(
            query_db, template_id, current_user.user.user_name
        )
        if delete_result.is_success:
            return ResponseUtil.success(msg=delete_result.message)
        return ResponseUtil.failure(msg=delete_result.message)
    except Exception as exc:
        return ResponseUtil.error(msg=str(exc))
