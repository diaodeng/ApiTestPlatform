"""工单同步门店候选选择工具。"""
from __future__ import annotations

from typing import Any


class TicketStoreResolutionUtil:
    """按外部来源编码和 AI 候选选择日志接口门店。"""

    @staticmethod
    def normalize_store_value(value: Any) -> str:
        """将门店候选规范化为可比较的字符串。"""
        return str(value or "").strip()

    @classmethod
    def resolve_source_store_code(
        cls,
        *,
        log_pull_config: Any = None,
        raw_payload: Any = None,
        extra_data: Any = None,
    ) -> str:
        """仅从外部来源字段解析 sourceStoreCode，不读取 AI 结果。"""
        sources = (raw_payload, extra_data, log_pull_config)
        source_keys = (
            "sourceStoreCode",
            "source_store_code",
            "storeCode",
            "store_code",
            "ticketStore",
            "ticket_store",
        )
        for source in sources:
            if isinstance(source, dict):
                for key in source_keys:
                    value = cls.normalize_store_value(source.get(key))
                    if value:
                        return value
        if isinstance(extra_data, dict):
            mapping = extra_data.get("external_field_mapping")
            if isinstance(mapping, dict):
                for key in source_keys:
                    value = cls.normalize_store_value(mapping.get(key))
                    if value:
                        return value
        return ""

    @classmethod
    def select_store_id(
        cls,
        *,
        source_store_code: Any,
        ai_store: Any,
        existing_store_id: Any = None,
    ) -> tuple[str, str]:
        """
        选择最终日志接口门店，并返回选择原因。

        有外部来源编码时，仅当 AI 值等于来源编码或是来源编码的子串才采用 AI；
        AI 为空或不匹配时回退来源编码。没有来源编码时，优先采用 AI，再保留旧值。
        """
        source = cls.normalize_store_value(source_store_code)
        ai_value = cls.normalize_store_value(ai_store)
        existing = cls.normalize_store_value(existing_store_id)
        if source:
            if ai_value and ai_value in source:
                reason = "ai_exact_match" if ai_value == source else "ai_value_contained"
                return ai_value, reason
            return source, "fallback_source_store_code"
        if ai_value:
            return ai_value, "ai_without_source"
        if existing:
            return existing, "keep_existing_store_id"
        return "", "empty_store_id"
