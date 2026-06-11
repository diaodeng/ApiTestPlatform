import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any

import requests
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from config.database import SessionLocal
from module_admin.entity.do.config_do import SysConfig
from module_admin.entity.vo.user_vo import CurrentUserModel
from module_hrm.entity.do.module_do import HrmModule
from module_hrm.entity.do.project_do import HrmProject
from module_hrm.entity.vo.common_vo import CrudResponseModel
from module_hrm.enums.enums import QtrDataStatusEnum
from modules.ticket.dao.ticket_ai_dao import TicketAiDao
from modules.ticket.dao.ticket_dao import TicketDao
from modules.ticket.entity.do.ticket_do import Ticket, TicketEvent, TicketMessage, TicketStatusHistory
from modules.ticket.entity.do.ticket_log_pull_do import TicketLogPullProjectVendorMap, TicketLogPullStoreConfig
from modules.ticket.entity.vo.ticket_log_pull_vo import TicketLogPullCreateModel
from modules.ticket.entity.vo.ticket_vo import (
    TicketAiAnalysisRequestModel,
    TicketBatchReclassifyRequestModel,
    TicketExternalSyncUpsertModel,
    TicketSyncAckRequestModel,
    TicketSyncAutomationModel,
    TicketSyncPullQueryModel,
)
from modules.ticket.enums.ticket_enums import TicketAiAnalysisStatus, TicketEventType, TicketStatus
from modules.ticket.service.ticket_ai_analysis_service import TicketAiAnalysisService
from modules.ticket.service.ticket_embedding_service import TicketEmbeddingService
from modules.ticket.service.ticket_light_ai_service import TicketLightAiService
from modules.ticket.service.ticket_log_pull_service import TicketLogPullService
from modules.ticket.service.ticket_service import TicketService, _extract_ticket_version_key, _user_id, _user_name
from modules.ticket.service.ticket_sync_notify_service import TicketSyncNotifyService
from utils.common_util import CamelCaseUtil
from utils.log_util import logger


