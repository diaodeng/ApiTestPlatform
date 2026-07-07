"""
工单同步字段识别与自动化执行服务。

负责外部同步入库后的项目/模块/人员/门店/版本号识别，以及相似工单、自动拉日志、
自动 AI 分析等同步自动化步骤。
"""
import re
from datetime import datetime
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from module_admin.entity.vo.user_vo import CurrentUserModel
from module_hrm.entity.do.module_do import HrmModule
from module_hrm.entity.do.project_do import HrmProject
from module_hrm.enums.enums import QtrDataStatusEnum
from modules.ticket.dao.ticket_dao import TicketDao
from modules.ticket.entity.do.ticket_do import Ticket
from modules.ticket.entity.vo.ticket_log_pull_vo import TicketLogPullCreateModel
from modules.ticket.entity.vo.ticket_vo import TicketAiAnalysisRequestModel, TicketExternalSyncUpsertModel
from modules.ticket.service.ai.ticket_ai_analysis_service import TicketAiAnalysisService
from modules.ticket.service.ai.ticket_embedding_service import TicketEmbeddingService
from modules.ticket.service.log_pull.ticket_log_pull_service import TicketLogPullService
from modules.ticket.service.sync.ticket_sync_config_service import TicketSyncConfigService
from modules.ticket.service.sync.ticket_sync_field_mapping_service import TicketSyncFieldMappingService
from modules.ticket.service.sync.ticket_sync_payload_service import TicketSyncPayloadService
from modules.ticket.util.sync_util import SyncUtil
from modules.ticket.util.ticket_common_util import extract_ticket_version_key as _extract_ticket_version_key
from modules.ticket.util.ticket_common_util import user_name as _user_name
from utils.log_util import logger


