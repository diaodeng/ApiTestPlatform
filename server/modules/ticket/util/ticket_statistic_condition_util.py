"""工单外部分类和自定义统计条件的无副作用匹配工具。"""
from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any


def normalize_match_values(value: Any) -> list[str]:
    """将规则值归一化为去重后的非空字符串列表。"""
    values = value if isinstance(value, list) else [value]
    result: list[str] = []
    for item in values:
        text = str(item if item is not None else "").strip()
        if text and text not in result:
            result.append(text)
    return result


def read_field_value(source: Any, field_name: str) -> Any:
    """从 ORM 实体、行对象或字典中读取注册字段。"""
    if isinstance(source, Mapping):
        return source.get(field_name)
    return getattr(source, field_name, None)


def match_value(actual: Any, operator: str, expected_values: Any) -> bool:
    """执行 equals、contains、in、regex 四种安全匹配规则。"""
    values = normalize_match_values(expected_values)
    if not values:
        return False
    normalized_operator = str(operator or "equals").strip().lower()
    actual_values = actual if isinstance(actual, (list, tuple, set)) else [actual]
    text_values = [str(item if item is not None else "").strip() for item in actual_values]
    if normalized_operator == "equals":
        return any(text == expected for text in text_values for expected in values)
    if normalized_operator == "contains":
        return any(expected in text for text in text_values for expected in values)
    if normalized_operator == "in":
        return any(text in values for text in text_values)
    if normalized_operator == "regex":
        for pattern in values:
            try:
                if any(re.search(pattern, text) for text in text_values):
                    return True
            except re.error:
                continue
    return False


def match_conditions(source: Any, conditions: Any, condition_mode: str = "all") -> bool:
    """按 all 或 any 计算一组字段条件。"""
    rows = [item for item in conditions if isinstance(item, dict)] if isinstance(conditions, list) else []
    if not rows:
        return False
    matches = [
        match_value(read_field_value(source, str(row.get("sourceField") or "").strip()), row.get("operator"), row.get("matchValues"))
        for row in rows
        if str(row.get("sourceField") or "").strip()
    ]
    if not matches:
        return False
    return any(matches) if str(condition_mode or "all").lower() == "any" else all(matches)
