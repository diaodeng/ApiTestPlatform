"""
工单同步 AI 字段回填服务。

统一处理 AI 提取结果到同步对象的回填，确保主同步和延后后处理使用相同的数据落点。
"""
from typing import Any

from modules.ticket.entity.vo.ticket_vo import TicketExternalSyncUpsertModel
from modules.ticket.service.sync.ticket_sync_payload_service import TicketSyncPayloadService
from modules.ticket.util.sync_util import SyncUtil
from modules.ticket.util.ticket_store_resolution_util import TicketStoreResolutionUtil


class TicketSyncAiFieldService:
    """工单同步 AI 字段回填编排。"""

    @classmethod
    def apply_extract_to_sync_object(
        cls,
        sync_object: TicketExternalSyncUpsertModel,
        extract_result: dict[str, Any] | None,
    ) -> tuple[TicketExternalSyncUpsertModel, dict[str, Any]]:
        """
        将 AI 提取结果回填到同步对象，并返回统一审计摘要。

        POS/SCO、门店和日期统一写入 log_pull_config，门店同时保留在 _ai_extract
        作为字段映射兜底；版本号保留在同步对象的 detected_version_key 中，供后续版本中心解析。
        :param sync_object: 外部同步对象。
        :param extract_result: AI 规范化提取结果。
        :return: 回填后的同步对象及回填摘要。
        """
        result = extract_result if isinstance(extract_result, dict) else {}
        store = str(result.get("store") or "").strip()
        pos_no = SyncUtil.safe_int(result.get("posNo"))
        sco_no = SyncUtil.safe_int(result.get("scoNo"))
        log_date = TicketSyncPayloadService.normalize_auto_log_pull_date_text(result.get("logDate"))
        version_key = str(result.get("versionKey") or "").strip()

        log_pull_payload = (
            dict(sync_object.log_pull_config or {})
            if isinstance(sync_object.log_pull_config, dict)
            else {}
        )
        source_store_code = TicketStoreResolutionUtil.resolve_source_store_code(
            raw_payload=sync_object.raw_payload,
            extra_data=sync_object.extra_data,
            log_pull_config=log_pull_payload,
        )
        if source_store_code and source_store_code != TicketStoreResolutionUtil.normalize_store_value(
            log_pull_payload.get("sourceStoreCode")
        ):
            log_pull_payload["sourceStoreCode"] = source_store_code
            changed = True
        else:
            changed = False
        if pos_no:
            if SyncUtil.safe_int(log_pull_payload.get("posNo")) != pos_no:
                log_pull_payload["posNo"] = pos_no
                changed = True
        elif sco_no:
            if SyncUtil.safe_int(log_pull_payload.get("scoNo")) != sco_no:
                log_pull_payload["scoNo"] = sco_no
                changed = True
        if log_date:
            previous_date = TicketSyncPayloadService.normalize_auto_log_pull_date_text(
                log_pull_payload.get("modifyTime") or log_pull_payload.get("logDate")
            )
            if previous_date != log_date:
                log_pull_payload["modifyTime"] = log_date
                changed = True
        if store:
            source_store_code = TicketStoreResolutionUtil.normalize_store_value(
                log_pull_payload.get("sourceStoreCode")
            )
            existing_store_id = TicketStoreResolutionUtil.normalize_store_value(
                log_pull_payload.get("storeId")
            )
            selected_store_id, selection_reason = TicketStoreResolutionUtil.select_store_id(
                source_store_code=source_store_code,
                ai_store=store,
                existing_store_id=existing_store_id,
            )
            if selected_store_id and existing_store_id != selected_store_id:
                log_pull_payload["storeId"] = selected_store_id
                changed = True
        else:
            source_store_code = TicketStoreResolutionUtil.normalize_store_value(
                log_pull_payload.get("sourceStoreCode")
            )
            existing_store_id = TicketStoreResolutionUtil.normalize_store_value(
                log_pull_payload.get("storeId")
            )
            selected_store_id, selection_reason = TicketStoreResolutionUtil.select_store_id(
                source_store_code=source_store_code,
                ai_store="",
                existing_store_id=existing_store_id,
            )
            if selected_store_id and existing_store_id != selected_store_id:
                log_pull_payload["storeId"] = selected_store_id
                changed = True

        selected_store_id = TicketStoreResolutionUtil.normalize_store_value(
            log_pull_payload.get("storeId")
        )
        source_store_code = TicketStoreResolutionUtil.normalize_store_value(
            log_pull_payload.get("sourceStoreCode")
        )

        extra_data = dict(sync_object.extra_data or {}) if isinstance(sync_object.extra_data, dict) else {}
        ai_extract_payload = dict(extra_data.get("_ai_extract") or {})
        if selected_store_id and str(ai_extract_payload.get("store") or "").strip() != selected_store_id:
            ai_extract_payload["store"] = selected_store_id
            extra_data["_ai_extract"] = ai_extract_payload
            changed = True
        if changed and source_store_code:
            log_pull_payload["sourceStoreCode"] = source_store_code

        update_payload: dict[str, Any] = {}
        if changed:
            update_payload["log_pull_config"] = log_pull_payload
            update_payload["extra_data"] = extra_data
        if version_key and str(sync_object.detected_version_key or "").strip() != version_key:
            update_payload["detected_version_key"] = version_key
            changed = True
        if not changed:
            return sync_object, {"updated": False}

        updated_sync_object = sync_object.model_copy(update=update_payload)
        return updated_sync_object, {
            "updated": True,
            "logPullConfig": {
                "sourceStoreCode": source_store_code,
                "storeId": selected_store_id,
                "selectionReason": selection_reason,
                "posNo": SyncUtil.safe_int(log_pull_payload.get("posNo")),
                "scoNo": SyncUtil.safe_int(log_pull_payload.get("scoNo")),
                "modifyTime": TicketSyncPayloadService.normalize_auto_log_pull_date_text(
                    log_pull_payload.get("modifyTime")
                ),
            },
            "aiExtract": {
                "aiStore": store,
                "sourceStoreCode": source_store_code,
                "selectedStoreId": selected_store_id,
                "selectionReason": selection_reason,
                "versionKey": version_key,
            },
        }
