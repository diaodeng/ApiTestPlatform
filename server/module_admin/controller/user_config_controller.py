from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from config.get_db import get_db
from module_admin.entity.vo.user_config_vo import UserConfigModel
from module_admin.entity.vo.user_vo import CurrentUserModel
from module_admin.service.login_service import LoginService
from module_admin.service.user_config_service import UserConfigService
from utils.log_util import logger
from utils.response_util import ResponseUtil

userConfigController = APIRouter(prefix="/system/user-config", dependencies=[Depends(LoginService.get_current_user)])


@userConfigController.get("/current")
async def list_current_user_configs(
    request: Request,
    config_type: str | None = Query(default=None, alias="configType"),
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """
    查询当前登录用户配置列表接口。
    :param request: 请求对象
    :param config_type: 可选配置类型，用于只查询某个功能域配置
    :param query_db: 数据库会话
    :param current_user: 当前登录用户
    :return: 当前用户配置列表
    """
    try:
        result = UserConfigService.list_current_user_config_services(
            query_db,
            current_user.user.user_id,
            config_type,
        )
        return ResponseUtil.success(data=[item.model_dump(by_alias=True) for item in result])
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@userConfigController.get("/current/{config_type}/{config_key}")
async def get_current_user_config(
    request: Request,
    config_type: str,
    config_key: str,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """
    查询当前登录用户单个配置接口。
    :param request: 请求对象
    :param config_type: 配置类型
    :param config_key: 配置键名
    :param query_db: 数据库会话
    :param current_user: 当前登录用户
    :return: 当前用户指定配置，不存在时data为空
    """
    try:
        result = UserConfigService.get_current_user_config_services(
            query_db,
            current_user.user.user_id,
            config_type,
            config_key,
        )
        return ResponseUtil.success(data=result.model_dump(by_alias=True) if result else None)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@userConfigController.put("/current")
async def save_current_user_config(
    request: Request,
    config_model: UserConfigModel,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """
    保存当前登录用户配置接口。
    :param request: 请求对象
    :param config_model: 用户配置内容，包含configType、configKey和configValue
    :param query_db: 数据库会话
    :param current_user: 当前登录用户
    :return: 保存后的用户配置
    """
    try:
        result = UserConfigService.save_current_user_config_services(
            query_db,
            current_user.user.user_id,
            current_user.user.user_name,
            config_model,
        )
        return ResponseUtil.success(data=result.model_dump(by_alias=True), msg="保存成功")
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))
