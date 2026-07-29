from typing import Any

from module_admin.entity.vo.user_vo import CurrentUserModel

INVALID_VERSION_TEXTS = {
    "version",
    "versionkey",
    "appversion",
    "deployversion",
    "版本",
    "版本号",
    "发生版本",
    "问题发生版本",
}


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


def normalize_ticket_version_key(value: Any) -> str:
    """
    归一化工单版本号，过滤字段名或标签被误识别成版本号的情况。
    :param value: 待归一化的版本号文本
    :return: 合法版本号；无效时返回空字符串
    """
    text = str(value or "").strip().strip("'\"`，,;；。")
    if not text:
        return ""
    normalized = text.replace("_", "").replace("-", "").replace(" ", "").lower()
    if normalized in INVALID_VERSION_TEXTS:
        return ""
    if len(text) > 100:
        return ""
    # 真实版本、分支版本或发版标识通常至少包含一个数字；可避免把 version 等字段名写入版本字段。
    if not any(char.isdigit() for char in text):
        return ""
    return text
