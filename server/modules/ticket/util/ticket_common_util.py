from typing import Any

from module_admin.entity.vo.user_vo import CurrentUserModel

VERSION_COMPAT_KEYS = (
    "version_key",
    "versionKey",
    "deployVersion",
    "deploy_version",
    "appVersion",
    "app_version",
    "version",
)
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


def extract_ticket_version_key(extra_data: Any) -> str:
    """
    从工单扩展信息中提取版本号。
    :param extra_data: 工单扩展字段
    :return: 版本号；未命中时返回空字符串
    """
    if not isinstance(extra_data, dict):
        return ""
    for key in VERSION_COMPAT_KEYS:
        version_key = normalize_ticket_version_key(extra_data.get(key))
        if version_key:
            return version_key
    return ""


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


def resolve_ticket_current_version_key(ticket: Any) -> str:
    """
    按主表发生版本优先、扩展字段兜底的顺序解析工单当前版本号。
    :param ticket: 工单 ORM 或兼容对象
    :return: 当前有效版本号；未命中时返回空字符串
    """
    affected_version = normalize_ticket_version_key(getattr(ticket, "affected_version", ""))
    if affected_version:
        return affected_version
    version_key = normalize_ticket_version_key(getattr(ticket, "version_key", ""))
    if version_key:
        return version_key
    return extract_ticket_version_key(getattr(ticket, "extra_data", None))
