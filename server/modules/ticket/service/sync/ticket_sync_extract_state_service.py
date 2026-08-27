"""
工单同步统一提取状态服务。

负责构造稳定的提取源快照和提示词指纹，避免评论、同步时间等无关变化
导致重复调用统一提取 AI。
"""
from __future__ import annotations

import json
from typing import Any

from modules.ticket.util.sync_util import SyncUtil


class TicketSyncExtractStateService:
    """统一提取的 sourceHash/promptHash 和缓存判定。"""

    COMMENT_KEYS = {
        "comment",
        "comments",
        "commentlist",
        "comment_list",
        "_remote_sync_comments",
        "stepreason",
        "step_reason",
    }
    VOLATILE_KEYS = {
        "recordid",
        "record_id",
        "recordurl",
        "record_url",
        "synctime",
        "sync_time",
        "fetchedat",
        "fetched_at",
        "pulledat",
        "pulled_at",
        "lastmodifiedtime",
        "last_modified_time",
        "updatedat",
        "updated_at",
        "updatetime",
        "update_time",
    }

    @classmethod
    def _filter_payload(cls, value: Any, *, parent_key: str = "") -> Any:
        """递归删除评论、同步噪声和上次 AI/自动化派生状态。"""
        if isinstance(value, dict):
            filtered: dict[str, Any] = {}
            ignored_keys = {
                item.replace("_", "") for item in cls.COMMENT_KEYS
            } | {
                "aisyncextract",
                "aiextract",
                "logpullhints",
                "externalsync",
                "syncstate",
                "revision",
            }
            for key, item in value.items():
                normalized_key = str(key).replace("-", "_").lower()
                compact_key = normalized_key.replace("_", "")
                if compact_key in ignored_keys:
                    continue
                if normalized_key in cls.VOLATILE_KEYS:
                    continue
                filtered[key] = cls._filter_payload(item, parent_key=normalized_key)
            return filtered
        if isinstance(value, list):
            return [cls._filter_payload(item, parent_key=parent_key) for item in value]
        return value

    @classmethod
    def build_source_snapshot(
        cls,
        *,
        title: str,
        description: str,
        raw_payload: dict[str, Any] | None,
        source_fields: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """构造不包含评论和同步噪声的稳定提取源快照。"""
        return {
            "title": str(title or "").strip(),
            "description": str(description or "").strip(),
            "sourceFields": cls._filter_payload(source_fields if isinstance(source_fields, dict) else {}),
            "rawPayload": cls._filter_payload(raw_payload if isinstance(raw_payload, dict) else {}),
        }

    @classmethod
    def build_source_hash(
        cls,
        *,
        title: str,
        description: str,
        raw_payload: dict[str, Any] | None,
        source_fields: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], str]:
        """构造提取源快照并计算稳定 SHA256。"""
        snapshot = cls.build_source_snapshot(
            title=title,
            description=description,
            raw_payload=raw_payload,
            source_fields=source_fields,
        )
        canonical = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
        return snapshot, SyncUtil.text_sha256(canonical)

    @classmethod
    def build_prompt_hash(
        cls,
        *,
        prompt_code: str,
        prompt_content: str,
        extract_fields: list[str] | tuple[str, ...] | set[str],
        categories: list[str] | tuple[str, ...],
        provider_code: str,
        model_name: str,
    ) -> str:
        """按静态提示词和模型配置计算提示词指纹。"""
        payload = {
            "promptCode": str(prompt_code or "").strip(),
            "promptContent": str(prompt_content or ""),
            "extractFields": sorted(str(item or "").strip() for item in extract_fields if str(item or "").strip()),
            "categories": [str(item or "").strip() for item in categories if str(item or "").strip()],
            "providerCode": str(provider_code or "").strip(),
            "modelName": str(model_name or "").strip(),
        }
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
        return SyncUtil.text_sha256(canonical)

    @classmethod
    def get_cache_hit(
        cls,
        cached_state: dict[str, Any] | None,
        *,
        source_hash: str,
        prompt_hash: str,
    ) -> dict[str, Any] | None:
        """读取同源且同提示词的成功提取结果，未命中返回 None。"""
        state = cached_state if isinstance(cached_state, dict) else {}
        meta = state.get("meta") if isinstance(state.get("meta"), dict) else {}
        result = state.get("result") if isinstance(state.get("result"), dict) else {}
        if not result or str(meta.get("sourceHash") or "") != source_hash:
            return None
        if str(meta.get("promptHash") or "") != prompt_hash:
            return None
        if meta.get("success") is False or meta.get("error"):
            return None
        return result