class TicketSyncAutomationService:
    """工单同步字段识别与自动化执行。"""

    @classmethod
    def collect_text(cls, payload: TicketExternalSyncUpsertModel | Ticket) -> str:
        """
        收集用于字段识别和相似检索的工单文本。
        :param payload: 外部同步模型或工单对象。
        :return: 拼接后的文本。
        """
        if isinstance(payload, Ticket):
            extra_data = payload.extra_data if isinstance(payload.extra_data, dict) else {}
            raw_payload = extra_data.get("raw_payload")
            parts = [
                payload.ticket_no,
                payload.title,
                payload.description,
                payload.merchant_name,
                payload.module_name,
                payload.root_cause,
                payload.solution,
                SyncUtil.json_dumps(raw_payload) if isinstance(raw_payload, dict) else "",
            ]
        else:
            parts = [
                payload.ticket_no,
                payload.title,
                payload.description,
                payload.project_name,
                payload.merchant_name,
                payload.module_name,
                payload.root_cause,
                payload.solution,
                SyncUtil.json_dumps(payload.raw_payload) if isinstance(payload.raw_payload, dict) else "",
                SyncUtil.json_dumps(payload.extra_data) if isinstance(payload.extra_data, dict) else "",
            ]
        return "\n".join(str(item).strip() for item in parts if str(item or "").strip())

    @classmethod
    def extract_pattern(cls, text: str, patterns: Any) -> str | None:
        """
        按正则列表提取第一个命中值。
        :param text: 待匹配文本。
        :param patterns: 正则表达式列表。
        :return: 第一个分组或完整匹配值。
        """
        if not isinstance(patterns, list):
            return None
        for pattern in patterns:
            try:
                matched = re.search(str(pattern), text, flags=re.IGNORECASE)
            except re.error:
                continue
            if not matched:
                continue
            if matched.groups():
                return str(matched.group(1)).strip()
            return str(matched.group(0)).strip()
        return None

    @classmethod
    def detect_fields(
        cls,
        db: Session,
        sync_object: TicketExternalSyncUpsertModel,
        config: dict[str, Any],
        apply_external_mappings: bool = True,
    ) -> dict[str, Any]:
        """
        解析同步入库所需的内部字段。
        :param db: 数据库会话。
        :param sync_object: 同步入库模型。
        :param config: 同步配置。
        :param apply_external_mappings: 是否应用外部字段映射。
        :return: 标准化后的内部字段候选值。
        """
        text = cls.collect_text(sync_object).lower()
        external_fields = TicketSyncFieldMappingService.extract_external_mapping_fields(sync_object)
        ticket_vender = external_fields.get("ticketVender") or ""
        ticket_modle = external_fields.get("ticketModle") or ""
        ticket_status = external_fields.get("ticketStatus") or ""
        ticket_store = external_fields.get("ticketStore") or ""
        ticket_assignee = external_fields.get("ticketAssignee") or ""
        current_assignee = external_fields.get("currentAssigneeName") or ticket_assignee
        current_assignee_email = (
            external_fields.get("currentAssigneeEmail")
            or external_fields.get("ticketAssigneeEmail")
            or ""
        )
        reporter_person = (
            external_fields.get("reporterName")
            or str(getattr(sync_object, "reporter_name", "") or "").strip()
        )
        reporter_email = external_fields.get("reporterEmail") or ""
        internal_owner = (
            external_fields.get("internalOwner")
            or str(getattr(sync_object, "internal_owner_name", "") or "").strip()
        )
        internal_owner_email = external_fields.get("internalOwnerEmail") or ""
        ticket_pos = external_fields.get("ticketPos") or ""
        ticket_sco = external_fields.get("ticketSco") or ""
        extra_data = sync_object.extra_data if isinstance(sync_object.extra_data, dict) else {}
        raw_payload = sync_object.raw_payload if isinstance(sync_object.raw_payload, dict) else {}
        mapping_payload = (
            extra_data.get("external_field_mapping")
            if isinstance(extra_data.get("external_field_mapping"), dict)
            else {}
        )
        log_pull_hints = extra_data.get("log_pull_hints") if isinstance(extra_data.get("log_pull_hints"), dict) else {}
        if not isinstance(log_pull_hints, dict):
            log_pull_hints = {}

        project = None
        project_name_by_vendor = ""
        raw_project_name = str(sync_object.project_name or sync_object.merchant_name or ticket_vender or "").strip()
        if apply_external_mappings and ticket_vender:
            project, project_name_by_vendor = TicketSyncFieldMappingService.resolve_project_by_ticket_vender(
                db,
                ticket_vender=ticket_vender,
                project_mappings=config.get("projectMappings") or [],
            )
        if not project and str(sync_object.project_code or "").strip():
            project = (
                db.query(HrmProject)
                .filter(
                    HrmProject.project_code == str(sync_object.project_code).strip(),
                    HrmProject.status == QtrDataStatusEnum.normal.value,
                    HrmProject.del_flag == "0",
                )
                .first()
            )
        if apply_external_mappings and not project and sync_object.project_id:
            project = (
                db.query(HrmProject)
                .filter(
                    HrmProject.project_id == sync_object.project_id,
                    HrmProject.status == QtrDataStatusEnum.normal.value,
                    HrmProject.del_flag == "0",
                )
                .first()
            )

        module = None
        if apply_external_mappings:
            module = TicketSyncFieldMappingService.resolve_module_by_ticket_modle(
                db,
                ticket_modle=ticket_modle,
                project_id=getattr(project, "project_id", None),
                module_mappings=config.get("moduleMappings") or [],
            )
        if not module and str(sync_object.module_code or "").strip():
            module_query = db.query(HrmModule).filter(
                func.lower(HrmModule.module_code) == str(sync_object.module_code).strip().lower(),
                HrmModule.status == QtrDataStatusEnum.normal.value,
            )
            if getattr(project, "project_id", None):
                module_query = module_query.filter(HrmModule.project_id == getattr(project, "project_id", None))
            module = module_query.first()
        if not module and apply_external_mappings and str(sync_object.module_name or "").strip():
            module = TicketSyncFieldMappingService.resolve_module_by_ticket_modle(
                db,
                ticket_modle=str(sync_object.module_name or "").strip(),
                project_id=getattr(project, "project_id", None),
                module_mappings=config.get("moduleMappings") or [],
            )
        if apply_external_mappings and not module and sync_object.module_id:
            module_query = db.query(HrmModule).filter(
                HrmModule.module_id == sync_object.module_id,
                HrmModule.status == QtrDataStatusEnum.normal.value,
            )
            if getattr(project, "project_id", None):
                module_query = module_query.filter(HrmModule.project_id == getattr(project, "project_id", None))
            module = module_query.first()

        if apply_external_mappings:
            vendor_id, vendor_name = TicketSyncFieldMappingService.resolve_vendor_by_ticket_vender(
                ticket_vender=ticket_vender,
                vendor_mappings=config.get("vendorMappings") or [],
            )
        else:
            vendor_id, vendor_name = None, ""
        if apply_external_mappings and not vendor_id:
            vendor_id = TicketSyncFieldMappingService.resolve_vendor_by_project(
                db,
                project_id=getattr(project, "project_id", None),
            )
        if not vendor_id:
            vendor_id = SyncUtil.safe_int(log_pull_hints.get("vendorId") or log_pull_hints.get("vendor_id"))
        if not vendor_id:
            vendor_id = SyncUtil.safe_int((sync_object.log_pull_config or {}).get("vendorId"))
        if vendor_id and not vendor_name:
            vendor_name = (
                ticket_vender
                or project_name_by_vendor
                or str(getattr(project, "project_name", "") or "").strip()
            )
        if apply_external_mappings:
            store_id, store_name = TicketSyncFieldMappingService.resolve_store_by_external_value(
                db,
                vendor_id=vendor_id,
                ticket_store=ticket_store,
            )
        else:
            store_id, store_name = "", ""
        if not store_name:
            store_name = str(log_pull_hints.get("storeName") or log_pull_hints.get("store_name") or "").strip()
        if not store_id:
            store_id = str(log_pull_hints.get("storeId") or log_pull_hints.get("store_id") or "").strip()
        if not store_id:
            store_id = str((sync_object.log_pull_config or {}).get("storeId") or "").strip()
        if apply_external_mappings:
            status_code = TicketSyncFieldMappingService.resolve_status_by_external_value(
                status_text=ticket_status or str(sync_object.status or "").strip(),
                status_mappings=config.get("statusMappings") or [],
            )
            assignee_id, assignee_name = TicketSyncFieldMappingService.resolve_external_person_by_mapping_or_email(
                db,
                person_text=current_assignee or str(sync_object.current_assignee_name or "").strip(),
                person_email=current_assignee_email,
                assignee_mappings=config.get("assigneeMappings") or [],
            )
            (
                first_line_assignee_id,
                first_line_assignee_name,
            ) = TicketSyncFieldMappingService.resolve_external_person_by_mapping_or_email(
                db,
                person_text=reporter_person,
                person_email=reporter_email,
                assignee_mappings=config.get("assigneeMappings") or [],
            )
            (
                internal_owner_id,
                internal_owner_name,
            ) = TicketSyncFieldMappingService.resolve_external_person_by_mapping_or_email(
                db,
                person_text=internal_owner,
                person_email=internal_owner_email,
                assignee_mappings=config.get("assigneeMappings") or [],
            )
        else:
            # 远端拉取不复用公网项目/模块/用户 ID，但状态与人员文本仍允许按内网本地配置映射。
            status_code = TicketSyncFieldMappingService.resolve_status_by_external_value(
                status_text=ticket_status or str(sync_object.status or "").strip(),
                status_mappings=config.get("statusMappings") or [],
            )
            assignee_email = str(
                current_assignee_email or SyncUtil.payload_field_value(
                    raw_payload,
                    "currentAssigneeEmail",
                    "current_assignee_email",
                    default=SyncUtil.payload_field_value(
                        raw_payload,
                        "ticketAssigneeEmail",
                        "ticket_assignee_email",
                        default=SyncUtil.payload_field_value(
                            raw_payload,
                            "assigneeEmail",
                            "assignee_email",
                            default=SyncUtil.payload_field_value(
                                mapping_payload,
                                "ticketAssigneeEmail",
                                "ticket_assignee_email",
                                default="",
                            ),
                        ),
                    ),
                )
                or ""
            ).strip()
            assignee_name = ticket_assignee or str(sync_object.current_assignee_name or "").strip()
            assignee_id, assignee_name = TicketSyncFieldMappingService.resolve_external_person_by_mapping_or_email(
                db,
                person_text=assignee_name,
                person_email=assignee_email,
                assignee_mappings=config.get("assigneeMappings") or [],
            )
            (
                first_line_assignee_id,
                first_line_assignee_name,
            ) = TicketSyncFieldMappingService.resolve_external_person_by_mapping_or_email(
                db,
                person_text=reporter_person,
                person_email=reporter_email,
                assignee_mappings=config.get("assigneeMappings") or [],
            )
            (
                internal_owner_id,
                internal_owner_name,
            ) = TicketSyncFieldMappingService.resolve_external_person_by_mapping_or_email(
                db,
                person_text=internal_owner,
                person_email=internal_owner_email,
                assignee_mappings=config.get("assigneeMappings") or [],
            )
        if apply_external_mappings and not assignee_id:
            assignee_id = SyncUtil.safe_int(sync_object.current_assignee_id)
        if not assignee_name:
            assignee_name = str(sync_object.current_assignee_name or "").strip()
        if apply_external_mappings and not first_line_assignee_id:
            first_line_assignee_id = SyncUtil.safe_int(getattr(sync_object, "first_line_assignee_id", None))
        if not first_line_assignee_name:
            first_line_assignee_name = str(
                getattr(sync_object, "first_line_assignee_name", "")
                or getattr(sync_object, "reporter_name", "")
                or ""
            ).strip()
        if apply_external_mappings and not internal_owner_id:
            internal_owner_id = SyncUtil.safe_int(getattr(sync_object, "internal_owner_id", None))
        if not internal_owner_name:
            internal_owner_name = str(getattr(sync_object, "internal_owner_name", "") or "").strip()
        # 版本号优先级：sync_object > extra_data > AI提取 > 正则
        ai_extract_payload = (
            (sync_object.extra_data or {}).get("_ai_extract")
            if isinstance(sync_object.extra_data, dict)
            else {}
        )
        ai_version_key = str(ai_extract_payload.get("versionKey") or "").strip() if isinstance(ai_extract_payload, dict) else ""
        version_key = (
            str(sync_object.version_key or "").strip()
            or _extract_ticket_version_key(sync_object.extra_data)
            or ai_version_key
            or str(cls.extract_pattern(text, config.get("versionPatterns")) or "").strip()
        )
        return {
            "projectId": getattr(project, "project_id", None)
            or (sync_object.project_id if apply_external_mappings else None),
            "projectName": (
                getattr(project, "project_name", "")
                or project_name_by_vendor
                or sync_object.project_name
                or sync_object.merchant_name
                or (raw_project_name if apply_external_mappings else "")
                or ""
            ),
            "projectCode": getattr(project, "project_code", "") or sync_object.project_code or "",
            "moduleId": getattr(module, "module_id", None)
            or (sync_object.module_id if apply_external_mappings else None),
            "moduleName": (
                getattr(module, "module_name", "")
                or sync_object.module_name
                or (ticket_modle if apply_external_mappings else "")
                or ""
            ),
            "moduleCode": getattr(module, "module_code", "") or sync_object.module_code or "",
            "vendorId": vendor_id,
            "vendorName": vendor_name,
            "storeId": store_id,
            "storeName": store_name,
            "status": status_code or str(sync_object.status or "").strip(),
            "assigneeId": assignee_id,
            "assigneeName": assignee_name,
            "firstLineAssigneeId": first_line_assignee_id,
            "firstLineAssigneeName": first_line_assignee_name,
            "internalOwnerId": internal_owner_id,
            "internalOwnerName": internal_owner_name,
            "posNo": SyncUtil.safe_int(ticket_pos)
            or SyncUtil.safe_int(log_pull_hints.get("posNo"))
            or SyncUtil.safe_int(log_pull_hints.get("pos_no"))
            or SyncUtil.safe_int((sync_object.log_pull_config or {}).get("posNo"))
            or SyncUtil.safe_int((sync_object.log_pull_config or {}).get("pos_id"))
            or SyncUtil.safe_int((sync_object.log_pull_config or {}).get("posId"))
            or SyncUtil.safe_int(cls.extract_pattern(text, config.get("posPatterns"))),
            "scoNo": SyncUtil.safe_int(ticket_sco)
            or SyncUtil.safe_int(log_pull_hints.get("scoNo"))
            or SyncUtil.safe_int(log_pull_hints.get("sco_no"))
            or SyncUtil.safe_int((sync_object.log_pull_config or {}).get("scoNo"))
            or SyncUtil.safe_int((sync_object.log_pull_config or {}).get("sco_no"))
            or SyncUtil.safe_int((sync_object.log_pull_config or {}).get("scoId"))
            or SyncUtil.safe_int((sync_object.log_pull_config or {}).get("sco_id"))
            or SyncUtil.safe_int(cls.extract_pattern(text, config.get("scoPatterns"))),
            "versionKey": version_key,
            "rawTextLength": len(text),
        }

    @classmethod
    def mark_automation_step(
        cls,
        meta: dict[str, Any],
        *,
        step: str,
        status: str,
        detail: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> dict[str, Any]:
        """
        更新同步自动化步骤状态。
        :param meta: 同步元数据。
        :param step: 步骤名称。
        :param status: 步骤状态。
        :param detail: 步骤详情。
        :param error: 错误信息。
        :return: 更新后的同步元数据。
        """
        sync_state = meta.get("sync_state") if isinstance(meta.get("sync_state"), dict) else {}
        automation = sync_state.get("automation") if isinstance(sync_state.get("automation"), dict) else {}
        steps = automation.get("steps") if isinstance(automation.get("steps"), dict) else {}
        previous = steps.get(step) if isinstance(steps.get(step), dict) else {}
        steps[step] = {
            **previous,
            "status": status,
            "updated_at": SyncUtil.now_iso(),
            "detail": detail,
            "error": error,
        }
        automation["steps"] = steps
        automation["current_step"] = step
        if error:
            automation["last_error"] = error
        if status == "failed":
            automation["status"] = "failed"
        elif any((item or {}).get("status") in {"queued", "running", "submitted"} for item in steps.values()):
            automation["status"] = "running"
        else:
            automation["status"] = "completed"
        sync_state["automation"] = automation
        meta["sync_state"] = sync_state
        return meta

    @classmethod
    def run_sync_automation(
        cls,
        db: Session,
        ticket_id: int,
        sync_object: TicketExternalSyncUpsertModel,
        detected: dict[str, Any],
        current_user: CurrentUserModel,
    ) -> dict[str, Any]:
        """
        执行同步后自动化链路。
        :param db: 数据库会话。
        :param ticket_id: 工单ID。
        :param sync_object: 外部同步模型。
        :param detected: 字段识别结果。
        :param current_user: 当前用户。
        :return: 自动化执行摘要。
        """
        ticket = TicketDao.get_ticket_by_id(db, ticket_id)
        if not ticket:
            return {}
        config = TicketSyncConfigService.load_sync_config(db)
        automation = sync_object.automation
        extra_data = dict(ticket.extra_data or {}) if isinstance(ticket.extra_data, dict) else {}
        meta = TicketSyncPayloadService.build_meta(extra_data)
        summary: dict[str, Any] = {"detected": detected}
        try:
            cls.mark_automation_step(meta, step="identify", status="success", detail=detected)
            update_data: dict[str, Any] = {}
            detected_project_id = SyncUtil.safe_int(detected.get("projectId"))
            detected_module_id = SyncUtil.safe_int(detected.get("moduleId"))
            detected_project_name = str(detected.get("projectName") or "").strip()
            detected_module_name = str(detected.get("moduleName") or "").strip()

            if detected_project_id and detected_project_id != ticket.project_id:
                update_data["project_id"] = detected_project_id
            if detected_project_name and detected_project_name != str(ticket.merchant_name or "").strip():
                update_data["merchant_name"] = detected_project_name
            if detected_module_id and detected_module_id != ticket.module_id:
                update_data["module_id"] = detected_module_id
            if detected_module_name and detected_module_name != str(ticket.module_name or "").strip():
                update_data["module_name"] = detected_module_name

            if update_data:
                update_data.update(
                    {
                        "update_by": _user_name(current_user),
                        "update_time": datetime.now(),
                    }
                )
                TicketDao.update_ticket(db, ticket_id, update_data)
                ticket = TicketDao.get_ticket_by_id(db, ticket_id)

            search_text = cls.collect_text(ticket)
            similar_tickets = [
                item
                for item in TicketEmbeddingService.search_tickets(db, search_text, 6)
                if item.get("ticketId") != ticket_id
            ]
            summary["similarTickets"] = similar_tickets[:5]
            cls.mark_automation_step(
                meta,
                step="similar_ticket",
                status="success",
                detail={"ticketIds": [item.get("ticketId") for item in similar_tickets[:5]]},
            )

            if automation and automation.auto_log_pull:
                log_pull_payload = dict(config.get("logPullDefaults") or {})
                if isinstance(automation.log_pull_config, dict):
                    log_pull_payload.update(automation.log_pull_config)
                if isinstance(sync_object.log_pull_config, dict):
                    log_pull_payload.update(sync_object.log_pull_config)
                resolved_vendor_id = SyncUtil.safe_int(detected.get("vendorId") or log_pull_payload.get("vendorId"))
                resolved_store_id = str(detected.get("storeId") or log_pull_payload.get("storeId") or "").strip()
                resolved_pos_no = SyncUtil.safe_int(
                    detected.get("posNo") or detected.get("scoNo") or log_pull_payload.get("posNo")
                )
                resolved_modify_time = TicketSyncPayloadService.resolve_auto_log_pull_modify_time(
                    sync_object=sync_object,
                    log_pull_payload=log_pull_payload,
                )
                log_pull_payload.update(
                    {
                        "ticketId": ticket_id,
                        "vendorId": resolved_vendor_id,
                        "storeId": resolved_store_id,
                        "posNo": resolved_pos_no,
                        "modifyTime": resolved_modify_time,
                    }
                )
                if automation.auto_ai_analysis:
                    log_pull_payload["autoAiEnabled"] = True
                    log_pull_payload["aiAgentCode"] = automation.ai_agent_code
                    log_pull_payload["aiProviderCode"] = automation.ai_provider_code
                missing_log_pull_fields: list[str] = []
                if not resolved_vendor_id:
                    missing_log_pull_fields.append("vendorId")
                if not resolved_store_id:
                    missing_log_pull_fields.append("storeId")
                if not resolved_pos_no:
                    missing_log_pull_fields.append("posNo/SCO")
                if not resolved_modify_time:
                    missing_log_pull_fields.append("modifyTime")
                if missing_log_pull_fields:
                    skip_reason = f"自动拉日志参数不完整，缺少: {', '.join(missing_log_pull_fields)}"
                    summary["logPullSkipReason"] = skip_reason
                    cls.mark_automation_step(
                        meta,
                        step="log_pull",
                        status="skipped",
                        detail={
                            "reason": skip_reason,
                            "vendorId": resolved_vendor_id,
                            "storeId": resolved_store_id,
                            "posNo": resolved_pos_no,
                            "modifyTime": resolved_modify_time,
                        },
                    )
                    if automation.auto_ai_analysis:
                        summary["aiAnalysisSkipReason"] = "自动拉日志未触发，自动AI分析跳过"
                        cls.mark_automation_step(
                            meta,
                            step="ai_analysis",
                            status="skipped",
                            detail={"reason": "自动拉日志参数不完整，跳过自动AI分析"},
                        )
                else:
                    try:
                        create_model = TicketLogPullCreateModel.model_validate(log_pull_payload)
                        log_result = TicketLogPullService.create_log_pull_services(
                            db, ticket_id, create_model, current_user
                        )
                        if log_result.is_success:
                            summary["logPull"] = log_result.result
                            cls.mark_automation_step(
                                meta,
                                step="log_pull",
                                status="submitted",
                                detail=log_result.result,
                            )
                            if automation.auto_ai_analysis:
                                cls.mark_automation_step(
                                    meta,
                                    step="ai_analysis",
                                    status="queued",
                                    detail={"via": "log_pull_auto_ai", "agentCode": automation.ai_agent_code},
                                )
                        else:
                            summary["logPullError"] = log_result.message
                            cls.mark_automation_step(meta, step="log_pull", status="failed", error=log_result.message)
                    except Exception as exc:
                        summary["logPullError"] = str(exc)
                        cls.mark_automation_step(meta, step="log_pull", status="failed", error=str(exc))
            elif automation and automation.auto_ai_analysis:
                version_key = str(detected.get("versionKey") or "").strip() or _extract_ticket_version_key(
                    ticket.extra_data
                )
                latest_log = TicketLogPullService.get_latest_summary(db, ticket_id)
                if version_key and latest_log and latest_log.get("id"):
                    ai_request = TicketAiAnalysisRequestModel(
                        version_key=version_key,
                        log_pull_record_id=int(latest_log["id"]),
                        agent_code=automation.ai_agent_code,
                        ai_provider_code=automation.ai_provider_code,
                        extra_instruction=automation.extra_instruction or "",
                    )
                    ai_result = TicketAiAnalysisService.create_analysis_task_services(
                        db, ticket_id, ai_request, current_user
                    )
                    if ai_result.is_success:
                        summary["aiAnalysis"] = ai_result.result
                        cls.mark_automation_step(meta, step="ai_analysis", status="submitted", detail=ai_result.result)
                    else:
                        summary["aiAnalysisError"] = ai_result.message
                        cls.mark_automation_step(meta, step="ai_analysis", status="failed", error=ai_result.message)
                else:
                    reason = "缺少版本号或可用日志记录，跳过自动 AI"
                    summary["aiAnalysisSkipReason"] = reason
                    cls.mark_automation_step(meta, step="ai_analysis", status="skipped", detail={"reason": reason})
        except Exception as exc:
            cls.mark_automation_step(meta, step="automation", status="failed", error=str(exc))
            logger.exception(f"工单[{ticket_id}]同步自动化执行异常: {exc}")
        finally:
            ticket = TicketDao.get_ticket_by_id(db, ticket_id)
            extra_data = dict(ticket.extra_data or {}) if ticket and isinstance(ticket.extra_data, dict) else {}
            extra_data = TicketSyncPayloadService.attach_meta(extra_data, meta)
            TicketDao.update_ticket(
                db,
                ticket_id,
                {
                    "extra_data": extra_data,
                    "update_by": _user_name(current_user),
                    "update_time": datetime.now(),
                },
            )
            db.commit()
        return summary
