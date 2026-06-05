from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from config.get_db import get_db
from module_admin.aspect.interface_auth import CheckUserInterfaceAuth
from module_admin.entity.vo.ai_config_vo import AiConfigUpdateModel
from module_admin.service.ai_config_service import AiConfigService
from module_admin.service.login_service import CurrentUserModel, LoginService
from utils.response_util import ResponseUtil

aiConfigController = APIRouter(prefix="/system/aiconfig", dependencies=[Depends(LoginService.get_current_user)])


@aiConfigController.get(
    "/summary",
    dependencies=[Depends(CheckUserInterfaceAuth("system:aiconfig:list"))],
)
async def get_ai_config_summary(
    request: Request,
    query_db: Session = Depends(get_db),
):
    """
    获取 AI 聚合配置页数据。
    :param request: Request对象
    :param query_db: orm对象
    :return: 聚合配置数据
    """
    try:
        summary = AiConfigService.get_ai_config_summary_services(query_db)
        return ResponseUtil.success(data=summary)
    except Exception as exc:
        return ResponseUtil.error(msg=str(exc))


@aiConfigController.put("", dependencies=[Depends(CheckUserInterfaceAuth("system:aiconfig:edit"))])
async def update_ai_config(
    request: Request,
    update_ai_config_model: AiConfigUpdateModel,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """
    保存 AI 聚合配置。
    :param request: Request对象
    :param update_ai_config_model: 配置更新对象
    :param query_db: orm对象
    :param current_user: 当前登录用户对象
    :return: 保存结果
    """
    try:
        update_result = await AiConfigService.update_ai_config_services(
            request, query_db, update_ai_config_model, current_user.user.user_name
        )
        if update_result.is_success:
            return ResponseUtil.success(msg=update_result.message)
        return ResponseUtil.failure(msg=update_result.message)
    except Exception as exc:
        return ResponseUtil.error(msg=str(exc))
