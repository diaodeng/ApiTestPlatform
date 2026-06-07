import json
import re
from datetime import datetime
from typing import Any

import requests
from sqlalchemy.orm import Session

from module_admin.entity.do.config_do import SysConfig
from module_admin.entity.vo.user_vo import CurrentUserModel
from module_hrm.entity.do.module_do import HrmModule
from module_hrm.entity.do.project_do import HrmProject
from module_hrm.entity.vo.common_vo import CrudResponseModel
from module_hrm.enums.enums import QtrDataStatusEnum
from modules.ticket.dao.ticket_dao import TicketDao
from modules.ticket.entity.do.ticket_do import Ticket, TicketEvent, TicketMessage, TicketStatusHistory
from modules.ticket.entity.vo.ticket_log_pull_vo import TicketLogPullCreateModel
from modules.ticket.entity.vo.ticket_vo import (
    TicketAiAnalysisRequestModel,
    TicketExternalSyncUpsertModel,
    TicketSyncAutomationModel,
    TicketSyncAckRequestModel,
    TicketSyncPullQueryModel,
)
from modules.ticket.enums.ticket_enums import TicketEventType, TicketStatus
from modules.ticket.service.ticket_ai_analysis_service import TicketAiAnalysisService
from modules.ticket.service.ticket_embedding_service import TicketEmbeddingService
from modules.ticket.service.ticket_light_ai_service import TicketLightAiService
from modules.ticket.service.ticket_log_pull_service import TicketLogPullService
from modules.ticket.service.ticket_service import TicketService, _extract_ticket_version_key, _user_id, _user_name
from utils.common_util import CamelCaseUtil
from utils.log_util import logger


