"""
外部工单同步请求读取与归一化服务。

只负责把 HTTP 请求体或扁平 payload 转换为 `TicketExternalSyncUpsertModel` 可校验的字典，
不执行入库、AI、通知或数据库副作用。
"""
import json
from typing import Any

from fastapi import HTTPException, Request

from modules.ticket.service.sync.ticket_sync_config_service import TicketSyncConfigService
from utils.field_util import compatible_field_value, extract_person_name_email, normalize_email_text
from utils.log_util import logger


class TicketExternalSyncRequestService:
    """外部同步请求读取与字段归一化。"""

    @classmethod
    def normalize_external_sync_payload(
        cls,
        payload: dict[str, Any] | None,
        required_fields: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        将外部同步请求体归一化为内部同步模型入参。
        :param payload: 外部请求体，仅支持约定字段的驼峰/下划线写法。
        :param required_fields: 必填字段列表，未传时使用默认外部同步契约。
        :return: 可用于 TicketExternalSyncUpsertModel 校验的字典。
        """
        data = dict(payload or {})
        raw_payload = dict(data)

        source = data.get("source") if isinstance(data.get("source"), dict) else {}
        ticket_no = str(compatible_field_value(data, "ticketNo", "ticket_no", default="") or "").strip()
        description = str(compatible_field_value(data, "description", "description", default="") or "").strip()
        internal_priority = str(
            compatible_field_value(data, "internalPriority", "internal_priority", default="") or ""
        ).strip()
        customer_priority = str(
            compatible_field_value(
                data,
                "customerPriority",
                "customer_priority",
                default=internal_priority,
            )
            or ""
        ).strip()
        ticket_vender = str(compatible_field_value(data, "ticketVender", "ticket_vender", default="") or "").strip()
        ticket_modle = str(compatible_field_value(data, "ticketModle", "ticket_modle", default="") or "").strip()
        create_time = compatible_field_value(data, "createTime", "create_time")
        reporter_raw = compatible_field_value(data, "reporterName", "reporter_name", default="")
        reporter_name, reporter_email_from_name = extract_person_name_email(reporter_raw)
        reporter_email = normalize_email_text(
            compatible_field_value(data, "reporterEmail", "reporter_email", default="")
        ) or reporter_email_from_name
        current_assignee_raw = compatible_field_value(
            data,
            "currentAssigneeName",
            "current_assignee_name",
            default=compatible_field_value(data, "ticketAssignee", "ticket_assignee", default=""),
        )
        current_assignee_name, current_assignee_email_from_name = extract_person_name_email(current_assignee_raw)
        current_assignee_email = normalize_email_text(
            compatible_field_value(
                data,
                "currentAssigneeEmail",
                "current_assignee_email",
                default=compatible_field_value(data, "ticketAssigneeEmail", "ticket_assignee_email", default=""),
            )
        ) or current_assignee_email_from_name
        internal_owner_raw = compatible_field_value(
            data,
            "internalOwner",
            "internal_owner",
            default=compatible_field_value(data, "internalOwnerName", "internal_owner_name", default=""),
        )
        internal_owner_name, internal_owner_email_from_name = extract_person_name_email(internal_owner_raw)
        internal_owner_email = normalize_email_text(
            compatible_field_value(data, "internalOwnerEmail", "internal_owner_email", default="")
        ) or internal_owner_email_from_name
        title = str(compatible_field_value(data, "title", "title", default="") or "").strip()
        reason = str(compatible_field_value(data, "reason", "reason", default="") or "").strip()
        step_reason = str(compatible_field_value(data, "stepReason", "step_reason", default="") or "").strip()
        ticket_url = str(
            compatible_field_value(
                data,
                "ticketUrl",
                "ticket_url",
            )
            or ""
        ).strip() or None

        field_value_map = {
            "ticketNo": ticket_no,
            "description": description,
            "title": title,
            "customerPriority": customer_priority,
            "internalPriority": internal_priority,
            "ticketVender": ticket_vender,
            "ticketModle": ticket_modle,
            "ticketStatus": str(
                compatible_field_value(data, "ticketStatus", "ticket_status", default="") or ""
            ).strip(),
            "ticketStore": compatible_field_value(data, "ticketStore", "ticket_store", default=""),
            "ticketPos": str(compatible_field_value(data, "ticketPos", "ticket_pos", default="") or "").strip(),
            "ticketSco": str(compatible_field_value(data, "ticketSco", "ticket_sco", default="") or "").strip(),
            "createTime": create_time,
            "reporterName": reporter_name,
            "reporterEmail": reporter_email,
            "currentAssigneeName": current_assignee_name,
            "currentAssigneeEmail": current_assignee_email,
            "internalOwner": internal_owner_name,
            "internalOwnerEmail": internal_owner_email,
            "ticketUrl": ticket_url,
            "recordId": str(compatible_field_value(data, "recordId", "record_id", default="") or "").strip(),
            "reason": reason,
            "stepReason": step_reason,
        }
        normalized_required_fields = cls.normalize_required_fields(required_fields)
        missing_fields = [field for field in normalized_required_fields if field_value_map.get(field) in (None, "", [])]
        if missing_fields:
            raise ValueError(f"外部同步缺少必填字段: {', '.join(missing_fields)}")

        record_id = str(compatible_field_value(data, "recordId", "record_id", default=ticket_no) or "").strip()
        if not record_id:
            record_id = ticket_no
        record_url = str(
            compatible_field_value(
                data,
                "ticketUrl",
                "ticket_url",
            )
            or ""
        ).strip() or None

        source_system = compatible_field_value(source, "system", "system", default="")
        if not source_system:
            source_system = ticket_vender or "external"

        assignee_name, assignee_email_from_name = extract_person_name_email(current_assignee_raw)
        assignee_email = current_assignee_email or assignee_email_from_name

        external_field_mapping = {
            "ticketVender": ticket_vender,
            "ticketModle": ticket_modle,
            "ticketStatus": str(
                compatible_field_value(data, "ticketStatus", "ticket_status", default="") or ""
            ).strip(),
            "ticketStore": str(compatible_field_value(data, "ticketStore", "ticket_store", default="") or "").strip(),
            "ticketAssignee": assignee_name,
            "ticketAssigneeEmail": assignee_email,
            "currentAssigneeName": current_assignee_name,
            "currentAssigneeEmail": current_assignee_email,
            "internalOwner": internal_owner_name,
            "internalOwnerEmail": internal_owner_email,
            "reporterName": reporter_name,
            "reporterEmail": reporter_email,
            "ticketPos": str(compatible_field_value(data, "ticketPos", "ticket_pos", default="") or "").strip(),
            "ticketSco": str(compatible_field_value(data, "ticketSco", "ticket_sco", default="") or "").strip(),
            "stepReason": step_reason,
        }
        external_field_mapping = {
            key: value
            for key, value in external_field_mapping.items()
            if value not in (None, "", [])
        }

        extra_data = data.get("extraData") if isinstance(data.get("extraData"), dict) else {}
        if not extra_data and isinstance(data.get("extra_data"), dict):
            extra_data = data.get("extra_data")
        extra_data = dict(extra_data or {})
        if external_field_mapping:
            extra_data["external_field_mapping"] = external_field_mapping
        if step_reason:
            extra_data["step_reason"] = step_reason

        data["source"] = {
            "system": str(source_system or "").strip() or "external",
            "recordId": record_id,
            "recordUrl": record_url,
            "pushedAt": compatible_field_value(source, "pushedAt", "pushed_at", default=None),
        }
        data["ticketNo"] = ticket_no
        data["description"] = description
        data["internalPriority"] = internal_priority
        data["customerPriority"] = customer_priority or internal_priority
        data["ticketVender"] = ticket_vender
        data["ticketModle"] = ticket_modle
        data["createTime"] = create_time
        data["reporterName"] = reporter_name
        data["reporterEmail"] = reporter_email
        data["firstLineAssigneeName"] = reporter_name
        data["currentAssigneeName"] = current_assignee_name
        data["internalOwnerName"] = internal_owner_name
        data["title"] = title
        data["reason"] = reason
        data["stepReason"] = step_reason
        data["ticketUrl"] = ticket_url
        data["extraData"] = extra_data
        if raw_payload:
            data["raw_payload"] = raw_payload
        return data

    @classmethod
    def normalize_required_fields(cls, required_fields: list[str] | None = None) -> list[str]:
        """
        归一化外部同步必填字段列表。
        :param required_fields: 可选配置字段列表。
        :return: 去重后的必填字段列表。
        """
        normalized_required_fields: list[str] = []
        for item in required_fields or TicketSyncConfigService.DEFAULT_EXTERNAL_SYNC_REQUIRED_FIELDS:
            field_name = str(item or "").strip()
            if field_name and field_name not in normalized_required_fields:
                normalized_required_fields.append(field_name)
        return normalized_required_fields

    @staticmethod
    async def load_external_sync_payload(request: Request) -> dict[str, Any]:
        """
        读取外部工单同步请求体，兼容 JSON 和表单提交。
        :param request: 当前请求对象。
        :return: 原始请求数据字典。
        """
        content_type = (request.headers.get("content-type") or "").lower()
        raw_payload: dict[str, Any] | None = None
        if "multipart/form-data" in content_type or "application/x-www-form-urlencoded" in content_type:
            form_data = await request.form()
            raw_payload = dict(form_data.multi_items())
        else:
            try:
                body = await request.json()
            except Exception:
                body = None
            if isinstance(body, dict):
                raw_payload = body
            else:
                try:
                    body_bytes = await request.body()
                    if body_bytes:
                        raw_payload = json.loads(body_bytes.decode("utf-8"))
                except Exception:
                    raw_payload = None

        if not isinstance(raw_payload, dict):
            raise HTTPException(status_code=422, detail="请求体必须是 JSON 或表单数据")
        logger.info(f"请求参数:{json.dumps(raw_payload, ensure_ascii=False)}")
        return raw_payload
