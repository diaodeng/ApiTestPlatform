from __future__ import annotations

from typing import Any

EXTERNAL_TO_INTERNAL_PRIORITY_MAP = {
    "LEVEL0": "P0",
    "LEVELA": "P1",
    "LEVELB": "P2",
    "LEVELC": "P3",
    "LEVELD": "P4",
}
INTERNAL_TO_EXTERNAL_PRIORITY_MAP = {
    "P0": "Level 0",
    "P1": "Level A",
    "P2": "Level B",
    "P3": "Level C",
    "P4": "Level D",
}


def normalize_priority_text(value: Any) -> str:
    """
    归一化优先级原始文本，仅去除首尾空白并保留调用方传入的业务文案。
    :param value: 原始优先级值。
    :return: 去空白后的优先级文本。
    """
    if value in (None, "", []):
        return ""
    return str(value or "").strip()


def normalize_priority_key(value: Any) -> str:
    """
    将优先级文本归一成便于匹配的无符号大写键。
    :param value: 原始优先级值。
    :return: 去除空格、下划线、横线和冒号后的大写键。
    """
    text = normalize_priority_text(value)
    return (
        text.upper()
        .replace(" ", "")
        .replace("_", "")
        .replace("-", "")
        .replace("/", "")
        .replace("：", "")
        .replace(":", "")
    )


def convert_external_priority_to_internal(value: Any) -> str:
    """
    将外部优先级转换为内部优先级。
    :param value: 外部优先级，支持 Level 0/Level A/Level B/Level C/Level D 和历史 P0-P4。
    :return: 内部优先级 P0-P4；无法识别时返回空字符串。
    """
    key = normalize_priority_key(value)
    if key in EXTERNAL_TO_INTERNAL_PRIORITY_MAP:
        return EXTERNAL_TO_INTERNAL_PRIORITY_MAP[key]
    if key in INTERNAL_TO_EXTERNAL_PRIORITY_MAP:
        return key
    if key.isdigit() and key in {"0", "1", "2", "3", "4"}:
        return f"P{key}"
    return ""


def convert_internal_priority_to_external(value: Any) -> str:
    """
    将内部优先级转换为外部优先级。
    :param value: 内部优先级，支持 P0-P4、0-4 和外部 Level 文案。
    :return: 外部优先级 Level 0/Level A/Level B/Level C/Level D；无法识别时返回空字符串。
    """
    key = normalize_priority_key(value)
    if key in INTERNAL_TO_EXTERNAL_PRIORITY_MAP:
        return INTERNAL_TO_EXTERNAL_PRIORITY_MAP[key]
    if key.isdigit() and key in {"0", "1", "2", "3", "4"}:
        return INTERNAL_TO_EXTERNAL_PRIORITY_MAP.get(f"P{key}", "")
    if key in EXTERNAL_TO_INTERNAL_PRIORITY_MAP:
        internal_priority = EXTERNAL_TO_INTERNAL_PRIORITY_MAP[key]
        return INTERNAL_TO_EXTERNAL_PRIORITY_MAP.get(internal_priority, "")
    return ""


def complete_ticket_priority_pair(
    customer_priority: Any,
    internal_priority: Any,
) -> tuple[str, str]:
    """
    补齐工单外部优先级和内部优先级的缺失侧。
    :param customer_priority: 外部/对方优先级。
    :param internal_priority: 内部优先级。
    :return: (外部优先级, 内部优先级)。双方都有值时只去空白，不互相覆盖。
    """
    normalized_customer_priority = normalize_priority_text(customer_priority)
    normalized_internal_priority = normalize_priority_text(internal_priority)
    if not normalized_internal_priority and normalized_customer_priority:
        normalized_internal_priority = (
            convert_external_priority_to_internal(normalized_customer_priority) or normalized_customer_priority
        )
    if not normalized_customer_priority and normalized_internal_priority:
        normalized_customer_priority = (
            convert_internal_priority_to_external(normalized_internal_priority) or normalized_internal_priority
        )
    return normalized_customer_priority, normalized_internal_priority