class TicketSyncService:
    """
    工单外部同步服务，统一处理外部推送、内网拉取和同步后自动化状态追踪。
    """

    CONFIG_KEY = "ticket.sync.automation"
    SOURCE_CODE = "external_sync"
    META_KEY = "external_sync"

    @classmethod
    def _json_dumps(cls, value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, indent=2)

    @classmethod
    def _json_loads(cls, value: Any, default: Any):
        if value in (None, ""):
            return default
        if isinstance(value, (dict, list)):
            return value
        try:
            return json.loads(str(value))
        except Exception:
            return default

    @classmethod
    def _now_iso(cls) -> str:
        return datetime.now().isoformat()

    @classmethod
    def _safe_int(cls, value: Any) -> int | None:
        try:
            if value in (None, ""):
                return None
            return int(value)
        except Exception:
            return None

    @classmethod
    def _default_sync_config(cls) -> dict[str, Any]:
        return {
            "autoRunOnSync": False,
            "autoTranslateOnSync": True,
            "defaultPullLimit": 50,
            "remoteSync": cls._default_remote_sync_config(),
            "projectMappings": [],
            "moduleMappings": [],
            "vendorMappings": [],
            "storeMappings": [],
            "statusMappings": [],
            "assigneeMappings": [],
            "posPatterns": [r"(?:^|[^A-Z0-9])POS[^0-9]{0,3}(\d{1,10})(?:[^A-Z0-9]|$)"],
            "scoPatterns": [r"(?:^|[^A-Z0-9])SCO[^0-9]{0,3}(\d{1,10})(?:[^A-Z0-9]|$)"],
            "versionPatterns": [
                r"(?:版本|version|app[_\\s-]*version)[:：\\s-]*([A-Za-z0-9._/-]+)",
            ],
            "logPullDefaults": {
                "commandDataType": 1,
                "fileMaxSize": 500,
                "zipMaxSize": 500,
                "storageMode": "local",
                "rangeBeforeMinutes": 10,
                "rangeAfterMinutes": 10,
                "autoAiEnabled": False,
                "aiAgentCode": "",
                "aiProviderCode": "",
            },
            "promptTemplates": {
                "classificationHint": "预留给后续 AI 识别场景，当前版本由可配置规则和正则完成识别。",
            },
        }

    @classmethod
    def _default_remote_sync_config(cls) -> dict[str, Any]:
        """
        构建远端工单同步默认配置。

        :return: 默认远端同步配置。
        """
        return {
            "enabled": False,
            "pullUrl": "",
            "ackUrl": "",
            "consumer": "",
            "sourceSystem": "public",
            "limit": 50,
            "includeClosed": True,
            "autoTranslateOnPull": True,
            "timeoutSec": 30,
            "headers": {
                "cookie": "",
                "authorization": "",
                "origin": "",
            },
        }

    @classmethod
    def _normalize_sync_config(cls, config: dict[str, Any] | None) -> dict[str, Any]:
        merged = cls._default_sync_config()
        if isinstance(config, dict):
            merged.update(config)
        if not isinstance(merged.get("logPullDefaults"), dict):
            merged["logPullDefaults"] = cls._default_sync_config()["logPullDefaults"]
        if not isinstance(merged.get("promptTemplates"), dict):
            merged["promptTemplates"] = cls._default_sync_config()["promptTemplates"]
        if not isinstance(merged.get("remoteSync"), dict):
            merged["remoteSync"] = cls._default_remote_sync_config()
        else:
            remote_sync = dict(cls._default_remote_sync_config())
            remote_sync.update(merged.get("remoteSync") or {})
            remote_headers = remote_sync.get("headers") if isinstance(remote_sync.get("headers"), dict) else {}
            remote_sync["headers"] = {**cls._default_remote_sync_config()["headers"], **remote_headers}
            remote_sync["enabled"] = bool(remote_sync.get("enabled"))
            remote_sync["limit"] = min(max(int(remote_sync.get("limit") or 50), 1), 200)
            remote_sync["includeClosed"] = bool(remote_sync.get("includeClosed", True))
            remote_sync["autoTranslateOnPull"] = bool(remote_sync.get("autoTranslateOnPull", True))
            remote_sync["timeoutSec"] = max(int(remote_sync.get("timeoutSec") or 30), 10)
            remote_sync["pullUrl"] = str(remote_sync.get("pullUrl") or "").strip()
            remote_sync["ackUrl"] = str(remote_sync.get("ackUrl") or "").strip()
            remote_sync["consumer"] = str(remote_sync.get("consumer") or "").strip()
            remote_sync["sourceSystem"] = str(remote_sync.get("sourceSystem") or "public").strip() or "public"
            merged["remoteSync"] = remote_sync
        if not isinstance(merged.get("projectMappings"), list):
            merged["projectMappings"] = []
        if not isinstance(merged.get("moduleMappings"), list):
            merged["moduleMappings"] = []
        if not isinstance(merged.get("vendorMappings"), list):
            merged["vendorMappings"] = []
        if not isinstance(merged.get("storeMappings"), list):
            merged["storeMappings"] = []
        if not isinstance(merged.get("statusMappings"), list):
            merged["statusMappings"] = []
        if not isinstance(merged.get("assigneeMappings"), list):
            merged["assigneeMappings"] = []
        if not isinstance(merged.get("posPatterns"), list):
            merged["posPatterns"] = cls._default_sync_config()["posPatterns"]
        if not isinstance(merged.get("scoPatterns"), list):
            merged["scoPatterns"] = cls._default_sync_config()["scoPatterns"]
        if not isinstance(merged.get("versionPatterns"), list):
            merged["versionPatterns"] = cls._default_sync_config()["versionPatterns"]
        merged["autoRunOnSync"] = bool(merged.get("autoRunOnSync"))
        merged["autoTranslateOnSync"] = bool(merged.get("autoTranslateOnSync", True))
        merged["defaultPullLimit"] = min(max(int(merged.get("defaultPullLimit") or 50), 1), 200)
        return merged

    @classmethod
    def ensure_param_config_rows(cls, db: Session) -> None:
        now = datetime.now()
        existing = db.query(SysConfig).filter(SysConfig.config_key == cls.CONFIG_KEY).first()
        if existing:
            return
        db.add(
            SysConfig(
                config_name="工单同步自动化配置",
                config_key=cls.CONFIG_KEY,
                config_value=cls._json_dumps(cls._default_sync_config()),
                config_type="Y",
                create_by="system",
                update_by="system",
                create_time=now,
                update_time=now,
                remark="外部工单同步、内网拉取、规则识别和自动化链路配置 JSON",
            )
        )
        db.flush()

    @classmethod
    def _load_sync_config(cls, db: Session) -> dict[str, Any]:
        cls.ensure_param_config_rows(db)
        row = db.query(SysConfig).filter(SysConfig.config_key == cls.CONFIG_KEY).first()
        config = cls._json_loads(getattr(row, "config_value", None), cls._default_sync_config())
        if not isinstance(config, dict):
            return cls._default_sync_config()
        return cls._normalize_sync_config(config)

    @classmethod
    def get_sync_automation_config_services(cls, db: Session) -> dict[str, Any]:
        return {
            "configKey": cls.CONFIG_KEY,
            "configValue": cls._load_sync_config(db),
        }

    @classmethod
    def update_sync_automation_config_services(
        cls,
        db: Session,
        config_value: dict[str, Any],
        current_user_name: str,
    ) -> CrudResponseModel:
        try:
            merged = cls._normalize_sync_config(config_value)
            now = datetime.now()
            row = db.query(SysConfig).filter(SysConfig.config_key == cls.CONFIG_KEY).first()
            if row:
                row.config_name = "宸ュ崟鍚屾鑷姩鍖栭厤缃?"
                row.config_value = cls._json_dumps(merged)
                row.config_type = "Y"
                row.update_by = current_user_name
                row.update_time = now
            else:
                db.add(
                    SysConfig(
                        config_name="宸ュ崟鍚屾鑷姩鍖栭厤缃?",
                        config_key=cls.CONFIG_KEY,
                        config_value=cls._json_dumps(merged),
                        config_type="Y",
                        create_by=current_user_name,
                        update_by=current_user_name,
                        create_time=now,
                        update_time=now,
                        remark="澶栭儴宸ュ崟鍚屾銆佸唴缃戞媺鍙栥€佽鍒欒瘑鍒拰鑷姩鍖栭摼璺厤缃?JSON",
                    )
                )
            db.commit()
            return CrudResponseModel(is_success=True, message="淇濆瓨鎴愬姛", result=merged)
        except Exception as exc:
            db.rollback()
            raise exc

    @classmethod
    def _build_remote_sync_request_headers(cls, remote_sync: dict[str, Any]) -> dict[str, str]:
        """
        构建远端工单同步请求头。

        :param remote_sync: 远端同步配置。
        :return: 请求头字典。
        """
        headers = dict(remote_sync.get("headers") or {})
        normalized = {str(key).strip().lower(): str(value or "").strip() for key, value in headers.items()}
        result = {"Content-Type": "application/json", "Accept": "application/json"}
        if normalized.get("cookie"):
            result["Cookie"] = normalized["cookie"]
        if normalized.get("authorization"):
            result["Authorization"] = normalized["authorization"]
        if normalized.get("origin"):
            result["Origin"] = normalized["origin"]
        return result

    @classmethod
    def _build_meta(cls, extra_data: dict[str, Any] | None) -> dict[str, Any]:
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
        }
        return meta

    @classmethod
    def _attach_meta(cls, extra_data: dict[str, Any] | None, meta: dict[str, Any]) -> dict[str, Any]:
        payload = dict(extra_data or {})
        payload[cls.META_KEY] = meta
        return payload

    @classmethod
    def extract_sync_summary(cls, extra_data: Any) -> dict[str, Any] | None:
        if not isinstance(extra_data, dict):
            return None
        meta = extra_data.get(cls.META_KEY)
        if not isinstance(meta, dict):
            return None
        sync_state = meta.get("sync_state") if isinstance(meta.get("sync_state"), dict) else {}
        automation = sync_state.get("automation") if isinstance(sync_state.get("automation"), dict) else {}
        return {
            "revision": int(meta.get("revision") or 0),
            "sourceSystem": meta.get("sourceSystem") or meta.get("source", {}).get("system"),
            "sourceRecordId": meta.get("sourceRecordId") or meta.get("source", {}).get("recordId"),
            "status": sync_state.get("status") or "pending",
            "lastPulledAt": sync_state.get("last_pulled_at"),
            "lastConsumer": sync_state.get("last_consumer"),
            "automationStatus": automation.get("status"),
            "automationStep": automation.get("current_step"),
            "automationError": automation.get("last_error"),
        }

    @classmethod
    def _normalize_keywords(cls, value: Any) -> list[str]:
        if isinstance(value, list):
            items = value
        elif isinstance(value, str):
            items = [item.strip() for item in value.split(",")]
        else:
            items = []
        result: list[str] = []
        for item in items:
            text = str(item or "").strip().lower()
            if text and text not in result:
                result.append(text)
        return result

    @classmethod
    def _collect_text(cls, payload: TicketExternalSyncUpsertModel | Ticket) -> str:
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
                cls._json_dumps(raw_payload) if isinstance(raw_payload, dict) else "",
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
                cls._json_dumps(payload.raw_payload) if isinstance(payload.raw_payload, dict) else "",
                cls._json_dumps(payload.extra_data) if isinstance(payload.extra_data, dict) else "",
            ]
        return "\n".join(str(item).strip() for item in parts if str(item or "").strip())

    @classmethod
    def _match_mapping(cls, text: str, mappings: Any) -> dict[str, Any] | None:
        if not isinstance(mappings, list):
            return None
        best_match = None
        best_score = 0
        for mapping in mappings:
            if not isinstance(mapping, dict):
                continue
            keywords = cls._normalize_keywords(mapping.get("keywords") or mapping.get("aliases"))
            if not keywords:
                continue
            score = sum(1 for keyword in keywords if keyword in text)
            if score > best_score:
                best_score = score
                best_match = mapping
        return best_match if best_score > 0 else None

    @classmethod
    def _mapping_keywords(cls, mapping: dict[str, Any]) -> list[str]:
        keywords = cls._normalize_keywords(mapping.get("keywords") or mapping.get("aliases"))
        if mapping.get("matchText"):
            keywords.extend(cls._normalize_keywords([mapping.get("matchText")]))
        return [keyword for keyword in keywords if keyword]

    @classmethod
    def _match_status(cls, text: str, mappings: list[dict[str, Any]]) -> str | None:
        status_map = {
            "pending": TicketStatus.PENDING.value,
            "processing": TicketStatus.PROCESSING.value,
            "wait_user": TicketStatus.WAIT_USER.value,
            "wait_dev": TicketStatus.WAIT_DEV.value,
            "wait_release": TicketStatus.WAIT_RELEASE.value,
            "wait_verify": TicketStatus.WAIT_VERIFY.value,
            "resolved": TicketStatus.RESOLVED.value,
            "closed": TicketStatus.CLOSED.value,
            "rejected": TicketStatus.REJECTED.value,
            "non_problem": TicketStatus.NON_PROBLEM.value,
            "design_as_expected": TicketStatus.DESIGN_AS_EXPECTED.value,
            "user_misoperation": TicketStatus.USER_MISOPERATION.value,
            "duplicated": TicketStatus.DUPLICATED.value,
        }
        matched = cls._match_mapping(text, mappings)
        if isinstance(matched, dict):
            for key in ("status", "ticketStatus", "statusCode", "value"):
                candidate = str(matched.get(key) or "").strip()
                if candidate:
                    return status_map.get(candidate.lower(), candidate)
        lowered = text.lower()
        for alias, status_code in (
            ("待受理", TicketStatus.PENDING.value),
            ("处理中", TicketStatus.PROCESSING.value),
            ("待用户", TicketStatus.WAIT_USER.value),
            ("待开发", TicketStatus.WAIT_DEV.value),
            ("待上线", TicketStatus.WAIT_RELEASE.value),
            ("待验证", TicketStatus.WAIT_VERIFY.value),
            ("已解决", TicketStatus.RESOLVED.value),
            ("已关闭", TicketStatus.CLOSED.value),
            ("已拒绝", TicketStatus.REJECTED.value),
            ("非问题", TicketStatus.NON_PROBLEM.value),
            ("重复", TicketStatus.DUPLICATED.value),
            ("误操作", TicketStatus.USER_MISOPERATION.value),
            ("按预期", TicketStatus.DESIGN_AS_EXPECTED.value),
        ):
            if alias in lowered:
                return status_code
        return None

    @classmethod
    def _match_assignee(cls, db: Session, text: str, mappings: list[dict[str, Any]]) -> tuple[int | None, str]:
        from module_admin.entity.do.user_do import SysUser

        matched = cls._match_mapping(text, mappings)
        if isinstance(matched, dict):
            user_id = cls._safe_int(matched.get("userId") or matched.get("user_id") or matched.get("assigneeId"))
            user_name = str(matched.get("userName") or matched.get("user_name") or matched.get("name") or "").strip()
            if user_id:
                user = db.query(SysUser).filter(SysUser.user_id == user_id, SysUser.status == "0", SysUser.del_flag == "0").first()
                if user:
                    return user.user_id, user.user_name or user.nick_name or user_name
            if user_name:
                user = (
                    db.query(SysUser)
                    .filter(
                        SysUser.status == "0",
                        SysUser.del_flag == "0",
                        (SysUser.user_name == user_name) | (SysUser.nick_name == user_name),
                    )
                    .first()
                )
                if user:
                    return user.user_id, user.user_name or user.nick_name or user_name
                return None, user_name
        lowered = text.lower()
        for user in db.query(SysUser).filter(SysUser.status == "0", SysUser.del_flag == "0").all():
            aliases = cls._normalize_keywords([user.user_name, user.nick_name, user.nick_name and f"{user.user_name}/{user.nick_name}"])
            if any(alias in lowered for alias in aliases):
                return user.user_id, user.user_name or user.nick_name or ""
        return None, ""

    @classmethod
    def _merge_external_text_fields(
        cls,
        base_data: dict[str, Any],
        detected: dict[str, Any],
        sync_object: TicketExternalSyncUpsertModel,
    ) -> dict[str, Any]:
        merged = dict(base_data)
        status_value = str(detected.get("status") or "").strip()
        assignee_id = cls._safe_int(detected.get("assigneeId"))
        assignee_name = str(detected.get("assigneeName") or "").strip()
        if status_value:
            merged["status"] = status_value
        if assignee_id:
            merged["current_assignee_id"] = assignee_id
        if assignee_name:
            merged["current_assignee_name"] = assignee_name

        extra_data = dict(merged.get("extra_data") or {}) if isinstance(merged.get("extra_data"), dict) else {}
        external_sync = extra_data.get(cls.META_KEY) if isinstance(extra_data.get(cls.META_KEY), dict) else {}
        source_snapshot = external_sync.get("source") if isinstance(external_sync.get("source"), dict) else {}
        source_snapshot.update(
            {
                "status": status_value or source_snapshot.get("status"),
                "assigneeId": assignee_id or source_snapshot.get("assigneeId"),
                "assigneeName": assignee_name or source_snapshot.get("assigneeName"),
                "projectName": str(sync_object.project_name or "").strip() or source_snapshot.get("projectName"),
                "moduleName": str(sync_object.module_name or "").strip() or source_snapshot.get("moduleName"),
            }
        )
        external_sync["source"] = source_snapshot
        extra_data[cls.META_KEY] = external_sync
        merged["extra_data"] = extra_data
        return merged

    @classmethod
    def _translate_sync_description(
        cls,
        db: Session,
        *,
        title: str,
        description: str,
        ticket_id: int | None,
        ticket_no: str,
        current_user: CurrentUserModel,
        enabled: bool,
    ) -> tuple[str, dict[str, Any], str]:
        origin_description = str(description or "").strip()
        if not origin_description:
            return "", {"translated_text": "", "skipped": True}, ""
        if not enabled:
            return origin_description, {"translated_text": "", "skipped": True}, origin_description
        translated_description, translation_meta = TicketLightAiService.translate_ticket_description(
            db,
            title=title,
            content=origin_description,
            source_type="ticket",
            source_id=ticket_id,
            source_ref=ticket_no,
            current_user_name=_user_name(current_user),
        )
        if translation_meta.get("skipped") or not str(translation_meta.get("translated_text") or "").strip():
            return origin_description, {**translation_meta, "skipped": True}, origin_description
        return translated_description, translation_meta, origin_description

    @classmethod
    def _extract_pattern(cls, text: str, patterns: Any) -> str | None:
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
    def _match_project(cls, db: Session, text: str, mappings: list[dict[str, Any]]) -> HrmProject | None:
        matched = cls._match_mapping(text, mappings)
        project_id = cls._safe_int(matched.get("projectId") if isinstance(matched, dict) else None)
        if project_id:
            return (
                db.query(HrmProject)
                .filter(
                    HrmProject.project_id == project_id,
                    HrmProject.status == QtrDataStatusEnum.normal.value,
                    HrmProject.del_flag == "0",
                )
                .first()
            )
        projects = (
            db.query(HrmProject)
            .filter(HrmProject.status == QtrDataStatusEnum.normal.value, HrmProject.del_flag == "0")
            .all()
        )
        best_project = None
        best_score = 0
        for project in projects:
            aliases = cls._normalize_keywords([project.project_name])
            score = sum(1 for alias in aliases if alias in text)
            if score > best_score:
                best_score = score
                best_project = project
        return best_project if best_score > 0 else None

    @classmethod
    def _match_module(
        cls,
        db: Session,
        text: str,
        mappings: list[dict[str, Any]],
        project_id: int | None = None,
    ) -> HrmModule | None:
        matched = cls._match_mapping(text, mappings)
        module_id = cls._safe_int(matched.get("moduleId") if isinstance(matched, dict) else None)
        query = db.query(HrmModule).filter(HrmModule.status == QtrDataStatusEnum.normal.value)
        if module_id:
            return query.filter(HrmModule.module_id == module_id).first()
        if project_id:
            query = query.filter(HrmModule.project_id == project_id)
        modules = query.all()
        best_module = None
        best_score = 0
        for module in modules:
            aliases = cls._normalize_keywords([module.module_name])
            score = sum(1 for alias in aliases if alias in text)
            if score > best_score:
                best_score = score
                best_module = module
        return best_module if best_score > 0 else None

    @classmethod
    def _detect_fields(
        cls,
        db: Session,
        sync_object: TicketExternalSyncUpsertModel,
        config: dict[str, Any],
    ) -> dict[str, Any]:
        text = cls._collect_text(sync_object).lower()
        project = cls._match_project(db, text, config.get("projectMappings") or [])
        module = cls._match_module(
            db,
            text,
            config.get("moduleMappings") or [],
            getattr(project, "project_id", None),
        )
        vendor_mapping = cls._match_mapping(text, config.get("vendorMappings") or [])
        store_mapping = cls._match_mapping(text, config.get("storeMappings") or [])
        status_code = cls._match_status(text, config.get("statusMappings") or [])
        assignee_id, assignee_name = cls._match_assignee(db, text, config.get("assigneeMappings") or [])
        version_key = (
            str(sync_object.version_key or "").strip()
            or _extract_ticket_version_key(sync_object.extra_data)
            or str(cls._extract_pattern(text, config.get("versionPatterns")) or "").strip()
        )
        return {
            "projectId": getattr(project, "project_id", None) or sync_object.project_id,
            "projectName": (
                getattr(project, "project_name", "")
                or sync_object.project_name
                or sync_object.merchant_name
                or ""
            ),
            "moduleId": getattr(module, "module_id", None) or sync_object.module_id,
            "moduleName": getattr(module, "module_name", "") or sync_object.module_name or "",
            "vendorId": cls._safe_int((vendor_mapping or {}).get("vendorId"))
            or cls._safe_int((sync_object.log_pull_config or {}).get("vendorId")),
            "vendorName": (vendor_mapping or {}).get("vendorName") or "",
            "storeId": cls._safe_int((store_mapping or {}).get("storeId"))
            or cls._safe_int((sync_object.log_pull_config or {}).get("storeId")),
            "storeName": (store_mapping or {}).get("storeName") or "",
            "status": status_code or str(sync_object.status or "").strip(),
            "assigneeId": assignee_id or cls._safe_int(sync_object.current_assignee_id),
            "assigneeName": assignee_name or str(sync_object.current_assignee_name or "").strip(),
            "posNo": cls._safe_int((sync_object.log_pull_config or {}).get("posNo"))
            or cls._safe_int(cls._extract_pattern(text, config.get("posPatterns"))),
            "scoNo": cls._safe_int(cls._extract_pattern(text, config.get("scoPatterns"))),
            "versionKey": version_key,
            "rawTextLength": len(text),
        }

    @classmethod
    def _update_consumer_state(
        cls,
        meta: dict[str, Any],
        *,
        consumer: str,
        revision: int,
        batch_id: str,
        status: str = "delivered",
        message: str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        sync_state = meta.get("sync_state") if isinstance(meta.get("sync_state"), dict) else {}
        consumers = sync_state.get("consumers") if isinstance(sync_state.get("consumers"), dict) else {}
        consumers[consumer] = {
            "status": status,
            "delivered_revision": revision,
            "delivered_at": cls._now_iso(),
            "batch_id": batch_id,
            "message": message,
            "detail": detail,
        }
        sync_state.update(
            {
                "status": status,
                "last_pulled_at": cls._now_iso(),
                "last_consumer": consumer,
                "last_batch_id": batch_id,
                "consumers": consumers,
            }
        )
        meta["sync_state"] = sync_state
        return meta

    @classmethod
    def _mark_automation_step(
        cls,
        meta: dict[str, Any],
        *,
        step: str,
        status: str,
        detail: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> dict[str, Any]:
        sync_state = meta.get("sync_state") if isinstance(meta.get("sync_state"), dict) else {}
        automation = sync_state.get("automation") if isinstance(sync_state.get("automation"), dict) else {}
        steps = automation.get("steps") if isinstance(automation.get("steps"), dict) else {}
        previous = steps.get(step) if isinstance(steps.get(step), dict) else {}
        steps[step] = {
            **previous,
            "status": status,
            "updated_at": cls._now_iso(),
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
    def _build_upsert_payload(
        cls,
        db: Session,
        ticket: Ticket | None,
        sync_object: TicketExternalSyncUpsertModel,
        detected: dict[str, Any] | None,
        current_user: CurrentUserModel,
    ) -> tuple[dict[str, Any], dict[str, Any], int]:
        now = datetime.now()
        source_extra = dict(ticket.extra_data or {}) if ticket and isinstance(ticket.extra_data, dict) else {}
        extra_data = dict(source_extra)
        if isinstance(sync_object.extra_data, dict):
            extra_data.update(sync_object.extra_data)
        if isinstance(sync_object.raw_payload, dict):
            extra_data["raw_payload"] = sync_object.raw_payload
        meta = cls._build_meta(extra_data)
        revision = int(meta.get("revision") or 0) + 1
        source_snapshot = {
            "system": sync_object.source.system,
            "recordId": sync_object.source.record_id,
            "recordUrl": sync_object.source.record_url,
            "pushedAt": sync_object.source.pushed_at.isoformat() if sync_object.source.pushed_at else cls._now_iso(),
        }
        meta.update(
            {
                "revision": revision,
                "sourceSystem": sync_object.source.system,
                "sourceRecordId": sync_object.source.record_id,
                "sourceRecordUrl": sync_object.source.record_url,
                "lastImportedAt": cls._now_iso(),
                "source": source_snapshot,
            }
        )
        sync_state = meta.get("sync_state") if isinstance(meta.get("sync_state"), dict) else {}
        sync_state.setdefault("status", "pending")
        sync_state.setdefault("automation", {})
        meta["sync_state"] = sync_state
        payload: dict[str, Any] = {
            "ticket_no": sync_object.ticket_no,
            "title": sync_object.title,
            "description": sync_object.description,
            "customer_priority": sync_object.customer_priority or (ticket.customer_priority if ticket else "P3"),
            "internal_priority": sync_object.internal_priority or (ticket.internal_priority if ticket else "P3"),
            "severity": sync_object.severity or (ticket.severity if ticket else ""),
            "source": cls.SOURCE_CODE,
            "reporter_id": sync_object.reporter_id or (ticket.reporter_id if ticket else _user_id(current_user)),
            "reporter_name": sync_object.reporter_name
            or (ticket.reporter_name if ticket else _user_name(current_user)),
            "current_assignee_id": sync_object.current_assignee_id or (ticket.current_assignee_id if ticket else None),
            "current_assignee_name": sync_object.current_assignee_name
            or (ticket.current_assignee_name if ticket else ""),
            "status": sync_object.status or (ticket.status if ticket else TicketStatus.PENDING.value),
            "root_cause": sync_object.root_cause or (ticket.root_cause if ticket else None),
            "solution": sync_object.solution or (ticket.solution if ticket else None),
            "tags": sync_object.tags or (ticket.tags if ticket else None),
            "update_by": _user_name(current_user),
            "update_time": now,
        }
        project_id = sync_object.project_id or cls._safe_int((detected or {}).get("projectId"))
        module_id = sync_object.module_id or cls._safe_int((detected or {}).get("moduleId"))
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
        elif ticket:
            payload["project_id"] = ticket.project_id
            payload["merchant_name"] = ticket.merchant_name
        else:
            payload["merchant_name"] = (
                sync_object.project_name
                or sync_object.merchant_name
                or str((detected or {}).get("projectName") or "").strip()
                or ""
            )
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
        elif ticket:
            payload["module_id"] = ticket.module_id
            payload["module_name"] = ticket.module_name
        else:
            payload["module_name"] = (
                sync_object.module_name
                or str((detected or {}).get("moduleName") or "").strip()
                or ""
            )
        payload = cls._merge_external_text_fields(payload, detected or {}, sync_object)
        version_key = str((detected or {}).get("versionKey") or sync_object.version_key or "").strip()
        if version_key:
            extra_data["version_key"] = version_key
        extra_data = cls._attach_meta(extra_data, meta)
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
    def sync_external_ticket(
        cls,
        db: Session,
        sync_object: TicketExternalSyncUpsertModel,
        current_user: CurrentUserModel,
    ) -> CrudResponseModel:
        ticket = TicketDao.get_ticket_by_no(db, sync_object.ticket_no)
        config = cls._load_sync_config(db)
        detected = cls._detect_fields(db, sync_object, config)
        automation = sync_object.automation
        translation_enabled = TicketLightAiService.is_translation_enabled(db)
        sync_translate_enabled = (
            automation.auto_translate
            if automation is not None
            else bool(config.get("autoTranslateOnSync", True))
        )
        should_translate = translation_enabled and sync_translate_enabled
        translated_description, translation_meta, origin_description = cls._translate_sync_description(
            db,
            title=sync_object.title,
            description=sync_object.description,
            ticket_id=getattr(ticket, "ticket_id", None),
            ticket_no=sync_object.ticket_no,
            current_user=current_user,
            enabled=should_translate,
        )
        if should_translate:
            sync_object = sync_object.model_copy(update={"description": translated_description})
        payload, meta, revision = cls._build_upsert_payload(db, ticket, sync_object, detected, current_user)
        if should_translate and origin_description and str(translation_meta.get("translated_text") or "").strip():
            extra_data = dict(payload.get("extra_data") or {}) if isinstance(payload.get("extra_data"), dict) else {}
            extra_data["origin_description"] = origin_description
            extra_data["ai_translation"] = translation_meta.get("translated_text") or translated_description
            if translation_meta.get("provider_code"):
                extra_data["ai_translation_provider_code"] = translation_meta.get("provider_code")
            if translation_meta.get("prompt_code"):
                extra_data["ai_translation_prompt_code"] = translation_meta.get("prompt_code")
            payload["extra_data"] = extra_data
        now = datetime.now()
        try:
            created = ticket is None
            if created:
                ticket = Ticket(**payload)
                ticket = TicketDao.add_ticket(db, ticket)
                TicketDao.add_status_history(
                    db,
                    TicketStatusHistory(
                        ticket_id=ticket.ticket_id,
                        from_status=None,
                        to_status=ticket.status,
                        operator_id=_user_id(current_user),
                        operator_name=_user_name(current_user),
                        started_at=now,
                        comment="外部同步创建工单",
                    ),
                )
                TicketDao.add_message(
                    db,
                    TicketMessage(
                        ticket_id=ticket.ticket_id,
                        role="system",
                        message_type="sync_import",
                        content=f"外部同步创建工单\n\n{sync_object.title}\n\n{sync_object.description or ''}".strip(),
                        attachments={"source": meta.get("source"), "revision": revision},
                        reference_type="sync",
                        created_by_id=_user_id(current_user),
                        created_by_name=_user_name(current_user),
                        create_time=now,
                    ),
                )
            else:
                TicketDao.update_ticket(db, ticket.ticket_id, payload)
            TicketDao.add_event(
                db,
                TicketEvent(
                    ticket_id=ticket.ticket_id,
                    event_type=(
                        TicketEventType.TICKET_UPDATED.value
                        if not created
                        else TicketEventType.TICKET_CREATED.value
                    ),
                    operator_id=_user_id(current_user),
                    operator_name=_user_name(current_user),
                    content="外部工单同步导入" if created else "外部工单同步更新",
                    event_data={
                        "syncRevision": revision,
                        "sourceSystem": meta.get("sourceSystem"),
                        "sourceRecordId": meta.get("sourceRecordId"),
                        "detected": detected,
                    },
                    create_time=now,
                ),
            )
            db.commit()
        except Exception:
            db.rollback()
            raise

        should_run_automation = bool(
            (
                automation
                and (
                    automation.auto_identify
                    or automation.auto_log_pull
                    or automation.auto_ai_analysis
                )
            )
            or config.get("autoRunOnSync")
        )
        automation_summary = None
        if should_run_automation:
            automation_summary = cls.run_sync_automation(db, ticket.ticket_id, sync_object, detected, current_user)

        result = (
            TicketService.get_ticket_detail_services(db, ticket.ticket_id)
            or CamelCaseUtil.transform_result(ticket)
        )
        result["syncSummary"] = cls.extract_sync_summary(result.get("extraData"))
        if automation_summary:
            result["syncAutomation"] = automation_summary
        return CrudResponseModel(
            is_success=True,
            message="外部工单同步成功",
            result=result,
        )

    @classmethod
    def run_sync_automation(
        cls,
        db: Session,
        ticket_id: int,
        sync_object: TicketExternalSyncUpsertModel,
        detected: dict[str, Any],
        current_user: CurrentUserModel,
    ) -> dict[str, Any]:
        ticket = TicketDao.get_ticket_by_id(db, ticket_id)
        if not ticket:
            return {}
        config = cls._load_sync_config(db)
        automation = sync_object.automation
        extra_data = dict(ticket.extra_data or {}) if isinstance(ticket.extra_data, dict) else {}
        meta = cls._build_meta(extra_data)
        summary: dict[str, Any] = {"detected": detected}
        try:
            cls._mark_automation_step(meta, step="identify", status="success", detail=detected)
            update_data: dict[str, Any] = {}
            detected_project_id = cls._safe_int(detected.get("projectId"))
            detected_module_id = cls._safe_int(detected.get("moduleId"))
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

            search_text = cls._collect_text(ticket)
            similar_tickets = [
                item
                for item in TicketEmbeddingService.search_tickets(db, search_text, 6)
                if item.get("ticketId") != ticket_id
            ]
            summary["similarTickets"] = similar_tickets[:5]
            cls._mark_automation_step(
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
                log_pull_payload.update(
                    {
                        "ticketId": ticket_id,
                        "vendorId": detected.get("vendorId") or log_pull_payload.get("vendorId"),
                        "storeId": detected.get("storeId") or log_pull_payload.get("storeId"),
                        "posNo": detected.get("posNo") or detected.get("scoNo") or log_pull_payload.get("posNo"),
                    }
                )
                if automation.auto_ai_analysis:
                    log_pull_payload["autoAiEnabled"] = True
                    log_pull_payload["aiAgentCode"] = automation.ai_agent_code
                    log_pull_payload["aiProviderCode"] = automation.ai_provider_code
                try:
                    create_model = TicketLogPullCreateModel.model_validate(log_pull_payload)
                    log_result = TicketLogPullService.create_log_pull_services(
                        db, ticket_id, create_model, current_user
                    )
                    if log_result.is_success:
                        summary["logPull"] = log_result.result
                        cls._mark_automation_step(meta, step="log_pull", status="submitted", detail=log_result.result)
                        if automation.auto_ai_analysis:
                            cls._mark_automation_step(
                                meta,
                                step="ai_analysis",
                                status="queued",
                                detail={"via": "log_pull_auto_ai", "agentCode": automation.ai_agent_code},
                            )
                    else:
                        summary["logPullError"] = log_result.message
                        cls._mark_automation_step(meta, step="log_pull", status="failed", error=log_result.message)
                except Exception as exc:
                    summary["logPullError"] = str(exc)
                    cls._mark_automation_step(meta, step="log_pull", status="failed", error=str(exc))
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
                        cls._mark_automation_step(meta, step="ai_analysis", status="submitted", detail=ai_result.result)
                    else:
                        summary["aiAnalysisError"] = ai_result.message
                        cls._mark_automation_step(meta, step="ai_analysis", status="failed", error=ai_result.message)
                else:
                    reason = "缺少版本号或可用日志记录，跳过自动 AI"
                    summary["aiAnalysisSkipReason"] = reason
                    cls._mark_automation_step(meta, step="ai_analysis", status="skipped", detail={"reason": reason})
        except Exception as exc:
            cls._mark_automation_step(meta, step="automation", status="failed", error=str(exc))
            logger.exception("工单[%s]同步自动化执行异常: %s", ticket_id, exc)
        finally:
            ticket = TicketDao.get_ticket_by_id(db, ticket_id)
            extra_data = dict(ticket.extra_data or {}) if ticket and isinstance(ticket.extra_data, dict) else {}
            extra_data = cls._attach_meta(extra_data, meta)
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

    @classmethod
    def pull_pending_tickets(
        cls,
        db: Session,
        query: TicketSyncPullQueryModel,
        current_user: CurrentUserModel,
    ) -> dict[str, Any]:
        rows = TicketDao.get_tickets_for_sync(
            db,
            consumer=query.consumer,
            limit=query.limit,
            include_closed=query.include_closed,
        )
        batch_id = f"{query.consumer}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        payload_rows: list[dict[str, Any]] = []
        for ticket in rows:
            extra_data = dict(ticket.extra_data or {}) if isinstance(ticket.extra_data, dict) else {}
            meta = cls._build_meta(extra_data)
            revision = int(meta.get("revision") or 0)
            meta = cls._update_consumer_state(meta, consumer=query.consumer, revision=revision, batch_id=batch_id)
            extra_data = cls._attach_meta(extra_data, meta)
            TicketDao.update_ticket(
                db,
                ticket.ticket_id,
                {
                    "extra_data": extra_data,
                    "update_by": _user_name(current_user),
                    "update_time": datetime.now(),
                },
            )
            item = (
                TicketService.get_ticket_detail_services(db, ticket.ticket_id)
                or CamelCaseUtil.transform_result(ticket)
            )
            item["syncRevision"] = revision
            item["syncSummary"] = cls.extract_sync_summary(extra_data)
            payload_rows.append(item)
        db.commit()
        return {
            "consumer": query.consumer,
            "batchId": batch_id,
            "count": len(payload_rows),
            "items": payload_rows,
        }

    @classmethod
    def ack_sync_delivery(
        cls,
        db: Session,
        request: TicketSyncAckRequestModel,
        current_user: CurrentUserModel,
    ) -> CrudResponseModel:
        updated = 0
        try:
            for item in request.items:
                ticket = TicketDao.get_ticket_by_id(db, item.ticket_id)
                if not ticket:
                    continue
                extra_data = dict(ticket.extra_data or {}) if isinstance(ticket.extra_data, dict) else {}
                meta = cls._build_meta(extra_data)
                meta = cls._update_consumer_state(
                    meta,
                    consumer=request.consumer,
                    revision=item.sync_revision,
                    batch_id=(meta.get("sync_state", {}) or {}).get("last_batch_id") or "",
                    status=item.delivery_status,
                    message=item.message,
                    detail=item.detail,
                )
                extra_data = cls._attach_meta(extra_data, meta)
                TicketDao.update_ticket(
                    db,
                    ticket.ticket_id,
                    {
                        "extra_data": extra_data,
                        "update_by": _user_name(current_user),
                        "update_time": datetime.now(),
                    },
                )
                updated += 1
            db.commit()
            return CrudResponseModel(is_success=True, message="同步回执已更新", result={"updated": updated})
        except Exception:
            db.rollback()
            raise

    @classmethod
    def _build_remote_sync_upsert_model(
        cls,
        item: dict[str, Any],
        *,
        remote_sync: dict[str, Any],
    ) -> TicketExternalSyncUpsertModel | None:
        """
        将远端拉取的工单数据转换为外部同步入库模型。

        :param item: 远端返回的工单字典。
        :param remote_sync: 远端同步配置。
        :return: 可用于外部同步入库的模型，失败时返回 None。
        """
        ticket_no = str(item.get("ticketNo") or item.get("ticket_no") or "").strip()
        title = str(item.get("title") or "").strip()
        if not ticket_no or not title:
            return None

        source_payload = {
            "system": str(remote_sync.get("sourceSystem") or "public").strip() or "public",
            "recordId": str(item.get("ticketId") or item.get("ticket_id") or ticket_no).strip() or ticket_no,
            "recordUrl": str(item.get("ticketUrl") or item.get("ticket_url") or "").strip() or None,
            "pushedAt": (
                item.get("updateTime")
                or item.get("update_time")
                or item.get("createTime")
                or item.get("create_time")
            ),
        }
        sync_payload = {
            "source": source_payload,
            "syncConsumer": str(remote_sync.get("consumer") or "").strip() or None,
            "rawPayload": item,
            "ticketNo": ticket_no,
            "title": title,
            "description": item.get("description") or "",
            "projectId": item.get("projectId") or item.get("project_id"),
            "projectName": item.get("projectName") or item.get("project_name") or item.get("merchantName") or "",
            "merchantName": item.get("merchantName") or item.get("projectName") or item.get("project_name") or "",
            "moduleId": item.get("moduleId") or item.get("module_id"),
            "moduleName": item.get("moduleName") or item.get("module_name") or "",
            "versionKey": item.get("versionKey") or item.get("version_key") or "",
            "status": item.get("status") or "",
            "customerPriority": item.get("customerPriority") or item.get("customer_priority") or "P3",
            "internalPriority": item.get("internalPriority") or item.get("internal_priority") or "P3",
            "severity": item.get("severity") or "",
            "reporterId": item.get("reporterId") or item.get("reporter_id"),
            "reporterName": item.get("reporterName") or item.get("reporter_name") or "",
            "currentAssigneeId": item.get("currentAssigneeId") or item.get("current_assignee_id"),
            "currentAssigneeName": item.get("currentAssigneeName") or item.get("current_assignee_name") or "",
            "rootCause": item.get("rootCause") or item.get("root_cause") or "",
            "solution": item.get("solution") or "",
            "tags": item.get("tags"),
            "extraData": item.get("extraData") or item.get("extra_data") or {},
            "createBy": item.get("createBy") or item.get("create_by") or "",
            "updateBy": item.get("updateBy") or item.get("update_by") or "",
        }
        try:
            return TicketExternalSyncUpsertModel.model_validate(sync_payload)
        except Exception as exc:
            logger.warning(f"转换远端工单同步模型失败，ticket_no={ticket_no}, error={exc}")
            return None

    @classmethod
    def sync_remote_pending_tickets(
        cls,
        db: Session,
        current_user: CurrentUserModel | None = None,
        remote_sync_override: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        从远端公网环境拉取未同步工单，入库后回写远端交付状态。

        :param db: 数据库会话。
        :param current_user: 当前用户，定时任务场景可为空。
        :param remote_sync_override: 可选远端同步覆盖配置。
        :return: 同步汇总结果。
        """
        config = cls._load_sync_config(db)
        remote_sync = dict(config.get("remoteSync") or cls._default_remote_sync_config())
        if remote_sync_override:
            override_remote_sync = (
                remote_sync_override.get("remoteSync")
                if isinstance(remote_sync_override, dict)
                else None
            )
            if isinstance(override_remote_sync, dict):
                remote_sync.update(override_remote_sync)
            elif isinstance(remote_sync_override, dict):
                remote_sync.update(remote_sync_override)
        remote_sync["pullUrl"] = str(remote_sync.get("pullUrl") or "").strip()
        remote_sync["ackUrl"] = str(remote_sync.get("ackUrl") or "").strip()
        remote_sync["consumer"] = str(remote_sync.get("consumer") or "").strip()
        remote_sync["sourceSystem"] = str(remote_sync.get("sourceSystem") or "public").strip() or "public"
        remote_sync["limit"] = min(max(int(remote_sync.get("limit") or config.get("defaultPullLimit") or 50), 1), 200)
        remote_sync["includeClosed"] = bool(remote_sync.get("includeClosed", True))
        remote_sync["autoTranslateOnPull"] = bool(remote_sync.get("autoTranslateOnPull", True))
        remote_sync["timeoutSec"] = max(int(remote_sync.get("timeoutSec") or 30), 10)
        remote_sync["headers"] = {
            **cls._default_remote_sync_config()["headers"],
            **(remote_sync.get("headers") if isinstance(remote_sync.get("headers"), dict) else {}),
        }

        if not remote_sync.get("enabled"):
            logger.info(
                "远端工单拉取已跳过：配置未启用 | consumer={} source_system={}",
                remote_sync["consumer"] or "-",
                remote_sync["sourceSystem"],
            )
            return {
                "consumer": remote_sync["consumer"],
                "batchId": "",
                "pulledCount": 0,
                "syncedCount": 0,
                "failedCount": 0,
                "ackedCount": 0,
                "skipped": True,
                "skipReason": "远端同步未启用",
            }

        if not remote_sync.get("pullUrl"):
            raise ValueError("远端工单拉取地址未配置，请检查 ticket.sync.automation.remoteSync.pullUrl")
        if not remote_sync.get("ackUrl"):
            raise ValueError("远端工单回写地址未配置，请检查 ticket.sync.automation.remoteSync.ackUrl")
        if not remote_sync.get("consumer"):
            raise ValueError("远端工单同步消费者未配置，请检查 ticket.sync.automation.remoteSync.consumer")

        logger.info(
            f"开始拉取远端工单同步数据 | pull_url={remote_sync['pullUrl']} ack_url={remote_sync['ackUrl']} "
            f"consumer={remote_sync['consumer']} limit={remote_sync['limit']} "
            f"include_closed={remote_sync['includeClosed']}"
        )
        response = requests.get(
            remote_sync["pullUrl"],
            params={
                "consumer": remote_sync["consumer"],
                "limit": remote_sync["limit"],
                "includeClosed": remote_sync["includeClosed"],
            },
            timeout=(10, remote_sync["timeoutSec"]),
            headers=cls._build_remote_sync_request_headers(remote_sync),
        )
        response.raise_for_status()
        payload = response.json()
        if int(payload.get("code") or 0) != 200:
            raise RuntimeError(f"远端工单拉取失败: {payload.get('msg') or payload}")

        data = payload.get("data")
        if isinstance(data, dict):
            items = data.get("items") if isinstance(data.get("items"), list) else []
            batch_id = str(data.get("batchId") or "")
        elif isinstance(data, list):
            items = data
            batch_id = ""
        else:
            items = []
            batch_id = ""

        summary = {
            "consumer": remote_sync["consumer"],
            "batchId": batch_id,
            "pulledCount": len(items),
            "syncedCount": 0,
            "failedCount": 0,
            "ackedCount": 0,
        }
        ack_items: list[dict[str, Any]] = []

        for item in items:
            if not isinstance(item, dict):
                continue
            remote_ticket_id = int(item.get("ticketId") or item.get("ticket_id") or 0)
            sync_revision = int(
                item.get("syncRevision")
                or (item.get("syncSummary") or {}).get("revision")
                or item.get("revision")
                or 0
            )
            upsert_model = cls._build_remote_sync_upsert_model(item, remote_sync=remote_sync)
            if not upsert_model:
                summary["failedCount"] += 1
                if remote_ticket_id:
                    ack_items.append(
                        {
                            "ticketId": remote_ticket_id,
                            "syncRevision": sync_revision,
                            "deliveryStatus": "failed",
                            "message": "远端工单数据缺少 ticketNo 或 title",
                        }
                    )
                continue

            upsert_model = upsert_model.model_copy(
                update={
                    "automation": TicketSyncAutomationModel(
                        auto_identify=False,
                        auto_log_pull=False,
                        auto_ai_analysis=False,
                        auto_translate=bool(remote_sync.get("autoTranslateOnPull", True)),
                    )
                }
            )

            try:
                sync_result = cls.sync_external_ticket(db, upsert_model, current_user)
                if sync_result.is_success:
                    summary["syncedCount"] += 1
                    local_ticket_id = None
                    if isinstance(sync_result.result, dict):
                        local_ticket_id = sync_result.result.get("ticketId") or sync_result.result.get("ticket_id")
                    ack_items.append(
                        {
                            "ticketId": remote_ticket_id,
                            "syncRevision": sync_revision,
                            "deliveryStatus": "delivered",
                            "message": sync_result.message,
                            "detail": {"localTicketId": local_ticket_id},
                        }
                    )
                else:
                    summary["failedCount"] += 1
                    if remote_ticket_id:
                        ack_items.append(
                            {
                                "ticketId": remote_ticket_id,
                                "syncRevision": sync_revision,
                                "deliveryStatus": "failed",
                                "message": sync_result.message,
                            }
                        )
            except Exception as exc:
                summary["failedCount"] += 1
                logger.exception(f"远端工单同步入库失败，ticketId={remote_ticket_id}, error={exc}")
                if remote_ticket_id:
                    ack_items.append(
                        {
                            "ticketId": remote_ticket_id,
                            "syncRevision": sync_revision,
                            "deliveryStatus": "failed",
                            "message": str(exc),
                            "detail": {"error": str(exc)},
                        }
                    )

        if ack_items:
            ack_response = requests.post(
                remote_sync["ackUrl"],
                json={"consumer": remote_sync["consumer"], "items": ack_items},
                timeout=(10, remote_sync["timeoutSec"]),
                headers=cls._build_remote_sync_request_headers(remote_sync),
            )
            ack_response.raise_for_status()
            ack_payload = ack_response.json()
            if int(ack_payload.get("code") or 0) != 200:
                raise RuntimeError(f"远端工单回写失败: {ack_payload.get('msg') or ack_payload}")
            summary["ackedCount"] = len(ack_items)

        return summary
