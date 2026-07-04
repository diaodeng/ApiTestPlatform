"""
工单外部同步入库载荷构造服务。

只负责把外部同步模型、字段识别结果和历史工单合成为 Ticket 持久化 payload，
不执行 AI、通知、日志拉取等后续副作用。
"""
import re
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from module_admin.entity.vo.user_vo import CurrentUserModel
from module_hrm.entity.do.module_do import HrmModule
from module_hrm.entity.do.project_do import HrmProject
from module_hrm.enums.enums import QtrDataStatusEnum
from modules.ticket.entity.do.ticket_do import Ticket
from modules.ticket.entity.vo.ticket_vo import TicketExternalSyncUpsertModel
from modules.ticket.enums.ticket_enums import TicketStatus
from modules.ticket.service.ticket_sync_field_mapping_service import TicketSyncFieldMappingService
from modules.ticket.util.sync_util import SyncUtil
from modules.ticket.util.ticket_common_util import user_id as _user_id
from modules.ticket.util.ticket_common_util import user_name as _user_name


class TicketSyncPayloadService:
    """外部工单同步入库 payload 构造。"""

    SOURCE_CODE = "external_sync"
    META_KEY = "external_sync"
    PUBLISH_STATUS_READY = "ready"

    @classmethod
    def build_meta(cls, extra_data: dict[str, Any] | None) -> dict[str, Any]:
        """
        构造或补齐外部同步元数据。
        :param extra_data: 工单扩展字段。
        :return: 补齐默认同步状态后的 external_sync 元数据。
        """
        source = extra_data if isinstance(extra_data, dict) else {}
        meta = source.get(cls.META_KEY) if isinstance(source.get(cls.META_KEY), dict) else {}
        sync_state = meta.get("sync_state") if isinstance(meta.get("sync_state"), dict) else {}
        meta.setdefault("revision", 0)
        meta.setdefault("source", {})
        meta["sync_state"] = {
            "status": str(sync_state.get("status") or "pending"),
            "last_pulled_at": sync_state.get("last_pulled_at"),
            "last_consumer": sync_state.get("last_consumer"),
            "last_batch_id": sync_state.get("last_batch_id"),
            "consumers": sync_state.get("consumers") if isinstance(sync_state.get("consumers"), dict) else {},
            "automation": sync_state.get("automation") if isinstance(sync_state.get("automation"), dict) else {},
            "publish_ready": bool(sync_state.get("publish_ready", True)),
            "publish_status": str(sync_state.get("publish_status") or cls.PUBLISH_STATUS_READY),
            "publish_reason": str(sync_state.get("publish_reason") or "").strip(),
            "publish_updated_at": sync_state.get("publish_updated_at"),
            "ai_task_status": str(sync_state.get("ai_task_status") or "").strip(),
            "group_push_sent_once": bool(sync_state.get("group_push_sent_once", False)),
            "group_push_sent_at": sync_state.get("group_push_sent_at"),
            "group_push_scene": sync_state.get("group_push_scene"),
            "group_push_revision": sync_state.get("group_push_revision"),
            "group_push_processing": bool(sync_state.get("group_push_processing", False)),
            "group_push_processing_at": sync_state.get("group_push_processing_at"),
            "group_push_processing_scene": sync_state.get("group_push_processing_scene"),
            "group_push_processing_revision": sync_state.get("group_push_processing_revision"),
        }
        return meta

    @classmethod
    def attach_meta(cls, extra_data: dict[str, Any] | None, meta: dict[str, Any]) -> dict[str, Any]:
        """
        将同步元数据写回扩展字段。
        :param extra_data: 原始扩展字段。
        :param meta: external_sync 元数据。
        :return: 写入 external_sync 后的扩展字段。
        """
        payload = dict(extra_data or {})
        payload[cls.META_KEY] = meta
        return payload

    @classmethod
    def normalize_auto_log_pull_date_text(cls, value: Any) -> str:
        """
        将任意输入归一化为日志拉取日期（YYYY-MM-DD）。
        :param value: 原始日期值。
        :return: 标准日期文本，无法解析时返回空字符串。
        """
        if value in (None, "", []):
            return ""
        parsed = SyncUtil.parse_datetime_value(value)
        if parsed:
            return parsed.strftime("%Y-%m-%d")
        value_text = str(value).strip()
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value_text):
            return value_text
        if re.fullmatch(r"\d{4}/\d{2}/\d{2}", value_text):
            return value_text.replace("/", "-")
        return ""

    @classmethod
    def resolve_auto_log_pull_modify_time(
        cls,
        *,
        sync_object: TicketExternalSyncUpsertModel,
        log_pull_payload: dict[str, Any] | None,
    ) -> str:
        """
        解析自动拉日志使用的 modifyTime（日期）。
        :param sync_object: 外部同步模型。
        :param log_pull_payload: 当前日志拉取参数。
        :return: YYYY-MM-DD 日期文本，缺失时返回空字符串。
        """
        payload = log_pull_payload if isinstance(log_pull_payload, dict) else {}
        payload_candidate = (
            SyncUtil.payload_field_value(payload, "modifyTime", "modify_time", default="")
            or SyncUtil.payload_field_value(payload, "logDate", "log_date", default="")
            or SyncUtil.payload_field_value(payload, "ticketDate", "ticket_date", default="")
        )
        normalized_payload_date = cls.normalize_auto_log_pull_date_text(payload_candidate)
        if normalized_payload_date:
            return normalized_payload_date

        raw_payload = sync_object.raw_payload if isinstance(sync_object.raw_payload, dict) else {}
        for camel_key, snake_key in (
            ("modifyTime", "modify_time"),
            ("logDate", "log_date"),
            ("businessDate", "business_date"),
            ("ticketDate", "ticket_date"),
            ("occurDate", "occur_date"),
            ("date", "date"),
            ("createTime", "create_time"),
        ):
            candidate = SyncUtil.payload_field_value(raw_payload, camel_key, snake_key, default="")
            normalized_date = cls.normalize_auto_log_pull_date_text(candidate)
            if normalized_date:
                return normalized_date
        return cls.normalize_auto_log_pull_date_text(sync_object.create_time)

    @classmethod
    def build_upsert_payload(
        cls,
        db: Session,
        ticket: Ticket | None,
        sync_object: TicketExternalSyncUpsertModel,
        detected: dict[str, Any] | None,
        current_user: CurrentUserModel,
        sync_scene: str = "external_sync",
    ) -> tuple[dict[str, Any], dict[str, Any], int]:
        """
        构造 Ticket 创建或更新使用的 payload。
        :param db: 数据库会话。
        :param ticket: 历史工单，创建场景为空。
        :param sync_object: 外部同步模型。
        :param detected: 字段识别结果。
        :param current_user: 当前用户。
        :param sync_scene: 同步场景，支持 external_sync/remote_pull。
        :return: (payload, meta, revision)。
        """
        now = datetime.now()
        source_extra = dict(ticket.extra_data or {}) if ticket and isinstance(ticket.extra_data, dict) else {}
        extra_data = dict(source_extra)
        if isinstance(sync_object.extra_data, dict):
            # 防止远端拉取携带的 external_sync 覆盖本地同步状态（尤其是 group_push_sent_once）。
            incoming_extra_data = dict(sync_object.extra_data)
            incoming_extra_data.pop(cls.META_KEY, None)
            incoming_extra_data.pop("externalSync", None)
            extra_data.update(incoming_extra_data)
        if isinstance(sync_object.raw_payload, dict):
            extra_data["raw_payload"] = sync_object.raw_payload
        if str(getattr(sync_object, "step_reason", "") or "").strip():
            extra_data["step_reason"] = str(sync_object.step_reason or "").strip()

        meta = cls.build_meta(extra_data)
        revision = int(meta.get("revision") or 0) + 1
        external_create_time = cls.resolve_external_create_time(sync_object=sync_object, existing_meta=meta)
        remote_source_revision = SyncUtil.safe_int((sync_object.extra_data or {}).get("_remote_sync_revision"))
        if remote_source_revision is None:
            remote_source_revision = SyncUtil.safe_int(meta.get("sourceRevision"))
        resolved_ticket_url = (
            str(sync_object.ticket_url or "").strip()
            or str(sync_object.source.record_url or "").strip()
            or (str(getattr(ticket, "ticket_url", "") or "").strip() if ticket else "")
        )
        source_snapshot = {
            "system": sync_object.source.system,
            "recordId": sync_object.source.record_id,
            "recordUrl": sync_object.source.record_url,
            "ticketUrl": resolved_ticket_url or None,
            "pushedAt": (
                sync_object.source.pushed_at.isoformat()
                if sync_object.source.pushed_at
                else SyncUtil.now_iso()
            ),
            "externalCreateTime": external_create_time,
        }
        meta.update(
            {
                "revision": revision,
                "sourceSystem": sync_object.source.system,
                "sourceRecordId": sync_object.source.record_id,
                "sourceRecordUrl": sync_object.source.record_url,
                "ticketUrl": resolved_ticket_url or None,
                "lastImportedAt": SyncUtil.now_iso(),
                "externalCreateTime": external_create_time,
                "source": source_snapshot,
            }
        )
        if remote_source_revision is not None:
            meta["sourceRevision"] = remote_source_revision
        sync_state = meta.get("sync_state") if isinstance(meta.get("sync_state"), dict) else {}
        sync_state.setdefault("status", "pending")
        sync_state.setdefault("automation", {})
        meta["sync_state"] = sync_state

        is_remote_pull = sync_scene == "remote_pull"
        resolved_assignee_id = SyncUtil.safe_int((detected or {}).get("assigneeId"))
        resolved_assignee_name = str((detected or {}).get("assigneeName") or "").strip()
        sync_is_problem = getattr(sync_object, "is_problem", None)
        payload: dict[str, Any] = {
            "ticket_no": sync_object.ticket_no,
            "title": sync_object.title,
            "description": sync_object.description,
            "customer_priority": sync_object.customer_priority or (ticket.customer_priority if ticket else "P3"),
            "internal_priority": sync_object.internal_priority or (ticket.internal_priority if ticket else "P3"),
            "severity": sync_object.severity or (ticket.severity if ticket else ""),
            "source": cls.SOURCE_CODE,
            "issue_type_id": getattr(sync_object, "issue_type_id", None) or (ticket.issue_type_id if ticket else ""),
            "issue_type_name": getattr(sync_object, "issue_type_name", None)
            or (ticket.issue_type_name if ticket else ""),
            "reporter_id": sync_object.reporter_id or (ticket.reporter_id if ticket else _user_id(current_user)),
            "reporter_name": sync_object.reporter_name
            or (ticket.reporter_name if ticket else _user_name(current_user)),
            "current_assignee_id": (
                resolved_assignee_id
                if is_remote_pull and resolved_assignee_id
                else (
                    None
                    if is_remote_pull and resolved_assignee_name
                    else sync_object.current_assignee_id or (ticket.current_assignee_id if ticket else None)
                )
            ),
            "current_assignee_name": (
                resolved_assignee_name
                if is_remote_pull and resolved_assignee_name
                else sync_object.current_assignee_name or (ticket.current_assignee_name if ticket else "")
            ),
            "first_line_assignee_id": getattr(sync_object, "first_line_assignee_id", None)
            or (ticket.first_line_assignee_id if ticket else None),
            "first_line_assignee_name": getattr(sync_object, "first_line_assignee_name", None)
            or (ticket.first_line_assignee_name if ticket else ""),
            "internal_owner_id": getattr(sync_object, "internal_owner_id", None)
            or (ticket.internal_owner_id if ticket else None),
            "internal_owner_name": getattr(sync_object, "internal_owner_name", None)
            or (ticket.internal_owner_name if ticket else ""),
            "status": sync_object.status or (ticket.status if ticket else TicketStatus.PENDING.value),
            "is_problem": sync_is_problem if sync_is_problem is not None else (ticket.is_problem if ticket else None),
            "root_cause_type": getattr(sync_object, "root_cause_type", None)
            or (ticket.root_cause_type if ticket else ""),
            "solution_type": getattr(sync_object, "solution_type", None)
            or (ticket.solution_type if ticket else ""),
            "resolution_code": getattr(sync_object, "resolution_code", None)
            or (ticket.resolution_code if ticket else ""),
            "resolution_name": getattr(sync_object, "resolution_name", None)
            or (ticket.resolution_name if ticket else ""),
            "problem_pattern_code": getattr(sync_object, "problem_pattern_code", None)
            or (ticket.problem_pattern_code if ticket else ""),
            "problem_pattern_name": getattr(sync_object, "problem_pattern_name", None)
            or (ticket.problem_pattern_name if ticket else ""),
            "problem_pattern_confidence": getattr(sync_object, "problem_pattern_confidence", None)
            if getattr(sync_object, "problem_pattern_confidence", None) is not None
            else (ticket.problem_pattern_confidence if ticket else None),
            "problem_pattern_source": getattr(sync_object, "problem_pattern_source", None)
            or (ticket.problem_pattern_source if ticket else ""),
            "problem_pattern_verified": getattr(sync_object, "problem_pattern_verified", None)
            if getattr(sync_object, "problem_pattern_verified", None) is not None
            else (ticket.problem_pattern_verified if ticket else None),
            "root_cause": sync_object.root_cause or (ticket.root_cause if ticket else None),
            "solution": sync_object.solution or (ticket.solution if ticket else None),
            "tags": sync_object.tags or (ticket.tags if ticket else None),
            "ticket_url": resolved_ticket_url or None,
            "update_by": _user_name(current_user),
            "update_time": now,
        }

        project_id = SyncUtil.safe_int((detected or {}).get("projectId")) or (
            None if is_remote_pull else sync_object.project_id
        )
        module_id = SyncUtil.safe_int((detected or {}).get("moduleId")) or (
            None if is_remote_pull else sync_object.module_id
        )
        external_fields = TicketSyncFieldMappingService.extract_external_mapping_fields(sync_object)
        raw_project_name = str(
            sync_object.project_name
            or sync_object.merchant_name
            or str((detected or {}).get("projectName") or "").strip()
            or external_fields.get("ticketVender")
            or ""
        ).strip()
        incoming_project_name = (
            str((detected or {}).get("projectName") or "").strip()
            or str(sync_object.project_name or "").strip()
            or str(sync_object.merchant_name or "").strip()
            or str(external_fields.get("ticketVender") or "").strip()
        )
        incoming_project_value = TicketSyncFieldMappingService.has_incoming_project_value(sync_object, detected)
        if is_remote_pull and not (incoming_project_name or raw_project_name):
            incoming_project_value = False
        if project_id:
            project = (
                db.query(HrmProject)
                .filter(
                    HrmProject.project_id == project_id,
                    HrmProject.status == QtrDataStatusEnum.normal.value,
                    HrmProject.del_flag == "0",
                )
                .first()
            )
            if project:
                payload["project_id"] = project.project_id
                payload["merchant_name"] = project.project_name
            else:
                project_id = None
        if not project_id and incoming_project_value:
            # 本次同步携带了项目归属但未解析到有效本地项目时，清空旧ID并保留本次文本。
            payload["project_id"] = None
            payload["merchant_name"] = incoming_project_name or raw_project_name
        elif not project_id and ticket:
            payload["project_id"] = ticket.project_id
            payload["merchant_name"] = ticket.merchant_name
        elif not project_id:
            payload["merchant_name"] = (
                sync_object.project_name
                or sync_object.merchant_name
                or str((detected or {}).get("projectName") or "").strip()
                or ""
            )
        if raw_project_name and not str(payload.get("merchant_name") or "").strip():
            payload["merchant_name"] = raw_project_name

        if module_id:
            module_query = db.query(HrmModule).filter(
                HrmModule.module_id == module_id,
                HrmModule.status == QtrDataStatusEnum.normal.value,
            )
            if payload.get("project_id"):
                module_query = module_query.filter(HrmModule.project_id == payload.get("project_id"))
            module = module_query.first()
            if module:
                payload["module_id"] = module.module_id
                payload["module_name"] = module.module_name
            else:
                module_id = None
        module_name_fallback = (
            str((detected or {}).get("moduleName") or "").strip()
            or str(sync_object.module_name or "").strip()
            or str(external_fields.get("ticketModle") or "").strip()
            or (str(ticket.module_name or "").strip() if ticket else "")
        )
        incoming_module_name = (
            str((detected or {}).get("moduleName") or "").strip()
            or str(sync_object.module_name or "").strip()
            or str(external_fields.get("ticketModle") or "").strip()
        )
        incoming_module_value = TicketSyncFieldMappingService.has_incoming_module_value(sync_object, detected)
        if is_remote_pull and not incoming_module_name:
            incoming_module_value = False
        if not module_id and incoming_module_value:
            payload["module_id"] = None
            payload["module_name"] = incoming_module_name
        elif not module_id and ticket:
            payload["module_id"] = ticket.module_id
            payload["module_name"] = ticket.module_name
        elif not module_id:
            payload["module_name"] = (
                sync_object.module_name
                or str((detected or {}).get("moduleName") or "").strip()
                or ""
            )
        if module_name_fallback and not str(payload.get("module_name") or "").strip():
            payload["module_name"] = module_name_fallback
        if module_name_fallback:
            meta_source = meta.get("source") if isinstance(meta.get("source"), dict) else {}
            meta_source["moduleName"] = module_name_fallback
            meta["source"] = meta_source

        payload = cls.merge_external_text_fields(payload, detected or {}, sync_object)
        if is_remote_pull and resolved_assignee_name and not resolved_assignee_id:
            payload["current_assignee_id"] = None
        version_key = str((detected or {}).get("versionKey") or sync_object.version_key or "").strip()
        if version_key:
            extra_data["version_key"] = version_key

        log_pull_hints = (
            dict(extra_data.get("log_pull_hints") or {})
            if isinstance(extra_data.get("log_pull_hints"), dict)
            else {}
        )
        vendor_id_hint = SyncUtil.safe_int((detected or {}).get("vendorId"))
        store_id_hint = str((detected or {}).get("storeId") or "").strip()
        pos_no_hint = SyncUtil.safe_int((detected or {}).get("posNo")) or SyncUtil.safe_int(
            (detected or {}).get("scoNo")
        )
        modify_time_hint = cls.resolve_auto_log_pull_modify_time(
            sync_object=sync_object,
            log_pull_payload=sync_object.log_pull_config,
        )
        if vendor_id_hint:
            log_pull_hints["vendorId"] = vendor_id_hint
        elif incoming_project_value:
            log_pull_hints.pop("vendorId", None)
            log_pull_hints.pop("vendor_id", None)
        if store_id_hint:
            log_pull_hints["storeId"] = store_id_hint
        if pos_no_hint:
            log_pull_hints["posNo"] = pos_no_hint
        if modify_time_hint:
            log_pull_hints["modifyTime"] = modify_time_hint
        if log_pull_hints:
            extra_data["log_pull_hints"] = log_pull_hints

        bitable_email_sync = (
            dict(extra_data.pop("_bitable_email_sync"))
            if isinstance(extra_data.get("_bitable_email_sync"), dict)
            else {}
        )
        if bitable_email_sync:
            meta["bitableEmailSync"] = bitable_email_sync
        extra_data = cls.attach_meta(extra_data, meta)
        payload["extra_data"] = extra_data
        if not ticket:
            payload.update(
                {
                    "create_by": _user_name(current_user),
                    "create_time": now,
                }
            )
        payload["extra_data"] = extra_data
        return payload, meta, revision

    @classmethod
    def resolve_external_create_time(
        cls,
        *,
        sync_object: TicketExternalSyncUpsertModel,
        existing_meta: dict[str, Any] | None,
    ) -> str:
        """
        解析并固定外部工单创建时间。
        :param sync_object: 外部同步模型。
        :param existing_meta: 已存在的同步元数据。
        :return: ISO 格式创建时间文本。
        """
        current_meta = existing_meta if isinstance(existing_meta, dict) else {}
        source_snapshot = current_meta.get("source") if isinstance(current_meta.get("source"), dict) else {}
        existing_external_time = current_meta.get("externalCreateTime") or source_snapshot.get("externalCreateTime")
        parsed_existing = SyncUtil.parse_datetime_value(existing_external_time)
        if parsed_existing:
            return parsed_existing.isoformat()

        raw_payload = sync_object.raw_payload if isinstance(sync_object.raw_payload, dict) else {}
        parsed_candidate = (
            SyncUtil.parse_datetime_value(sync_object.create_time)
            or SyncUtil.parse_datetime_value(raw_payload.get("externalCreateTime"))
            or SyncUtil.parse_datetime_value(raw_payload.get("external_create_time"))
            or SyncUtil.parse_datetime_value(raw_payload.get("createTime"))
            or SyncUtil.parse_datetime_value(raw_payload.get("create_time"))
            or SyncUtil.parse_datetime_value(sync_object.source.pushed_at)
            or datetime.now()
        )
        return parsed_candidate.isoformat()

    @classmethod
    def merge_external_text_fields(
        cls,
        base_data: dict[str, Any],
        detected: dict[str, Any],
        sync_object: TicketExternalSyncUpsertModel,
    ) -> dict[str, Any]:
        """
        将识别出的外部文本字段合并到 Ticket payload 和同步来源快照。
        :param base_data: 已构造的 Ticket payload。
        :param detected: 字段识别结果。
        :param sync_object: 外部同步模型。
        :return: 合并后的 payload。
        """
        merged = dict(base_data)
        status_value = str(detected.get("status") or "").strip()
        assignee_id = SyncUtil.safe_int(detected.get("assigneeId"))
        assignee_name = str(detected.get("assigneeName") or "").strip()
        first_line_assignee_id = SyncUtil.safe_int(detected.get("firstLineAssigneeId"))
        first_line_assignee_name = str(detected.get("firstLineAssigneeName") or "").strip()
        internal_owner_id = SyncUtil.safe_int(detected.get("internalOwnerId"))
        internal_owner_name = str(detected.get("internalOwnerName") or "").strip()
        detected_module_name = str(detected.get("moduleName") or "").strip()
        if status_value:
            merged["status"] = status_value
        if assignee_id:
            merged["current_assignee_id"] = assignee_id
        if assignee_name:
            merged["current_assignee_name"] = assignee_name
        if first_line_assignee_id:
            merged["first_line_assignee_id"] = first_line_assignee_id
            merged["reporter_id"] = first_line_assignee_id
        if first_line_assignee_name:
            merged["first_line_assignee_name"] = first_line_assignee_name
            merged["reporter_name"] = first_line_assignee_name
        if internal_owner_id:
            merged["internal_owner_id"] = internal_owner_id
        if internal_owner_name:
            merged["internal_owner_name"] = internal_owner_name

        extra_data = dict(merged.get("extra_data") or {}) if isinstance(merged.get("extra_data"), dict) else {}
        external_sync = extra_data.get(cls.META_KEY) if isinstance(extra_data.get(cls.META_KEY), dict) else {}
        source_snapshot = external_sync.get("source") if isinstance(external_sync.get("source"), dict) else {}
        source_snapshot.update(
            {
                "status": status_value or source_snapshot.get("status"),
                "assigneeId": assignee_id or source_snapshot.get("assigneeId"),
                "assigneeName": assignee_name or source_snapshot.get("assigneeName"),
                "firstLineAssigneeId": first_line_assignee_id or source_snapshot.get("firstLineAssigneeId"),
                "firstLineAssigneeName": first_line_assignee_name or source_snapshot.get("firstLineAssigneeName"),
                "internalOwnerId": internal_owner_id or source_snapshot.get("internalOwnerId"),
                "internalOwnerName": internal_owner_name or source_snapshot.get("internalOwnerName"),
                "ticketUrl": str(sync_object.ticket_url or "").strip() or source_snapshot.get("ticketUrl"),
                "projectName": str(sync_object.project_name or "").strip() or source_snapshot.get("projectName"),
                "moduleName": str(sync_object.module_name or "").strip()
                or detected_module_name
                or source_snapshot.get("moduleName"),
                "vendorId": SyncUtil.safe_int(detected.get("vendorId")) or source_snapshot.get("vendorId"),
                "vendorName": str(detected.get("vendorName") or "").strip() or source_snapshot.get("vendorName"),
                "storeId": str(detected.get("storeId") or "").strip() or source_snapshot.get("storeId"),
                "storeName": str(detected.get("storeName") or "").strip() or source_snapshot.get("storeName"),
                "posNo": SyncUtil.safe_int(detected.get("posNo")) or source_snapshot.get("posNo"),
                "scoNo": SyncUtil.safe_int(detected.get("scoNo")) or source_snapshot.get("scoNo"),
            }
        )
        external_sync["source"] = source_snapshot
        extra_data[cls.META_KEY] = external_sync
        merged["extra_data"] = extra_data
        return merged
