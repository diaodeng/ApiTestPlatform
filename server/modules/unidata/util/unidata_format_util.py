"""Unidata 响应格式化纯工具：高亮剥离、分层识别、分页行提取。

只包含无副作用的纯函数，不做任何网络或数据库访问。
"""
import re
from typing import Any

# keyword 搜索返回值中的 HTML 高亮标签，例如 <span style='color:red' >ads_xxx</span>
_HIGHLIGHT_PATTERN = re.compile(r"<[^>]+>")
# 分层识别：gray 前缀（gray06_xxx）或中缀（xxx_gray06 / xxx_gray06_yyy）都视为 gray 层
_LAYER_PATTERN = re.compile(r"(?:^|_)gray(\d+)(?:_|$)")


def strip_highlight(value: Any) -> str:
    """剥离 Unidata keyword 搜索返回值中的 HTML 高亮标签并去除首尾空白。"""
    if value is None:
        return ""
    return _HIGHLIGHT_PATTERN.sub("", str(value)).strip()


def resolve_db_layer(db_name: str) -> str:
    """按库名识别所属分层：gray06/gray08 等，无 gray 标识视为 stable（与 gray02 共用）。"""
    matched = _LAYER_PATTERN.search(str(db_name or ""))
    return f"gray{matched.group(1)}" if matched else "stable"


def extract_payload_rows(data: Any) -> list[dict[str, Any]]:
    """从 Unidata 统一分页响应中提取行列表。

    Unidata 各接口的分页载荷字段不统一（list/records/rows/items），
    这里做兼容提取；非分页结构时返回载荷本身或空列表。
    """
    if isinstance(data, dict):
        payload = data.get("data") if "data" in data else data
        if isinstance(payload, dict):
            for key in ("list", "records", "rows", "items"):
                if isinstance(payload.get(key), list):
                    return payload[key]
            return [payload]
        if isinstance(payload, list):
            return payload
    if isinstance(data, list):
        return data
    return []
