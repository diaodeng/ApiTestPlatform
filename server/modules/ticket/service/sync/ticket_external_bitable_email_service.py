import json
from typing import Any

from modules.ticket.entity.do.ticket_do import Ticket
from modules.ticket.entity.vo.ticket_vo import TicketExternalSyncUpsertModel
from modules.ticket.service.sync.ticket_sync_config_service import TicketSyncConfigService
from modules.ticket.service.sync.ticket_sync_notify_service import TicketSyncNotifyService
from modules.ticket.util.sync_util import SyncUtil
from modules.ticket.util.ticket_feishu_bitable_util import FeishuBitableUtil
from utils.log_util import logger


class TicketExternalBitableEmailService:
    """
    外部工单推送的飞书多维表格邮箱补齐服务。

    该服务只处理外部推送携带 recordId 后，按配置查询飞书多维表格人员字段并写入
    extra_data.external_field_mapping；不负责工单入库、状态流转或群推送。
    """

    @classmethod
    def build_external_sync_meta(cls, extra_data: dict[str, Any] | None) -> dict[str, Any]:
        """
        从工单 extra_data 中读取外部同步元数据。

        :param extra_data: 工单扩展字段。
        :return: external_sync 元数据；不存在时返回空字典。
        """
        source = extra_data if isinstance(extra_data, dict) else {}
        meta = source.get("external_sync") if isinstance(source.get("external_sync"), dict) else {}
        return dict(meta or {})

    @classmethod
    def query_record_fields(
        cls,
        config: dict[str, Any],
        *,
        record_id: str,
    ) -> dict[str, Any]:
        """
        根据外部推送 recordId 查询飞书多维表格记录字段。

        :param config: 同步自动化配置。
        :param record_id: 飞书多维表格记录 ID。
        :return: 记录 fields 字典，查询失败返回空字典。
        """
        bitable_config = TicketSyncConfigService.resolve_bitable_runtime_config(
            config,
            "externalSyncBitable",
            TicketSyncConfigService.default_external_sync_bitable_config(),
            keep_filter_formula=False,
        )
        if not bool(bitable_config.get("enabled")):
            logger.info("外部同步多维表格邮箱查询跳过: reason=externalSyncBitable 未启用")
            return {}
        app_id, app_secret = TicketSyncNotifyService.resolve_feishu_auth(bitable_config)
        app_token = str(bitable_config.get("appToken") or "").strip()
        table_id = str(bitable_config.get("tableId") or "").strip()
        normalized_record_id = str(record_id or "").strip()
        if not (app_id and app_secret and app_token and table_id and normalized_record_id):
            missing_items = []
            if not app_id:
                missing_items.append("appId")
            if not app_secret:
                missing_items.append("appSecret")
            if not app_token:
                missing_items.append("appToken")
            if not table_id:
                missing_items.append("tableId")
            if not normalized_record_id:
                missing_items.append("recordId")
            logger.info(
                f"外部同步多维表格邮箱查询跳过: reason=配置不完整, "
                f"missing={missing_items}, record_id={normalized_record_id or '-'}"
            )
            return {}
        try:
            logger.info(
                f"外部同步多维表格邮箱查询开始: record_id={normalized_record_id}, "
                f"app_token_configured={bool(app_token)}, table_id={table_id}"
            )
            token = TicketSyncNotifyService.get_tenant_access_token(app_id, app_secret)
            url = (
                f"{TicketSyncNotifyService.FEISHU_BASE_URL}/bitable/v1/apps/"
                f"{app_token}/tables/{table_id}/records/{normalized_record_id}"
            )
            response_data = TicketSyncNotifyService.request_feishu_json(
                method="GET",
                url=url,
                tenant_access_token=token,
            ).get("data") or {}
            record = response_data.get("record") if isinstance(response_data.get("record"), dict) else {}
            fields = record.get("fields") if isinstance(record.get("fields"), dict) else {}
            logger.info(
                f"外部同步多维表格邮箱查询完成: record_id={normalized_record_id}, "
                f"field_count={len(fields)}, field_names={list(fields.keys())[:100]}"
            )
            return fields
        except Exception as exc:
            logger.warning(f"外部同步多维表格记录查询失败: record_id={normalized_record_id}, error={exc}")
            return {}

    @classmethod
    def enrich_person_emails(
        cls,
        config: dict[str, Any],
        sync_object: TicketExternalSyncUpsertModel,
        existing_ticket: Ticket | None = None,
    ) -> TicketExternalSyncUpsertModel:
        """
        外部推送时按 recordId 查询多维表格人员邮箱，并写入 external_field_mapping 快照。

        :param config: 同步自动化配置。
        :param sync_object: 外部同步入库模型。
        :param existing_ticket: 已存在的工单，用于判断同一 recordId 是否已成功补齐过邮箱。
        :return: 补齐邮箱快照后的同步模型。
        """
        record_id = str(getattr(sync_object.source, "record_id", "") or "").strip()
        ticket_no = str(getattr(sync_object, "ticket_no", "") or "").strip()
        if not record_id:
            logger.info(
                f"外部同步多维表格邮箱补齐跳过: ticket_no={ticket_no or '-'}, "
                f"reason=外部推送未携带 recordId"
            )
            return sync_object
        existing_extra = (
            dict(getattr(existing_ticket, "extra_data", None) or {})
            if existing_ticket and isinstance(getattr(existing_ticket, "extra_data", None), dict)
            else {}
        )
        existing_meta = cls.build_external_sync_meta(existing_extra) if existing_extra else {}
        existing_bitable_sync = (
            existing_meta.get("bitableEmailSync")
            if isinstance(existing_meta.get("bitableEmailSync"), dict)
            else {}
        )
        if (
            str(existing_bitable_sync.get("status") or "").strip().lower() == "success"
            and str(existing_bitable_sync.get("recordId") or "").strip() == record_id
        ):
            logger.info(
                f"外部同步多维表格邮箱补齐跳过: ticket_no={ticket_no or '-'}, "
                f"record_id={record_id}, reason=已成功同步过同一 recordId"
            )
            return sync_object
        logger.info(
            f"外部同步多维表格邮箱补齐开始: ticket_no={ticket_no or '-'}, record_id={record_id}"
        )
        fields = cls.query_record_fields(config, record_id=record_id)
        if not fields:
            logger.info(
                f"外部同步多维表格邮箱补齐结束: ticket_no={ticket_no or '-'}, "
                f"record_id={record_id}, updated=false, reason=未获取到多维表格 fields"
            )
            return sync_object

        email_field_map = {
            "reporterEmail": "(IT) L1 PIC",
            "internalOwnerEmail": "1.5 当前负责人",
            "currentAssigneeEmail": "当前负责人",
        }
        email_map = {}
        extraction_logs: list[dict[str, Any]] = []
        for email_key, field_name in email_field_map.items():
            field_present = field_name in fields
            field_value = fields.get(field_name)
            email = FeishuBitableUtil.extract_email(field_value)
            if email:
                email_map[email_key] = email
                status = "success"
                reason = ""
            elif not field_present:
                status = "failed"
                reason = "field_not_found"
            else:
                status = "failed"
                reason = "email_empty_or_unparseable"
            extraction_logs.append(
                {
                    "emailKey": email_key,
                    "fieldName": field_name,
                    "fieldPresent": field_present,
                    "status": status,
                    "reason": reason,
                    "email": FeishuBitableUtil.mask_email_for_log(email),
                    "fieldSummary": FeishuBitableUtil.describe_field_value_for_log(field_value),
                }
            )
        logger.info(
            f"外部同步多维表格邮箱提取结果: ticket_no={ticket_no or '-'}, "
            f"record_id={record_id}, detail={json.dumps(extraction_logs, ensure_ascii=False)}"
        )
        email_map = {key: value for key, value in email_map.items() if value}
        if not email_map:
            logger.info(
                f"外部同步多维表格邮箱补齐结束: ticket_no={ticket_no or '-'}, "
                f"record_id={record_id}, updated=false, reason=三类邮箱均未提取成功"
            )
            return sync_object

        extra_data = dict(sync_object.extra_data or {}) if isinstance(sync_object.extra_data, dict) else {}
        external_mapping = (
            dict(extra_data.get("external_field_mapping"))
            if isinstance(extra_data.get("external_field_mapping"), dict)
            else {}
        )
        external_mapping.update(email_map)
        external_mapping["bitableRecordId"] = record_id
        external_mapping["bitableEmailFields"] = email_field_map
        external_mapping["bitableEmailSyncedAt"] = SyncUtil.now_iso()
        external_mapping["bitableEmailSyncStatus"] = "success"
        extra_data["external_field_mapping"] = external_mapping
        extra_data["_bitable_email_sync"] = {
            "status": "success",
            "recordId": record_id,
            "emailKeys": list(email_map.keys()),
            "syncedAt": external_mapping["bitableEmailSyncedAt"],
        }
        masked_emails = {key: FeishuBitableUtil.mask_email_for_log(value) for key, value in email_map.items()}
        logger.info(
            f"外部同步多维表格邮箱补齐结束: ticket_no={ticket_no or '-'}, "
            f"record_id={record_id}, updated=true, email_keys={list(email_map.keys())}, "
            f"masked_emails={masked_emails}"
        )
        return sync_object.model_copy(update={"extra_data": extra_data})
