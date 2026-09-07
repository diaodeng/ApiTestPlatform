"""
工单同步字段识别与自动化执行服务。

负责外部同步入库后的项目/模块/人员/门店/版本号识别，以及相似工单、自动拉日志、
自动 AI 分析等同步自动化步骤。
"""
import re
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from module_admin.entity.vo.user_vo import CurrentUserModel
from module_hrm.entity.do.module_do import HrmModule
from module_hrm.entity.do.project_do import HrmProject
from module_hrm.enums.enums import QtrDataStatusEnum
from modules.ticket.dao.ticket_dao import TicketDao
from modules.ticket.dao.ticket_log_pull_dao import TicketLogPullDao
from modules.ticket.entity.do.ticket_do import Ticket
from modules.ticket.entity.vo.ticket_log_pull_vo import TicketLogPullCreateModel
from modules.ticket.entity.vo.ticket_vo import TicketExternalSyncUpsertModel
from modules.ticket.service.ai.ticket_auto_ai_analysis_condition_service import TicketAutoAiAnalysisConditionService
from modules.ticket.service.ai.ticket_embedding_service import TicketEmbeddingService
from modules.ticket.service.log_pull.ticket_log_pull_service import TicketLogPullService
from modules.ticket.service.notification.ticket_notify_service import TicketNotifyService
from modules.ticket.service.sync.ticket_sync_automation_input_service import TicketSyncAutomationInputService
from modules.ticket.service.sync.ticket_sync_config_service import TicketSyncConfigService
from modules.ticket.service.sync.ticket_sync_field_mapping_service import (
    ModuleMappingResult,
    TicketSyncFieldMappingService,
)
from modules.ticket.service.sync.ticket_sync_payload_service import TicketSyncPayloadService
from modules.ticket.util.sync_util import SyncUtil
from modules.ticket.util.ticket_common_util import normalize_ticket_version_key
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

        # 模块解析：使用 ModuleMappingResult 统一处理映射和查表
        module_result = None  # type: ModuleMappingResult | None
        if apply_external_mappings:
            module_result = TicketSyncFieldMappingService.resolve_module_by_ticket_modle(
                db,
                ticket_modle=ticket_modle,
                project_id=getattr(project, "project_id", None),
                module_mappings=config.get("moduleMappings") or [],
            )
        # 映射未命中或未查到记录时，尝试直接用 module_code 查表
        if not module_result or (not module_result.mapping_matched and not module_result.resolved_module_id):
            if str(sync_object.module_code or "").strip():
                module_query = db.query(HrmModule).filter(
                    func.lower(HrmModule.module_code) == str(sync_object.module_code).strip().lower(),
                    HrmModule.status == QtrDataStatusEnum.normal.value,
                )
                if getattr(project, "project_id", None):
                    module_query = module_query.filter(HrmModule.project_id == getattr(project, "project_id", None))
                resolved = module_query.first()
                if resolved:
                    module_result = ModuleMappingResult(
                        resolved_module_id=resolved.module_id,
                        resolved_module_code=str(resolved.module_code or "").strip(),
                        resolved_module_name=str(resolved.module_name or "").strip(),
                        matched_by="direct_code",
                    )
        # 仍未命中，尝试用 module_name 走映射
        if not module_result or (not module_result.mapping_matched and not module_result.resolved_module_id):
            if apply_external_mappings and str(sync_object.module_name or "").strip():
                module_result = TicketSyncFieldMappingService.resolve_module_by_ticket_modle(
                    db,
                    ticket_modle=str(sync_object.module_name or "").strip(),
                    project_id=getattr(project, "project_id", None),
                    module_mappings=config.get("moduleMappings") or [],
                )
        # 仍未命中，尝试用 module_id 直接查表
        if not module_result or (not module_result.mapping_matched and not module_result.resolved_module_id):
            if apply_external_mappings and sync_object.module_id:
                module_query = db.query(HrmModule).filter(
                    HrmModule.module_id == sync_object.module_id,
                    HrmModule.status == QtrDataStatusEnum.normal.value,
                )
                if getattr(project, "project_id", None):
                    module_query = module_query.filter(HrmModule.project_id == getattr(project, "project_id", None))
                resolved = module_query.first()
                if resolved:
                    module_result = ModuleMappingResult(
                        resolved_module_id=resolved.module_id,
                        resolved_module_code=str(resolved.module_code or "").strip(),
                        resolved_module_name=str(resolved.module_name or "").strip(),
                        matched_by="direct_id",
                    )

        # 从 ModuleMappingResult 提取最终模块字段值
        # 优先级：resolved（查到记录）> mapped（映射规则）> 空
        module_id_val = (
            module_result.resolved_module_id
            if module_result and module_result.resolved_module_id is not None
            else (module_result.mapped_module_id if module_result and module_result.mapping_matched else None)
        )
        module_code_val = (
            module_result.resolved_module_code
            if module_result and module_result.resolved_module_code
            else (module_result.mapped_module_code if module_result else "")
        )
        module_name_val = (
            module_result.resolved_module_name
            if module_result and module_result.resolved_module_name
            else (module_result.mapped_module_name if module_result else "")
        )

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
            # 自动分析环境与日志拉取配置的默认环境一致，取其分组部分（冒号前）用于门店过滤。
            default_log_pull_environment = str(
                (config.get("logPullDefaults") or {}).get("environment") or ""
            ).strip().split(":", 1)[0].strip()
            store_id, store_name = TicketSyncFieldMappingService.resolve_store_by_external_value(
                db,
                vendor_id=vendor_id,
                ticket_store=ticket_store,
                environment=default_log_pull_environment,
            )
        else:
            store_id, store_name = "", ""
        store_candidates = (
            TicketSyncFieldMappingService.list_store_candidates_by_external_value(
                db,
                vendor_id=vendor_id,
                ticket_store=ticket_store,
                environment=default_log_pull_environment,
            )
            if apply_external_mappings
            else []
        )
        store_mapping_ambiguous = len(store_candidates) > 1
        if store_mapping_ambiguous:
            # 多个 org_no 命中同一外部编码时禁止静默选值，交由自动日志参数校验中断。
            store_id, store_name = "", ""
        if not store_name:
            store_name = str(log_pull_hints.get("storeName") or log_pull_hints.get("store_name") or "").strip()
        if not store_id and not store_mapping_ambiguous:
            store_id = str(log_pull_hints.get("storeId") or log_pull_hints.get("store_id") or "").strip()
        if not store_id and not store_mapping_ambiguous:
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
        # 版本文本仅在同步输入边界用于解析版本中心ID，不写入工单扩展字段。
        version_key = (
            normalize_ticket_version_key(sync_object.detected_version_key)
            or normalize_ticket_version_key(cls.extract_pattern(text, config.get("versionPatterns")))
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
            "moduleId": module_id_val,
            "moduleName": module_name_val or sync_object.module_name
            or (ticket_modle if apply_external_mappings else "") or "",
            "moduleCode": module_code_val or sync_object.module_code or "",
            "moduleMappingResult": module_result,  # 附加完整的映射匹配结果，供后续审计写入
            "vendorId": vendor_id,
            "vendorName": vendor_name,
            "storeId": store_id,
            "storeName": store_name,
            "storeMappingAmbiguous": store_mapping_ambiguous,
            "storeMappingCandidates": store_candidates,
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
    def _json_safe_detected(cls, detected: dict[str, Any] | None) -> dict[str, Any]:
        """将字段识别结果转换为可写入 JSON 的结构，保留模块映射审计字段。"""
        payload = dict(detected or {}) if isinstance(detected, dict) else {}
        module_result = payload.get("moduleMappingResult")
        if isinstance(module_result, ModuleMappingResult):
            payload["moduleMappingResult"] = module_result.to_payload()
        return cls._json_safe_value(payload)

    @classmethod
    def _json_safe_value(cls, value: Any) -> Any:
        """递归转换自动化审计值，确保 JSON 扩展字段不包含 ORM 或时间对象。"""
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        if isinstance(value, ModuleMappingResult):
            return cls._json_safe_value(value.to_payload())
        if hasattr(value, "model_dump"):
            return cls._json_safe_value(value.model_dump(mode="json"))
        if is_dataclass(value):
            return cls._json_safe_value(asdict(value))
        if isinstance(value, dict):
            return {str(key): cls._json_safe_value(item) for key, item in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [cls._json_safe_value(item) for item in value]
        return value

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
            "detail": cls._json_safe_value(detail),
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
    def apply_auto_ai_result(cls, meta: dict[str, Any], summary: dict[str, Any], result: dict[str, Any]) -> None:
        """
        将自动 AI 触发结果同步到自动化摘要和审计步骤。
        :param meta: 自动化元数据
        :param summary: 自动化执行摘要
        :param result: 自动 AI 处理结果
        :return: 无
        """
        safe_result = cls._json_safe_value(result if isinstance(result, dict) else {})
        status = str((safe_result or {}).get("status") or "").strip().lower()
        reason = str((safe_result or {}).get("reason") or "").strip()
        if status == "submitted":
            summary["aiAnalysis"] = safe_result
            cls.mark_automation_step(meta, step="ai_analysis", status="submitted", detail=safe_result)
            return
        if status == "skipped":
            summary["aiAnalysisSkipReason"] = reason or "自动 AI 分析已跳过"
            cls.mark_automation_step(meta, step="ai_analysis", status="skipped", detail=safe_result)
            return
        failure_reason = reason or "自动 AI 分析执行失败"
        summary["aiAnalysisError"] = failure_reason
        cls.mark_automation_step(meta, step="ai_analysis", status="failed", detail=safe_result, error=failure_reason)

    @classmethod
    def run_sync_automation(
        cls,
        db: Session,
        ticket_id: int,
        sync_object: TicketExternalSyncUpsertModel,
        detected: dict[str, Any],
        current_user: CurrentUserModel,
        sync_scene: str = "external_sync",
    ) -> dict[str, Any]:
        """
        执行同步后自动化链路。
        :param db: 数据库会话。
        :param ticket_id: 工单ID。
        :param sync_object: 外部同步模型。
        :param detected: 字段识别结果。
        :param current_user: 当前用户。
        :param sync_scene: 同步场景，automation 为 None 时从 automationConfig 读取。
        :return: 自动化执行摘要。
        """
        ticket = TicketDao.get_ticket_by_id(db, ticket_id)
        if not ticket:
            return {}
        config = TicketSyncConfigService.load_sync_config(db)
        automation = sync_object.automation
        notification_config = (
            config.get("automationNotification")
            if isinstance(config.get("automationNotification"), dict)
            else {}
        )
        log_pull_defaults = config.get("logPullDefaults") if isinstance(config.get("logPullDefaults"), dict) else {}
        auto_ai_analysis_condition = (
            dict(log_pull_defaults.get("autoAiAnalysisCondition"))
            if isinstance(log_pull_defaults.get("autoAiAnalysisCondition"), dict)
            else {"analysisMode": "always", "statusFilterEnabled": False, "statusCodes": []}
        )
        # 优先级: 任务级 automation > automationConfig 页面配置
        if automation is not None:
            auto_log_pull = bool(automation.auto_log_pull)
            auto_ai_analysis = bool(automation.auto_ai_analysis)
            ai_agent_code = automation.ai_agent_code
            ai_provider_code = automation.ai_provider_code
        else:
            auto_config = config.get("automationConfig") if isinstance(config.get("automationConfig"), dict) else {}
            scene_map = {
                "external_sync": "ExternalSync",
                "remote_pull": "RemotePull",
                "bitable_pull": "BitablePull",
                "manual_create": "ManualCreate",
            }
            scene_suffix = scene_map.get(sync_scene, "")
            auto_log_pull = bool(auto_config.get(f"autoLogPullOn{scene_suffix}"))
            auto_ai_analysis = bool(auto_config.get(f"autoAiAnalysisOn{scene_suffix}"))
            ai_agent_code = str(log_pull_defaults.get("aiAgentCode") or "").strip() or None
            ai_provider_code = str(log_pull_defaults.get("aiProviderCode") or "").strip() or None
        extra_data = dict(ticket.extra_data or {}) if isinstance(ticket.extra_data, dict) else {}
        ticket_automation = (
            dict(extra_data.get("ticket_automation"))
            if isinstance(extra_data.get("ticket_automation"), dict)
            else {}
        )
        # 自动化执行时固化通知配置，避免后台日志/AI任务读取到后续修改后的配置。
        ticket_automation["notifyConfig"] = notification_config
        extra_data["ticket_automation"] = ticket_automation
        TicketDao.update_ticket(db, ticket_id, {"extra_data": extra_data})
        db.flush()
        ticket = TicketDao.get_ticket_by_id(db, ticket_id) or ticket
        meta = TicketSyncPayloadService.build_meta(extra_data)
        safe_detected = cls._json_safe_detected(detected)
        summary: dict[str, Any] = {"detected": safe_detected}
        try:
            cls.mark_automation_step(meta, step="identify", status="success", detail=safe_detected)
            update_data: dict[str, Any] = {}
            detected_project_id = SyncUtil.safe_int(detected.get("projectId"))
            detected_project_name = str(detected.get("projectName") or "").strip()

            if detected_project_id and detected_project_id != ticket.project_id:
                update_data["project_id"] = detected_project_id
            if detected_project_name and detected_project_name != str(ticket.merchant_name or "").strip():
                update_data["merchant_name"] = detected_project_name

            # 模块字段原子更新：module_id/module_code/module_name 任一变化则三个一起更新
            detected_module_id = SyncUtil.safe_int(detected.get("moduleId"))
            detected_module_code = str(detected.get("moduleCode") or "").strip()
            detected_module_name = str(detected.get("moduleName") or "").strip()

            current_module_id = ticket.module_id
            current_module_code = str(getattr(ticket, "module_code", "") or "").strip()
            current_module_name = str(ticket.module_name or "").strip()

            module_changed = False
            if detected_module_id is not None and detected_module_id != current_module_id:
                module_changed = True
            if detected_module_code and detected_module_code != current_module_code:
                module_changed = True
            if detected_module_name and detected_module_name != current_module_name:
                module_changed = True

            if module_changed:
                update_data["module_id"] = detected_module_id
                update_data["module_code"] = detected_module_code
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

            # 相似检索文本与入库向量同构：使用 build_ticket_text（symptom scope），
            # 不再复用 collect_text（其含 raw_payload 全量 JSON 和工单号，超长会击穿
            # 外部 Embedding 的 token 上限，且查询/入库向量字段分布不一致）。
            similarity_config = TicketEmbeddingService.get_similarity_config(db)
            search_text = TicketEmbeddingService.build_ticket_text(
                ticket, config=similarity_config, scope=TicketEmbeddingService.SCOPE_SYMPTOM
            )
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

            if auto_log_pull:
                runtime_config = TicketSyncAutomationInputService.resolve_runtime_config(
                    config=config,
                    automation=automation,
                    sync_object=sync_object,
                    detected=detected,
                    ticket_id=ticket_id,
                    ticket_extra_data=extra_data,
                )
                resolved_vendor_id = SyncUtil.safe_int(runtime_config.get("vendorId"))
                resolved_store_id = str(runtime_config.get("storeId") or "").strip()
                resolved_pos_no = SyncUtil.safe_int(runtime_config.get("posNo")) or SyncUtil.safe_int(
                    runtime_config.get("scoNo")
                )
                resolved_modify_time = TicketSyncAutomationInputService.resolve_modify_time(
                    sync_object=sync_object,
                    runtime_config=runtime_config,
                )
                runtime_config.update(
                    {
                        "ticketId": ticket_id,
                        "vendorId": resolved_vendor_id,
                        "storeId": resolved_store_id,
                        "posNo": resolved_pos_no,
                        "modifyTime": resolved_modify_time,
                    }
                )
                runtime_config["notifyConfig"] = notification_config
                automation_snapshot = (
                    dict(runtime_config.get("automationSnapshot"))
                    if isinstance(runtime_config.get("automationSnapshot"), dict)
                    else {}
                )
                automation_snapshot["autoCreated"] = True
                automation_snapshot["notifyConfig"] = notification_config
                if auto_ai_analysis:
                    runtime_config["autoAiEnabled"] = True
                    runtime_config["aiAgentCode"] = ai_agent_code
                    runtime_config["aiProviderCode"] = ai_provider_code
                    # 将自动分析条件一并写入日志拉取记录，保证后台执行使用创建时快照。
                    runtime_config["autoAiAnalysisCondition"] = auto_ai_analysis_condition
                    automation_snapshot["autoAiEnabled"] = True
                    automation_snapshot["aiAgentCode"] = ai_agent_code
                    automation_snapshot["aiProviderCode"] = ai_provider_code
                    automation_snapshot["autoAiAnalysisCondition"] = auto_ai_analysis_condition
                runtime_config["automationSnapshot"] = automation_snapshot
                stop_context = TicketSyncConfigService.match_auto_log_pull_stop_condition(ticket.status, config)
                store_mapping_ambiguous = bool(runtime_config.get("storeMappingAmbiguous"))
                store_mapping_candidates = runtime_config.get("storeMappingCandidates")
                if stop_context.get("matched"):
                    skip_reason = str(stop_context.get("reason") or "工单状态命中自动拉日志停止条件")
                    audit_detail = {
                        "reason": skip_reason,
                        "ticketStatus": stop_context.get("ticketStatus"),
                        "configuredStatusCodes": stop_context.get("condition", {}).get("statusCodes", []),
                        "cancelActiveRecords": bool(
                            stop_context.get("condition", {}).get("cancelActiveRecords")
                        ),
                        **runtime_config,
                    }
                    summary["logPullSkipReason"] = skip_reason
                    cls.mark_automation_step(
                        meta,
                        step="log_pull",
                        status="skipped",
                        detail=audit_detail,
                    )
                    if auto_ai_analysis:
                        ai_skip_reason = "工单状态命中自动拉日志停止条件，自动AI分析跳过"
                        summary["aiAnalysisSkipReason"] = ai_skip_reason
                        cls.mark_automation_step(
                            meta,
                            step="ai_analysis",
                            status="skipped",
                            detail={
                                "reason": ai_skip_reason,
                                "ticketStatus": stop_context.get("ticketStatus"),
                            },
                        )
                else:
                    missing_log_pull_fields: list[str] = []
                    if store_mapping_ambiguous:
                        # 同一商家和外部编码命中多个 org_no 时必须人工消歧，禁止静默提交任一门店。
                        missing_log_pull_fields.append("storeId(外部门店编码匹配到多个org_no)")
                    if not resolved_vendor_id:
                        missing_log_pull_fields.append("vendorId")
                    if not str(runtime_config.get("environment") or "").strip():
                        missing_log_pull_fields.append("environment")
                    if not resolved_store_id and not store_mapping_ambiguous:
                        missing_log_pull_fields.append("storeId")
                    elif resolved_store_id and not store_mapping_ambiguous:
                        # 按商家过滤后的门店中校验 org_no 是否匹配。
                        if resolved_vendor_id:
                            # 门店配置按环境隔离，使用运行时环境分组（group:item 的 group 部分）校验。
                            runtime_environment_group = str(
                                runtime_config.get("environment") or ""
                            ).strip().split(":", 1)[0].strip()
                            store_verified = TicketLogPullDao.verify_store_by_org_no(
                                db,
                                vendor_no=str(resolved_vendor_id),
                                org_no=resolved_store_id,
                                environment=runtime_environment_group,
                            )
                            if not store_verified:
                                missing_log_pull_fields.append("storeId(门店未匹配到正确的org_no)")
                    if not resolved_pos_no:
                        missing_log_pull_fields.append("posNo/SCO")
                    if not resolved_modify_time:
                        missing_log_pull_fields.append("modifyTime")
                    if missing_log_pull_fields:
                        skip_reason = (
                            "外部门店编码匹配到多个日志门店，无法自动选择"
                            if store_mapping_ambiguous
                            else f"自动拉日志参数不完整，缺少: {', '.join(missing_log_pull_fields)}"
                        )
                        audit_detail = {
                            "reason": skip_reason,
                            **runtime_config,
                        }
                        if store_mapping_ambiguous:
                            audit_detail["storeMappingCandidates"] = store_mapping_candidates or []
                        logger.warning(
                            f"自动拉日志跳过: ticket_no={sync_object.ticket_no}, "
                            f"ticket_id={ticket_id}, scene={sync_scene}, reason={skip_reason}, "
                            f"vendorId={resolved_vendor_id}, sourceStoreCode={runtime_config.get('sourceStoreCode')}, "
                            f"storeMappingCandidates={store_mapping_candidates or []}, "
                            f"runtime_config={runtime_config}"
                        )
                        summary["logPullSkipReason"] = skip_reason
                        if store_mapping_ambiguous:
                            summary["storeMappingCandidates"] = store_mapping_candidates or []
                        cls.mark_automation_step(
                            meta,
                            step="log_pull",
                            status="skipped",
                            detail=audit_detail,
                        )
                        TicketNotifyService.send_ticket_notification(
                            db,
                            ticket,
                            title="工单自动化结果通知",
                            status="failed",
                            message="自动日志拉取已跳过",
                            detail=skip_reason,
                            notify_config=notification_config,
                            stage="log_pull",
                        )
                        if auto_ai_analysis:
                            summary["aiAnalysisSkipReason"] = "自动拉日志未触发，自动AI分析跳过"
                            cls.mark_automation_step(
                                meta,
                                step="ai_analysis",
                                status="skipped",
                                detail={
                                    "reason": "自动拉日志参数不完整，跳过自动AI分析",
                                    "storeMappingCandidates": store_mapping_candidates or [],
                                },
                            )
                    else:
                        try:
                            create_model = TicketLogPullCreateModel.model_validate(runtime_config)
                            existing_success_record = TicketLogPullService.find_matching_success_record(
                                db, ticket_id, create_model
                            )
                            if existing_success_record:
                                reuse_reason = (
                                    f"已存在相同拉取参数且成功的日志记录，跳过自动拉取并复用记录[{existing_success_record.id}]"
                                )
                                summary["logPull"] = {
                                    "recordId": str(existing_success_record.id),
                                    "status": str(existing_success_record.status or ""),
                                    "statusDesc": str(existing_success_record.status_desc or ""),
                                    "reused": True,
                                }
                                summary["logPullSkipReason"] = reuse_reason
                                cls.mark_automation_step(
                                    meta,
                                    step="log_pull",
                                    status="skipped",
                                    detail={
                                        "reason": reuse_reason,
                                        "runtimeConfig": runtime_config,
                                        "existingRecordId": str(existing_success_record.id),
                                    },
                                )
                                if auto_ai_analysis:
                                    ai_result = TicketLogPullService.trigger_auto_ai_analysis(
                                        db, existing_success_record.id
                                    )
                                    cls.apply_auto_ai_result(meta, summary, ai_result)
                            else:
                                log_result = TicketLogPullService.create_log_pull_services(
                                    db, ticket_id, create_model, current_user
                                )
                                if log_result.is_success:
                                    summary["logPull"] = log_result.result
                                    cls.mark_automation_step(
                                        meta,
                                        step="log_pull",
                                        status="submitted",
                                        detail={"runtimeConfig": runtime_config, "result": log_result.result},
                                    )
                                    if auto_ai_analysis:
                                        cls.mark_automation_step(
                                            meta,
                                            step="ai_analysis",
                                            status="queued",
                                            detail={"via": "log_pull_auto_ai", "agentCode": ai_agent_code},
                                        )
                                else:
                                    summary["logPullError"] = log_result.message
                                    cls.mark_automation_step(
                                        meta,
                                        step="log_pull",
                                        status="failed",
                                        error=log_result.message,
                                    )
                                    TicketNotifyService.send_ticket_notification(
                                        db,
                                        ticket,
                                        title="工单自动化结果通知",
                                        status="failed",
                                        message="自动日志拉取任务创建失败",
                                        detail=log_result.message,
                                        notify_config=notification_config,
                                        stage="log_pull",
                                    )
                        except Exception as exc:
                            summary["logPullError"] = str(exc)
                            cls.mark_automation_step(meta, step="log_pull", status="failed", error=str(exc))
                            TicketNotifyService.send_ticket_notification(
                                db,
                                ticket,
                                title="工单自动化结果通知",
                                status="failed",
                                message="自动日志拉取任务创建异常",
                                detail=str(exc),
                                notify_config=notification_config,
                                stage="log_pull",
                            )
            elif auto_ai_analysis:
                condition_skip = TicketAutoAiAnalysisConditionService.check_conditions(
                    db, ticket, auto_ai_analysis_condition
                )
                if condition_skip:
                    skip_reason, skip_detail = condition_skip
                    summary["aiAnalysisSkipReason"] = skip_reason
                    logger.info(
                        f"工单[{ticket_id}]同步自动AI分析跳过 | reason={skip_reason}, detail={skip_detail}"
                    )
                    cls.mark_automation_step(
                        meta,
                        step="ai_analysis",
                        status="skipped",
                        detail={"reason": skip_reason, **skip_detail},
                    )
                else:
                    latest_success_record = TicketLogPullDao.get_latest_success_record_by_ticket_id(db, ticket_id)
                    if latest_success_record:
                        ai_result = TicketLogPullService.trigger_auto_ai_analysis(db, latest_success_record.id)
                        cls.apply_auto_ai_result(meta, summary, ai_result)
                    else:
                        reason = "缺少成功日志记录，跳过自动 AI"
                        summary["aiAnalysisSkipReason"] = reason
                        cls.mark_automation_step(meta, step="ai_analysis", status="skipped", detail={"reason": reason})
                        TicketNotifyService.send_ticket_notification(
                            db,
                            ticket,
                            title="工单自动化结果通知",
                            status="failed",
                            message="自动 AI 分析已跳过",
                            detail=reason,
                            notify_config=notification_config,
                            stage="ai_analysis",
                        )

        except Exception as exc:
            cls.mark_automation_step(meta, step="automation", status="failed", error=str(exc))
            logger.exception(f"工单[{ticket_id}]同步自动化执行异常: {exc}")
            TicketNotifyService.send_ticket_notification(
                db,
                ticket,
                title="工单自动化结果通知",
                status="failed",
                message="同步后自动化执行异常",
                detail=str(exc),
                notify_config=notification_config,
                stage="automation",
            )
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
