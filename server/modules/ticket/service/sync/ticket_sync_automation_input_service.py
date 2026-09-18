"""
工单同步自动化输入服务。

统一解析自动拉日志和自动 AI 所需的运行时参数，避免 identify、日志请求和
自动 AI 分别从不同字段拼装出不一致的结果。
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from modules.ticket.entity.vo.ticket_vo import TicketExternalSyncUpsertModel
from modules.ticket.service.sync.ticket_sync_field_mapping_service import TicketSyncFieldMappingService
from modules.ticket.service.sync.ticket_sync_payload_service import TicketSyncPayloadService
from modules.ticket.util.sync_util import SyncUtil
from modules.ticket.util.ticket_store_resolution_util import TicketStoreResolutionUtil
from utils.log_util import logger


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
        for key in (
            "environment",
            "path",
            "commandDataType",
            "fileMaxSize",
            "zipMaxSize",
            "storageMode",
        ):
            value = cls._value(source, key)
            if value not in (None, ""):
                result[key] = str(value).strip() if key in {"environment", "path", "storageMode"} else value
        return result

    @classmethod
    def _map_ai_store_to_org_no(
        cls,
        db: Session,
        *,
        ai_result: dict[str, Any],
        detected_config: dict[str, Any],
        hints: dict[str, Any],
        sync_config: dict[str, Any],
        config: dict[str, Any],
    ) -> None:
        """
        将 AI 提取的外部门店编码按门店配置映射为日志接口 org_no（原地更新 ai_result）。

        背景（回归场景 INC00001988278）：AI 统一提取的 store 是外部门店编码（如 8555），
        而字段识别 detected.storeId 已通过门店配置映射为内部 org_no（如 558464）；
        运行参数合并优先级 AI 高于 detected/hints，直接合并会用外部编码覆盖 org_no，
        导致提交前门店校验失败、自动拉日志被跳过。

        实现过程：
        1. 商家ID优先取字段识别结果，其次已落库 hints 与任务级 logPullConfig；
        2. 环境取 logPullDefaults.environment 的分组部分（冒号前），与 detect_fields 的门店映射口径一致；
        3. 调用 resolve_store_by_external_value 按 sap_org_no → org_no 唯一候选映射；
           商家未知或候选不唯一时返回原值，不视为映射成功，交由提交前门店校验拦截；
        4. 映射成功时写入 aiStoreMappedFrom 保留原始编码，供自动化审计追溯。

        :param db: 数据库会话
        :param ai_result: AI 统一提取结果（原地修改 storeId）
        :param detected_config: 字段识别结果
        :param hints: 工单已落库的日志拉取提示快照
        :param sync_config: 任务级日志拉取配置
        :param config: 同步自动化全局配置
        :return: 无
        """
        ai_store = str(ai_result.get("storeId") or "").strip()
        if not ai_store:
            return
        vendor_id = (
            SyncUtil.safe_int(detected_config.get("vendorId"))
            or SyncUtil.safe_int(hints.get("vendorId"))
            or SyncUtil.safe_int(sync_config.get("vendorId"))
        )
        environment = str(
            (config.get("logPullDefaults") or {}).get("environment") or ""
        ).strip().split(":", 1)[0].strip()
        mapped_store_id, _ = TicketSyncFieldMappingService.resolve_store_by_external_value(
            db,
            vendor_id=vendor_id,
            ticket_store=ai_store,
            environment=environment,
        )
        if mapped_store_id and mapped_store_id != ai_store:
            ai_result["aiStoreMappedFrom"] = ai_store
            ai_result["storeId"] = mapped_store_id
            logger.info(
                f"自动拉日志运行参数：AI提取门店[{ai_store}]已按门店配置映射为org_no[{mapped_store_id}]，"
                f"vendorId={vendor_id}, environment={environment or '未配置'}"
            )

    @classmethod
    def resolve_runtime_config(
        cls,
        *,
        db: Session | None = None,
        config: dict[str, Any],
        automation: Any,
        sync_object: TicketExternalSyncUpsertModel,
        detected: dict[str, Any] | None,
        ticket_id: int,
        ticket_extra_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        按固定优先级合并自动拉日志运行参数。
        :param db: 数据库会话，提供时会把 AI 提取的门店编码映射为内部 org_no；为 None 时跳过映射（仅测试场景）
        :param config: 同步自动化全局配置
        :param automation: 任务级自动化配置
        :param sync_object: 外部同步模型
        :param detected: 字段识别结果
        :param ticket_id: 工单ID
        :param ticket_extra_data: 工单已落库扩展字段
        :return: 合并后的运行参数
        """
        defaults = cls._canonicalize(config.get("logPullDefaults"))
        hints = {}
        if isinstance(ticket_extra_data, dict):
            hints = cls._canonicalize(ticket_extra_data.get("log_pull_hints"))
        elif isinstance(sync_object.extra_data, dict):
            hints = cls._canonicalize(sync_object.extra_data.get("log_pull_hints"))
        sync_config = cls._canonicalize(sync_object.log_pull_config)
        detected_config = cls._canonicalize(detected)
        detected_store_mapping_ambiguous = bool(
            isinstance(detected, dict) and detected.get("storeMappingAmbiguous")
        )
        detected_store_mapping_candidates = (
            detected.get("storeMappingCandidates")
            if isinstance(detected, dict) and isinstance(detected.get("storeMappingCandidates"), list)
            else []
        )
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
        # AI 提取的门店是外部门店编码，与字段识别映射出的内部 org_no 不同命名空间；
        # 合并优先级 AI 高于 detected/hints，直接合并会用外部编码覆盖 org_no，
        # 导致提交前门店校验失败而跳过自动拉日志（回归场景 INC00001988278）。
        # 因此合并前先把 AI 门店按门店配置映射为 org_no，映射失败时保留原值交由校验拦截。
        if db is not None and ai_result.get("storeId"):
            cls._map_ai_store_to_org_no(
                db,
                ai_result=ai_result,
                detected_config=detected_config,
                hints=hints,
                sync_config=sync_config,
                config=config,
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
        if detected_store_mapping_ambiguous:
            # 同一商家和外部编码命中多个 org_no 时必须中断自动提交，不能静默采用历史或任务参数。
            merged.pop("storeId", None)
            merged["storeMappingAmbiguous"] = True
            merged["storeMappingCandidates"] = detected_store_mapping_candidates
            merged["storeSelectionReason"] = "ambiguous_external_store_mapping"
        elif source_store_code:
            detected_store_id = TicketStoreResolutionUtil.normalize_store_value(detected_config.get("storeId"))
            ai_store = ai_result.get("storeId")
            existing_store_id = sync_config.get("storeId") or hints.get("storeId") or detected_store_id
            if "storeId" not in task_config and detected_store_id and detected_store_id != source_store_code:
                # 字段识别已将外部编码映射为日志接口 org_no，不能再被原始来源编码覆盖。
                merged["storeId"] = detected_store_id
                merged["storeSelectionReason"] = "detected_mapped_store_id"
            else:
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
