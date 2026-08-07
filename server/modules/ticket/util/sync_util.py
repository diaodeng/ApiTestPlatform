"""
工单同步工具方法：类型转换、JSON 序列化、Hash、日期解析等通用函数。
"""
import hashlib
import json
from datetime import datetime, timezone
from typing import Any


class SyncUtil:
    """工单同步通用工具方法集合。"""

    @staticmethod
    def to_bool(value: Any, default: bool = False) -> bool:
        """
        将任务参数或配置值转换为布尔值。
        :param value: 原始布尔、数字或字符串值。
        :param default: 值为空或无法识别时返回的默认值。
        :return: 归一化后的布尔值。
        """
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        normalized_value = str(value).strip().lower()
        if normalized_value in {"true", "1", "yes", "y", "on", "开启", "是"}:
            return True
        if normalized_value in {"false", "0", "no", "n", "off", "关闭", "否"}:
            return False
        return default

    @staticmethod
    def safe_int(value: Any) -> int | None:
        try:
            if value in (None, ""):
                return None
            return int(value)
        except Exception:
            return None

    @staticmethod
    def json_dumps(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, indent=2)

    @staticmethod
    def json_loads(value: Any, default: Any = None):
        if value in (None, ""):
            return default
        if isinstance(value, (dict, list)):
            return value
        try:
            return json.loads(str(value))
        except Exception:
            return default

    @staticmethod
    def now_iso() -> str:
        return datetime.now().isoformat()

    @staticmethod
    def text_sha256(value: Any) -> str:
        """
        计算文本的 SHA256 摘要，用于判断翻译源是否变化。
        :param value: 原始文本。
        :return: 文本摘要，空值返回空字符串。
        """
        normalized = str(value or "").strip()
        if not normalized:
            return ""
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    @staticmethod
    def parse_datetime_value(value: Any) -> datetime | None:
        """
        将多种时间格式解析为可比较的 datetime。
        :param value: 原始时间值
        :return: datetime，失败返回 None
        """
        if value in (None, ""):
            return None
        parsed: datetime | None = None
        if isinstance(value, datetime):
            parsed = value
        elif isinstance(value, (int, float)):
            timestamp = float(value)
            if timestamp > 10_000_000_000:
                timestamp = timestamp / 1000.0
            try:
                parsed = datetime.fromtimestamp(timestamp, tz=timezone.utc)
            except Exception:
                parsed = None
        else:
            text = str(value or "").strip()
            if not text:
                return None
            try:
                parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            except Exception:
                parsed = None
            if parsed is None:
                for fmt in (
                    "%Y-%m-%d %H:%M:%S",
                    "%Y/%m/%d %H:%M:%S",
                    "%Y-%m-%d %H:%M",
                    "%Y/%m/%d %H:%M",
                    "%Y-%m-%d",
                    "%Y/%m/%d",
                ):
                    try:
                        parsed = datetime.strptime(text, fmt)
                        break
                    except Exception:
                        continue
        if parsed is not None and parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed

    @staticmethod
    def normalize_keywords(value: Any) -> list[str]:
        """归一化关键词列表。"""
        if value in (None, ""):
            return []
        if isinstance(value, list):
            return [str(item).strip() for item in value if item not in (None, "")]
        return [kw.strip() for kw in str(value).split(",") if kw.strip()]

    @staticmethod
    def payload_field_value(payload: dict, *keys: str, default=None):
        """
        从 payload 中按优先级获取第一个非空字段值。
        :param payload: 数据字典
        :param keys: 字段名列表，按优先级排序
        :param default: 默认值
        """
        for key in keys:
            value = payload.get(key)
            if value not in (None, "", []):
                return value
        return default
