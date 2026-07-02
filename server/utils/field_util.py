"""
字段工具函数：外部同步字段兼容、邮箱/人员解析等通用工具。
"""


def compatible_field_value(payload: dict, camel_key: str, snake_key: str | None = None, default=None):
    """
    读取外部字段值，仅兼容驼峰与下划线写法，不做猜测。

    :param payload: 原始请求数据。
    :param camel_key: 驼峰字段名。
    :param snake_key: 下划线字段名，未传时由驼峰自动转换。
    :param default: 字段缺失时返回的默认值。
    :return: 匹配字段值或默认值。
    """
    normalized_snake_key = snake_key or "".join(
        [f"_{char.lower()}" if char.isupper() else char for char in camel_key]
    )
    for key in (camel_key, normalized_snake_key):
        if key not in payload:
            continue
        value = payload.get(key)
        if value in (None, "", []):
            continue
        return value
    return default


def normalize_email_text(value: object) -> str:
    """
    归一化邮箱文本。

    :param value: 原始邮箱值。
    :return: 去空格并小写后的邮箱；为空返回空字符串。
    """
    text = str(value or "").strip().lower()
    if "@" not in text:
        return ""
    return text


def extract_person_name_email(value: object) -> tuple[str, str]:
    """
    从人员字段中提取姓名与邮箱，兼容字符串/对象/数组。

    :param value: 人员字段值。
    :return: (姓名, 邮箱)。
    """
    if isinstance(value, list):
        for item in value:
            name, email = extract_person_name_email(item)
            if name or email:
                return name, email
        return "", ""
    if isinstance(value, dict):
        name = str(
            value.get("name")
            or value.get("displayName")
            or value.get("nickName")
            or value.get("nickname")
            or value.get("userName")
            or value.get("realName")
            or value.get("value")
            or ""
        ).strip()
        email = normalize_email_text(
            value.get("email")
            or value.get("mail")
            or value.get("userEmail")
            or value.get("workEmail")
            or ""
        )
        return name, email
    raw_text = str(value or "").strip()
    if not raw_text:
        return "", ""
    email_text = normalize_email_text(raw_text)
    if email_text:
        return "", email_text
    return raw_text, ""
