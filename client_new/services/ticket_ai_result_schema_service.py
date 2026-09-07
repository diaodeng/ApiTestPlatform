from __future__ import annotations

import json
from typing import Any


def _type_name(value: Any) -> str:
    """
    返回值的 JSON 类型名，用于清洗动作描述。
    :param value: 任意值
    :return: JSON 类型名称（string/number/object 等）
    """
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


class TicketAiResultSchemaService:
    """工单 AI 分析结果清洗服务 — 供 Agent 结果解析与缓存复用前共用的纯函数集合。

    背景：部分模型（如 deepseek-v4-flash 经 ai-router 中转）即使被 Codex
    --output-schema 约束，仍会输出 schema 之外的字段（如 ticket_no、
    merchant_name、version、root_cause_type）或把 evidence 写成
    {source, content} 对象数组。这里在 schema 校验前做一次保守清洗：
    只处理"模型真实意图明确"的偏差，避免大范围兜底掩盖真实问题。
    """

    @classmethod
    def sanitize_result_payload(
        cls,
        payload: dict[str, Any],
        schema: dict[str, Any],
    ) -> tuple[dict[str, Any], list[str]]:
        """
        按 schema 清洗模型输出，返回 (清洗后结果, 清洗动作说明列表)。
        清洗范围：
        1. 剔除 additionalProperties=False 时 schema 之外的额外字段（如 ticket_no）；
        2. evidence 数组元素为对象时，提取 source/content 拼接为字符串；
        3. evidence 数组元素为其他非字符串类型时序列化为 JSON 字符串。
        :param payload: 模型输出的原始结果
        :param schema: 本次任务的输出 JSON Schema
        :return: (清洗后的结果, 清洗动作描述列表，如 ["$.ticket_no: 已剔除 schema 外额外字段"])
        """
        cleaned = dict(payload or {})
        actions: list[str] = []

        # 1. 剔除 schema 不允许的额外字段（模型自行附加的工单号、商家名等）。
        if schema.get("additionalProperties") is False:
            properties = schema.get("properties") or {}
            extra_keys = [key for key in cleaned if key not in properties]
            for key in extra_keys:
                cleaned.pop(key)
                actions.append(f"$.{key}: 已剔除 schema 外额外字段")

        # 2. evidence 元素为对象/其他类型时归一化为字符串。
        evidence_schema = (schema.get("properties") or {}).get("evidence") or {}
        evidence_items_schema = evidence_schema.get("items") or {}
        if evidence_items_schema.get("type") == "string" and isinstance(cleaned.get("evidence"), list):
            normalized_evidence: list[str] = []
            for index, item in enumerate(cleaned["evidence"]):
                if isinstance(item, str):
                    normalized_evidence.append(item)
                    continue
                normalized_evidence.append(cls._coerce_evidence_entry(item))
                actions.append(
                    f"$.evidence[{index}]: 已从 {_type_name(item)} 归一化为 string"
                )
            cleaned["evidence"] = normalized_evidence
        return cleaned, actions

    @staticmethod
    def _coerce_evidence_entry(item: Any) -> str:
        """
        把单条 evidence 归一化为字符串。
        优先识别 {source, content} 结构（模型最常见的对象化证据写法），
        拼接为 "source: content"；其余类型直接 JSON 序列化，保留完整信息。
        :param item: 原始 evidence 元素
        :return: 字符串形式的证据
        """
        if isinstance(item, dict):
            source = str(item.get("source") or "").strip()
            content = str(item.get("content") or "").strip()
            if source and content:
                return f"{source}: {content}"
            return content or source
        return json.dumps(item, ensure_ascii=False)