class TicketSyncService:
    """
    工单外部同步服务，统一处理外部推送、内网拉取和同步后自动化状态追踪。
    """

    CONFIG_KEY = "ticket.sync.automation"
    SOURCE_CODE = "external_sync"
    META_KEY = "external_sync"
    CELERY_DISPATCH_MODE = "celery"
    BACKGROUND_DISPATCH_MODE = "background"
    PUBLISH_STATUS_READY = "ready"
    PUBLISH_STATUS_PROCESSING_AI = "processing_ai"
    AI_PENDING_AUTOMATION_STATUSES = {"queued", "submitted", "running"}
    AI_PENDING_TASK_STATUSES = {
        TicketAiAnalysisStatus.CREATED.value,
        TicketAiAnalysisStatus.RUNNING.value,
    }

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
    def _text_sha256(cls, value: Any) -> str:
        """
        计算文本的 SHA256 摘要，用于判断翻译源是否变化。

        :param value: 原始文本。
        :return: 文本摘要，空值返回空字符串。
        """
        normalized = str(value or "").strip()
        if not normalized:
            return ""
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    @classmethod
    def _set_publish_state(
        cls,
        meta: dict[str, Any],
        *,
        ready: bool,
        status: str,
        reason: str = "",
        ai_task_status: str | None = None,
    ) -> dict[str, Any]:
        """
        更新同步数据发布状态。
        :param meta: 同步元数据
        :param ready: 是否允许对外发布（内网拉取/群推送）
        :param status: 发布状态编码
        :param reason: 状态说明
        :param ai_task_status: AI任务状态
        :return: 更新后的同步元数据
        """
        sync_state = meta.get("sync_state") if isinstance(meta.get("sync_state"), dict) else {}
        sync_state["publish_ready"] = bool(ready)
        sync_state["publish_status"] = str(status or "").strip() or cls.PUBLISH_STATUS_READY
        sync_state["publish_reason"] = str(reason or "").strip()
        sync_state["publish_updated_at"] = cls._now_iso()
        if ai_task_status is not None:
            sync_state["ai_task_status"] = str(ai_task_status or "").strip()
        meta["sync_state"] = sync_state
        return meta

    @classmethod
    def _is_publish_ready(cls, meta: dict[str, Any]) -> bool:
        """
        判断同步数据是否允许对外发布。
        :param meta: 同步元数据
        :return: 是否可发布
        """
        sync_state = meta.get("sync_state") if isinstance(meta.get("sync_state"), dict) else {}
        if "publish_ready" not in sync_state:
            return True
        return bool(sync_state.get("publish_ready"))

    @classmethod
    def _is_group_push_sent_once(cls, meta: dict[str, Any]) -> bool:
        """
        判断工单是否已成功发送过群推送。
        :param meta: 同步元数据
        :return: 是否已发送过
        """
        sync_state = meta.get("sync_state") if isinstance(meta.get("sync_state"), dict) else {}
        return bool(sync_state.get("group_push_sent_once"))

    @classmethod
    def _mark_group_push_sent_once(
        cls,
        meta: dict[str, Any],
        *,
        scene: str,
        revision: int,
    ) -> dict[str, Any]:
        """
        标记工单已成功发送过群推送（仅一次）。
        :param meta: 同步元数据
        :param scene: 触发场景
        :param revision: 同步修订号
        :return: 更新后的同步元数据
        """
        sync_state = meta.get("sync_state") if isinstance(meta.get("sync_state"), dict) else {}
        sync_state["group_push_sent_once"] = True
        sync_state["group_push_sent_at"] = cls._now_iso()
        sync_state["group_push_scene"] = str(scene or "").strip() or "external_sync"
        sync_state["group_push_revision"] = int(revision or 0)
        meta["sync_state"] = sync_state
        return meta

    @classmethod
    def _resolve_ai_pending_state(
        cls,
        db: Session,
        *,
        ticket_id: int,
        meta: dict[str, Any],
    ) -> tuple[bool, str]:
        """
        判断工单是否仍处于 AI 处理中状态。
        :param db: 数据库会话
        :param ticket_id: 工单ID
        :param meta: 同步元数据
        :return: (是否处理中, AI状态文本)
        """
        sync_state = meta.get("sync_state") if isinstance(meta.get("sync_state"), dict) else {}
        automation = sync_state.get("automation") if isinstance(sync_state.get("automation"), dict) else {}
        steps = automation.get("steps") if isinstance(automation.get("steps"), dict) else {}
        ai_step = steps.get("ai_analysis") if isinstance(steps.get("ai_analysis"), dict) else {}
        ai_step_status = str(ai_step.get("status") or "").strip().lower()
        ai_task_status = str(sync_state.get("ai_task_status") or "").strip().lower()
        ai_terminal_statuses = {
            TicketAiAnalysisStatus.SUCCESS.value,
            TicketAiAnalysisStatus.FAILED.value,
            TicketAiAnalysisStatus.CANCELED.value,
        }

        latest_task = TicketAiDao.get_latest_task_by_ticket_id(db, ticket_id)
        latest_status = str(getattr(latest_task, "status", "") or "").strip().lower()
        if latest_status in cls.AI_PENDING_TASK_STATUSES:
            return True, latest_status
        if latest_status in ai_terminal_statuses:
            return False, latest_status
        if ai_task_status in ai_terminal_statuses:
            return False, ai_task_status
        if ai_task_status in cls.AI_PENDING_TASK_STATUSES:
            return True, ai_task_status
        if ai_step_status in cls.AI_PENDING_AUTOMATION_STATUSES:
            return True, ai_task_status or ai_step_status
        if latest_status:
            return False, latest_status
        if ai_task_status:
            return False, ai_task_status
        return False, ai_step_status

    @classmethod
    def _persist_sync_meta(
        cls,
        db: Session,
        *,
        ticket: Ticket,
        meta: dict[str, Any],
        update_by: str,
    ) -> Ticket:
        """
        将同步元数据回写到工单并提交。
        :param db: 数据库会话
        :param ticket: 工单对象
        :param meta: 同步元数据
        :param update_by: 更新人
        :return: 刷新后的工单对象
        """
        extra_data = dict(ticket.extra_data or {}) if isinstance(ticket.extra_data, dict) else {}
        extra_data = cls._attach_meta(extra_data, meta)
        TicketDao.update_ticket(
            db,
            ticket.ticket_id,
            {
                "extra_data": extra_data,
                "update_by": update_by,
                "update_time": datetime.now(),
            },
        )
        db.commit()
        return TicketDao.get_ticket_by_id(db, ticket.ticket_id) or ticket

    @classmethod
    def _send_auto_group_message_once(
        cls,
        db: Session,
        *,
        ticket: Ticket,
        meta: dict[str, Any],
        group_config: dict[str, Any],
        scene: str,
        update_by: str,
    ) -> tuple[dict[str, Any], Ticket, dict[str, Any]]:
        """
        自动触发群推送（仅发送一次）。
        :param db: 数据库会话
        :param ticket: 工单对象
        :param meta: 同步元数据
        :param group_config: 群推送配置
        :param scene: 触发场景
        :param update_by: 更新人
        :return: (推送结果, 刷新后的工单, 最新元数据)
        """
        if not cls._is_publish_ready(meta):
            logger.info(
                f"自动群推送跳过: ticket_no={ticket.ticket_no}, scene={scene}, "
                f"reason=同步数据未发布就绪"
            )
            return (
                {"skipped": True, "skipReason": "同步数据未发布就绪", "scene": scene},
                ticket,
                meta,
            )
        if cls._is_group_push_sent_once(meta):
            logger.info(
                f"自动群推送跳过: ticket_no={ticket.ticket_no}, scene={scene}, "
                f"reason=工单已发送过群推送"
            )
            return (
                {"skipped": True, "skipReason": "工单已发送过群推送", "scene": scene},
                ticket,
                meta,
            )

        sync_summary = cls.extract_sync_summary(
            cls._attach_meta(dict(ticket.extra_data or {}) if isinstance(ticket.extra_data, dict) else {}, meta)
        ) or {}
        result = TicketSyncNotifyService.send_group_message_for_ticket(
            db,
            ticket=ticket,
            group_config=group_config,
            scene=scene,
            manual_trigger=False,
            sync_summary=sync_summary,
        )
        push_success_count = int(result.get("pushSuccessCount") or 0)
        app_success_count = int(result.get("chatSuccessCount") or 0)
        if not bool(result.get("skipped")) and (push_success_count > 0 or app_success_count > 0):
            meta = cls._mark_group_push_sent_once(
                meta,
                scene=scene,
                revision=int(meta.get("revision") or 0),
            )
            ticket = cls._persist_sync_meta(
                db,
                ticket=ticket,
                meta=meta,
                update_by=update_by,
            )
            logger.info(
                f"自动群推送已标记去重: ticket_no={ticket.ticket_no}, scene={scene}, "
                f"push_success_count={push_success_count}, app_success_count={app_success_count}"
            )
        elif not bool(result.get("skipped")):
            logger.warning(
                f"自动群推送未产生成功发送，保持未去重状态: ticket_no={ticket.ticket_no}, scene={scene}, "
                f"push_success_count={push_success_count}, app_success_count={app_success_count}"
            )
        return result, ticket, meta

    @classmethod
    def _finalize_publish_state_after_post_process(
        cls,
        db: Session,
        *,
        ticket: Ticket,
        sync_scene: str,
        update_by: str,
    ) -> tuple[Ticket, dict[str, Any], dict[str, Any] | None]:
        """
        根据 AI 状态收敛发布状态，并按需触发自动群推送。
        :param db: 数据库会话
        :param ticket: 工单对象
        :param sync_scene: 触发场景
        :param update_by: 更新人
        :return: (刷新后的工单, 元数据, 群推送结果)
        """
        extra_data = dict(ticket.extra_data or {}) if isinstance(ticket.extra_data, dict) else {}
        meta = cls._build_meta(extra_data)
        ai_pending, ai_status = cls._resolve_ai_pending_state(db, ticket_id=ticket.ticket_id, meta=meta)
        ai_task_status = str(ai_status or "").strip().lower()
        if ai_pending:
            meta = cls._set_publish_state(
                meta,
                ready=False,
                status=cls.PUBLISH_STATUS_PROCESSING_AI,
                reason="AI分析处理中，暂不对外发布",
                ai_task_status=ai_task_status or TicketAiAnalysisStatus.RUNNING.value,
            )
            ticket = cls._persist_sync_meta(
                db,
                ticket=ticket,
                meta=meta,
                update_by=update_by,
            )
            return ticket, meta, {"skipped": True, "skipReason": "AI分析处理中，暂不推送", "scene": sync_scene}

        reason = "AI分析已结束，允许对外发布" if ai_task_status else "后处理完成，允许对外发布"
        meta = cls._set_publish_state(
            meta,
            ready=True,
            status=cls.PUBLISH_STATUS_READY,
            reason=reason,
            ai_task_status=ai_task_status,
        )
        ticket = cls._persist_sync_meta(
            db,
            ticket=ticket,
            meta=meta,
            update_by=update_by,
        )
        config = cls._load_sync_config(db)
        group_config = config.get("groupPush") if isinstance(config.get("groupPush"), dict) else {}
        group_push_result, ticket, meta = cls._send_auto_group_message_once(
            db,
            ticket=ticket,
            meta=meta,
            group_config=group_config,
            scene=sync_scene,
            update_by=update_by,
        )
        return ticket, meta, group_push_result

    @classmethod
    def finalize_sync_after_ai(
        cls,
        db: Session,
        *,
        ticket_id: int,
        ai_task_status: str,
        sync_scene: str = "external_sync",
    ) -> None:
        """
        在 AI 任务终态后收敛同步发布状态并补发一次自动群推送。
        :param db: 数据库会话
        :param ticket_id: 工单ID
        :param ai_task_status: AI任务状态
        :param sync_scene: 触发场景
        :return: 无
        """
        try:
            ticket = TicketDao.get_ticket_by_id(db, ticket_id)
            if not ticket:
                return
            extra_data = dict(ticket.extra_data or {}) if isinstance(ticket.extra_data, dict) else {}
            meta = cls._build_meta(extra_data)
            normalized_status = str(ai_task_status or "").strip().lower()
            if normalized_status in cls.AI_PENDING_TASK_STATUSES:
                meta = cls._set_publish_state(
                    meta,
                    ready=False,
                    status=cls.PUBLISH_STATUS_PROCESSING_AI,
                    reason="AI分析处理中，暂不对外发布",
                    ai_task_status=normalized_status,
                )
                cls._persist_sync_meta(db, ticket=ticket, meta=meta, update_by="system")
                return

            reason = (
                "AI分析成功，允许对外发布"
                if normalized_status == TicketAiAnalysisStatus.SUCCESS.value
                else "AI分析结束，允许对外发布"
            )
            meta = cls._set_publish_state(
                meta,
                ready=True,
                status=cls.PUBLISH_STATUS_READY,
                reason=reason,
                ai_task_status=normalized_status,
            )
            ticket = cls._persist_sync_meta(db, ticket=ticket, meta=meta, update_by="system")
            config = cls._load_sync_config(db)
            group_config = config.get("groupPush") if isinstance(config.get("groupPush"), dict) else {}
            cls._send_auto_group_message_once(
                db,
                ticket=ticket,
                meta=meta,
                group_config=group_config,
                scene=sync_scene,
                update_by="system",
            )
        except Exception as exc:
            db.rollback()
            logger.warning(
                f"AI任务完成后同步发布状态回写失败: "
                f"ticket_id={ticket_id}, ai_task_status={ai_task_status}, error={exc}"
            )

    @classmethod
    def _safe_int(cls, value: Any) -> int | None:
        try:
            if value in (None, ""):
                return None
            return int(value)
        except Exception:
            return None

    @classmethod
    def _parse_datetime_value(cls, value: Any) -> datetime | None:
        """
        将多种时间格式解析为可比较的 datetime。
        :param value: 原始时间值
        :return: datetime，失败返回 None
        """
        if value in (None, ""):
            return None
        parsed: datetime | None = None
        if isinstance(value, datetime):
            parsed = value
        elif isinstance(value, (int, float)):
            timestamp = float(value)
            if timestamp > 10_000_000_000:
                timestamp = timestamp / 1000.0
            try:
                parsed = datetime.fromtimestamp(timestamp, tz=timezone.utc)
            except Exception:
                parsed = None
        else:
            text = str(value or "").strip()
            if not text:
                return None
            try:
                parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            except Exception:
                parsed = None
            if parsed is None:
                for fmt in (
                    "%Y-%m-%d %H:%M:%S",
                    "%Y/%m/%d %H:%M:%S",
                    "%Y-%m-%d %H:%M",
                    "%Y/%m/%d %H:%M",
                    "%Y-%m-%d",
                    "%Y/%m/%d",
                ):
                    try:
                        parsed = datetime.strptime(text, fmt)
                        break
                    except Exception:
                        continue
        if parsed is None:
            return None
        if parsed.tzinfo is not None:
            try:
                parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
            except Exception:
                parsed = parsed.replace(tzinfo=None)
        return parsed

    @classmethod
    def _resolve_external_create_time(
        cls,
        *,
        sync_object: TicketExternalSyncUpsertModel,
        existing_meta: dict[str, Any] | None,
    ) -> str:
        """
        解析并固定外部工单创建时间。
        :param sync_object: 外部同步模型
        :param existing_meta: 已存在的同步元数据
        :return: ISO 格式创建时间文本
        """
        current_meta = existing_meta if isinstance(existing_meta, dict) else {}
        source_snapshot = current_meta.get("source") if isinstance(current_meta.get("source"), dict) else {}
        existing_external_time = (
            current_meta.get("externalCreateTime")
            or source_snapshot.get("externalCreateTime")
        )
        parsed_existing = cls._parse_datetime_value(existing_external_time)
        if parsed_existing:
            return parsed_existing.isoformat()

        raw_payload = sync_object.raw_payload if isinstance(sync_object.raw_payload, dict) else {}
        parsed_candidate = (
            cls._parse_datetime_value(sync_object.create_time)
            or cls._parse_datetime_value(raw_payload.get("externalCreateTime"))
            or cls._parse_datetime_value(raw_payload.get("external_create_time"))
            or cls._parse_datetime_value(raw_payload.get("createTime"))
            or cls._parse_datetime_value(raw_payload.get("create_time"))
            or cls._parse_datetime_value(sync_object.source.pushed_at)
            or datetime.now()
        )
        return parsed_candidate.isoformat()

    @classmethod
    def _has_successful_ai_translation(cls, ticket: Ticket | None, source_description: str | None = None) -> bool:
        """
        判断工单是否已有成功的 AI 翻译结果。

        :param ticket: 工单对象
        :param source_description: 本次待翻译原文；传入后会校验是否与历史翻译源一致。
        :return: 是否已存在翻译结果
        """
        if not ticket or not isinstance(ticket.extra_data, dict):
            return False
        extra_data = ticket.extra_data
        translated_text = str(extra_data.get("ai_translation") or "").strip()
        if not translated_text:
            return False
        normalized_source = str(source_description or "").strip()
        if not normalized_source:
            return True
        source_hash = cls._text_sha256(normalized_source)
        stored_source_hash = str(extra_data.get("ai_translation_source_hash") or "").strip()
        if stored_source_hash:
            return stored_source_hash == source_hash
        origin_description = str(extra_data.get("origin_description") or "").strip()
        if origin_description:
            return cls._text_sha256(origin_description) == source_hash
        legacy_source_description = str(extra_data.get("ai_translation_source_description") or "").strip()
        if legacy_source_description:
            return cls._text_sha256(legacy_source_description) == source_hash
        return False

    @classmethod
    def _should_apply_remote_sync_item(
        cls,
        *,
        local_ticket: Ticket | None,
        remote_sync_revision: int,
        remote_pushed_at: Any,
    ) -> tuple[bool, str]:
        """
        判断远端工单是否需要覆盖本地数据（仅远端较新时更新）。
        :param local_ticket: 本地工单
        :param remote_sync_revision: 远端同步修订号
        :param remote_pushed_at: 远端最新更新时间
        :return: (是否需要同步, 原因)
        """
        if not local_ticket:
            return True, "local_missing"
        extra_data = local_ticket.extra_data if isinstance(local_ticket.extra_data, dict) else {}
        local_meta = cls._build_meta(extra_data)
        local_source_revision = cls._safe_int(local_meta.get("sourceRevision"))
        if remote_sync_revision > 0 and local_source_revision is not None:
            if remote_sync_revision <= local_source_revision:
                return (
                    False,
                    f"remote_revision_not_newer(remote={remote_sync_revision}, local={local_source_revision})",
                )
            return True, "remote_revision_newer"

        local_source = local_meta.get("source") if isinstance(local_meta.get("source"), dict) else {}
        local_pushed_at = (
            local_source.get("pushedAt")
            or local_meta.get("lastImportedAt")
        )
        parsed_remote_time = cls._parse_datetime_value(remote_pushed_at)
        parsed_local_time = cls._parse_datetime_value(local_pushed_at)
        if parsed_remote_time and parsed_local_time and parsed_remote_time <= parsed_local_time:
            return (
                False,
                f"remote_time_not_newer(remote={parsed_remote_time.isoformat()}, local={parsed_local_time.isoformat()})",
            )
        return True, "remote_time_newer_or_unknown"

    @classmethod
    def _default_sync_config(cls) -> dict[str, Any]:
        return {
            "autoRunOnSync": False,
            "autoTranslateOnSync": True,
            "defaultPullLimit": 50,
            "feishuAuth": cls._default_feishu_auth_config(),
            "remoteSync": cls._default_remote_sync_config(),
            "groupPush": cls._default_group_push_config(),
            "personReminder": cls._default_person_reminder_config(),
            "summaryReport": cls._default_summary_report_config(),
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
    def _default_feishu_auth_config(cls) -> dict[str, Any]:
        """
        构建飞书应用统一凭证默认配置。

        :return: 统一凭证配置默认值。
        """
        return {
            "appId": "",
            "appSecret": "",
        }

    @classmethod
    def _default_group_push_config(cls) -> dict[str, Any]:
        """
        构建工单群推送默认配置。

        :return: 群推送配置默认值。
        """
        return {
            "enabled": False,
            "sendMode": "push_config",
            "pushIds": [],
            "appChatIds": [],
            "priorityRoutes": [],
            "sendAfterExternalSync": False,
            "sendAfterRemotePull": False,
            "template": "",
            "manualTemplate": "",
        }

    @classmethod
    def _default_person_reminder_config(cls) -> dict[str, Any]:
        """
        构建按人催办默认配置。

        :return: 人维度催办配置默认值。
        """
        return {
            "enabled": False,
            "sendMode": "push_config",
            "dataSource": "bitable",
            "pushIds": [],
            "appId": "",
            "appSecret": "",
            "feishuAppId": "",
            "feishuAppSecret": "",
            "appToken": "",
            "tableId": "",
            "viewId": "",
            "filterFormula": "",
            "personField": "",
            "timeField": "",
            "thresholdMinutes": 30,
            "messageTemplate": "",
            "maxRowsPerPerson": 20,
            "pageSize": 500,
        }

    @classmethod
    def _default_summary_report_config(cls) -> dict[str, Any]:
        """
        构建工单汇总通知默认配置。

        :return: 汇总通知配置默认值。
        """
        return {
            "enabled": False,
            "sendMode": "push_config",
            "dataSource": "local",
            "pushIds": [],
            "appChatIds": [],
            "appId": "",
            "appSecret": "",
            "timeField": "create_time",
            "appToken": "",
            "tableId": "",
            "viewId": "",
            "filterFormula": "",
            "statusField": "状态",
            "categoryField": "分类",
            "priorityField": "优先级",
            "bitableTimeField": "",
            "pageSize": 500,
            "aiEnabled": False,
            "aiProviderCode": "",
            "aiPromptCode": "",
            "windowMinutes": 60,
            "endDelayMinutes": 0,
            "startTime": "",
            "endTime": "",
            "includeClosed": True,
            "messageTemplate": "",
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
        feishu_auth = merged.get("feishuAuth") if isinstance(merged.get("feishuAuth"), dict) else {}
        feishu_auth = {**cls._default_feishu_auth_config(), **feishu_auth}
        feishu_auth["appId"] = str(feishu_auth.get("appId") or "").strip()
        feishu_auth["appSecret"] = str(feishu_auth.get("appSecret") or "").strip()
        merged["feishuAuth"] = feishu_auth
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
        group_push = merged.get("groupPush") if isinstance(merged.get("groupPush"), dict) else {}
        default_group_push = cls._default_group_push_config()
        group_push = {**default_group_push, **group_push}
        group_push["sendMode"] = TicketSyncNotifyService._normalize_send_mode(group_push.get("sendMode"))
        group_push["enabled"] = bool(group_push.get("enabled"))
        group_push["sendAfterExternalSync"] = bool(group_push.get("sendAfterExternalSync"))
        group_push["sendAfterRemotePull"] = bool(group_push.get("sendAfterRemotePull"))
        group_push["pushIds"] = TicketSyncNotifyService._normalize_push_ids(group_push.get("pushIds"))
        group_push["appChatIds"] = TicketSyncNotifyService._normalize_chat_ids(group_push.get("appChatIds"))
        group_push["appId"] = str(group_push.get("appId") or "").strip()
        group_push["appSecret"] = str(group_push.get("appSecret") or "").strip()
        priority_routes = group_push.get("priorityRoutes") if isinstance(group_push.get("priorityRoutes"), list) else []
        normalized_priority_routes: list[dict[str, Any]] = []
        for route in priority_routes:
            if not isinstance(route, dict):
                continue
            priorities_raw = route.get("priorities")
            if isinstance(priorities_raw, str):
                priorities = [TicketSyncNotifyService._normalize_priority(item) for item in priorities_raw.split(",")]
            elif isinstance(priorities_raw, list):
                priorities = [TicketSyncNotifyService._normalize_priority(item) for item in priorities_raw]
            else:
                priorities = []
            priorities = [item for item in priorities if item]
            push_ids = TicketSyncNotifyService._normalize_push_ids(route.get("pushIds"))
            chat_ids = TicketSyncNotifyService._normalize_chat_ids(route.get("chatIds") or route.get("appChatIds"))
            if not priorities:
                continue
            normalized_priority_routes.append(
                {
                    "priorities": priorities,
                    "pushIds": push_ids,
                    "chatIds": chat_ids,
                }
            )
        group_push["priorityRoutes"] = normalized_priority_routes
        group_push["template"] = str(group_push.get("template") or "").strip()
        group_push["manualTemplate"] = str(group_push.get("manualTemplate") or "").strip()
        if not group_push["appId"]:
            group_push["appId"] = feishu_auth["appId"]
        if not group_push["appSecret"]:
            group_push["appSecret"] = feishu_auth["appSecret"]
        merged["groupPush"] = group_push

        person_reminder = merged.get("personReminder") if isinstance(merged.get("personReminder"), dict) else {}
        default_person_reminder = cls._default_person_reminder_config()
        person_reminder = {**default_person_reminder, **person_reminder}
        person_reminder["sendMode"] = TicketSyncNotifyService._normalize_send_mode(person_reminder.get("sendMode"))
        person_reminder["dataSource"] = TicketSyncNotifyService._normalize_person_data_source(
            person_reminder.get("dataSource")
        )
        person_reminder["enabled"] = bool(person_reminder.get("enabled"))
        person_reminder["pushIds"] = TicketSyncNotifyService._normalize_push_ids(person_reminder.get("pushIds"))
        person_reminder["appId"] = str(person_reminder.get("appId") or "").strip()
        person_reminder["appSecret"] = str(person_reminder.get("appSecret") or "").strip()
        person_reminder["feishuAppId"] = str(person_reminder.get("feishuAppId") or "").strip()
        person_reminder["feishuAppSecret"] = str(person_reminder.get("feishuAppSecret") or "").strip()
        person_reminder["appToken"] = str(person_reminder.get("appToken") or "").strip()
        person_reminder["tableId"] = str(person_reminder.get("tableId") or "").strip()
        person_reminder["viewId"] = str(person_reminder.get("viewId") or "").strip()
        person_reminder["filterFormula"] = str(person_reminder.get("filterFormula") or "").strip()
        person_reminder["personField"] = str(person_reminder.get("personField") or "").strip()
        person_reminder["timeField"] = str(person_reminder.get("timeField") or "").strip()
        person_reminder["thresholdMinutes"] = max(cls._safe_int(person_reminder.get("thresholdMinutes")) or 30, 1)
        person_reminder["messageTemplate"] = str(person_reminder.get("messageTemplate") or "").strip()
        person_reminder["maxRowsPerPerson"] = max(cls._safe_int(person_reminder.get("maxRowsPerPerson")) or 20, 1)
        person_reminder["pageSize"] = min(max(cls._safe_int(person_reminder.get("pageSize")) or 500, 1), 500)
        if not person_reminder["appId"]:
            person_reminder["appId"] = person_reminder["feishuAppId"] or feishu_auth["appId"]
        if not person_reminder["appSecret"]:
            person_reminder["appSecret"] = person_reminder["feishuAppSecret"] or feishu_auth["appSecret"]
        person_reminder["feishuAppId"] = person_reminder["appId"]
        person_reminder["feishuAppSecret"] = person_reminder["appSecret"]
        merged["personReminder"] = person_reminder

        summary_report = merged.get("summaryReport") if isinstance(merged.get("summaryReport"), dict) else {}
        default_summary_report = cls._default_summary_report_config()
        summary_report = {**default_summary_report, **summary_report}
        summary_report["enabled"] = bool(summary_report.get("enabled"))
        summary_report["sendMode"] = TicketSyncNotifyService._normalize_send_mode(summary_report.get("sendMode"))
        summary_report["dataSource"] = TicketSyncNotifyService._normalize_summary_data_source(
            summary_report.get("dataSource")
        )
        summary_report["pushIds"] = TicketSyncNotifyService._normalize_push_ids(summary_report.get("pushIds"))
        summary_report["appChatIds"] = TicketSyncNotifyService._normalize_chat_ids(summary_report.get("appChatIds"))
        summary_report["appId"] = str(summary_report.get("appId") or "").strip() or feishu_auth["appId"]
        summary_report["appSecret"] = str(summary_report.get("appSecret") or "").strip() or feishu_auth["appSecret"]
        summary_report["timeField"] = TicketSyncNotifyService._resolve_summary_time_field(
            summary_report.get("timeField")
        )
        summary_report["appToken"] = str(summary_report.get("appToken") or "").strip()
        summary_report["tableId"] = str(summary_report.get("tableId") or "").strip()
        summary_report["viewId"] = str(summary_report.get("viewId") or "").strip()
        summary_report["filterFormula"] = str(summary_report.get("filterFormula") or "").strip()
        summary_report["statusField"] = str(summary_report.get("statusField") or "状态").strip() or "状态"
        summary_report["categoryField"] = str(summary_report.get("categoryField") or "分类").strip() or "分类"
        summary_report["priorityField"] = str(summary_report.get("priorityField") or "优先级").strip() or "优先级"
        summary_report["bitableTimeField"] = str(summary_report.get("bitableTimeField") or "").strip()
        summary_report["pageSize"] = min(max(cls._safe_int(summary_report.get("pageSize")) or 500, 1), 500)
        summary_report["aiEnabled"] = bool(summary_report.get("aiEnabled"))
        summary_report["aiProviderCode"] = str(summary_report.get("aiProviderCode") or "").strip()
        summary_report["aiPromptCode"] = str(summary_report.get("aiPromptCode") or "").strip()
        summary_report["windowMinutes"] = max(cls._safe_int(summary_report.get("windowMinutes")) or 60, 1)
        summary_report["endDelayMinutes"] = max(cls._safe_int(summary_report.get("endDelayMinutes")) or 0, 0)
        summary_report["startTime"] = str(summary_report.get("startTime") or "").strip()
        summary_report["endTime"] = str(summary_report.get("endTime") or "").strip()
        summary_report["includeClosed"] = bool(summary_report.get("includeClosed", True))
        summary_report["messageTemplate"] = str(summary_report.get("messageTemplate") or "").strip()
        merged["summaryReport"] = summary_report
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
    def get_sync_notify_push_options_services(cls, db: Session) -> list[dict[str, Any]]:
        """
        查询通知相关可选推送配置。

        :param db: 数据库会话。
        :return: 推送配置列表。
        """
        return TicketSyncNotifyService.list_push_options(db)

    @classmethod
    def preview_person_reminder_services(
        cls,
        db: Session,
        *,
        user_id: int | None = None,
        email: str | None = None,
    ) -> dict[str, Any]:
        """
        预览人维度催办统计。

        :param db: 数据库会话。
        :param user_id: 可选用户ID。
        :param email: 可选邮箱。
        :return: 统计结果。
        """
        config = cls._load_sync_config(db)
        person_config = config.get("personReminder") if isinstance(config.get("personReminder"), dict) else {}
        return TicketSyncNotifyService.preview_person_overdue_statistics(
            db,
            config=person_config,
            user_id=user_id,
            email=email,
        )

    @classmethod
    def run_person_reminder_services(
        cls,
        db: Session,
        *,
        trigger_source: str,
        user_id: int | None = None,
        email: str | None = None,
    ) -> dict[str, Any]:
        """
        执行人维度催办通知。

        :param db: 数据库会话。
        :param trigger_source: 触发来源。
        :param user_id: 可选用户ID。
        :param email: 可选邮箱。
        :return: 执行结果摘要。
        """
        config = cls._load_sync_config(db)
        person_config = config.get("personReminder") if isinstance(config.get("personReminder"), dict) else {}
        return TicketSyncNotifyService.run_person_overdue_reminder(
            db,
            config=person_config,
            trigger_source=trigger_source,
            user_id=user_id,
            email=email,
        )

    @classmethod
    def run_summary_report_services(
        cls,
        db: Session,
        *,
        trigger_source: str,
        start_time: Any | None = None,
        end_time: Any | None = None,
    ) -> dict[str, Any]:
        """
        执行工单汇总统计通知。

        :param db: 数据库会话。
        :param trigger_source: 触发来源（manual/scheduler）。
        :param start_time: 可选统计开始时间。
        :param end_time: 可选统计结束时间。
        :return: 执行结果摘要。
        """
        config = cls._load_sync_config(db)
        summary_config = config.get("summaryReport") if isinstance(config.get("summaryReport"), dict) else {}
        parsed_start_time = TicketSyncNotifyService._parse_datetime_value(start_time)
        parsed_end_time = TicketSyncNotifyService._parse_datetime_value(end_time)
        return TicketSyncNotifyService.run_ticket_summary_report(
            db,
            config=summary_config,
            trigger_source=trigger_source,
            start_time=parsed_start_time,
            end_time=parsed_end_time,
        )

    @classmethod
    def send_group_push_by_ticket_no_services(
        cls,
        db: Session,
        *,
        ticket_no: str,
        push_ids: list[int] | None = None,
        message_template: str | None = None,
        force_push: bool = False,
        update_by: str = "system",
    ) -> dict[str, Any]:
        """
        手动按工单号发送群消息。

        :param db: 数据库会话。
        :param ticket_no: 工单号。
        :param push_ids: 覆盖推送渠道ID列表。
        :param message_template: 覆盖消息模板。
        :param force_push: 是否强制推送（忽略已推送状态）。
        :param update_by: 推送状态更新人。
        :return: 发送结果。
        """
        ticket = TicketDao.get_ticket_by_no(db, ticket_no)
        if not ticket:
            raise ValueError(f"工单不存在: {ticket_no}")
        config = cls._load_sync_config(db)
        group_config = config.get("groupPush") if isinstance(config.get("groupPush"), dict) else {}
        extra_data = dict(ticket.extra_data or {}) if isinstance(ticket.extra_data, dict) else {}
        meta = cls._build_meta(extra_data)
        already_sent = cls._is_group_push_sent_once(meta)
        force_push_enabled = bool(force_push)
        manual_scene = "manual_force" if force_push_enabled else "manual"
        if already_sent and not force_push_enabled:
            logger.info(
                f"手动群推送跳过: ticket_no={ticket.ticket_no}, scene={manual_scene}, "
                f"reason=工单已发送过群推送且未开启强制推送"
            )
            return {
                "skipped": True,
                "skipReason": "工单已发送过群推送，未开启强制推送",
                "scene": manual_scene,
                "ticketNo": ticket.ticket_no,
                "alreadySent": True,
                "forcePush": False,
                "groupPushSentOnceUpdated": False,
            }
        sync_summary = cls.extract_sync_summary(ticket.extra_data) or {}
        logger.info(
            f"手动群推送触发: ticket_no={ticket.ticket_no}, scene={manual_scene}, "
            f"force_push={force_push_enabled}, already_sent={already_sent}"
        )
        result = TicketSyncNotifyService.send_group_message_for_ticket(
            db,
            ticket=ticket,
            group_config=group_config,
            scene=manual_scene,
            manual_trigger=True,
            override_push_ids=push_ids,
            override_template=message_template,
            sync_summary=sync_summary,
        )
        push_success_count = int(result.get("pushSuccessCount") or 0)
        app_success_count = int(result.get("chatSuccessCount") or 0)
        group_push_state_updated = False
        if not bool(result.get("skipped")) and (push_success_count > 0 or app_success_count > 0):
            meta = cls._mark_group_push_sent_once(
                meta,
                scene=manual_scene,
                revision=int(meta.get("revision") or 0),
            )
            ticket = cls._persist_sync_meta(
                db,
                ticket=ticket,
                meta=meta,
                update_by=str(update_by or "system"),
            )
            group_push_state_updated = True
            logger.info(
                f"手动群推送已更新去重状态: ticket_no={ticket.ticket_no}, scene={manual_scene}, "
                f"push_success_count={push_success_count}, app_success_count={app_success_count}"
            )
        elif not bool(result.get("skipped")):
            logger.warning(
                f"手动群推送未产生成功发送，不更新去重状态: ticket_no={ticket.ticket_no}, scene={manual_scene}, "
                f"push_success_count={push_success_count}, app_success_count={app_success_count}"
            )
        return {
            **result,
            "ticketNo": ticket.ticket_no,
            "alreadySent": already_sent,
            "forcePush": force_push_enabled,
            "groupPushSentOnceUpdated": group_push_state_updated,
        }

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
            "publish_ready": bool(sync_state.get("publish_ready", True)),
            "publish_status": str(sync_state.get("publish_status") or cls.PUBLISH_STATUS_READY),
            "publish_reason": str(sync_state.get("publish_reason") or "").strip(),
            "publish_updated_at": sync_state.get("publish_updated_at"),
            "ai_task_status": str(sync_state.get("ai_task_status") or "").strip(),
            "group_push_sent_once": bool(sync_state.get("group_push_sent_once", False)),
            "group_push_sent_at": sync_state.get("group_push_sent_at"),
            "group_push_scene": sync_state.get("group_push_scene"),
            "group_push_revision": sync_state.get("group_push_revision"),
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
            "sourceRecordUrl": meta.get("sourceRecordUrl") or meta.get("source", {}).get("recordUrl"),
            "ticketUrl": (
                meta.get("ticketUrl")
                or meta.get("sourceRecordUrl")
                or (meta.get("source", {}) or {}).get("recordUrl")
            ),
            "sourceRevision": cls._safe_int(meta.get("sourceRevision")) or 0,
            "externalCreateTime": (
                meta.get("externalCreateTime")
                or (meta.get("source") or {}).get("externalCreateTime")
            ),
            "status": sync_state.get("status") or "pending",
            "publishReady": bool(sync_state.get("publish_ready", True)),
            "publishStatus": sync_state.get("publish_status") or cls.PUBLISH_STATUS_READY,
            "publishReason": sync_state.get("publish_reason") or "",
            "aiTaskStatus": sync_state.get("ai_task_status") or "",
            "groupPushSentOnce": bool(sync_state.get("group_push_sent_once", False)),
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
    def _payload_field_value(
        cls,
        payload: dict[str, Any] | None,
        camel_key: str,
        snake_key: str | None = None,
        default=None,
    ):
        """
        从外部载荷中读取字段值，仅兼容驼峰与下划线写法。
        :param payload: 外部载荷字典
        :param camel_key: 驼峰字段名
        :param snake_key: 下划线字段名，未传时自动转换
        :param default: 默认值
        :return: 命中的字段值或默认值
        """
        if not isinstance(payload, dict):
            return default
        normalized_snake_key = snake_key or "".join(
            [f"_{char.lower()}" if char.isupper() else char for char in camel_key]
        )
        for key in (camel_key, normalized_snake_key):
            if key not in payload:
                continue
            value = payload.get(key)
            if value in (None, "", []):
                continue
            return value
        return default

    @classmethod
    def _extract_external_mapping_fields(cls, sync_object: TicketExternalSyncUpsertModel) -> dict[str, str]:
        """
        提取外部同步字段映射上下文。
        :param sync_object: 外部同步模型
        :return: 字段映射字典
        """
        raw_payload = sync_object.raw_payload if isinstance(sync_object.raw_payload, dict) else {}
        extra_data = sync_object.extra_data if isinstance(sync_object.extra_data, dict) else {}
        mapping_payload = (
            extra_data.get("external_field_mapping")
            if isinstance(extra_data.get("external_field_mapping"), dict)
            else {}
        )
        ticket_vender = str(
            cls._payload_field_value(
                raw_payload,
                "ticketVender",
                "ticket_vender",
                default=cls._payload_field_value(mapping_payload, "ticketVender", "ticket_vender", default=""),
            )
            or ""
        ).strip()
        ticket_modle = str(
            cls._payload_field_value(
                raw_payload,
                "ticketModle",
                "ticket_modle",
                default=cls._payload_field_value(mapping_payload, "ticketModle", "ticket_modle", default=""),
            )
            or ""
        ).strip()
        ticket_status = str(
            cls._payload_field_value(
                raw_payload,
                "ticketStatus",
                "ticket_status",
                default=cls._payload_field_value(raw_payload, "status", "status", default=""),
            )
            or ""
        ).strip()
        ticket_store = str(
            cls._payload_field_value(
                raw_payload,
                "ticketStore",
                "ticket_store",
                default=cls._payload_field_value(
                    raw_payload,
                    "storeInfo",
                    "store_info",
                    default=cls._payload_field_value(
                        raw_payload,
                        "storeId",
                        "store_id",
                        default=cls._payload_field_value(mapping_payload, "ticketStore", "ticket_store", default=""),
                    ),
                ),
            )
            or ""
        ).strip()
        ticket_assignee = str(
            cls._payload_field_value(
                raw_payload,
                "ticketAssignee",
                "ticket_assignee",
                default=cls._payload_field_value(raw_payload, "currentAssigneeName", "current_assignee_name", default=""),
            )
            or ""
        ).strip()
        ticket_pos = str(
            cls._payload_field_value(
                raw_payload,
                "ticketPos",
                "ticket_pos",
                default=cls._payload_field_value(
                    raw_payload,
                    "posNo",
                    "pos_no",
                    default=cls._payload_field_value(
                        raw_payload,
                        "posId",
                        "pos_id",
                        default=cls._payload_field_value(mapping_payload, "ticketPos", "ticket_pos", default=""),
                    ),
                ),
            )
            or ""
        ).strip()
        ticket_sco = str(
            cls._payload_field_value(
                raw_payload,
                "ticketSco",
                "ticket_sco",
                default=cls._payload_field_value(
                    raw_payload,
                    "scoNo",
                    "sco_no",
                    default=cls._payload_field_value(
                        raw_payload,
                        "scoId",
                        "sco_id",
                        default=cls._payload_field_value(mapping_payload, "ticketSco", "ticket_sco", default=""),
                    ),
                ),
            )
            or ""
        ).strip()
        return {
            "ticketVender": ticket_vender,
            "ticketModle": ticket_modle,
            "ticketStatus": ticket_status,
            "ticketStore": ticket_store,
            "ticketAssignee": ticket_assignee,
            "ticketPos": ticket_pos,
            "ticketSco": ticket_sco,
        }

    @classmethod
    def _match_mapping_exact(cls, field_value: str, mappings: Any) -> dict[str, Any] | None:
        """
        按完整关键字做精确映射，不进行模糊猜测。
        :param field_value: 外部字段值
        :param mappings: 映射配置列表
        :return: 命中的映射对象
        """
        target = str(field_value or "").strip().lower()
        if not target or not isinstance(mappings, list):
            return None
        for mapping in mappings:
            if not isinstance(mapping, dict):
                continue
            keywords = cls._mapping_keywords(mapping)
            if target in keywords:
                return mapping
        return None

    @classmethod
    def _match_mapping_contains(cls, field_value: str, mappings: Any) -> dict[str, Any] | None:
        """
        按关键字“包含关系”匹配映射配置（外部字段包含任意关键词即命中）。
        :param field_value: 外部字段值
        :param mappings: 映射配置列表
        :return: 命中的映射对象
        """
        target = str(field_value or "").strip().lower()
        if not target or not isinstance(mappings, list):
            return None
        for mapping in mappings:
            if not isinstance(mapping, dict):
                continue
            keywords = cls._mapping_keywords(mapping)
            if any(keyword and keyword in target for keyword in keywords):
                return mapping
        return None

    @classmethod
    def _resolve_project_by_ticket_vender(
        cls,
        db: Session,
        *,
        ticket_vender: str,
        project_mappings: list[dict[str, Any]],
    ) -> tuple[HrmProject | None, str]:
        """
        按 ticketVender 匹配所属项目与项目名称。
        :param db: 数据库会话
        :param ticket_vender: 外部商家文本
        :param project_mappings: 项目映射配置
        :return: (项目对象, 项目名称)
        """
        vendor_text = str(ticket_vender or "").strip()
        if not vendor_text:
            return None, ""
        matched_mapping = cls._match_mapping_contains(vendor_text, project_mappings)
        if isinstance(matched_mapping, dict):
            project_id = cls._safe_int(
                matched_mapping.get("projectId")
                or matched_mapping.get("project_id")
                or matched_mapping.get("id")
            )
            project_code = str(
                matched_mapping.get("projectCode")
                or matched_mapping.get("project_code")
                or ""
            ).strip()
            project_name = str(
                matched_mapping.get("projectName")
                or matched_mapping.get("project_name")
                or ""
            ).strip()
            query = db.query(HrmProject).filter(
                HrmProject.status == QtrDataStatusEnum.normal.value,
                HrmProject.del_flag == "0",
            )
            if project_id:
                project = query.filter(HrmProject.project_id == project_id).first()
                if project:
                    return project, str(project.project_name or "").strip()
            if project_code:
                project = query.filter(HrmProject.project_code == project_code).first()
                if project:
                    return project, str(project.project_name or "").strip()
            if project_name:
                project = query.filter(func.lower(HrmProject.project_name) == project_name.lower()).first()
                if project:
                    return project, str(project.project_name or "").strip()
                return None, project_name

        # 向后兼容：若商户编号本身可直接匹配项目商家映射表，则仍可命中项目。
        project_vendor_row = (
            db.query(TicketLogPullProjectVendorMap)
            .filter(TicketLogPullProjectVendorMap.vender_no == vendor_text)
            .order_by(TicketLogPullProjectVendorMap.modifid.desc(), TicketLogPullProjectVendorMap.id.desc())
            .first()
        )
        if not project_vendor_row:
            return None, ""
        project = (
            db.query(HrmProject)
            .filter(
                HrmProject.project_id == project_vendor_row.project_id,
                HrmProject.status == QtrDataStatusEnum.normal.value,
                HrmProject.del_flag == "0",
            )
            .first()
        )
        if project:
            return project, str(project.project_name or "").strip()
        return None, str(project_vendor_row.project_name or "").strip()

    @classmethod
    def _resolve_module_by_ticket_modle(
        cls,
        db: Session,
        *,
        ticket_modle: str,
        project_id: int | None,
        module_mappings: list[dict[str, Any]],
    ) -> HrmModule | None:
        """
        按 ticketModle 匹配所属模块。
        :param db: 数据库会话
        :param ticket_modle: 外部模块字段
        :param project_id: 已匹配项目ID
        :param module_mappings: 模块映射配置
        :return: 模块对象
        """
        module_text = str(ticket_modle or "").strip()
        if not module_text:
            return None
        matched_mapping = cls._match_mapping_contains(module_text, module_mappings)
        module_id = cls._safe_int((matched_mapping or {}).get("moduleId") or (matched_mapping or {}).get("module_id"))
        module_code = str(
            (matched_mapping or {}).get("moduleCode")
            or (matched_mapping or {}).get("module_code")
            or ""
        ).strip()
        module_name = str(
            (matched_mapping or {}).get("moduleName")
            or (matched_mapping or {}).get("module_name")
            or ""
        ).strip()
        query = db.query(HrmModule).filter(HrmModule.status == QtrDataStatusEnum.normal.value)
        if project_id:
            query = query.filter(HrmModule.project_id == project_id)
        if module_id:
            module = query.filter(HrmModule.module_id == module_id).first()
            if module:
                return module
        if module_code:
            module = query.filter(func.lower(HrmModule.module_code) == module_code.lower()).first()
            if module:
                return module
        if module_name:
            module = query.filter(func.lower(HrmModule.module_name) == module_name.lower()).first()
            if module:
                return module
        module = query.filter(func.lower(HrmModule.module_code) == module_text.lower()).first()
        if module:
            return module
        return query.filter(func.lower(HrmModule.module_name) == module_text.lower()).first()

    @classmethod
    def _resolve_status_by_external_value(
        cls,
        *,
        status_text: str,
        status_mappings: list[dict[str, Any]],
    ) -> str:
        """
        按显式外部状态字段匹配本地状态，不做模糊猜测。
        :param status_text: 外部状态值
        :param status_mappings: 状态映射配置
        :return: 本地状态编码或原始状态值
        """
        source_status = str(status_text or "").strip()
        if not source_status:
            return ""
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
        matched_mapping = cls._match_mapping_exact(source_status, status_mappings)
        status_candidate = source_status
        if isinstance(matched_mapping, dict):
            status_candidate = str(
                matched_mapping.get("status")
                or matched_mapping.get("ticketStatus")
                or matched_mapping.get("statusCode")
                or matched_mapping.get("value")
                or source_status
            ).strip()
        return status_map.get(status_candidate.lower(), status_candidate)

    @classmethod
    def _resolve_vendor_by_ticket_vender(
        cls,
        *,
        ticket_vender: str,
        vendor_mappings: list[dict[str, Any]],
    ) -> tuple[int | None, str]:
        """
        按 ticketVender 解析日志拉取商家信息。
        :param ticket_vender: 外部商家文本
        :param vendor_mappings: 商家映射配置
        :return: (vendor_id, vendor_name)
        """
        vendor_text = str(ticket_vender or "").strip()
        if not vendor_text:
            return None, ""
        matched_mapping = cls._match_mapping_contains(vendor_text, vendor_mappings)
        if isinstance(matched_mapping, dict):
            vendor_id = cls._safe_int(
                matched_mapping.get("vendorId")
                or matched_mapping.get("vendor_id")
                or matched_mapping.get("id")
            )
            vendor_name = str(matched_mapping.get("vendorName") or matched_mapping.get("vendor_name") or "").strip()
            if vendor_id:
                return vendor_id, vendor_name or vendor_text
        return None, vendor_text

    @classmethod
    def _resolve_vendor_by_project(cls, db: Session, *, project_id: int | None) -> int | None:
        """
        按项目映射配置回退解析商家ID。
        :param db: 数据库会话
        :param project_id: 项目ID
        :return: 商家ID，未命中返回 None
        """
        if not project_id:
            return None
        row = (
            db.query(TicketLogPullProjectVendorMap)
            .filter(TicketLogPullProjectVendorMap.project_id == project_id)
            .order_by(TicketLogPullProjectVendorMap.modifid.desc(), TicketLogPullProjectVendorMap.id.desc())
            .first()
        )
        if not row:
            return None
        return cls._safe_int(getattr(row, "vender_no", None))

    @classmethod
    def _resolve_store_by_external_value(
        cls,
        db: Session,
        *,
        vendor_id: int | None,
        ticket_store: str,
    ) -> tuple[str, str]:
        """
        按商家ID + 外部门店字段（sap_org_no）匹配门店配置。
        :param db: 数据库会话
        :param vendor_id: 已匹配商家ID
        :param ticket_store: 外部门店字段
        :return: (store_id, store_name)
        """
        store_text = str(ticket_store or "").strip()
        if not store_text:
            return "", ""
        if not vendor_id:
            return store_text, ""

        query = db.query(TicketLogPullStoreConfig).filter(TicketLogPullStoreConfig.sap_org_no == store_text)
        query = query.filter(TicketLogPullStoreConfig.vender_no == str(vendor_id))
        row = query.order_by(TicketLogPullStoreConfig.modifid.desc(), TicketLogPullStoreConfig.id.desc()).first()
        if not row:
            return store_text, ""
        resolved_store_id = str(row.org_no or row.sap_org_no or "").strip() or store_text
        return resolved_store_id, str(row.org_name or "").strip()

    @classmethod
    def _match_assignee_mapping_exact(cls, assignee_text: str, assignee_mappings: Any) -> dict[str, Any] | None:
        """
        按人员名称做完整匹配（不支持模糊包含）。
        :param assignee_text: 外部处理人文本
        :param assignee_mappings: 处理人映射配置
        :return: 命中的映射对象
        """
        target = str(assignee_text or "").strip().lower()
        if not target or not isinstance(assignee_mappings, list):
            return None
        for mapping in assignee_mappings:
            if not isinstance(mapping, dict):
                continue
            candidates = cls._mapping_keywords(mapping)
            candidates.extend(
                cls._normalize_keywords(
                    [
                        mapping.get("userName"),
                        mapping.get("user_name"),
                        mapping.get("name"),
                        mapping.get("email"),
                    ]
                )
            )
            if any(target == candidate for candidate in candidates if candidate):
                return mapping
        return None

    @classmethod
    def _resolve_assignee_by_external_value(
        cls,
        db: Session,
        *,
        assignee_text: str,
        assignee_mappings: list[dict[str, Any]],
    ) -> tuple[int | None, str]:
        """
        按显式处理人字段匹配本地用户，不做包含式猜测。
        :param db: 数据库会话
        :param assignee_text: 外部处理人字段
        :param assignee_mappings: 处理人映射配置
        :return: (处理人ID, 处理人名称)
        """
        from module_admin.entity.do.user_do import SysUser

        source_text = str(assignee_text or "").strip()
        matched_mapping = cls._match_assignee_mapping_exact(source_text, assignee_mappings)
        mapped_user_id = cls._safe_int(
            (matched_mapping or {}).get("userId")
            or (matched_mapping or {}).get("user_id")
            or (matched_mapping or {}).get("assigneeId")
        )
        mapped_email = str((matched_mapping or {}).get("email") or "").strip()
        mapped_user_name = str(
            (matched_mapping or {}).get("userName")
            or (matched_mapping or {}).get("user_name")
            or (matched_mapping or {}).get("name")
            or source_text
        ).strip()
        if mapped_user_id:
            user = (
                db.query(SysUser)
                .filter(
                    SysUser.user_id == mapped_user_id,
                    SysUser.status == "0",
                    SysUser.del_flag == "0",
                )
                .first()
            )
            if user:
                return user.user_id, user.user_name or user.nick_name or mapped_user_name
        if mapped_email:
            user = (
                db.query(SysUser)
                .filter(
                    SysUser.status == "0",
                    SysUser.del_flag == "0",
                    func.lower(SysUser.email) == mapped_email.lower(),
                )
                .first()
            )
            if user:
                return user.user_id, user.user_name or user.nick_name or mapped_user_name
        if mapped_user_name:
            user = (
                db.query(SysUser)
                .filter(
                    SysUser.status == "0",
                    SysUser.del_flag == "0",
                    (SysUser.user_name == mapped_user_name) | (SysUser.nick_name == mapped_user_name),
                )
                .first()
            )
            if user:
                return user.user_id, user.user_name or user.nick_name or mapped_user_name
        if source_text:
            user = (
                db.query(SysUser)
                .filter(
                    SysUser.status == "0",
                    SysUser.del_flag == "0",
                    (
                        (SysUser.user_name == source_text)
                        | (SysUser.nick_name == source_text)
                        | (func.lower(SysUser.email) == source_text.lower())
                    ),
                )
                .first()
            )
            if user:
                return user.user_id, user.user_name or user.nick_name or source_text
        return None, mapped_user_name or source_text

    @classmethod
    def _resolve_sync_title(
        cls,
        db: Session,
        *,
        sync_object: TicketExternalSyncUpsertModel,
        ticket_id: int | None,
        current_user: CurrentUserModel,
    ) -> tuple[str, dict[str, Any]]:
        """
        解析外部同步工单标题：优先原始标题，其次轻量AI总结，最后回退描述截断。
        :param db: 数据库会话
        :param sync_object: 外部同步模型
        :param ticket_id: 工单ID
        :param current_user: 当前用户
        :return: (最终标题, 标题元信息)
        """
        raw_title = str(sync_object.title or "").strip()
        if raw_title:
            return raw_title, {"mode": "raw", "title": raw_title}
        description = str(sync_object.description or "").strip()
        if not description:
            return sync_object.ticket_no, {"mode": "fallback", "fallback_reason": "description_empty"}
        ai_title, title_meta = TicketLightAiService.summarize_ticket_title(
            db,
            description=description,
            source_type="ticket",
            source_id=ticket_id,
            source_ref=sync_object.ticket_no,
            current_user_name=_user_name(current_user),
        )
        normalized_ai_title = str(ai_title or "").strip()
        if normalized_ai_title:
            return normalized_ai_title, {**title_meta, "mode": "ai"}
        fallback_title = description[:100]
        return fallback_title, {**title_meta, "mode": "fallback", "fallback_title": fallback_title}

    @classmethod
    def _should_skip_ai_analysis_for_update_with_title(
        cls,
        *,
        ticket: Ticket | None,
        incoming_title: str,
        meta: dict[str, Any] | None = None,
    ) -> bool:
        """
        判断是否因“更新且已带标题”跳过 AI 分析类任务（标题总结/分类/日志参数提取）。
        :param ticket: 当前工单对象
        :param incoming_title: 本次入参标题
        :param meta: 可选同步元数据，用于补充判断是否更新场景
        :return: 是否跳过
        """
        if not ticket:
            return False
        if not str(incoming_title or "").strip():
            return False
        revision = cls._safe_int((meta or {}).get("revision"))
        if revision is None:
            return True
        return revision > 1

    @classmethod
    def _apply_ai_extract_to_sync_object(
        cls,
        sync_object: TicketExternalSyncUpsertModel,
        extract_result: dict[str, Any] | None,
    ) -> tuple[TicketExternalSyncUpsertModel, dict[str, Any]]:
        """
        将统一提取结果回填到同步对象（当前仅回填日志拉取参数）。
        :param sync_object: 外部同步对象
        :param extract_result: 统一提取结果
        :return: (回填后的同步对象, 回填摘要)
        """
        result = extract_result if isinstance(extract_result, dict) else {}
        pos_no = cls._safe_int(result.get("posNo"))
        sco_no = cls._safe_int(result.get("scoNo"))
        log_date = cls._normalize_auto_log_pull_date_text(result.get("logDate"))

        log_pull_payload = dict(sync_object.log_pull_config or {}) if isinstance(sync_object.log_pull_config, dict) else {}
        changed = False
        if pos_no:
            if cls._safe_int(log_pull_payload.get("posNo")) != pos_no:
                log_pull_payload["posNo"] = pos_no
                changed = True
        elif sco_no:
            if cls._safe_int(log_pull_payload.get("scoNo")) != sco_no:
                log_pull_payload["scoNo"] = sco_no
                changed = True
        if log_date:
            previous_date = cls._normalize_auto_log_pull_date_text(
                log_pull_payload.get("modifyTime") or log_pull_payload.get("logDate")
            )
            if previous_date != log_date:
                log_pull_payload["modifyTime"] = log_date
                changed = True

        if not changed:
            return sync_object, {"updated": False}
        updated_sync_object = sync_object.model_copy(update={"log_pull_config": log_pull_payload})
        return updated_sync_object, {
            "updated": True,
            "logPullConfig": {
                "posNo": cls._safe_int(log_pull_payload.get("posNo")),
                "scoNo": cls._safe_int(log_pull_payload.get("scoNo")),
                "modifyTime": cls._normalize_auto_log_pull_date_text(log_pull_payload.get("modifyTime")),
            },
        }

    @classmethod
    def _attach_sync_ai_extract_meta(
        cls,
        extra_data: dict[str, Any],
        *,
        extract_result: dict[str, Any] | None,
        extract_meta: dict[str, Any] | None,
        applied_meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        将统一提取执行信息写入 extra_data，便于排查和复盘。
        :param extra_data: 工单扩展字段
        :param extract_result: 提取结果
        :param extract_meta: 提取元信息
        :param applied_meta: 回填摘要
        :return: 更新后的扩展字段
        """
        payload = dict(extra_data or {})
        if not isinstance(extract_meta, dict):
            return payload
        payload["ai_sync_extract"] = {
            "executedAt": cls._now_iso(),
            "result": extract_result if isinstance(extract_result, dict) else {},
            "meta": extract_meta,
            "applied": applied_meta if isinstance(applied_meta, dict) else {},
        }
        return payload

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
    def _mapping_keywords(cls, mapping: dict[str, Any]) -> list[str]:
        keywords = cls._normalize_keywords(mapping.get("keywords") or mapping.get("aliases"))
        if mapping.get("matchText"):
            keywords.extend(cls._normalize_keywords([mapping.get("matchText")]))
        return [keyword for keyword in keywords if keyword]

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
                "ticketUrl": str(sync_object.ticket_url or "").strip() or source_snapshot.get("ticketUrl"),
                "projectName": str(sync_object.project_name or "").strip() or source_snapshot.get("projectName"),
                "moduleName": str(sync_object.module_name or "").strip() or source_snapshot.get("moduleName"),
                "vendorId": cls._safe_int(detected.get("vendorId")) or source_snapshot.get("vendorId"),
                "vendorName": str(detected.get("vendorName") or "").strip() or source_snapshot.get("vendorName"),
                "storeId": str(detected.get("storeId") or "").strip() or source_snapshot.get("storeId"),
                "storeName": str(detected.get("storeName") or "").strip() or source_snapshot.get("storeName"),
                "posNo": cls._safe_int(detected.get("posNo")) or source_snapshot.get("posNo"),
                "scoNo": cls._safe_int(detected.get("scoNo")) or source_snapshot.get("scoNo"),
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
    def _normalize_auto_log_pull_date_text(cls, value: Any) -> str:
        """
        将任意输入归一化为日志拉取日期（YYYY-MM-DD）。
        :param value: 原始日期值
        :return: 标准日期文本，无法解析时返回空字符串
        """
        if value in (None, "", []):
            return ""
        parsed = cls._parse_datetime_value(value)
        if parsed:
            return parsed.strftime("%Y-%m-%d")
        value_text = str(value).strip()
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value_text):
            return value_text
        if re.fullmatch(r"\d{4}/\d{2}/\d{2}", value_text):
            return value_text.replace("/", "-")
        return ""

    @classmethod
    def _resolve_auto_log_pull_modify_time(
        cls,
        *,
        sync_object: TicketExternalSyncUpsertModel,
        log_pull_payload: dict[str, Any] | None,
    ) -> str:
        """
        解析自动拉日志使用的 modifyTime（日期）。
        :param sync_object: 外部同步模型
        :param log_pull_payload: 当前日志拉取参数
        :return: YYYY-MM-DD 日期文本，缺失时返回空字符串
        """
        payload = log_pull_payload if isinstance(log_pull_payload, dict) else {}
        payload_candidate = (
            cls._payload_field_value(payload, "modifyTime", "modify_time", default="")
            or cls._payload_field_value(payload, "logDate", "log_date", default="")
            or cls._payload_field_value(payload, "ticketDate", "ticket_date", default="")
        )
        normalized_payload_date = cls._normalize_auto_log_pull_date_text(payload_candidate)
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
            candidate = cls._payload_field_value(raw_payload, camel_key, snake_key, default="")
            normalized_date = cls._normalize_auto_log_pull_date_text(candidate)
            if normalized_date:
                return normalized_date
        return cls._normalize_auto_log_pull_date_text(sync_object.create_time)

    @classmethod
    def _run_auto_ticket_category_classification(
        cls,
        db: Session,
        *,
        ticket: Ticket,
        title: str,
        description: str,
        current_user_name: str,
        source_type: str,
        source_ref: str,
        force_reclassify: bool = False,
        classification_strategy: str = "ai",
        regex_rules: list[dict[str, Any]] | None = None,
        ai_prompt_code: str | None = None,
        pre_classified_category: str | None = None,
        pre_classified_meta: dict[str, Any] | None = None,
        prefer_no_ai_fallback: bool = False,
    ) -> tuple[Ticket, dict[str, Any]]:
        """
        执行工单自动分类并在成功时回填工单分类字段。
        :param db: 数据库会话
        :param ticket: 工单对象
        :param title: 工单标题
        :param description: 工单描述
        :param current_user_name: 当前用户名
        :param source_type: 分类来源类型
        :param source_ref: 分类来源引用
        :param force_reclassify: 是否强制覆盖已有分类
        :param classification_strategy: 分类策略（ai/regex）
        :param regex_rules: 正则归类规则列表
        :param ai_prompt_code: AI归类提示词编码，留空走系统配置
        :param pre_classified_category: 预提取分类结果，非空时优先使用
        :param pre_classified_meta: 预提取分类元信息
        :param prefer_no_ai_fallback: 预提取场景下，分类缺失时是否不再追加第二次 AI 分类调用
        :return: (最新工单对象, 分类执行摘要)
        """
        existing_category = str(getattr(ticket, "category_name", "") or "").strip()
        if existing_category and not force_reclassify:
            return ticket, {
                "skipped": True,
                "skipReason": "工单已归类，跳过自动分类",
                "categoryName": existing_category,
            }

        normalized_category = str(pre_classified_category or "").strip()
        category_meta = dict(pre_classified_meta or {})
        normalized_strategy = str(classification_strategy or "ai").strip().lower()
        if normalized_strategy not in {"ai", "regex"}:
            normalized_strategy = "ai"
        if normalized_strategy == "regex" and not normalized_category:
            normalized_category, regex_meta = cls._classify_ticket_category_by_regex(
                title=title,
                description=description,
                regex_rules=regex_rules,
            )
            category_meta = {**category_meta, **regex_meta}
        if not normalized_category:
            if prefer_no_ai_fallback:
                return ticket, {
                    "skipped": True,
                    "skipReason": "统一提取未返回分类，已按配置跳过二次分类AI调用",
                    "categoryName": existing_category,
                    "meta": category_meta,
                }
            category_name, category_meta = TicketLightAiService.classify_ticket_category(
                db,
                title=title,
                description=description,
                override_prompt_code=ai_prompt_code,
                source_type=source_type,
                source_id=ticket.ticket_id,
                source_ref=source_ref,
                current_user_name=current_user_name,
            )
            normalized_category = str(category_name or "").strip()
        if not normalized_category:
            return ticket, {
                "skipped": True,
                "skipReason": str(category_meta.get("error") or "未返回可识别分类").strip(),
                "categoryName": existing_category,
                "meta": category_meta,
            }

        next_extra_data = dict(ticket.extra_data or {}) if isinstance(ticket.extra_data, dict) else {}
        next_extra_data["auto_category_classify"] = {
            "categoryName": normalized_category,
            "providerCode": category_meta.get("provider_code"),
            "promptCode": category_meta.get("prompt_code"),
            "rawCategory": category_meta.get("raw_category"),
            "strategy": category_meta.get("strategy") or normalized_strategy,
            "matchedPattern": category_meta.get("matchedPattern"),
            "classifiedAt": cls._now_iso(),
            "forceReclassify": bool(force_reclassify),
        }
        if normalized_category == existing_category and ticket.extra_data == next_extra_data:
            return ticket, {"skipped": True, "skipReason": "分类结果未变化", "categoryName": normalized_category}

        update_by = str(current_user_name or "").strip() or "system"
        try:
            TicketDao.update_ticket(
                db,
                ticket.ticket_id,
                {
                    "category_name": normalized_category,
                    "extra_data": next_extra_data,
                    "update_by": update_by,
                    "update_time": datetime.now(),
                },
            )
            db.commit()
            ticket = TicketDao.get_ticket_by_id(db, ticket.ticket_id) or ticket
            return ticket, {
                "skipped": False,
                "categoryName": normalized_category,
                "meta": category_meta,
            }
        except Exception:
            db.rollback()
            raise

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
    def _classify_ticket_category_by_regex(
        cls,
        *,
        title: str,
        description: str,
        regex_rules: list[dict[str, Any]] | None,
    ) -> tuple[str, dict[str, Any]]:
        """
        使用正则规则匹配工单分类。

        :param title: 工单标题。
        :param description: 工单描述。
        :param regex_rules: 规则列表，元素包含 pattern/category/flags。
        :return: (分类名称, 元信息)。
        """
        text = "\n".join(
            [
                str(title or "").strip(),
                str(description or "").strip(),
            ]
        ).strip()
        if not text:
            return "", {"strategy": "regex", "error": "工单标题和描述都为空"}
        rules = regex_rules if isinstance(regex_rules, list) else []
        if not rules:
            return "", {"strategy": "regex", "error": "未配置正则归类规则"}
        for rule in rules:
            if not isinstance(rule, dict):
                continue
            pattern = str(rule.get("pattern") or "").strip()
            category_name = str(rule.get("category") or "").strip()
            if not pattern or not category_name:
                continue
            flags_text = str(rule.get("flags") or "").strip().lower()
            regex_flags = 0
            if "i" in flags_text:
                regex_flags |= re.IGNORECASE
            if "m" in flags_text:
                regex_flags |= re.MULTILINE
            if "s" in flags_text:
                regex_flags |= re.DOTALL
            try:
                if re.search(pattern, text, flags=regex_flags):
                    return category_name, {
                        "strategy": "regex",
                        "matchedPattern": pattern,
                        "raw_category": category_name,
                    }
            except re.error as exc:
                logger.warning(f"正则归类规则无效，已跳过: pattern={pattern}, error={exc}")
                continue
        return "", {"strategy": "regex", "error": "未命中正则归类规则"}

    @classmethod
    def _detect_fields(
        cls,
        db: Session,
        sync_object: TicketExternalSyncUpsertModel,
        config: dict[str, Any],
    ) -> dict[str, Any]:
        text = cls._collect_text(sync_object).lower()
        external_fields = cls._extract_external_mapping_fields(sync_object)
        ticket_vender = external_fields.get("ticketVender") or ""
        ticket_modle = external_fields.get("ticketModle") or ""
        ticket_status = external_fields.get("ticketStatus") or ""
        ticket_store = external_fields.get("ticketStore") or ""
        ticket_assignee = external_fields.get("ticketAssignee") or ""
        ticket_pos = external_fields.get("ticketPos") or ""
        ticket_sco = external_fields.get("ticketSco") or ""

        project = None
        project_name_by_vendor = ""
        if ticket_vender:
            project, project_name_by_vendor = cls._resolve_project_by_ticket_vender(
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
        if not project and sync_object.project_id:
            project = (
                db.query(HrmProject)
                .filter(
                    HrmProject.project_id == sync_object.project_id,
                    HrmProject.status == QtrDataStatusEnum.normal.value,
                    HrmProject.del_flag == "0",
                )
                .first()
            )

        module = cls._resolve_module_by_ticket_modle(
            db,
            ticket_modle=ticket_modle or str(sync_object.module_code or sync_object.module_name or "").strip(),
            project_id=getattr(project, "project_id", None),
            module_mappings=config.get("moduleMappings") or [],
        )
        if not module and sync_object.module_id:
            module_query = db.query(HrmModule).filter(
                HrmModule.module_id == sync_object.module_id,
                HrmModule.status == QtrDataStatusEnum.normal.value,
            )
            if getattr(project, "project_id", None):
                module_query = module_query.filter(HrmModule.project_id == getattr(project, "project_id", None))
            module = module_query.first()

        vendor_id, vendor_name = cls._resolve_vendor_by_ticket_vender(
            ticket_vender=ticket_vender,
            vendor_mappings=config.get("vendorMappings") or [],
        )
        if not vendor_id:
            vendor_id = cls._resolve_vendor_by_project(db, project_id=getattr(project, "project_id", None))
        if not vendor_id:
            vendor_id = cls._safe_int((sync_object.log_pull_config or {}).get("vendorId"))
        if vendor_id and not vendor_name:
            vendor_name = (
                ticket_vender
                or project_name_by_vendor
                or str(getattr(project, "project_name", "") or "").strip()
            )
        store_id, store_name = cls._resolve_store_by_external_value(
            db,
            vendor_id=vendor_id,
            ticket_store=ticket_store,
        )
        if not store_id:
            store_id = str((sync_object.log_pull_config or {}).get("storeId") or "").strip()
        status_code = cls._resolve_status_by_external_value(
            status_text=ticket_status or str(sync_object.status or "").strip(),
            status_mappings=config.get("statusMappings") or [],
        )
        assignee_id, assignee_name = cls._resolve_assignee_by_external_value(
            db,
            assignee_text=ticket_assignee or str(sync_object.current_assignee_name or "").strip(),
            assignee_mappings=config.get("assigneeMappings") or [],
        )
        if not assignee_id:
            assignee_id = cls._safe_int(sync_object.current_assignee_id)
        if not assignee_name:
            assignee_name = str(sync_object.current_assignee_name or "").strip()
        version_key = (
            str(sync_object.version_key or "").strip()
            or _extract_ticket_version_key(sync_object.extra_data)
            or str(cls._extract_pattern(text, config.get("versionPatterns")) or "").strip()
        )
        return {
            "projectId": getattr(project, "project_id", None) or sync_object.project_id,
            "projectName": (
                getattr(project, "project_name", "")
                or project_name_by_vendor
                or sync_object.project_name
                or sync_object.merchant_name
                or ""
            ),
            "projectCode": getattr(project, "project_code", "") or sync_object.project_code or "",
            "moduleId": getattr(module, "module_id", None) or sync_object.module_id,
            "moduleName": getattr(module, "module_name", "") or sync_object.module_name or "",
            "moduleCode": getattr(module, "module_code", "") or sync_object.module_code or "",
            "vendorId": vendor_id,
            "vendorName": vendor_name,
            "storeId": store_id,
            "storeName": store_name,
            "status": status_code or str(sync_object.status or "").strip(),
            "assigneeId": assignee_id,
            "assigneeName": assignee_name,
            "posNo": cls._safe_int(ticket_pos)
            or cls._safe_int((sync_object.log_pull_config or {}).get("posNo"))
            or cls._safe_int((sync_object.log_pull_config or {}).get("pos_id"))
            or cls._safe_int((sync_object.log_pull_config or {}).get("posId"))
            or cls._safe_int(cls._extract_pattern(text, config.get("posPatterns"))),
            "scoNo": cls._safe_int(ticket_sco)
            or cls._safe_int((sync_object.log_pull_config or {}).get("scoNo"))
            or cls._safe_int((sync_object.log_pull_config or {}).get("sco_no"))
            or cls._safe_int((sync_object.log_pull_config or {}).get("scoId"))
            or cls._safe_int((sync_object.log_pull_config or {}).get("sco_id"))
            or cls._safe_int(cls._extract_pattern(text, config.get("scoPatterns"))),
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
        external_create_time = cls._resolve_external_create_time(sync_object=sync_object, existing_meta=meta)
        remote_source_revision = cls._safe_int((sync_object.extra_data or {}).get("_remote_sync_revision"))
        if remote_source_revision is None:
            remote_source_revision = cls._safe_int(meta.get("sourceRevision"))
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
            "pushedAt": sync_object.source.pushed_at.isoformat() if sync_object.source.pushed_at else cls._now_iso(),
            "externalCreateTime": external_create_time,
        }
        meta.update(
            {
                "revision": revision,
                "sourceSystem": sync_object.source.system,
                "sourceRecordId": sync_object.source.record_id,
                "sourceRecordUrl": sync_object.source.record_url,
                "ticketUrl": resolved_ticket_url or None,
                "lastImportedAt": cls._now_iso(),
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
            "ticket_url": resolved_ticket_url or None,
            "update_by": _user_name(current_user),
            "update_time": now,
        }
        project_id = cls._safe_int((detected or {}).get("projectId")) or sync_object.project_id
        module_id = cls._safe_int((detected or {}).get("moduleId")) or sync_object.module_id
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
        log_pull_hints = (
            dict(extra_data.get("log_pull_hints") or {})
            if isinstance(extra_data.get("log_pull_hints"), dict)
            else {}
        )
        vendor_id_hint = cls._safe_int((detected or {}).get("vendorId"))
        store_id_hint = str((detected or {}).get("storeId") or "").strip()
        pos_no_hint = cls._safe_int((detected or {}).get("posNo")) or cls._safe_int((detected or {}).get("scoNo"))
        modify_time_hint = cls._resolve_auto_log_pull_modify_time(sync_object=sync_object, log_pull_payload=sync_object.log_pull_config)
        if vendor_id_hint:
            log_pull_hints["vendorId"] = vendor_id_hint
        if store_id_hint:
            log_pull_hints["storeId"] = store_id_hint
        if pos_no_hint:
            log_pull_hints["posNo"] = pos_no_hint
        if modify_time_hint:
            log_pull_hints["modifyTime"] = modify_time_hint
        if log_pull_hints:
            extra_data["log_pull_hints"] = log_pull_hints
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
        sync_scene: str = "external_sync",
        defer_post_process: bool = False,
    ) -> CrudResponseModel:
        """
        外部工单同步入库并按配置执行后续动作。

        :param db: 数据库会话。
        :param sync_object: 外部同步入参。
        :param current_user: 当前登录用户。
        :param sync_scene: 同步触发场景，支持 external_sync/remote_pull。
        :param defer_post_process: 是否延后执行AI、自动化和群推送，开启后先快速入库返回。
        :return: 同步结果。
        """
        ticket = TicketDao.get_ticket_by_no(db, sync_object.ticket_no)
        config = cls._load_sync_config(db)
        automation = sync_object.automation
        raw_title = str(sync_object.title or "").strip()
        existing_title = str(ticket.title or "").strip() if ticket else ""
        skip_ai_analysis_due_to_update_title = cls._should_skip_ai_analysis_for_update_with_title(
            ticket=ticket,
            incoming_title=raw_title,
        )
        ai_extract_result: dict[str, Any] = {}
        ai_extract_meta: dict[str, Any] = {"skipped": True}
        ai_extract_apply_meta: dict[str, Any] = {"updated": False}
        title_meta: dict[str, Any] = {"mode": "raw", "title": raw_title}
        if defer_post_process:
            # 延后AI时先用稳定兜底标题入库，避免主链路被AI网络调用阻塞。
            resolved_title = raw_title or existing_title or str(sync_object.description or "").strip()[:100]
            if not resolved_title:
                resolved_title = sync_object.ticket_no
            if resolved_title != raw_title:
                sync_object = sync_object.model_copy(update={"title": resolved_title})
            if not raw_title and existing_title:
                title_meta = {"mode": "keep_existing", "title": existing_title}
            elif not raw_title:
                title_meta = {"mode": "fallback", "fallback_title": resolved_title}
        else:
            if skip_ai_analysis_due_to_update_title:
                logger.info(
                    "外部工单同步跳过统一提取与标题AI：更新场景且已携带标题, ticket_no=%s",
                    sync_object.ticket_no,
                )
            else:
                try:
                    ai_extract_result, ai_extract_meta = TicketLightAiService.extract_ticket_sync_fields(
                        db,
                        title=raw_title or existing_title,
                        description=str(sync_object.description or "").strip(),
                        raw_payload=sync_object.raw_payload if isinstance(sync_object.raw_payload, dict) else {},
                        source_type=f"{sync_scene}_sync_extract",
                        source_id=getattr(ticket, "ticket_id", None),
                        source_ref=sync_object.ticket_no,
                        current_user_name=_user_name(current_user),
                    )
                    sync_object, ai_extract_apply_meta = cls._apply_ai_extract_to_sync_object(
                        sync_object,
                        ai_extract_result,
                    )
                except Exception as exc:
                    logger.warning(
                        "外部工单同步统一提取执行失败，已继续后续流程: ticket_no=%s, error=%s",
                        sync_object.ticket_no,
                        exc,
                    )
                    ai_extract_result = {}
                    ai_extract_meta = {"skipped": True, "error": str(exc)}
                    ai_extract_apply_meta = {"updated": False}
            resolved_title = raw_title or existing_title
            if resolved_title:
                if not raw_title and existing_title:
                    title_meta = {"mode": "keep_existing", "title": existing_title}
            else:
                ai_extract_title = str((ai_extract_result or {}).get("title") or "").strip()
                if ai_extract_title:
                    resolved_title = ai_extract_title
                    title_meta = {"mode": "ai_extract", "title": ai_extract_title}
                else:
                    try:
                        resolved_title, title_meta = cls._resolve_sync_title(
                            db,
                            sync_object=sync_object,
                            ticket_id=getattr(ticket, "ticket_id", None),
                            current_user=current_user,
                        )
                    except Exception as exc:
                        logger.warning(
                            f"外部工单同步标题处理异常，已回退描述截断: "
                            f"ticket_no={sync_object.ticket_no}, error={exc}"
                        )
                        resolved_title = str(sync_object.description or "").strip()[:100]
                        if not resolved_title:
                            resolved_title = sync_object.ticket_no
                        title_meta = {"mode": "fallback", "fallback_title": resolved_title, "error": str(exc)}
            if resolved_title != raw_title:
                sync_object = sync_object.model_copy(update={"title": resolved_title})
        detected = cls._detect_fields(db, sync_object, config)
        should_translate = False
        translated_description = str(sync_object.description or "").strip()
        translation_meta: dict[str, Any] = {"translated_text": "", "skipped": True}
        origin_description = str(sync_object.description or "").strip()
        if not defer_post_process:
            translation_enabled = TicketLightAiService.is_translation_enabled(db)
            translation_already_succeeded = cls._has_successful_ai_translation(
                ticket,
                source_description=sync_object.description,
            )
            if sync_scene == "remote_pull":
                sync_translate_enabled = bool(
                    automation.auto_translate
                    if automation is not None
                    else (config.get("remoteSync") or {}).get("autoTranslateOnPull", True)
                )
            else:
                sync_translate_enabled = bool(config.get("autoTranslateOnSync", True))
            should_translate = translation_enabled and sync_translate_enabled and not translation_already_succeeded
            logger.info(
                f"外部工单同步翻译决策: ticket_no={sync_object.ticket_no}, scene={sync_scene}, "
                f"global_switch={translation_enabled}, scene_switch={sync_translate_enabled}, "
                f"already_translated={translation_already_succeeded}, should_translate={should_translate}"
            )
            try:
                translated_description, translation_meta, origin_description = cls._translate_sync_description(
                    db,
                    title=sync_object.title or "",
                    description=sync_object.description,
                    ticket_id=getattr(ticket, "ticket_id", None),
                    ticket_no=sync_object.ticket_no,
                    current_user=current_user,
                    enabled=should_translate,
                )
            except Exception as exc:
                logger.warning(
                    f"外部工单同步翻译异常，已回退原文: ticket_no={sync_object.ticket_no}, scene={sync_scene}, error={exc}"
                )
                translated_description = str(sync_object.description or "").strip()
                translation_meta = {"translated_text": "", "skipped": True, "error": str(exc)}
                origin_description = str(sync_object.description or "").strip()
            if should_translate:
                sync_object = sync_object.model_copy(update={"description": translated_description})
        payload, meta, revision = cls._build_upsert_payload(db, ticket, sync_object, detected, current_user)
        if defer_post_process:
            meta = cls._set_publish_state(
                meta,
                ready=False,
                status=cls.PUBLISH_STATUS_PROCESSING_AI,
                reason="工单已入库，等待后台后处理完成",
                ai_task_status="pending",
            )
            extra_data = dict(payload.get("extra_data") or {}) if isinstance(payload.get("extra_data"), dict) else {}
            extra_data = cls._attach_meta(extra_data, meta)
            payload["extra_data"] = extra_data
        if title_meta and title_meta.get("mode") != "raw":
            extra_data = dict(payload.get("extra_data") or {}) if isinstance(payload.get("extra_data"), dict) else {}
            extra_data["title_summary"] = title_meta
            payload["extra_data"] = extra_data
        if should_translate and origin_description and str(translation_meta.get("translated_text") or "").strip():
            extra_data = dict(payload.get("extra_data") or {}) if isinstance(payload.get("extra_data"), dict) else {}
            extra_data["origin_description"] = origin_description
            extra_data["ai_translation"] = translation_meta.get("translated_text") or translated_description
            extra_data["ai_translation_source_hash"] = cls._text_sha256(origin_description)
            if translation_meta.get("provider_code"):
                extra_data["ai_translation_provider_code"] = translation_meta.get("provider_code")
            if translation_meta.get("prompt_code"):
                extra_data["ai_translation_prompt_code"] = translation_meta.get("prompt_code")
            payload["extra_data"] = extra_data
        if not defer_post_process and isinstance(ai_extract_meta, dict):
            if not bool(ai_extract_meta.get("skipped")) or str(ai_extract_meta.get("error") or "").strip():
                extra_data = dict(payload.get("extra_data") or {}) if isinstance(payload.get("extra_data"), dict) else {}
                extra_data = cls._attach_sync_ai_extract_meta(
                    extra_data,
                    extract_result=ai_extract_result,
                    extract_meta=ai_extract_meta,
                    applied_meta=ai_extract_apply_meta,
                )
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

        if defer_post_process:
            result = (
                TicketService.get_ticket_detail_services(db, ticket.ticket_id)
                or CamelCaseUtil.transform_result(ticket)
            )
            result["syncSummary"] = cls.extract_sync_summary(result.get("extraData"))
            result["syncDeferred"] = True
            return CrudResponseModel(
                is_success=True,
                message="外部工单同步成功（AI与自动化已转后台处理）",
                result=result,
            )

        category_summary = None
        if skip_ai_analysis_due_to_update_title:
            category_summary = {"skipped": True, "skipReason": "更新场景且已携带标题，跳过AI分类"}
        else:
            try:
                ticket = TicketDao.get_ticket_by_id(db, ticket.ticket_id) or ticket
                pre_category_name = str((ai_extract_result or {}).get("categoryName") or "").strip()
                prefer_no_ai_fallback = not bool(ai_extract_meta.get("skipped", True)) if isinstance(ai_extract_meta, dict) else False
                ticket, category_summary = cls._run_auto_ticket_category_classification(
                    db,
                    ticket=ticket,
                    title=str(sync_object.title or ticket.title or "").strip(),
                    description=str(sync_object.description or ticket.description or "").strip(),
                    current_user_name=_user_name(current_user),
                    source_type=f"{sync_scene}_auto_category",
                    source_ref=sync_object.ticket_no,
                    force_reclassify=False,
                    pre_classified_category=pre_category_name,
                    pre_classified_meta=ai_extract_meta if isinstance(ai_extract_meta, dict) else None,
                    prefer_no_ai_fallback=prefer_no_ai_fallback,
                )
            except Exception as exc:
                logger.warning(f"外部工单同步自动分类执行失败: ticket_no={sync_object.ticket_no}, error={exc}")

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

        group_push_summary = None
        try:
            ticket = TicketDao.get_ticket_by_id(db, ticket.ticket_id) or ticket
            ticket, _, group_push_summary = cls._finalize_publish_state_after_post_process(
                db,
                ticket=ticket,
                sync_scene=sync_scene,
                update_by=_user_name(current_user),
            )
        except Exception as exc:
            logger.warning(
                f"工单同步发布状态收敛失败: ticket_no={sync_object.ticket_no}, "
                f"scene={sync_scene}, error={exc}"
            )

        result = (
            TicketService.get_ticket_detail_services(db, ticket.ticket_id)
            or CamelCaseUtil.transform_result(ticket)
        )
        result["syncSummary"] = cls.extract_sync_summary(result.get("extraData"))
        if automation_summary:
            result["syncAutomation"] = automation_summary
        if category_summary:
            result["syncCategory"] = category_summary
        if group_push_summary is not None:
            result["syncGroupPush"] = group_push_summary
        return CrudResponseModel(
            is_success=True,
            message="外部工单同步成功",
            result=result,
        )

    @classmethod
    def _is_celery_worker_available(cls) -> bool:
        """
        判断 Celery Worker 当前是否可用（基于 inspect.ping）。

        :return: Worker 可用返回 True，否则返回 False。
        """
        try:
            from config.celery_app import celery_app

            inspector = celery_app.control.inspect(timeout=1.0)
            ping_result = inspector.ping() if inspector else {}
            return bool(ping_result)
        except Exception as exc:
            logger.warning(f"检测Celery可用性失败，降级本地后台任务: error={exc}")
            return False

    @classmethod
    def dispatch_deferred_sync_post_process_task(
        cls,
        sync_payload: dict[str, Any],
        current_user_payload: dict[str, Any],
        sync_scene: str = "external_sync",
    ) -> dict[str, Any]:
        """
        分发外部工单延后后处理任务。

        优先在 Celery Worker 可用时投递 Celery 任务；不可用或投递失败时由调用方回退本地后台任务。

        :param sync_payload: 外部同步入参字典。
        :param current_user_payload: 当前用户字典。
        :param sync_scene: 同步触发场景。
        :return: 分发结果摘要。
        """
        ticket_no = str(sync_payload.get("ticketNo") or sync_payload.get("ticket_no") or "").strip()
        if not cls._is_celery_worker_available():
            return {
                "mode": cls.BACKGROUND_DISPATCH_MODE,
                "celeryAvailable": False,
                "reason": "celery_worker_unavailable",
                "ticketNo": ticket_no or None,
            }
        try:
            from config.celery_app import celery_app
            from module_task.celery_contract import CELERY_TICKET_SYNC_DEFERRED_POST_PROCESS_TASK

            async_result = celery_app.send_task(
                CELERY_TICKET_SYNC_DEFERRED_POST_PROCESS_TASK,
                args=[sync_payload, current_user_payload, sync_scene],
            )
            task_id = str(getattr(async_result, "id", "") or "").strip()
            logger.info(
                f"外部工单延后后处理已投递Celery: ticket_no={ticket_no or '-'}, "
                f"sync_scene={sync_scene}, celery_task_id={task_id or '-'}"
            )
            return {
                "mode": cls.CELERY_DISPATCH_MODE,
                "celeryAvailable": True,
                "taskName": CELERY_TICKET_SYNC_DEFERRED_POST_PROCESS_TASK,
                "taskId": task_id or None,
                "ticketNo": ticket_no or None,
            }
        except Exception as exc:
            logger.warning(
                f"外部工单延后后处理投递Celery失败，降级本地后台任务: "
                f"ticket_no={ticket_no or '-'}, sync_scene={sync_scene}, error={exc}"
            )
            return {
                "mode": cls.BACKGROUND_DISPATCH_MODE,
                "celeryAvailable": False,
                "reason": f"celery_dispatch_failed:{exc}",
                "ticketNo": ticket_no or None,
            }

    @classmethod
    def run_deferred_sync_post_process(
        cls,
        sync_payload: dict[str, Any],
        current_user_payload: dict[str, Any],
        sync_scene: str = "external_sync",
    ) -> None:
        """
        执行外部工单同步的延后后处理任务（AI、自动化、群推送）。
        :param sync_payload: 外部同步入参字典。
        :param current_user_payload: 当前用户字典。
        :param sync_scene: 同步触发场景。
        :return: 无。
        """
        query_db = SessionLocal()
        try:
            sync_object = TicketExternalSyncUpsertModel.model_validate(sync_payload)
            current_user = CurrentUserModel.model_validate(current_user_payload)
            cls._execute_deferred_sync_post_process(query_db, sync_object, current_user, sync_scene)
        except Exception as exc:
            logger.warning(
                f"外部工单同步延后后处理异常: "
                f"ticket_no={sync_payload.get('ticketNo') or sync_payload.get('ticket_no')}, error={exc}"
            )
        finally:
            query_db.close()

    @classmethod
    def _execute_deferred_sync_post_process(
        cls,
        db: Session,
        sync_object: TicketExternalSyncUpsertModel,
        current_user: CurrentUserModel,
        sync_scene: str,
    ) -> None:
        """
        处理外部同步入库后的重任务，避免阻塞主入库链路。
        :param db: 数据库会话。
        :param sync_object: 外部同步入参。
        :param current_user: 当前用户。
        :param sync_scene: 同步触发场景。
        :return: 无。
        """
        ticket = TicketDao.get_ticket_by_no(db, sync_object.ticket_no)
        if not ticket:
            logger.warning(f"外部工单同步延后后处理跳过: 未找到工单 ticket_no={sync_object.ticket_no}")
            return
        config = cls._load_sync_config(db)
        automation = sync_object.automation
        update_data: dict[str, Any] = {}
        extra_data = dict(ticket.extra_data or {}) if isinstance(ticket.extra_data, dict) else {}
        existing_title = str(ticket.title or "").strip()
        incoming_title = str(sync_object.title or "").strip()
        meta = cls._build_meta(extra_data)
        skip_ai_analysis_due_to_update_title = cls._should_skip_ai_analysis_for_update_with_title(
            ticket=ticket,
            incoming_title=incoming_title,
            meta=meta,
        )
        ai_extract_result: dict[str, Any] = {}
        ai_extract_meta: dict[str, Any] = {"skipped": True}
        ai_extract_apply_meta: dict[str, Any] = {"updated": False}

        if skip_ai_analysis_due_to_update_title:
            logger.info(
                "外部工单同步延后处理跳过统一提取与分类AI：更新场景且已携带标题, ticket_no=%s",
                sync_object.ticket_no,
            )
        else:
            try:
                ai_extract_result, ai_extract_meta = TicketLightAiService.extract_ticket_sync_fields(
                    db,
                    title=incoming_title or existing_title,
                    description=str(sync_object.description or "").strip(),
                    raw_payload=sync_object.raw_payload if isinstance(sync_object.raw_payload, dict) else {},
                    source_type=f"{sync_scene}_sync_extract",
                    source_id=ticket.ticket_id,
                    source_ref=sync_object.ticket_no,
                    current_user_name=_user_name(current_user),
                )
                sync_object, ai_extract_apply_meta = cls._apply_ai_extract_to_sync_object(sync_object, ai_extract_result)
                ai_extract_title = str((ai_extract_result or {}).get("title") or "").strip()
                if not incoming_title and not existing_title and ai_extract_title:
                    update_data["title"] = ai_extract_title
                    extra_data["title_summary"] = {"mode": "ai_extract", "title": ai_extract_title}
            except Exception as exc:
                logger.warning(f"外部工单同步延后统一提取失败: ticket_no={sync_object.ticket_no}, error={exc}")
                ai_extract_result = {}
                ai_extract_meta = {"skipped": True, "error": str(exc)}
                ai_extract_apply_meta = {"updated": False}

        try:
            if not incoming_title and not existing_title and "title" not in update_data:
                resolved_title, title_meta = cls._resolve_sync_title(
                    db,
                    sync_object=sync_object,
                    ticket_id=ticket.ticket_id,
                    current_user=current_user,
                )
                if resolved_title and resolved_title != str(ticket.title or "").strip():
                    update_data["title"] = resolved_title
                if title_meta and title_meta.get("mode") != "raw":
                    extra_data["title_summary"] = title_meta
        except Exception as exc:
            logger.warning(f"外部工单同步延后标题处理失败: ticket_no={sync_object.ticket_no}, error={exc}")

        try:
            translation_enabled = TicketLightAiService.is_translation_enabled(db)
            if sync_scene == "remote_pull":
                sync_translate_enabled = bool(
                    automation.auto_translate
                    if automation is not None
                    else (config.get("remoteSync") or {}).get("autoTranslateOnPull", True)
                )
            else:
                sync_translate_enabled = bool(config.get("autoTranslateOnSync", True))
            translation_already_succeeded = cls._has_successful_ai_translation(
                ticket,
                source_description=sync_object.description,
            )
            should_translate = translation_enabled and sync_translate_enabled and not translation_already_succeeded
            if translation_already_succeeded:
                logger.info(f"外部工单同步延后翻译跳过：已有历史翻译结果, ticket_no={sync_object.ticket_no}")
            translated_description, translation_meta, origin_description = cls._translate_sync_description(
                db,
                title=str(update_data.get("title") or ticket.title or ""),
                description=sync_object.description,
                ticket_id=ticket.ticket_id,
                ticket_no=sync_object.ticket_no,
                current_user=current_user,
                enabled=should_translate,
            )
            if should_translate and translated_description and translated_description != str(ticket.description or "").strip():
                update_data["description"] = translated_description
            if should_translate and origin_description and str(translation_meta.get("translated_text") or "").strip():
                extra_data["origin_description"] = origin_description
                extra_data["ai_translation"] = translation_meta.get("translated_text") or translated_description
                extra_data["ai_translation_source_hash"] = cls._text_sha256(origin_description)
                if translation_meta.get("provider_code"):
                    extra_data["ai_translation_provider_code"] = translation_meta.get("provider_code")
                if translation_meta.get("prompt_code"):
                    extra_data["ai_translation_prompt_code"] = translation_meta.get("prompt_code")
        except Exception as exc:
            logger.warning(f"外部工单同步延后翻译处理失败: ticket_no={sync_object.ticket_no}, error={exc}")

        if isinstance(ai_extract_meta, dict):
            if not bool(ai_extract_meta.get("skipped")) or str(ai_extract_meta.get("error") or "").strip():
                extra_data = cls._attach_sync_ai_extract_meta(
                    extra_data,
                    extract_result=ai_extract_result,
                    extract_meta=ai_extract_meta,
                    applied_meta=ai_extract_apply_meta,
                )

        if update_data or extra_data != (ticket.extra_data or {}):
            update_data["extra_data"] = extra_data
            update_data["update_by"] = _user_name(current_user)
            update_data["update_time"] = datetime.now()
            try:
                TicketDao.update_ticket(db, ticket.ticket_id, update_data)
                db.commit()
                ticket = TicketDao.get_ticket_by_id(db, ticket.ticket_id) or ticket
            except Exception as exc:
                db.rollback()
                logger.warning(f"外部工单同步延后更新工单失败: ticket_no={sync_object.ticket_no}, error={exc}")

        if not skip_ai_analysis_due_to_update_title:
            try:
                ticket = TicketDao.get_ticket_by_id(db, ticket.ticket_id) or ticket
                pre_category_name = str((ai_extract_result or {}).get("categoryName") or "").strip()
                prefer_no_ai_fallback = not bool(ai_extract_meta.get("skipped", True)) if isinstance(ai_extract_meta, dict) else False
                cls._run_auto_ticket_category_classification(
                    db,
                    ticket=ticket,
                    title=str(update_data.get("title") or ticket.title or "").strip(),
                    description=str(update_data.get("description") or sync_object.description or ticket.description or "").strip(),
                    current_user_name=_user_name(current_user),
                    source_type=f"{sync_scene}_auto_category",
                    source_ref=sync_object.ticket_no,
                    force_reclassify=False,
                    pre_classified_category=pre_category_name,
                    pre_classified_meta=ai_extract_meta if isinstance(ai_extract_meta, dict) else None,
                    prefer_no_ai_fallback=prefer_no_ai_fallback,
                )
            except Exception as exc:
                logger.warning(f"外部工单同步延后自动分类失败: ticket_no={sync_object.ticket_no}, error={exc}")

        detected = cls._detect_fields(db, sync_object, config)

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
        if should_run_automation:
            try:
                cls.run_sync_automation(db, ticket.ticket_id, sync_object, detected, current_user)
            except Exception as exc:
                logger.warning(f"外部工单同步延后自动化失败: ticket_no={sync_object.ticket_no}, error={exc}")
        ticket = TicketDao.get_ticket_by_id(db, ticket.ticket_id) or ticket
        try:
            cls._finalize_publish_state_after_post_process(
                db,
                ticket=ticket,
                sync_scene=sync_scene,
                update_by=_user_name(current_user),
            )
        except Exception as exc:
            logger.warning(
                f"外部工单同步延后发布状态收敛失败: ticket_no={sync_object.ticket_no}, "
                f"scene={sync_scene}, error={exc}"
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
                resolved_vendor_id = cls._safe_int(detected.get("vendorId") or log_pull_payload.get("vendorId"))
                resolved_store_id = str(detected.get("storeId") or log_pull_payload.get("storeId") or "").strip()
                resolved_pos_no = cls._safe_int(
                    detected.get("posNo") or detected.get("scoNo") or log_pull_payload.get("posNo")
                )
                resolved_modify_time = cls._resolve_auto_log_pull_modify_time(
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
                    cls._mark_automation_step(
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
                        cls._mark_automation_step(
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
            if not cls._is_publish_ready(meta):
                continue
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
            sync_summary = cls.extract_sync_summary(extra_data)
            item["syncSummary"] = sync_summary
            item["ticketUrl"] = str(
                item.get("ticketUrl")
                or item.get("ticket_url")
                or (sync_summary.get("ticketUrl") if isinstance(sync_summary, dict) else "")
                or (sync_summary.get("sourceRecordUrl") if isinstance(sync_summary, dict) else "")
                or ""
            ).strip() or None
            if isinstance(sync_summary, dict) and sync_summary.get("externalCreateTime"):
                item["externalCreateTime"] = sync_summary.get("externalCreateTime")
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
    def batch_reclassify_ticket_categories_services(
        cls,
        db: Session,
        request: TicketBatchReclassifyRequestModel,
        current_user: CurrentUserModel,
    ) -> dict[str, Any]:
        """
        批量执行工单自动分类。
        :param db: 数据库会话
        :param request: 批量重归类请求模型
        :param current_user: 当前登录用户
        :return: 执行结果摘要
        """
        current_user_name = _user_name(current_user) or "system"
        strategy = str(getattr(request, "strategy", "ai") or "ai").strip().lower()
        if strategy not in {"ai", "regex"}:
            strategy = "ai"
        ai_prompt_code = str(getattr(request, "ai_prompt_code", "") or "").strip() or None
        regex_rules = getattr(request, "regex_rules", None)
        only_uncategorized = bool(getattr(request, "only_uncategorized", False))
        all_tickets = bool(getattr(request, "all_tickets", False))

        base_query = db.query(Ticket).filter(Ticket.del_flag == "0")
        if only_uncategorized:
            base_query = base_query.filter(
                or_(
                    Ticket.category_name.is_(None),
                    Ticket.category_name == "",
                )
            )
        base_query = base_query.order_by(Ticket.update_time.desc(), Ticket.ticket_id.desc())

        if getattr(request, "ticket_ids", None):
            query = base_query.filter(Ticket.ticket_id.in_(request.ticket_ids))
            total = query.count()
            tickets = query.all()
        else:
            total = base_query.count()
            if all_tickets:
                tickets = base_query.all()
            else:
                page_num = max(int(getattr(request, "page_num", 1) or 1), 1)
                page_size = min(max(int(getattr(request, "page_size", 100) or 100), 1), 500)
                tickets = base_query.offset((page_num - 1) * page_size).limit(page_size).all()

        summary = {
            "total": total,
            "selectedCount": len(tickets),
            "successCount": 0,
            "skippedCount": 0,
            "failedCount": 0,
            "strategy": strategy,
            "onlyUncategorized": only_uncategorized,
            "allTickets": all_tickets,
            "details": [],
        }
        if strategy == "regex" and not regex_rules:
            summary["skippedCount"] = len(tickets)
            summary["details"] = [
                {
                    "ticketId": ticket.ticket_id,
                    "ticketNo": ticket.ticket_no,
                    "skipped": True,
                    "skipReason": "未配置正则归类规则",
                }
                for ticket in tickets
            ]
            return summary

        for ticket in tickets:
            try:
                _, category_result = cls._run_auto_ticket_category_classification(
                    db,
                    ticket=ticket,
                    title=str(ticket.title or "").strip(),
                    description=str(ticket.description or "").strip(),
                    current_user_name=current_user_name,
                    source_type="ticket_batch_reclassify",
                    source_ref=str(ticket.ticket_no or ticket.ticket_id),
                    force_reclassify=bool(getattr(request, "force_reclassify", False)),
                    classification_strategy=strategy,
                    regex_rules=regex_rules,
                    ai_prompt_code=ai_prompt_code,
                )
                detail = {
                    "ticketId": ticket.ticket_id,
                    "ticketNo": ticket.ticket_no,
                    **category_result,
                }
                summary["details"].append(detail)
                if category_result.get("skipped"):
                    summary["skippedCount"] += 1
                else:
                    summary["successCount"] += 1
            except Exception as exc:
                logger.warning(
                    f"批量工单自动分类失败: ticket_id={ticket.ticket_id}, ticket_no={ticket.ticket_no}, error={exc}"
                )
                summary["failedCount"] += 1
                summary["details"].append(
                    {
                        "ticketId": ticket.ticket_id,
                        "ticketNo": ticket.ticket_no,
                        "skipped": False,
                        "failed": True,
                        "error": str(exc),
                    }
                )
        return summary

    @classmethod
    def get_uncategorized_ticket_statistics_services(cls, db: Session) -> dict[str, Any]:
        """
        统计当前工单中未归类数量。

        :param db: 数据库会话。
        :return: 未归类统计结果。
        """
        total_count = db.query(Ticket).filter(Ticket.del_flag == "0").count()
        uncategorized_count = (
            db.query(Ticket)
            .filter(
                Ticket.del_flag == "0",
                or_(
                    Ticket.category_name.is_(None),
                    Ticket.category_name == "",
                ),
            )
            .count()
        )
        categorized_count = max(total_count - uncategorized_count, 0)
        uncategorized_ratio = round((uncategorized_count / total_count) * 100, 2) if total_count else 0
        return {
            "totalCount": total_count,
            "categorizedCount": categorized_count,
            "uncategorizedCount": uncategorized_count,
            "uncategorizedRatio": uncategorized_ratio,
        }

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
        description = str(item.get("description") or "").strip()
        title = str(item.get("title") or "").strip()
        if not ticket_no or not description:
            return None
        sync_summary = item.get("syncSummary") if isinstance(item.get("syncSummary"), dict) else {}
        remote_sync_revision = int(
            item.get("syncRevision")
            or sync_summary.get("revision")
            or item.get("revision")
            or 0
        )
        external_create_time = (
            item.get("externalCreateTime")
            or item.get("external_create_time")
            or sync_summary.get("externalCreateTime")
            or item.get("createTime")
            or item.get("create_time")
        )
        remote_ticket_url = str(
            item.get("ticketUrl")
            or item.get("ticket_url")
            or item.get("url")
            or item.get("detailUrl")
            or item.get("detail_url")
            or sync_summary.get("ticketUrl")
            or sync_summary.get("sourceRecordUrl")
            or ""
        ).strip() or None

        source_payload = {
            "system": str(remote_sync.get("sourceSystem") or "public").strip() or "public",
            "recordId": str(item.get("ticketId") or item.get("ticket_id") or ticket_no).strip() or ticket_no,
            "recordUrl": remote_ticket_url,
            "pushedAt": (
                item.get("updateTime")
                or item.get("update_time")
                or item.get("createTime")
                or item.get("create_time")
            ),
        }
        sync_extra_data = item.get("extraData") if isinstance(item.get("extraData"), dict) else {}
        if not sync_extra_data and isinstance(item.get("extra_data"), dict):
            sync_extra_data = item.get("extra_data")
        sync_extra_data = dict(sync_extra_data or {})
        sync_extra_data["_remote_sync_revision"] = remote_sync_revision
        sync_payload = {
            "source": source_payload,
            "syncConsumer": str(remote_sync.get("consumer") or "").strip() or None,
            "rawPayload": item,
            "ticketNo": ticket_no,
            "ticketUrl": remote_ticket_url,
            "title": title,
            "description": description,
            "createTime": external_create_time or source_payload.get("pushedAt"),
            "projectId": item.get("projectId") or item.get("project_id"),
            "projectName": item.get("projectName") or item.get("project_name") or item.get("merchantName") or "",
            "projectCode": item.get("projectCode") or item.get("project_code") or "",
            "merchantName": item.get("merchantName") or item.get("projectName") or item.get("project_name") or "",
            "moduleId": item.get("moduleId") or item.get("module_id"),
            "moduleName": item.get("moduleName") or item.get("module_name") or "",
            "moduleCode": item.get("moduleCode") or item.get("module_code") or "",
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
            "extraData": sync_extra_data,
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
            "skippedCount": 0,
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
                            "message": "远端工单数据缺少 ticketNo 或 description",
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
            local_ticket = TicketDao.get_ticket_by_no(db, upsert_model.ticket_no)
            should_apply_remote, apply_reason = cls._should_apply_remote_sync_item(
                local_ticket=local_ticket,
                remote_sync_revision=sync_revision,
                remote_pushed_at=upsert_model.source.pushed_at,
            )
            if not should_apply_remote:
                summary["skippedCount"] += 1
                summary["syncedCount"] += 1
                if remote_ticket_id:
                    ack_items.append(
                        {
                            "ticketId": remote_ticket_id,
                            "syncRevision": sync_revision,
                            "deliveryStatus": "delivered",
                            "message": "本地数据已是最新，跳过覆盖更新",
                            "detail": {
                                "skipReason": apply_reason,
                                "localTicketId": getattr(local_ticket, "ticket_id", None),
                            },
                        }
                    )
                continue

            try:
                sync_result = cls.sync_external_ticket(
                    db,
                    upsert_model,
                    current_user,
                    sync_scene="remote_pull",
                )
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
