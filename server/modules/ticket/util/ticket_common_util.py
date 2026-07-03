from typing import Any

from module_admin.entity.vo.user_vo import CurrentUserModel


def user_id(current_user: CurrentUserModel | None) -> int | None:
    """
    获取当前登录用户ID。
    :param current_user: 当前登录用户
    :return: 用户ID；缺少登录态时返回 None
    """
    return current_user.user.user_id if current_user and current_user.user else None


def user_name(current_user: CurrentUserModel | None) -> str:
    """
    获取当前登录用户名。
    :param current_user: 当前登录用户
    :return: 用户名；缺少登录态时返回空字符串
    """
    if not current_user or not current_user.user:
        return ""
    return current_user.user.user_name or current_user.user.nick_name or ""


def extract_ticket_version_key(extra_data: Any) -> str:
    """
    从工单扩展信息中提取版本号。
    :param extra_data: 工单扩展字段
    :return: 版本号；未命中时返回空字符串
    """
    if not isinstance(extra_data, dict):
        return ""
    for key in ("versionKey", "version_key", "version", "deployVersion", "deploy_version", "appVersion"):
        value = extra_data.get(key)
        if str(value or "").strip():
            return str(value).strip()
    return ""
