"""
工单同步自动化输入服务。

统一解析自动拉日志和自动 AI 所需的运行时参数，避免 identify、日志请求和
自动 AI 分别从不同字段拼装出不一致的结果。
"""
from __future__ import annotations

from typing import Any

from modules.ticket.entity.vo.ticket_vo import TicketExternalSyncUpsertModel
from modules.ticket.service.sync.ticket_sync_payload_service import TicketSyncPayloadService
from modules.ticket.util.sync_util import SyncUtil
from modules.ticket.util.ticket_store_resolution_util import TicketStoreResolutionUtil


class TicketSyncAutomationInputService:
    """自动化运行参数规范化服务。"""

    @staticmethod
    def _value(source: Any, *keys: str) -> Any:
        if not isinstance(source, dict):
            return None
        return SyncUtil.payload_field_value(source, *keys, default=None)

    @classmethod
    def _canonicalize(cls, source: Any) -> dict[str, Any]:
        """读取 camel/snake 历史字段并输出统一字段。"""
        if not isinstance(source, dict):
            return {}
        result: dict[str, Any] = {}
        vendor_id = SyncUtil.safe_int(cls._value(source, "vendorId", "vendor_id"))
        store_id = str(cls._value(source, "storeId", "store_id") or "").strip()
        source_store_code = str(
            cls._value(source, "sourceStoreCode", "source_store_code", "storeCode", "store_code") or ""
        ).strip()
        pos_no = SyncUtil.safe_int(cls._value(source, "posNo", "pos_no", "posId", "pos_id"))
        sco_no = SyncUtil.safe_int(cls._value(source, "scoNo", "sco_no", "scoId", "sco_id"))
        modify_time = cls._value(
            source,
            "modifyTime",
            "modify_time",
            "logDate",
            "log_date",
            "ticketDate",
            "ticket_date",
        )
        if vendor_id is not None:
            result["vendorId"] = vendor_id
        if store_id:
            result["storeId"] = store_id
        if source_store_code:
            result["sourceStoreCode"] = source_store_code
        if pos_no is not None:
            result["posNo"] = pos_no
        if sco_no is not None:
            result["scoNo"] = sco_no
        normalized_date = TicketSyncPayloadService.normalize_auto_log_pull_date_text(modify_time)
        if normalized_date:
            result["modifyTime"] = normalized_date
        for key in ("path", "commandDataType", "fileMaxSize", "zipMaxSize", "storageMode"):
            value = cls._value(source, key)
            if value not in (None, ""):
                result[key] = value
        return result

    @classmethod
    def resolve_runtime_config(
        cls,
        *,
        config: dict[str, Any],
        automation: Any,
        sync_object: TicketExternalSyncUpsertModel,
        detected: dict[str, Any] | None,
        ticket_id: int,
        ticket_extra_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """按固定优先级合并自动拉日志运行参数。"""
        defaults = cls._canonicalize(config.get("logPullDefaults"))
        hints = {}
        if isinstance(ticket_extra_data, dict):
            hints = cls._canonicalize(ticket_extra_data.get("log_pull_hints"))
        elif isinstance(sync_object.extra_data, dict):
            hints = cls._canonicalize(sync_object.extra_data.get("log_pull_hints"))
        sync_config = cls._canonicalize(sync_object.log_pull_config)
        detected_config = cls._canonicalize(detected)
        ai_result: dict[str, Any] = {}
        if isinstance(ticket_extra_data, dict):
            state = ticket_extra_data.get("ai_sync_extract")
        elif isinstance(sync_object.extra_data, dict):
            state = sync_object.extra_data.get("ai_sync_extract")
        else:
            state = None
        if isinstance(state, dict):
            meta = state.get("meta") if isinstance(state.get("meta"), dict) else {}
            result = state.get("result") if isinstance(state.get("result"), dict) else {}
            if meta.get("success") is not False and not meta.get("error"):
                ai_result = cls._canonicalize(
                    {
                        **result,
                        "storeId": result.get("store"),
                        "modifyTime": result.get("logDate"),
                    }
                )
        source_store_code = TicketStoreResolutionUtil.resolve_source_store_code(
            log_pull_config=sync_object.log_pull_config,
            raw_payload=sync_object.raw_payload,
            extra_data=ticket_extra_data if isinstance(ticket_extra_data, dict) else sync_object.extra_data,
        )
        task_config = cls._canonicalize(
            automation.log_pull_config if automation is not None else None
        )
        merged: dict[str, Any] = {}
        for source in (defaults, detected_config, hints, sync_config, ai_result, task_config):
            merged.update(source)
        if source_store_code:
            merged["sourceStoreCode"] = source_store_code
            ai_store = ai_result.get("storeId")
            existing_store_id = sync_config.get("storeId") or hints.get("storeId") or detected_config.get("storeId")
            selected_store_id, selection_reason = TicketStoreResolutionUtil.select_store_id(
                source_store_code=source_store_code,
                ai_store=ai_store,
                existing_store_id=existing_store_id,
            )
            if "storeId" not in task_config and selected_store_id:
                merged["storeId"] = selected_store_id
            merged["storeSelectionReason"] = (
                "task_store_id_override" if "storeId" in task_config else selection_reason
            )
        # 明确字段优先于检测结果，但不能将空值覆盖为旧值。
        merged["ticketId"] = ticket_id
        if "scoNo" in merged and "posNo" not in merged:
            merged["posNo"] = merged["scoNo"]
        return merged

    @classmethod
    def resolve_modify_time(
        cls,
        *,
        sync_object: TicketExternalSyncUpsertModel,
        runtime_config: dict[str, Any],
    ) -> str:
        """补齐并规范化自动拉日志日期。"""
        resolved = TicketSyncPayloadService.resolve_auto_log_pull_modify_time(
            sync_object=sync_object,
            log_pull_payload=runtime_config,
        )
        if resolved:
            return resolved
        hints = sync_object.extra_data.get("log_pull_hints") if isinstance(sync_object.extra_data, dict) else {}
        return TicketSyncPayloadService.normalize_auto_log_pull_date_text(
            cls._value(hints, "modifyTime", "modify_time", "logDate", "log_date")
        )
