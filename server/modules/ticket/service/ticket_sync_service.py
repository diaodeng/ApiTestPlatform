import hashlib
import json
import re
from datetime import datetime, time, timedelta, timezone
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
from modules.ticket.entity.do.ticket_do import Ticket, TicketComment, TicketEvent, TicketMessage, TicketStatusHistory
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
    DEFAULT_GROUP_PUSH_AUTO_STATUSES = [
        "2. 1.5线处理",
        "3. 待产研处理",
        "4. 产研处理中",
    ]
    DEFAULT_EXTERNAL_SYNC_REQUIRED_FIELDS = [
        "ticketNo",
        "description",
        "internalPriority",
        "ticketVender",
        "ticketModle",
        "createTime",
        "reporterName",
    ]
    DEFAULT_EXTERNAL_FIELD_MODEL_FIELDS = [
        {"fieldName": "ticketNo", "label": "工单号", "required": True, "category": "basic"},
        {"fieldName": "title", "label": "工单标题", "required": False, "category": "basic"},
        {"fieldName": "description", "label": "问题描述", "required": True, "category": "basic"},
        {"fieldName": "customerPriority", "label": "对方优先级", "required": False, "category": "priority"},
        {"fieldName": "internalPriority", "label": "内部优先级", "required": True, "category": "priority"},
        {"fieldName": "ticketVender", "label": "商家/供应商", "required": True, "category": "mapping"},
        {"fieldName": "ticketModle", "label": "模块", "required": True, "category": "mapping"},
        {"fieldName": "ticketStatus", "label": "外部状态", "required": False, "category": "mapping"},
        {"fieldName": "ticketStore", "label": "门店信息", "required": False, "category": "mapping"},
        {"fieldName": "ticketPos", "label": "POS号", "required": False, "category": "mapping"},
        {"fieldName": "ticketSco", "label": "SCO号", "required": False, "category": "mapping"},
        {"fieldName": "createTime", "label": "创建时间", "required": True, "category": "time"},
        {"fieldName": "reporterName", "label": "报告人/1线处理人", "required": True, "category": "person"},
        {"fieldName": "reporterEmail", "label": "报告人邮箱", "required": False, "category": "person"},
        {"fieldName": "currentAssigneeName", "label": "当前处理人", "required": False, "category": "person"},
        {"fieldName": "currentAssigneeEmail", "label": "当前处理人邮箱", "required": False, "category": "person"},
        {"fieldName": "internalOwner", "label": "内部负责人", "required": False, "category": "person"},
        {"fieldName": "internalOwnerEmail", "label": "内部负责人邮箱", "required": False, "category": "person"},
        {"fieldName": "ticketUrl", "label": "工单链接", "required": False, "category": "basic"},
        {"fieldName": "recordId", "label": "多维表格记录ID", "required": False, "category": "source"},
        {"fieldName": "reason", "label": "原因说明", "required": False, "category": "basic"},
        {"fieldName": "stepReason", "label": "排查过程", "required": False, "category": "basic"},
    ]
    DEFAULT_TICKET_STAT_CLASSIFICATIONS = {
        "issueTypes": [
            {"value": "system_bug", "label": "系统Bug", "isProblem": True},
            {"value": "data_error", "label": "数据错误", "isProblem": True},
            {"value": "config_issue", "label": "配置问题", "isProblem": True},
            {"value": "performance_issue", "label": "性能问题", "isProblem": True},
            {"value": "support_consulting", "label": "支持咨询", "isProblem": False},
            {"value": "requirement_consulting", "label": "需求咨询", "isProblem": False},
            {"value": "user_operation", "label": "用户操作问题", "isProblem": False},
            {"value": "api_exception", "label": "接口异常", "isProblem": True},
        ],
        "rootCauseTypes": [
            {"value": "code_defect", "label": "代码缺陷"},
            {"value": "config_error", "label": "配置错误"},
            {"value": "data_exception", "label": "数据异常"},
            {"value": "third_party", "label": "第三方问题"},
            {"value": "network_issue", "label": "网络问题"},
            {"value": "environment_issue", "label": "环境问题"},
            {"value": "operation_mistake", "label": "操作失误"},
            {"value": "requirement_design", "label": "需求设计问题"},
            {"value": "unknown", "label": "未知"},
        ],
        "solutionTypes": [
            {"value": "code_fix", "label": "代码修复"},
            {"value": "config_fix", "label": "配置修复"},
            {"value": "data_fix", "label": "数据修复"},
            {"value": "temporary_workaround", "label": "临时处理"},
            {"value": "manual_process", "label": "人工处理"},
            {"value": "no_action", "label": "无需处理"},
        ],
        "resolutions": [
            {"value": "fixed", "label": "已修复", "isProblem": True},
            {"value": "non_problem", "label": "非问题", "isProblem": False},
            {"value": "data_processed", "label": "数据已处理", "isProblem": True},
            {"value": "config_fixed", "label": "配置已修复", "isProblem": True},
            {"value": "user_canceled", "label": "用户撤销", "isProblem": False},
            {"value": "duplicated", "label": "重复工单", "isProblem": False},
            {"value": "cannot_reproduce", "label": "无法复现", "isProblem": None},
            {"value": "as_designed", "label": "需求如此", "isProblem": False},
            {"value": "transferred", "label": "已转其他团队", "isProblem": None},
        ],
    }
    GROUP_PUSH_LOCK_TIMEOUT_SECONDS = 300

    @classmethod
    def _to_bool(cls, value: Any, default: bool = False) -> bool:
        """
        将任务参数或配置值转换为布尔值。

        :param value: 原始布尔、数字或字符串值。
        :param default: 值为空或无法识别时返回的默认值。
        :return: 归一化后的布尔值。
        """
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        normalized_value = str(value).strip().lower()
        if normalized_value in {"true", "1", "yes", "y", "on", "开启", "是"}:
            return True
        if normalized_value in {"false", "0", "no", "n", "off", "关闭", "否"}:
            return False
        return default

    @classmethod
    def _build_system_current_user(cls) -> CurrentUserModel:
        """
        构造后台任务使用的系统用户上下文。

        :return: 包含空权限、空角色和 system 用户信息的当前用户模型。
        """
        return CurrentUserModel.model_validate(cls._build_system_current_user_payload())

    @classmethod
    def _build_system_current_user_payload(cls) -> dict[str, Any]:
        """
        构造可跨 Celery 序列化的系统用户载荷。

        :return: 满足 CurrentUserModel 校验要求的用户字典。
        """
        return {
            "permissions": [],
            "roles": [],
            "user": {"userId": 0, "userName": "system", "nickName": "system"},
        }

    @classmethod
    def _normalize_current_user_payload(cls, current_user_payload: dict[str, Any] | None) -> dict[str, Any]:
        """
        归一化延后后处理任务的当前用户载荷。

        :param current_user_payload: Celery 或本地后台任务传入的当前用户字典。
        :return: 补齐 permissions、roles 和 user 后的当前用户字典。
        """
        payload = dict(current_user_payload or {})
        payload.setdefault("permissions", [])
        payload.setdefault("roles", [])
        user_payload = payload.get("user")
        if isinstance(user_payload, dict):
            payload["user"] = {
                "userId": user_payload.get("userId", user_payload.get("user_id")),
                "userName": user_payload.get("userName", user_payload.get("user_name")),
                "nickName": user_payload.get("nickName", user_payload.get("nick_name")),
            }
        else:
            payload["user"] = cls._build_system_current_user_payload()["user"]
        return payload

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
    def _parse_step_reason_date(cls, value: str) -> datetime | None:
        """
        解析 stepReason 分段开头的日期。
        :param value: 日期文本，支持 yyyyMMdd
        :return: 日期时间，解析失败返回 None
        """
        text = str(value or "").strip()
        if not re.fullmatch(r"\d{8}", text):
            return None
        try:
            return datetime.combine(datetime.strptime(text, "%Y%m%d").date(), time.min)
        except Exception:
            return None

    @classmethod
    def parse_step_reason_segments(cls, step_reason: Any) -> list[dict[str, Any]]:
        """
        将飞书排查过程 stepReason 拆分为评论片段。
        :param step_reason: 原始排查过程文本
        :return: 片段列表，包含 segmentIndex/date/person/content/contentHash
        """
        text = str(step_reason or "").replace("\r\n", "\n").replace("\r", "\n").strip()
        if not text:
            return []
        pattern = re.compile(r"(?m)^(?P<date>\d{8})(?:\s+(?P<person>[^：:\n]{1,50}))?[：:]")
        matches = list(pattern.finditer(text))
        segments: list[dict[str, Any]] = []
        if not matches:
            content_hash = cls._text_sha256(text)
            return [
                {
                    "segmentIndex": 0,
                    "dateText": "",
                    "personName": "",
                    "content": text,
                    "contentHash": content_hash,
                    "externalCreatedAt": None,
                }
            ]
        prefix = text[: matches[0].start()].strip()
        if prefix:
            segments.append(
                {
                    "segmentIndex": len(segments),
                    "dateText": "",
                    "personName": "",
                    "content": prefix,
                    "contentHash": cls._text_sha256(prefix),
                    "externalCreatedAt": None,
                }
            )
        for index, match in enumerate(matches):
            start = match.end()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            content = text[start:end].strip()
            if not content:
                continue
            date_text = str(match.group("date") or "").strip()
            person_name = str(match.group("person") or "").strip()
            segments.append(
                {
                    "segmentIndex": len(segments),
                    "dateText": date_text,
                    "personName": person_name,
                    "content": content,
                    "contentHash": cls._text_sha256(content),
                    "externalCreatedAt": cls._parse_step_reason_date(date_text),
                }
            )
        return segments

    @classmethod
    def _build_step_reason_segment_key(
        cls,
        *,
        source_system: str,
        source_record_id: str,
        segment_index: int,
    ) -> str:
        """
        构建 stepReason 评论分段幂等键。
        :param source_system: 来源系统
        :param source_record_id: 来源记录ID
        :param segment_index: 分段序号
        :return: 稳定幂等键
        """
        raw_key = "|".join(
            [
                str(source_system or "").strip() or cls.SOURCE_CODE,
                str(source_record_id or "").strip(),
                "stepReason",
                str(int(segment_index or 0)),
            ]
        )
        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    @classmethod
    def sync_step_reason_comments(
        cls,
        db: Session,
        *,
        ticket: Ticket,
        sync_object: TicketExternalSyncUpsertModel,
    ) -> dict[str, Any]:
        """
        将外部 stepReason 排查过程幂等同步为工单评论。
        :param db: 数据库会话
        :param ticket: 工单对象
        :param sync_object: 外部同步入参
        :return: 同步结果摘要
        """
        step_reason = str(getattr(sync_object, "step_reason", "") or "").strip()
        if not step_reason and isinstance(sync_object.extra_data, dict):
            step_reason = str(sync_object.extra_data.get("step_reason") or "").strip()
        if not step_reason and isinstance(sync_object.raw_payload, dict):
            step_reason = str(
                sync_object.raw_payload.get("stepReason")
                or sync_object.raw_payload.get("step_reason")
                or ""
            ).strip()
        if not step_reason:
            return {"skipped": True, "reason": "empty_step_reason", "created": 0, "updated": 0, "skippedCount": 0}
        source_system = str(getattr(sync_object.source, "system", "") or "").strip() or cls.SOURCE_CODE
        source_record_id = str(getattr(sync_object.source, "record_id", "") or "").strip() or str(
            sync_object.ticket_no or ""
        ).strip()
        segments = cls.parse_step_reason_segments(step_reason)
        summary = {"skipped": False, "total": len(segments), "created": 0, "updated": 0, "skippedCount": 0}
        for segment in segments:
            segment_index = int(segment.get("segmentIndex") or 0)
            segment_key = cls._build_step_reason_segment_key(
                source_system=source_system,
                source_record_id=source_record_id,
                segment_index=segment_index,
            )
            _, action = TicketService.upsert_synced_comment(
                db,
                ticket_id=ticket.ticket_id,
                content=str(segment.get("content") or "").strip(),
                user_name=str(segment.get("personName") or "").strip() or "外部同步",
                source_type="feishu_bitable",
                source_system=source_system,
                source_record_id=source_record_id,
                source_field="stepReason",
                source_segment_key=segment_key,
                source_segment_index=segment_index,
                source_content_hash=str(segment.get("contentHash") or "").strip(),
                external_created_at=segment.get("externalCreatedAt"),
                attachments=None,
                is_internal=False,
            )
            if action == "created":
                summary["created"] += 1
            elif action == "updated":
                summary["updated"] += 1
            else:
                summary["skippedCount"] += 1
        return summary

    @classmethod
    def sync_remote_payload_comments(
        cls,
        db: Session,
        *,
        ticket: Ticket,
        sync_object: TicketExternalSyncUpsertModel,
    ) -> dict[str, Any]:
        """
        将远端 pending payload 中的同步评论幂等写入本地。
        :param db: 数据库会话
        :param ticket: 本地工单对象
        :param sync_object: 远端拉取入库模型
        :return: 同步结果摘要
        """
        if not isinstance(sync_object.extra_data, dict):
            return {"skipped": True, "reason": "empty_extra_data", "created": 0, "updated": 0, "skippedCount": 0}
        comments = sync_object.extra_data.get("_remote_sync_comments")
        if not isinstance(comments, list) or not comments:
            return {"skipped": True, "reason": "empty_comments", "created": 0, "updated": 0, "skippedCount": 0}
        summary = {"skipped": False, "total": 0, "created": 0, "updated": 0, "skippedCount": 0}
        for item in comments:
            if not isinstance(item, dict):
                continue
            source_type = str(item.get("sourceType") or item.get("source_type") or "local").strip()
            if source_type in ("", "local"):
                continue
            source_segment_key = str(item.get("sourceSegmentKey") or item.get("source_segment_key") or "").strip()
            content = str(item.get("content") or "").strip()
            if not source_segment_key or not content:
                continue
            summary["total"] += 1
            external_created_at = cls._parse_datetime_value(
                item.get("externalCreatedAt")
                or item.get("external_created_at")
                or item.get("createTime")
                or item.get("create_time")
            )
            _, action = TicketService.upsert_synced_comment(
                db,
                ticket_id=ticket.ticket_id,
                content=content,
                user_name=str(item.get("userName") or item.get("user_name") or "").strip() or "外部同步",
                source_type=source_type,
                source_system=str(item.get("sourceSystem") or item.get("source_system") or "").strip(),
                source_record_id=str(item.get("sourceRecordId") or item.get("source_record_id") or "").strip(),
                source_field=str(item.get("sourceField") or item.get("source_field") or "").strip(),
                source_segment_key=source_segment_key,
                source_segment_index=int(item.get("sourceSegmentIndex") or item.get("source_segment_index") or 0),
                source_content_hash=str(item.get("sourceContentHash") or item.get("source_content_hash") or "").strip()
                or cls._text_sha256(content),
                external_created_at=external_created_at,
                attachments=item.get("attachments"),
                is_internal=bool(item.get("isInternal") if "isInternal" in item else item.get("is_internal", False)),
            )
            if action == "created":
                summary["created"] += 1
            elif action == "updated":
                summary["updated"] += 1
            else:
                summary["skippedCount"] += 1
        return summary

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
    def _can_recover_publish_state(cls, db: Session, *, ticket: Ticket, meta: dict[str, Any]) -> tuple[bool, str]:
        """
        判断未发布同步数据是否可恢复为可发布状态。
        :param db: 数据库会话
        :param ticket: 待检查工单
        :param meta: 同步元数据
        :return: (是否可恢复, 恢复原因)
        """
        if cls._is_publish_ready(meta):
            return False, "already_ready"
        sync_state = meta.get("sync_state") if isinstance(meta.get("sync_state"), dict) else {}
        publish_status = str(sync_state.get("publish_status") or "").strip()
        if publish_status != cls.PUBLISH_STATUS_PROCESSING_AI:
            return False, f"publish_status_not_recoverable:{publish_status or '-'}"
        ai_pending, ai_status = cls._resolve_ai_pending_state(db, ticket_id=ticket.ticket_id, meta=meta)
        if ai_pending:
            return False, f"ai_still_pending:{ai_status or '-'}"
        return True, f"ai_not_pending:{ai_status or '-'}"

    @classmethod
    def _ensure_publish_ready_for_pull(
        cls,
        db: Session,
        *,
        ticket: Ticket,
        current_user: CurrentUserModel,
    ) -> tuple[Ticket, dict[str, Any], bool]:
        """
        拉取前自愈同步发布状态，避免服务重启后 processing_ai 长期卡住。
        :param db: 数据库会话
        :param ticket: 候选工单
        :param current_user: 当前用户
        :return: (刷新后的工单, 同步元数据, 是否已恢复)
        """
        extra_data = dict(ticket.extra_data or {}) if isinstance(ticket.extra_data, dict) else {}
        meta = cls._build_meta(extra_data)
        recoverable, recover_reason = cls._can_recover_publish_state(db, ticket=ticket, meta=meta)
        if not recoverable:
            return ticket, meta, False
        logger.warning(
            "工单同步发布状态自愈: ticket_no=%s, revision=%s, reason=%s",
            ticket.ticket_no,
            meta.get("revision"),
            recover_reason,
        )
        meta = cls._set_publish_state(
            meta,
            ready=True,
            status=cls.PUBLISH_STATUS_READY,
            reason="拉取前检测到无活动AI任务，自动恢复发布状态",
            ai_task_status=str((meta.get("sync_state") or {}).get("ai_task_status") or "").strip(),
        )
        ticket = cls._persist_sync_meta(
            db,
            ticket=ticket,
            meta=meta,
            update_by=_user_name(current_user),
        )
        return ticket, meta, True

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
    def _mark_group_push_processing(
        cls,
        meta: dict[str, Any],
        *,
        scene: str,
        revision: int,
    ) -> dict[str, Any]:
        """
        标记工单群推送正在处理中，作为并发互斥锁。
        :param meta: 同步元数据
        :param scene: 触发场景
        :param revision: 同步修订号
        :return: 更新后的同步元数据
        """
        sync_state = meta.get("sync_state") if isinstance(meta.get("sync_state"), dict) else {}
        sync_state["group_push_processing"] = True
        sync_state["group_push_processing_at"] = cls._now_iso()
        sync_state["group_push_processing_scene"] = str(scene or "").strip() or "external_sync"
        sync_state["group_push_processing_revision"] = int(revision or 0)
        meta["sync_state"] = sync_state
        return meta

    @classmethod
    def _clear_group_push_processing(cls, meta: dict[str, Any]) -> dict[str, Any]:
        """
        清理工单群推送处理中锁。
        :param meta: 同步元数据
        :return: 更新后的同步元数据
        """
        sync_state = meta.get("sync_state") if isinstance(meta.get("sync_state"), dict) else {}
        sync_state["group_push_processing"] = False
        sync_state["group_push_processing_at"] = None
        sync_state["group_push_processing_scene"] = None
        sync_state["group_push_processing_revision"] = None
        meta["sync_state"] = sync_state
        return meta

    @classmethod
    def _is_group_push_processing_locked(cls, meta: dict[str, Any]) -> tuple[bool, str]:
        """
        判断群推送处理锁是否生效。
        :param meta: 同步元数据
        :return: (是否锁定, 锁定原因)
        """
        sync_state = meta.get("sync_state") if isinstance(meta.get("sync_state"), dict) else {}
        if not bool(sync_state.get("group_push_processing")):
            return False, ""
        lock_time = cls._parse_datetime_value(sync_state.get("group_push_processing_at"))
        if lock_time is None:
            return True, "群推送处理中（锁时间缺失）"
        elapsed_seconds = (datetime.now() - lock_time).total_seconds()
        if elapsed_seconds > cls.GROUP_PUSH_LOCK_TIMEOUT_SECONDS:
            return False, ""
        return True, "群推送处理中"

    @classmethod
    def _persist_group_push_meta_state(
        cls,
        db: Session,
        *,
        ticket_id: int,
        update_by: str,
        scene: str,
        acquire_lock: bool = False,
        clear_lock: bool = False,
        mark_sent_once: bool = False,
    ) -> tuple[bool, Ticket | None, dict[str, Any], str]:
        """
        在数据库行级锁内更新群推送状态，保障并发下的去重一致性。
        :param db: 数据库会话
        :param ticket_id: 工单ID
        :param update_by: 更新人
        :param scene: 触发场景
        :param acquire_lock: 是否抢占群推送处理锁
        :param clear_lock: 是否清理群推送处理锁
        :param mark_sent_once: 是否标记已发送过
        :return: (是否更新成功, 工单对象, 最新元数据, 结果原因)
        """
        try:
            ticket = (
                db.query(Ticket)
                .filter(Ticket.ticket_id == ticket_id, Ticket.del_flag == "0")
                .with_for_update()
                .first()
            )
            if not ticket:
                db.rollback()
                return False, None, {}, "ticket_not_found"

            extra_data = dict(ticket.extra_data or {}) if isinstance(ticket.extra_data, dict) else {}
            meta = cls._build_meta(extra_data)
            if acquire_lock:
                if cls._is_group_push_sent_once(meta):
                    db.rollback()
                    return False, ticket, meta, "already_sent"
                locked, lock_reason = cls._is_group_push_processing_locked(meta)
                if locked:
                    db.rollback()
                    return False, ticket, meta, lock_reason or "group_push_processing"
                meta = cls._mark_group_push_processing(
                    meta,
                    scene=scene,
                    revision=int(meta.get("revision") or 0),
                )
            if clear_lock:
                meta = cls._clear_group_push_processing(meta)
            if mark_sent_once:
                meta = cls._mark_group_push_sent_once(
                    meta,
                    scene=scene,
                    revision=int(meta.get("revision") or 0),
                )
            if acquire_lock or clear_lock or mark_sent_once:
                refreshed_extra_data = cls._attach_meta(extra_data, meta)
                TicketDao.update_ticket(
                    db,
                    ticket.ticket_id,
                    {
                        "extra_data": refreshed_extra_data,
                        "update_by": update_by,
                        "update_time": datetime.now(),
                    },
                )
                db.commit()
                ticket = TicketDao.get_ticket_by_id(db, ticket.ticket_id) or ticket
            else:
                db.rollback()
            return True, ticket, meta, "updated"
        except Exception:
            db.rollback()
            raise

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
        skip_by_status, status_skip_reason = cls._should_skip_auto_group_push_by_status(
            ticket=ticket,
            group_config=group_config,
        )
        if skip_by_status:
            logger.info(
                f"自动群推送跳过: ticket_no={ticket.ticket_no}, scene={scene}, "
                f"reason={status_skip_reason or '工单状态不满足自动推送条件'}"
            )
            return (
                {
                    "skipped": True,
                    "skipReason": status_skip_reason or "工单状态不满足自动推送条件",
                    "scene": scene,
                },
                ticket,
                meta,
            )

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
        skip_by_submit_time, submit_time_skip_reason = cls._should_skip_auto_group_push_by_submit_time(
            ticket=ticket,
            meta=meta,
            group_config=group_config,
        )
        if skip_by_submit_time:
            logger.info(
                f"自动群推送跳过: ticket_no={ticket.ticket_no}, scene={scene}, "
                f"reason={submit_time_skip_reason or '工单提交时间不满足自动推送起始时间'}"
            )
            return (
                {
                    "skipped": True,
                    "skipReason": submit_time_skip_reason or "工单提交时间不满足自动推送起始时间",
                    "scene": scene,
                },
                ticket,
                meta,
            )

        lock_acquired, locked_ticket, locked_meta, lock_reason = cls._persist_group_push_meta_state(
            db,
            ticket_id=ticket.ticket_id,
            update_by=update_by,
            scene=scene,
            acquire_lock=True,
        )
        if not lock_acquired:
            if lock_reason == "already_sent":
                logger.info(
                    f"自动群推送跳过: ticket_no={ticket.ticket_no}, scene={scene}, "
                    f"reason=工单已发送过群推送"
                )
                return (
                    {"skipped": True, "skipReason": "工单已发送过群推送", "scene": scene},
                    ticket,
                    meta,
                )
            logger.info(
                f"自动群推送跳过: ticket_no={ticket.ticket_no}, scene={scene}, "
                f"reason={lock_reason or '群推送处理中'}"
            )
            return (
                {"skipped": True, "skipReason": lock_reason or "群推送处理中", "scene": scene},
                ticket,
                meta,
            )
        if locked_ticket:
            ticket = locked_ticket
        if locked_meta:
            meta = locked_meta

        sync_summary = cls.extract_sync_summary(
            cls._attach_meta(dict(ticket.extra_data or {}) if isinstance(ticket.extra_data, dict) else {}, meta)
        ) or {}
        result: dict[str, Any] = {}
        mark_sent_once = False
        try:
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
            mark_sent_once = not bool(result.get("skipped")) and (push_success_count > 0 or app_success_count > 0)
            if mark_sent_once:
                logger.info(
                    f"自动群推送已标记去重: ticket_no={ticket.ticket_no}, scene={scene}, "
                    f"push_success_count={push_success_count}, app_success_count={app_success_count}"
                )
            elif not bool(result.get("skipped")):
                logger.warning(
                    f"自动群推送未产生成功发送，保持未去重状态: ticket_no={ticket.ticket_no}, scene={scene}, "
                    f"push_success_count={push_success_count}, app_success_count={app_success_count}"
                )
        finally:
            state_updated, refreshed_ticket, refreshed_meta, _ = cls._persist_group_push_meta_state(
                db,
                ticket_id=ticket.ticket_id,
                update_by=update_by,
                scene=scene,
                clear_lock=True,
                mark_sent_once=mark_sent_once,
            )
            if state_updated:
                if refreshed_ticket:
                    ticket = refreshed_ticket
                if refreshed_meta:
                    meta = refreshed_meta
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
    def _resolve_ticket_submit_time(cls, *, ticket: Ticket, meta: dict[str, Any] | None) -> datetime | None:
        """
        解析工单提交时间：优先外部 createTime，缺失时回退本地创建时间。

        :param ticket: 工单对象。
        :param meta: 同步元数据。
        :return: 可比较的提交时间，无法解析时返回 None。
        """
        sync_meta = meta if isinstance(meta, dict) else {}
        source_snapshot = sync_meta.get("source") if isinstance(sync_meta.get("source"), dict) else {}
        external_create_time = (
            sync_meta.get("externalCreateTime")
            or source_snapshot.get("externalCreateTime")
        )
        parsed_external_time = cls._parse_datetime_value(external_create_time)
        if parsed_external_time:
            return parsed_external_time
        return cls._parse_datetime_value(getattr(ticket, "create_time", None))

    @classmethod
    def _resolve_group_push_auto_send_after_time(cls, group_config: dict[str, Any] | None) -> datetime | None:
        """
        解析自动群推送起始时间配置。

        :param group_config: 群推送配置。
        :return: 起始时间，未配置或解析失败时返回 None。
        """
        config = group_config if isinstance(group_config, dict) else {}
        return cls._parse_datetime_value(
            config.get("autoSendAfterTime")
            or config.get("auto_send_after_time")
        )

    @classmethod
    def _normalize_group_push_auto_statuses(
        cls,
        value: Any,
        *,
        fallback: Any = None,
    ) -> list[str]:
        """
        归一化自动群推送状态条件配置。

        :param value: 原始状态条件，支持列表或逗号分隔字符串。
        :param fallback: 回退配置值。
        :return: 去重后的状态文本列表。
        """
        source_value = value
        if source_value is None:
            source_value = fallback
        if isinstance(source_value, str):
            source_list = [item.strip() for item in source_value.split(",")]
        elif isinstance(source_value, list):
            source_list = source_value
        else:
            source_list = []
        normalized: list[str] = []
        for item in source_list:
            status_text = str(item or "").strip()
            if status_text and status_text not in normalized:
                normalized.append(status_text)
        return normalized

    @classmethod
    def _should_skip_auto_group_push_by_status(
        cls,
        *,
        ticket: Ticket,
        group_config: dict[str, Any] | None,
    ) -> tuple[bool, str | None]:
        """
        判断自动群推送是否因状态条件不满足而跳过。

        :param ticket: 工单对象。
        :param group_config: 群推送配置。
        :return: (是否跳过, 跳过原因)。
        """
        config = group_config if isinstance(group_config, dict) else {}
        auto_push_statuses = cls._normalize_group_push_auto_statuses(
            config.get("autoPushStatuses", config.get("auto_push_statuses")),
        )
        if not auto_push_statuses:
            return False, None
        ticket_status = str(getattr(ticket, "status", "") or "").strip()
        if ticket_status in auto_push_statuses:
            return False, None
        return True, f"工单状态({ticket_status or '-'})未命中自动推送状态条件"

    @classmethod
    def _should_skip_auto_group_push_by_submit_time(
        cls,
        *,
        ticket: Ticket,
        meta: dict[str, Any] | None,
        group_config: dict[str, Any] | None,
    ) -> tuple[bool, str | None]:
        """
        判断自动群推送是否因“起始提交时间”配置而跳过。

        :param ticket: 工单对象。
        :param meta: 同步元数据。
        :param group_config: 群推送配置。
        :return: (是否跳过, 跳过原因)。
        """
        auto_send_after_time = cls._resolve_group_push_auto_send_after_time(group_config)
        if not auto_send_after_time:
            return False, None
        submit_time = cls._resolve_ticket_submit_time(ticket=ticket, meta=meta)
        if submit_time is None:
            return False, None
        if submit_time <= auto_send_after_time:
            return (
                True,
                f"工单提交时间({submit_time.isoformat()})未晚于自动推送起始时间({auto_send_after_time.isoformat()})",
            )
        return False, None

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
        if remote_sync_revision > 0 and local_source_revision is None:
            return True, "remote_revision_available_without_local_revision"

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
                (
                    f"remote_time_not_newer(remote={parsed_remote_time.isoformat()}, "
                    f"local={parsed_local_time.isoformat()})"
                ),
            )
        return True, "remote_time_newer_or_unknown"

    @classmethod
    def _default_sync_config(cls) -> dict[str, Any]:
        return {
            "autoRunOnSync": False,
            "autoTranslateOnSync": True,
            "defaultPullLimit": 50,
            "feishuAuth": cls._default_feishu_auth_config(),
            "bitableCommon": cls._default_bitable_common_config(),
            "externalFieldModel": cls._default_external_field_model_config(),
            "externalSyncBitable": cls._default_external_sync_bitable_config(),
            "remoteSync": cls._default_remote_sync_config(),
            "bitablePull": cls._default_bitable_pull_config(),
            "groupPush": cls._default_group_push_config(),
            "personReminder": cls._default_person_reminder_config(),
            "summaryReport": cls._default_summary_report_config(),
            "statClassification": cls._default_stat_classification_config(),
            "aiClassification": cls._default_ai_classification_config(),
            "externalSyncRequiredFields": list(cls.DEFAULT_EXTERNAL_SYNC_REQUIRED_FIELDS),
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
    def _default_bitable_common_config(cls) -> dict[str, Any]:
        """
        构建飞书多维表格公共配置。

        :return: 公共多维表格配置默认值。
        """
        return {
            "appId": "",
            "appSecret": "",
            "appToken": "",
            "tableId": "",
            "viewId": "",
            "pageSize": 500,
            "filterFormula": "",
        }

    @classmethod
    def _default_external_field_model_config(cls) -> dict[str, Any]:
        """
        构建外部工单字段模型默认配置。

        :return: 外部字段模型默认值。
        """
        return {
            "fields": [dict(item) for item in cls.DEFAULT_EXTERNAL_FIELD_MODEL_FIELDS],
        }

    @classmethod
    def _default_external_sync_bitable_config(cls) -> dict[str, Any]:
        """
        构建外部同步多维表格补充查询默认配置。

        :return: 外部同步多维表格配置默认值。
        """
        return {
            "enabled": False,
            "appId": "",
            "appSecret": "",
            "appToken": "",
            "tableId": "",
            "viewId": "",
        }

    @classmethod
    def _default_bitable_pull_config(cls) -> dict[str, Any]:
        """
        构建飞书多维表格主动拉取默认配置。

        :return: 主动拉取配置默认值。
        """
        return {
            "enabled": False,
            "appId": "",
            "appSecret": "",
            "appToken": "",
            "tableId": "",
            "viewId": "",
            "pageSize": 200,
            "filterFormula": "",
            "fieldMappings": [],
            "sourceSystem": "feishu_bitable_pull",
            "ticketNoField": "ticketNo",
            "updatedAtField": "",
            "sortField": "",
            "includeRecordUrl": True,
            "createdAfter": "",
            "forceSync": False,
            "automation": {
                "autoIdentify": True,
                "autoLogPull": False,
                "autoAiAnalysis": False,
                "autoTranslate": True,
            },
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
            "autoPushStatuses": list(cls.DEFAULT_GROUP_PUSH_AUTO_STATUSES),
            "priorityRoutes": [],
            "sendAfterExternalSync": False,
            "sendAfterRemotePull": False,
            "autoSendAfterTime": "",
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
            "rowsMarkdownTemplate": "",
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
    def _default_stat_classification_config(cls) -> dict[str, Any]:
        """
        构建工单分类统计枚举默认配置。

        :return: 分类统计枚举配置。
        """
        return {
            "issueTypes": [dict(item) for item in cls.DEFAULT_TICKET_STAT_CLASSIFICATIONS["issueTypes"]],
            "rootCauseTypes": [dict(item) for item in cls.DEFAULT_TICKET_STAT_CLASSIFICATIONS["rootCauseTypes"]],
            "solutionTypes": [dict(item) for item in cls.DEFAULT_TICKET_STAT_CLASSIFICATIONS["solutionTypes"]],
            "resolutions": [dict(item) for item in cls.DEFAULT_TICKET_STAT_CLASSIFICATIONS["resolutions"]],
        }

    @classmethod
    def _default_ai_classification_config(cls) -> dict[str, Any]:
        """
        构建工单 AI 分类统计默认配置。

        :return: AI 分类统计配置。
        """
        return {
            "enabled": False,
            "runOnExternalSync": False,
            "runOnRemotePull": False,
            "runOnManualCreate": False,
            "providerCode": "",
            "promptCode": "ticket_stat_classify_default",
            "promptContent": "",
        }

    @classmethod
    def _normalize_stat_option_rows(cls, value: Any, default_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        归一化可视化维护的统计枚举行。

        :param value: 前端提交的枚举行。
        :param default_rows: 默认枚举。
        :return: 去重后的枚举行。
        """
        source_rows = value if isinstance(value, list) else default_rows
        result: list[dict[str, Any]] = []
        seen_values: set[str] = set()
        for row in source_rows:
            if not isinstance(row, dict):
                continue
            option_value = str(row.get("value") or row.get("code") or row.get("id") or "").strip()
            option_label = str(row.get("label") or row.get("name") or option_value).strip()
            if not option_value or option_value in seen_values:
                continue
            normalized_row: dict[str, Any] = {
                "value": option_value,
                "label": option_label or option_value,
            }
            if "isProblem" in row:
                raw_is_problem = row.get("isProblem")
                normalized_row["isProblem"] = raw_is_problem if isinstance(raw_is_problem, bool) else None
            elif "is_problem" in row:
                raw_is_problem = row.get("is_problem")
                normalized_row["isProblem"] = raw_is_problem if isinstance(raw_is_problem, bool) else None
            if str(row.get("remark") or "").strip():
                normalized_row["remark"] = str(row.get("remark") or "").strip()
            result.append(normalized_row)
            seen_values.add(option_value)
        return result or [dict(item) for item in default_rows]

    @classmethod
    def _normalize_stat_classification_config(cls, value: Any) -> dict[str, Any]:
        """
        归一化工单分类统计配置。

        :param value: 原始配置。
        :return: 带默认值的配置。
        """
        source = value if isinstance(value, dict) else {}
        defaults = cls._default_stat_classification_config()
        return {
            "issueTypes": cls._normalize_stat_option_rows(
                source.get("issueTypes") or source.get("issue_types"),
                defaults["issueTypes"],
            ),
            "rootCauseTypes": cls._normalize_stat_option_rows(
                source.get("rootCauseTypes") or source.get("root_cause_types"),
                defaults["rootCauseTypes"],
            ),
            "solutionTypes": cls._normalize_stat_option_rows(
                source.get("solutionTypes") or source.get("solution_types"),
                defaults["solutionTypes"],
            ),
            "resolutions": cls._normalize_stat_option_rows(
                source.get("resolutions"),
                defaults["resolutions"],
            ),
        }

    @classmethod
    def _normalize_ai_classification_config(cls, value: Any) -> dict[str, Any]:
        """
        归一化工单 AI 分类统计配置。

        :param value: 原始配置。
        :return: 带默认值的配置。
        """
        source = value if isinstance(value, dict) else {}
        defaults = cls._default_ai_classification_config()
        return {
            "enabled": bool(source.get("enabled", defaults["enabled"])),
            "runOnExternalSync": bool(source.get("runOnExternalSync", source.get("run_on_external_sync", False))),
            "runOnRemotePull": bool(source.get("runOnRemotePull", source.get("run_on_remote_pull", False))),
            "runOnManualCreate": bool(source.get("runOnManualCreate", source.get("run_on_manual_create", False))),
            "providerCode": str(source.get("providerCode") or source.get("provider_code") or "").strip(),
            "promptCode": str(
                source.get("promptCode")
                or source.get("prompt_code")
                or defaults["promptCode"]
                or ""
            ).strip(),
            "promptContent": str(source.get("promptContent") or source.get("prompt_content") or "").strip(),
        }

    @classmethod
    def _normalize_external_field_model_config(cls, value: Any) -> dict[str, Any]:
        """
        归一化外部工单字段模型配置。

        :param value: 原始配置。
        :return: 归一化后的字段模型。
        """
        source = value if isinstance(value, dict) else {}
        source_fields = source.get("fields") if isinstance(source.get("fields"), list) else []
        normalized_fields: list[dict[str, Any]] = []
        seen_field_names: set[str] = set()
        for field in source_fields or cls.DEFAULT_EXTERNAL_FIELD_MODEL_FIELDS:
            if not isinstance(field, dict):
                continue
            field_name = str(field.get("fieldName") or field.get("value") or field.get("name") or "").strip()
            if not field_name or field_name in seen_field_names:
                continue
            normalized_fields.append(
                {
                    "fieldName": field_name,
                    "label": str(field.get("label") or field.get("name") or field_name).strip() or field_name,
                    "required": bool(field.get("required")),
                    "category": str(field.get("category") or "custom").strip() or "custom",
                    "description": str(field.get("description") or "").strip(),
                }
            )
            seen_field_names.add(field_name)
        if not normalized_fields:
            normalized_fields = [dict(item) for item in cls.DEFAULT_EXTERNAL_FIELD_MODEL_FIELDS]
        return {"fields": normalized_fields}

    @classmethod
    def _derive_required_fields_from_external_field_model(cls, value: Any) -> list[str]:
        """
        根据外部字段模型推导必填字段列表。

        :param value: 外部字段模型配置。
        :return: 必填字段列表。
        """
        model_config = cls._normalize_external_field_model_config(value)
        required_fields: list[str] = []
        for item in model_config.get("fields") or []:
            if not isinstance(item, dict):
                continue
            if not bool(item.get("required")):
                continue
            field_name = str(item.get("fieldName") or "").strip()
            if field_name and field_name not in required_fields:
                required_fields.append(field_name)
        return required_fields or list(cls.DEFAULT_EXTERNAL_SYNC_REQUIRED_FIELDS)

    @classmethod
    def _normalize_bitable_filter_config(cls, value: Any) -> str | dict[str, Any]:
        """
        归一化飞书多维表格查询过滤配置。

        :param value: 页面保存的 JSON 字符串，或任务参数直接传入的 JSON 对象。
        :return: 字符串或对象；空值返回空字符串。
        """
        if isinstance(value, dict):
            return value
        if value in (None, ""):
            return ""
        return str(value or "").strip()

    @classmethod
    def _parse_bitable_filter_config(cls, value: Any) -> dict[str, Any]:
        """
        将飞书多维表格过滤配置解析为条件对象。

        :param value: JSON 字符串或字典。
        :return: 可传给飞书 records/search 的 filter 对象；无效时返回空字典。
        """
        if isinstance(value, dict):
            return dict(value)
        if value in (None, ""):
            return {}
        try:
            parsed = json.loads(str(value or "").strip())
        except Exception as exc:
            raise ValueError("过滤条件格式错误，请填写飞书 records/search filter JSON") from exc
        return dict(parsed) if isinstance(parsed, dict) else {}

    @classmethod
    def _format_bitable_filter_config(cls, value: Any) -> str | dict[str, Any]:
        """
        按原输入形态输出过滤配置，兼容页面保存字符串和任务参数对象。

        :param value: 过滤条件对象。
        :return: JSON 字符串或对象。
        """
        if isinstance(value, dict):
            return value
        return ""

    @classmethod
    def _normalize_bitable_common_config(cls, value: Any, *, feishu_auth: dict[str, Any]) -> dict[str, Any]:
        """
        归一化飞书多维表格公共配置。

        :param value: 原始公共配置。
        :param feishu_auth: 飞书统一凭证。
        :return: 归一化后的公共配置。
        """
        source = value if isinstance(value, dict) else {}
        config = {**cls._default_bitable_common_config(), **source}
        config["appId"] = str(config.get("appId") or "").strip()
        config["appSecret"] = str(config.get("appSecret") or "").strip()
        config["appToken"] = str(config.get("appToken") or "").strip()
        config["tableId"] = str(config.get("tableId") or "").strip()
        config["viewId"] = str(config.get("viewId") or "").strip()
        config["pageSize"] = min(max(cls._safe_int(config.get("pageSize")) or 500, 1), 500)
        config["filterFormula"] = cls._normalize_bitable_filter_config(config.get("filterFormula"))
        return config

    @classmethod
    def _apply_bitable_common_defaults(
        cls,
        config: dict[str, Any] | None,
        *,
        bitable_common: dict[str, Any],
        keep_filter_formula: bool = True,
    ) -> dict[str, Any]:
        """
        将公共多维表格配置补齐到具体业务配置中。

        :param config: 业务侧配置。
        :param bitable_common: 公共多维表格配置。
        :param keep_filter_formula: 是否保留业务侧的 filterFormula 覆盖。
        :return: 合并后的配置。
        """
        source = dict(config or {})
        for key in ("appId", "appSecret", "appToken", "tableId", "viewId"):
            if not str(source.get(key) or "").strip():
                source[key] = bitable_common.get(key)
        page_size = cls._safe_int(source.get("pageSize"))
        if page_size is None:
            source["pageSize"] = bitable_common.get("pageSize")
        else:
            source["pageSize"] = min(max(page_size, 1), 500)
        if keep_filter_formula and not cls._normalize_bitable_filter_config(source.get("filterFormula")):
            source["filterFormula"] = bitable_common.get("filterFormula")
        return source

    @classmethod
    def _resolve_bitable_runtime_config(
        cls,
        config: dict[str, Any],
        section_key: str,
        default_config: dict[str, Any],
        *,
        keep_filter_formula: bool = True,
    ) -> dict[str, Any]:
        """
        解析运行时多维表格配置，只在真正执行飞书查询前继承公共配置。

        :param config: 完整同步配置。
        :param section_key: 业务配置段名称。
        :param default_config: 业务配置默认值。
        :param keep_filter_formula: 是否允许公共过滤公式兜底。
        :return: 已按“独立配置优先，公共配置兜底”合并后的运行时配置。
        """
        feishu_auth = config.get("feishuAuth") if isinstance(config.get("feishuAuth"), dict) else {}
        bitable_common = config.get("bitableCommon") if isinstance(config.get("bitableCommon"), dict) else {}
        section_config = config.get(section_key) if isinstance(config.get(section_key), dict) else {}
        runtime_config = {**default_config, **section_config}
        runtime_config = cls._apply_bitable_common_defaults(
            runtime_config,
            bitable_common=bitable_common,
            keep_filter_formula=keep_filter_formula,
        )
        if not str(runtime_config.get("appId") or "").strip():
            runtime_config["appId"] = str(feishu_auth.get("appId") or "").strip()
        if not str(runtime_config.get("appSecret") or "").strip():
            runtime_config["appSecret"] = str(feishu_auth.get("appSecret") or "").strip()
        return runtime_config

    @classmethod
    def _merge_non_empty_runtime_override(
        cls,
        base_config: dict[str, Any],
        override_config: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """
        合并运行时覆盖配置，空字符串不覆盖已继承的公共配置。

        :param base_config: 已解析的基础运行时配置。
        :param override_config: 页面预览或定时任务传入的覆盖配置。
        :return: 合并后的运行时配置。
        """
        merged_config = dict(base_config or {})
        if not isinstance(override_config, dict):
            return merged_config
        for key, value in override_config.items():
            if value is None:
                continue
            if isinstance(value, str) and not value.strip():
                continue
            merged_config[key] = value
        return merged_config

    @classmethod
    def _normalize_bitable_field_mappings(cls, value: Any) -> list[dict[str, Any]]:
        """
        归一化多维表格字段映射列表。

        :param value: 原始映射列表。
        :return: 归一化后的映射。
        """
        source_rows = value if isinstance(value, list) else []
        mappings: list[dict[str, Any]] = []
        seen_targets: set[str] = set()
        for row in source_rows:
            if not isinstance(row, dict):
                continue
            source_field = str(row.get("sourceField") or row.get("from") or row.get("bitableField") or "").strip()
            target_field = cls._normalize_bitable_pull_target_field(
                row.get("targetField") or row.get("to") or row.get("externalField")
            )
            if not source_field or not target_field:
                continue
            unique_key = f"{source_field}->{target_field}"
            if unique_key in seen_targets:
                continue
            mappings.append(
                {
                    "sourceField": source_field,
                    "targetField": target_field,
                    "defaultValue": row.get("defaultValue"),
                    "joinSeparator": str(row.get("joinSeparator") or "").strip() or ",",
                }
            )
            seen_targets.add(unique_key)
        return mappings

    @classmethod
    def _normalize_bitable_pull_target_field(cls, value: Any) -> str:
        """
        归一化主动拉取字段映射的目标字段名。

        :param value: 配置中的目标字段名。
        :return: 外部同步模型识别的规范字段名。
        """
        field_name = str(value or "").strip()
        alias_map = {
            "ticketModel": "ticketModle",
            "ticket_model": "ticketModle",
            "moduleName": "ticketModle",
            "module_name": "ticketModle",
            "projectName": "ticketVender",
            "project_name": "ticketVender",
            "merchantName": "ticketVender",
            "merchant_name": "ticketVender",
            "internalOwnerName": "internalOwner",
            "internal_owner_name": "internalOwner",
            "ticketAssigneeName": "ticketAssignee",
            "ticket_assignee_name": "ticketAssignee",
            "assigneeName": "ticketAssignee",
            "assignee_name": "ticketAssignee",
            "ticketAssigneeEmail": "ticketAssigneeEmail",
            "ticket_assignee_email": "ticketAssigneeEmail",
            "assigneeEmail": "ticketAssigneeEmail",
            "assignee_email": "ticketAssigneeEmail",
        }
        return alias_map.get(field_name, field_name)

    @classmethod
    def _normalize_bitable_pull_config(
        cls,
        value: Any,
        *,
        feishu_auth: dict[str, Any],
        bitable_common: dict[str, Any],
    ) -> dict[str, Any]:
        """
        归一化飞书多维表格主动拉取配置。

        :param value: 原始配置。
        :param feishu_auth: 飞书统一凭证。
        :param bitable_common: 多维公共配置。
        :return: 归一化后的主动拉取配置。
        """
        source = value if isinstance(value, dict) else {}
        config = {**cls._default_bitable_pull_config(), **source}
        config["enabled"] = cls._to_bool(config.get("enabled"), False)
        config["appId"] = str(config.get("appId") or "").strip() or str(feishu_auth.get("appId") or "").strip()
        config["appSecret"] = (
            str(config.get("appSecret") or "").strip() or str(feishu_auth.get("appSecret") or "").strip()
        )
        config["appToken"] = str(config.get("appToken") or "").strip()
        config["tableId"] = str(config.get("tableId") or "").strip()
        config["viewId"] = str(config.get("viewId") or "").strip()
        config["pageSize"] = min(max(cls._safe_int(config.get("pageSize")) or 200, 1), 500)
        config["filterFormula"] = cls._normalize_bitable_filter_config(config.get("filterFormula"))
        config["sourceSystem"] = (
            str(config.get("sourceSystem") or "feishu_bitable_pull").strip() or "feishu_bitable_pull"
        )
        config["ticketNoField"] = str(config.get("ticketNoField") or "ticketNo").strip() or "ticketNo"
        config["updatedAtField"] = str(config.get("updatedAtField") or "").strip()
        config["sortField"] = str(config.get("sortField") or "").strip()
        config["includeRecordUrl"] = cls._to_bool(config.get("includeRecordUrl"), True)
        config["createdAfter"] = str(config.get("createdAfter") or "").strip()
        config["forceSync"] = cls._to_bool(config.get("forceSync"), False)
        config["fieldMappings"] = cls._normalize_bitable_field_mappings(config.get("fieldMappings"))
        automation = config.get("automation") if isinstance(config.get("automation"), dict) else {}
        config["automation"] = {
            "autoIdentify": cls._to_bool(automation.get("autoIdentify"), True),
            "autoLogPull": cls._to_bool(automation.get("autoLogPull"), False),
            "autoAiAnalysis": cls._to_bool(automation.get("autoAiAnalysis"), False),
            "autoTranslate": cls._to_bool(automation.get("autoTranslate"), True),
        }
        return config

    @classmethod
    def _resolve_bitable_pull_created_after(cls, value: Any) -> datetime | None:
        """
        解析飞书多维表格主动拉取的创建时间下限。

        :param value: 用户指定的时间，支持 datetime、时间戳或常见日期时间文本。
        :return: 可比较的时间对象；为空或无法解析时返回 None。
        """
        if value in (None, ""):
            return None
        return cls._parse_datetime_value(value)

    @classmethod
    def _datetime_to_bitable_filter_millis(cls, value: datetime) -> int:
        """
        将 datetime 转换为飞书多维表格日期过滤使用的毫秒时间戳。

        :param value: 时间对象；无时区时按本地时间解释。
        :return: 13 位毫秒时间戳。
        """
        return int(value.timestamp() * 1000)

    @classmethod
    def _resolve_bitable_pull_create_time_field(cls, field_mappings: list[dict[str, Any]]) -> str:
        """
        从主动拉取字段映射中解析外部创建时间对应的多维字段名。

        :param field_mappings: 字段映射配置。
        :return: 多维表格创建时间字段名。
        """
        for item in field_mappings or []:
            if not isinstance(item, dict):
                continue
            if str(item.get("targetField") or "").strip() == "createTime":
                source_field = str(item.get("sourceField") or "").strip()
                if source_field:
                    return source_field
        return "创建时间"

    @classmethod
    def _condition_needs_dynamic_time_value(
        cls,
        condition: dict[str, Any],
        *,
        time_field_names: set[str],
    ) -> bool:
        """
        判断过滤条件是否需要补齐动态时间值。

        :param condition: 飞书 filter 条件。
        :param time_field_names: 可识别为时间字段的字段名集合。
        :return: 时间比较条件 value 为空时返回 True。
        """
        if not isinstance(condition, dict):
            return False
        operator = str(condition.get("operator") or "").strip()
        if operator not in {"isGreater", "isGreaterEqual", "isLess", "isLessEqual"}:
            return False
        field_name = str(condition.get("field_name") or "").strip()
        if field_name not in time_field_names:
            return False
        return condition.get("value") in (None, "", [])

    @classmethod
    def _fill_dynamic_time_filter_values(
        cls,
        filter_item: Any,
        *,
        time_field_names: set[str],
        filter_value: Any,
    ) -> Any:
        """
        递归补齐时间过滤条件中的动态 value。

        :param filter_item: 飞书 filter 条件、条件组或条件列表。
        :param time_field_names: 可识别为时间字段的字段名集合。
        :param filter_value: 时间窗口下限值。
        :return: 补齐后的 filter 条件结构。
        """
        if isinstance(filter_item, list):
            return [
                cls._fill_dynamic_time_filter_values(
                    item,
                    time_field_names=time_field_names,
                    filter_value=filter_value,
                )
                for item in filter_item
                if isinstance(item, dict)
            ]
        if not isinstance(filter_item, dict):
            return filter_item

        normalized_filter = dict(filter_item)
        if isinstance(normalized_filter.get("children"), list):
            normalized_filter["children"] = cls._fill_dynamic_time_filter_values(
                normalized_filter.get("children"),
                time_field_names=time_field_names,
                filter_value=filter_value,
            )
        if isinstance(normalized_filter.get("conditions"), list):
            normalized_filter["conditions"] = cls._fill_dynamic_time_filter_values(
                normalized_filter.get("conditions"),
                time_field_names=time_field_names,
                filter_value=filter_value,
            )
        if cls._condition_needs_dynamic_time_value(
            normalized_filter,
            time_field_names=time_field_names,
        ):
            normalized_filter["value"] = filter_value
        return normalized_filter

    @classmethod
    def _build_bitable_pull_time_filters(
        cls,
        *,
        filter_formula: Any,
        created_after: datetime | None,
        updated_at_field: str,
        create_time_field: str,
    ) -> list[dict[str, Any]]:
        """
        构建主动拉取时间窗口对应的飞书 records/search filter 列表。

        :param filter_formula: 用户配置的 filter 条件。
        :param created_after: 时间窗口下限。
        :param updated_at_field: 多维表格更新时间字段名。
        :param create_time_field: 多维表格创建时间字段名。
        :return: 一个或多个 filter 条件对象；多个对象表示需要分别请求飞书后按 record_id 合并。
        """
        parsed_filter = cls._parse_bitable_filter_config(filter_formula)
        if not created_after:
            return [parsed_filter] if parsed_filter else []

        filter_millis = cls._datetime_to_bitable_filter_millis(created_after)
        filter_value = ["ExactDate", f"{filter_millis}"]
        time_field_names = {str(updated_at_field or "").strip(), str(create_time_field or "").strip()}
        time_field_names = {item for item in time_field_names if item}

        time_conditions = []
        for field_name in (updated_at_field, create_time_field):
            normalized_field = str(field_name or "").strip()
            if not normalized_field:
                continue
            time_conditions.append(
                {
                    "field_name": normalized_field,
                    "operator": "isGreater",
                    "value": filter_value,
                }
            )

        if not parsed_filter:
            return [{"conjunction": "or", "conditions": time_conditions}]

        normalized_filter = cls._fill_dynamic_time_filter_values(
            parsed_filter,
            time_field_names=time_field_names,
            filter_value=filter_value,
        )
        if isinstance(normalized_filter.get("children"), list):
            if time_conditions:
                normalized_filter["children"].append(
                    {
                        "conjunction": "or",
                        "conditions": time_conditions,
                    }
                )
            return [normalized_filter]

        return [normalized_filter]

    @classmethod
    def _query_bitable_pull_records(
        cls,
        pull_config: dict[str, Any],
        filters: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        按一个或多个飞书 filter 查询主动拉取记录，并按 record_id 去重。

        :param pull_config: 主动拉取配置。
        :param filters: 过滤条件列表。
        :return: 去重后的飞书记录。
        """
        if not filters:
            return TicketSyncNotifyService.query_bitable_records(pull_config)
        merged_records: list[dict[str, Any]] = []
        seen_record_ids: set[str] = set()
        for filter_item in filters:
            query_config = dict(pull_config)
            query_config["filterFormula"] = filter_item
            page_records = TicketSyncNotifyService.query_bitable_records(query_config)
            for record in page_records:
                if not isinstance(record, dict):
                    continue
                record_id = str(record.get("record_id") or record.get("recordId") or "").strip()
                unique_key = record_id or cls._text_sha256(json.dumps(record, ensure_ascii=False, sort_keys=True))
                if unique_key in seen_record_ids:
                    continue
                seen_record_ids.add(unique_key)
                merged_records.append(record)
        return merged_records

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
        merged["bitableCommon"] = cls._normalize_bitable_common_config(
            merged.get("bitableCommon"),
            feishu_auth=feishu_auth,
        )
        merged["externalFieldModel"] = cls._normalize_external_field_model_config(merged.get("externalFieldModel"))
        if not isinstance(merged.get("logPullDefaults"), dict):
            merged["logPullDefaults"] = cls._default_sync_config()["logPullDefaults"]
        if not isinstance(merged.get("promptTemplates"), dict):
            merged["promptTemplates"] = cls._default_sync_config()["promptTemplates"]
        merged["statClassification"] = cls._normalize_stat_classification_config(merged.get("statClassification"))
        merged["aiClassification"] = cls._normalize_ai_classification_config(merged.get("aiClassification"))
        external_sync_bitable = (
            merged.get("externalSyncBitable")
            if isinstance(merged.get("externalSyncBitable"), dict)
            else {}
        )
        external_sync_bitable = {
            **cls._default_external_sync_bitable_config(),
            **external_sync_bitable,
        }
        external_sync_bitable["enabled"] = bool(external_sync_bitable.get("enabled"))
        external_sync_bitable["appId"] = str(external_sync_bitable.get("appId") or "").strip()
        external_sync_bitable["appSecret"] = str(external_sync_bitable.get("appSecret") or "").strip()
        external_sync_bitable["appToken"] = str(external_sync_bitable.get("appToken") or "").strip()
        external_sync_bitable["tableId"] = str(external_sync_bitable.get("tableId") or "").strip()
        external_sync_bitable["viewId"] = str(external_sync_bitable.get("viewId") or "").strip()
        merged["externalSyncBitable"] = external_sync_bitable
        merged["bitablePull"] = cls._normalize_bitable_pull_config(
            merged.get("bitablePull"),
            feishu_auth=feishu_auth,
            bitable_common=merged["bitableCommon"],
        )
        external_sync_required_fields = merged.get("externalSyncRequiredFields")
        if isinstance(external_sync_required_fields, list):
            normalized_required_fields: list[str] = []
            for item in external_sync_required_fields:
                field_name = str(item or "").strip()
                if field_name and field_name not in normalized_required_fields:
                    normalized_required_fields.append(field_name)
            merged["externalSyncRequiredFields"] = normalized_required_fields or list(
                cls.DEFAULT_EXTERNAL_SYNC_REQUIRED_FIELDS
            )
        else:
            merged["externalSyncRequiredFields"] = cls._derive_required_fields_from_external_field_model(
                merged.get("externalFieldModel")
            )
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
        group_push["autoPushStatuses"] = cls._normalize_group_push_auto_statuses(
            group_push.get("autoPushStatuses", group_push.get("auto_push_statuses")),
            fallback=default_group_push.get("autoPushStatuses"),
        )
        parsed_group_push_auto_send_after = cls._parse_datetime_value(
            group_push.get("autoSendAfterTime")
            or group_push.get("auto_send_after_time")
        )
        group_push["autoSendAfterTime"] = (
            parsed_group_push_auto_send_after.isoformat()
            if parsed_group_push_auto_send_after
            else ""
        )
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
        person_reminder["filterFormula"] = cls._normalize_bitable_filter_config(person_reminder.get("filterFormula"))
        person_reminder["personField"] = str(person_reminder.get("personField") or "").strip()
        person_reminder["timeField"] = str(person_reminder.get("timeField") or "").strip()
        person_reminder["thresholdMinutes"] = max(cls._safe_int(person_reminder.get("thresholdMinutes")) or 30, 1)
        person_reminder["messageTemplate"] = str(person_reminder.get("messageTemplate") or "").strip()
        person_reminder["rowsMarkdownTemplate"] = str(person_reminder.get("rowsMarkdownTemplate") or "").strip()
        person_reminder["maxRowsPerPerson"] = max(cls._safe_int(person_reminder.get("maxRowsPerPerson")) or 20, 1)
        person_reminder["pageSize"] = min(max(cls._safe_int(person_reminder.get("pageSize")) or 500, 1), 500)
        if not person_reminder["appId"]:
            person_reminder["appId"] = person_reminder["feishuAppId"]
        if not person_reminder["appSecret"]:
            person_reminder["appSecret"] = person_reminder["feishuAppSecret"]
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
        summary_report["appId"] = str(summary_report.get("appId") or "").strip()
        summary_report["appSecret"] = str(summary_report.get("appSecret") or "").strip()
        summary_report["timeField"] = TicketSyncNotifyService._resolve_summary_time_field(
            summary_report.get("timeField")
        )
        summary_report["appToken"] = str(summary_report.get("appToken") or "").strip()
        summary_report["tableId"] = str(summary_report.get("tableId") or "").strip()
        summary_report["viewId"] = str(summary_report.get("viewId") or "").strip()
        summary_report["filterFormula"] = cls._normalize_bitable_filter_config(summary_report.get("filterFormula"))
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
        config_value = cls._load_sync_config(db)
        config_value["externalSyncRequiredFields"] = cls._derive_required_fields_from_external_field_model(
            config_value.get("externalFieldModel")
        )
        return {
            "configKey": cls.CONFIG_KEY,
            "configValue": config_value,
        }

    @classmethod
    def preview_bitable_pull_fields_services(
        cls,
        db: Session,
        *,
        bitable_pull_override: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        预览主动拉取配置对应多维表格中的字段名列表。

        :param db: 数据库会话。
        :param bitable_pull_override: 页面当前临时配置覆盖。
        :return: 字段名预览结果。
        """
        config = cls._load_sync_config(db)
        pull_config = cls._resolve_bitable_runtime_config(
            config,
            "bitablePull",
            cls._default_bitable_pull_config(),
        )
        if isinstance(bitable_pull_override, dict):
            nested_override = (
                bitable_pull_override.get("bitablePull")
                if isinstance(bitable_pull_override.get("bitablePull"), dict)
                else bitable_pull_override
            )
            pull_config = cls._merge_non_empty_runtime_override(pull_config, nested_override)
        pull_config = cls._normalize_bitable_pull_config(
            pull_config,
            feishu_auth=config.get("feishuAuth") or cls._default_feishu_auth_config(),
            bitable_common=config.get("bitableCommon") or cls._default_bitable_common_config(),
        )
        preview_config = {
            **pull_config,
            "pageSize": 1,
            "filterFormula": "",
            "createdAfter": "",
        }
        fields_metadata: list[dict[str, Any]] = []
        try:
            fields_metadata = TicketSyncNotifyService.query_bitable_fields(preview_config)
        except Exception as exc:
            logger.warning(f"飞书多维表格字段元数据读取失败，回退样例记录推断字段: error={exc}")
        if fields_metadata:
            field_names = sorted(
                [
                    str(item.get("field_name") or item.get("name") or "").strip()
                    for item in fields_metadata
                    if str(item.get("field_name") or item.get("name") or "").strip()
                ]
            )
            return {
                "recordCount": 0,
                "fieldNames": field_names,
                "sampleRecordId": "",
                "source": "fields",
            }

        records = TicketSyncNotifyService.query_bitable_records(preview_config)
        first_record = records[0] if records else {}
        fields = first_record.get("fields") if isinstance(first_record.get("fields"), dict) else {}
        field_names = sorted([str(key).strip() for key in fields.keys() if str(key).strip()])
        return {
            "recordCount": len(records),
            "fieldNames": field_names,
            "sampleRecordId": str(first_record.get("record_id") or first_record.get("recordId") or "").strip(),
            "source": "sample_record",
        }

    @classmethod
    def get_ticket_stat_classification_options(cls, db: Session) -> dict[str, Any]:
        """
        获取工单分类统计枚举选项。
        :param db: 数据库会话
        :return: 工单分类统计枚举配置
        """
        config = cls._load_sync_config(db)
        return cls._normalize_stat_classification_config(config.get("statClassification"))

    @classmethod
    def update_sync_automation_config_services(
        cls,
        db: Session,
        config_value: dict[str, Any],
        current_user_name: str,
    ) -> CrudResponseModel:
        try:
            current_config = cls._load_sync_config(db)
            merged = cls._normalize_sync_config(config_value)
            merged = cls._merge_legacy_ai_classification_prompt_content(current_config, merged)
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
        person_config = cls._resolve_bitable_runtime_config(
            config,
            "personReminder",
            cls._default_person_reminder_config(),
        )
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
        is_all: bool = False,
        person_config_override: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        执行人维度催办通知。

        :param db: 数据库会话。
        :param trigger_source: 触发来源。
        :param user_id: 可选用户ID。
        :param email: 可选邮箱。
        :param is_all: 是否直接统计所有。
        :param person_config_override: 定时任务传入的人员催办配置覆盖项，非空字段优先于全局参数配置。
        :return: 执行结果摘要。
        """
        config = cls._load_sync_config(db)
        person_config = cls._resolve_bitable_runtime_config(
            config,
            "personReminder",
            cls._default_person_reminder_config(),
        )
        if isinstance(person_config_override, dict):
            normalized_override = {
                str(key): value
                for key, value in person_config_override.items()
                if value is not None and str(value).strip() != ""
            }
            if normalized_override:
                person_config = {**person_config, **normalized_override}
                logger.info(
                    f"人员催办使用任务级配置覆盖: trigger={trigger_source}, "
                    f"override_keys={list(normalized_override.keys())}"
                )
        return TicketSyncNotifyService.run_person_overdue_reminder(
            db,
            config=person_config,
            trigger_source=trigger_source,
            user_id=user_id,
            email=email,
            is_all=is_all,
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
        summary_config = cls._resolve_bitable_runtime_config(
            config,
            "summaryReport",
            cls._default_summary_report_config(),
        )
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
    def run_bitable_pull_services(
        cls,
        db: Session,
        *,
        trigger_source: str,
        current_user: CurrentUserModel | None = None,
        bitable_pull_override: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        执行飞书多维表格主动拉取并复用外部同步逻辑入库。

        :param db: 数据库会话。
        :param trigger_source: 触发来源，支持 manual/scheduler。
        :param current_user: 当前用户，定时任务场景可为空。
        :param bitable_pull_override: 任务级覆盖配置。
        :return: 执行结果摘要。
        """
        config = cls._load_sync_config(db)
        pull_config = cls._resolve_bitable_runtime_config(
            config,
            "bitablePull",
            cls._default_bitable_pull_config(),
        )
        if isinstance(bitable_pull_override, dict):
            nested_override = (
                bitable_pull_override.get("bitablePull")
                if isinstance(bitable_pull_override.get("bitablePull"), dict)
                else bitable_pull_override
            )
            pull_config = cls._merge_non_empty_runtime_override(pull_config, nested_override)
        pull_config = cls._normalize_bitable_pull_config(
            pull_config,
            feishu_auth=config.get("feishuAuth") or cls._default_feishu_auth_config(),
            bitable_common=config.get("bitableCommon") or cls._default_bitable_common_config(),
        )
        if not pull_config.get("enabled"):
            logger.info(f"飞书多维表格主动拉取已跳过: enabled=false, trigger={trigger_source}")
            return {"triggerSource": trigger_source, "skipped": True, "skipReason": "主动拉取未启用"}

        normalized_override = {}
        if isinstance(bitable_pull_override, dict):
            nested_override = (
                bitable_pull_override.get("bitablePull")
                if isinstance(bitable_pull_override.get("bitablePull"), dict)
                else bitable_pull_override
            )
            normalized_override = {
                str(key): value for key, value in dict(nested_override or {}).items() if value not in (None, "")
            }
        if normalized_override:
            logger.info(
                f"飞书多维表格主动拉取使用任务级覆盖: trigger={trigger_source}, "
                f"override_keys={list(normalized_override.keys())}"
            )

        required_missing: list[str] = [
            field_name
            for field_name in ("appId", "appSecret", "appToken", "tableId")
            if not str(pull_config.get(field_name) or "").strip()
        ]
        if not pull_config.get("fieldMappings"):
            required_missing.append("fieldMappings")
        if required_missing:
            return {
                "triggerSource": trigger_source,
                "skipped": True,
                "skipReason": f"主动拉取配置不完整: {', '.join(required_missing)}",
                "configErrors": required_missing,
            }

        raw_created_after = str(pull_config.get("createdAfter") or "").strip()
        created_after = cls._resolve_bitable_pull_created_after(raw_created_after)
        if raw_created_after and not created_after:
            return {
                "triggerSource": trigger_source,
                "skipped": True,
                "skipReason": "主动拉取创建时间格式错误",
                "configErrors": ["createdAfter"],
                "createdAfter": raw_created_after,
            }
        if not created_after:
            created_after = datetime.now() - timedelta(hours=1)
            pull_config["createdAfter"] = created_after.strftime("%Y-%m-%d %H:%M:%S")
        pull_filters: list[dict[str, Any]] = []
        if created_after:
            create_time_field = cls._resolve_bitable_pull_create_time_field(pull_config.get("fieldMappings") or [])
            updated_at_field = str(pull_config.get("updatedAtField") or "").strip() or "更新时间"
            try:
                pull_filters = cls._build_bitable_pull_time_filters(
                    filter_formula=pull_config.get("filterFormula"),
                    created_after=created_after,
                    updated_at_field=updated_at_field,
                    create_time_field=create_time_field,
                )
            except ValueError as exc:
                return {
                    "triggerSource": trigger_source,
                    "skipped": True,
                    "skipReason": str(exc),
                    "configErrors": ["filterFormula"],
                    "createdAfter": created_after.strftime("%Y-%m-%d %H:%M:%S"),
                }
            logger.info(
                f"飞书多维表格主动拉取云端时间过滤: trigger={trigger_source}, "
                f"created_after={created_after.strftime('%Y-%m-%d %H:%M:%S')}, "
                f"updated_at_field={updated_at_field}, create_time_field={create_time_field}"
            )
        else:
            try:
                pull_filters = cls._build_bitable_pull_time_filters(
                    filter_formula=pull_config.get("filterFormula"),
                    created_after=None,
                    updated_at_field="",
                    create_time_field="",
                )
            except ValueError as exc:
                return {
                    "triggerSource": trigger_source,
                    "skipped": True,
                    "skipReason": str(exc),
                    "configErrors": ["filterFormula"],
                    "createdAfter": "",
                }
        records = cls._query_bitable_pull_records(pull_config, pull_filters)
        queried_count = len(records)
        force_sync = cls._to_bool(pull_config.get("forceSync"), False)
        required_fields = cls._derive_required_fields_from_external_field_model(config.get("externalFieldModel"))
        summary = {
            "triggerSource": trigger_source,
            "skipped": False,
            "recordCount": len(records),
            "queriedRecordCount": queried_count,
            "createdAfter": created_after.strftime("%Y-%m-%d %H:%M:%S") if created_after else "",
            "forceSync": force_sync,
            "syncedCount": 0,
            "skippedCount": 0,
            "failedCount": 0,
            "skipReasons": {},
            "failures": [],
        }
        fallback_user = current_user or cls._build_system_current_user()
        deferred_current_user_payload = (
            cls._build_system_current_user_payload()
            if current_user is None
            else cls._normalize_current_user_payload(current_user.model_dump())
        )
        automation_override = pull_config.get("automation") if isinstance(pull_config.get("automation"), dict) else {}

        for record in records:
            sync_object = cls._build_bitable_pull_sync_object(
                record=record,
                config=pull_config,
                field_mappings=pull_config.get("fieldMappings") or [],
                required_fields=required_fields,
            )
            record_id = str(record.get("record_id") or record.get("recordId") or "").strip()
            if not sync_object:
                summary["failedCount"] += 1
                summary["failures"].append({"recordId": record_id, "reason": "record_to_sync_object_failed"})
                continue
            sync_object = sync_object.model_copy(
                update={
                    "automation": TicketSyncAutomationModel.model_validate(automation_override),
                }
            )
            existing_ticket = TicketDao.get_ticket_by_no(db, sync_object.ticket_no)
            should_skip, skip_reason = (
                (False, "")
                if force_sync
                else cls._should_skip_bitable_pull_record(
                    existing_ticket=existing_ticket,
                    sync_object=sync_object,
                )
            )
            if should_skip:
                summary["skippedCount"] += 1
                summary["skipReasons"][skip_reason] = int(summary["skipReasons"].get(skip_reason) or 0) + 1
                continue
            if force_sync and existing_ticket:
                logger.info(
                    f"飞书多维表格主动拉取强制同步记录: ticket_no={sync_object.ticket_no}, "
                    f"record_id={record_id or '-'}"
                )
            try:
                result = cls.sync_external_ticket(
                    db,
                    sync_object,
                    fallback_user,
                    "external_sync",
                    True,
                )
                if result.is_success:
                    summary["syncedCount"] += 1
                    deferred_dispatch = cls.dispatch_deferred_sync_post_process_task(
                        sync_object.model_dump(),
                        deferred_current_user_payload,
                        "external_sync",
                    )
                    if deferred_dispatch.get("mode") != cls.CELERY_DISPATCH_MODE:
                        cls.run_deferred_sync_post_process(
                            sync_object.model_dump(),
                            deferred_current_user_payload,
                            "external_sync",
                        )
                else:
                    summary["failedCount"] += 1
                    summary["failures"].append(
                        {"recordId": record_id, "ticketNo": sync_object.ticket_no, "reason": result.message}
                    )
            except Exception as exc:
                logger.exception(f"飞书多维表格主动拉取入库失败: record_id={record_id or '-'}, error={exc}")
                summary["failedCount"] += 1
                summary["failures"].append(
                    {"recordId": record_id, "ticketNo": sync_object.ticket_no, "reason": str(exc)}
                )
        return summary

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
            "group_push_processing": bool(sync_state.get("group_push_processing", False)),
            "group_push_processing_at": sync_state.get("group_push_processing_at"),
            "group_push_processing_scene": sync_state.get("group_push_processing_scene"),
            "group_push_processing_revision": sync_state.get("group_push_processing_revision"),
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
                default=cls._payload_field_value(
                    raw_payload,
                    "currentAssigneeName",
                    "current_assignee_name",
                    default="",
                ),
            )
            or ""
        ).strip()
        current_assignee = str(
            cls._payload_field_value(
                raw_payload,
                "currentAssigneeName",
                "current_assignee_name",
                default=cls._payload_field_value(
                    mapping_payload,
                    "currentAssigneeName",
                    "current_assignee_name",
                    default=ticket_assignee,
                ),
            )
            or ""
        ).strip()
        ticket_assignee_email = str(
            cls._payload_field_value(
                raw_payload,
                "ticketAssigneeEmail",
                "ticket_assignee_email",
                default=cls._payload_field_value(
                    raw_payload,
                    "currentAssigneeEmail",
                    "current_assignee_email",
                    default=cls._payload_field_value(
                        raw_payload,
                        "assigneeEmail",
                        "assignee_email",
                        default=cls._payload_field_value(
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
        current_assignee_email = str(
            cls._payload_field_value(
                raw_payload,
                "currentAssigneeEmail",
                "current_assignee_email",
                default=cls._payload_field_value(
                    mapping_payload,
                    "currentAssigneeEmail",
                    "current_assignee_email",
                    default=ticket_assignee_email,
                ),
            )
            or ""
        ).strip()
        reporter_email = str(
            cls._payload_field_value(
                raw_payload,
                "reporterEmail",
                "reporter_email",
                default=cls._payload_field_value(
                    mapping_payload,
                    "reporterEmail",
                    "reporter_email",
                    default="",
                ),
            )
            or ""
        ).strip()
        internal_owner = str(
            cls._payload_field_value(
                raw_payload,
                "internalOwner",
                "internal_owner",
                default=cls._payload_field_value(
                    raw_payload,
                    "internalOwnerName",
                    "internal_owner_name",
                    default=cls._payload_field_value(
                        mapping_payload,
                        "internalOwner",
                        "internal_owner",
                        default=cls._payload_field_value(
                            mapping_payload,
                            "internalOwnerName",
                            "internal_owner_name",
                            default="",
                        ),
                    ),
                ),
            )
            or ""
        ).strip()
        internal_owner_email = str(
            cls._payload_field_value(
                raw_payload,
                "internalOwnerEmail",
                "internal_owner_email",
                default=cls._payload_field_value(
                    mapping_payload,
                    "internalOwnerEmail",
                    "internal_owner_email",
                    default="",
                ),
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
            "ticketAssigneeEmail": ticket_assignee_email,
            "currentAssigneeName": current_assignee,
            "currentAssigneeEmail": current_assignee_email,
            "reporterEmail": reporter_email,
            "internalOwner": internal_owner,
            "internalOwnerEmail": internal_owner_email,
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
    def _resolve_sys_user_by_email(cls, db: Session, email: str):
        """
        根据邮箱匹配本地系统用户。
        :param db: 数据库会话
        :param email: 邮箱地址
        :return: 系统用户对象或 None
        """
        from module_admin.entity.do.user_do import SysUser

        normalized_email = str(email or "").strip().lower()
        if not normalized_email:
            return None
        return (
            db.query(SysUser)
            .filter(
                SysUser.status == "0",
                SysUser.del_flag == "0",
                func.lower(SysUser.email) == normalized_email,
            )
            .first()
        )

    @classmethod
    def _resolve_external_person_by_mapping_or_email(
        cls,
        db: Session,
        *,
        person_text: str,
        person_email: str,
        assignee_mappings: list[dict[str, Any]],
    ) -> tuple[int | None, str]:
        """
        外部推送人员先按显式映射表解析，再用多维表格邮箱匹配本地用户；失败时只保留名称。
        :param db: 数据库会话
        :param person_text: 外部人员名称
        :param person_email: 多维表格或入参补充邮箱
        :param assignee_mappings: 人员映射配置
        :return: (本地用户ID, 人员名称)
        """
        from module_admin.entity.do.user_do import SysUser

        source_text = str(person_text or "").strip()
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

        lookup_email = mapped_email or str(person_email or "").strip()
        if lookup_email:
            user = cls._resolve_sys_user_by_email(db, lookup_email)
            if user:
                return user.user_id, user.user_name or user.nick_name or mapped_user_name

        if matched_mapping and mapped_user_name:
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

        return None, mapped_user_name or source_text

    @classmethod
    def _resolve_remote_assignee_by_email_or_name(
        cls,
        db: Session,
        *,
        assignee_email: str,
        assignee_name: str,
    ) -> tuple[int | None, str]:
        """
        远端拉取人员只按邮箱或名称关联本地用户，禁止使用跨环境用户 ID。
        :param db: 数据库会话
        :param assignee_email: 远端处理人邮箱
        :param assignee_name: 远端处理人名称
        :return: (本地用户ID, 处理人名称)，未命中时只返回名称不返回ID
        """
        from module_admin.entity.do.user_do import SysUser

        normalized_email = str(assignee_email or "").strip().lower()
        normalized_name = str(assignee_name or "").strip()
        if normalized_email:
            user = (
                db.query(SysUser)
                .filter(
                    SysUser.status == "0",
                    SysUser.del_flag == "0",
                    func.lower(SysUser.email) == normalized_email,
                )
                .first()
            )
            if user:
                return user.user_id, user.user_name or user.nick_name or normalized_name
        if normalized_name:
            user = (
                db.query(SysUser)
                .filter(
                    SysUser.status == "0",
                    SysUser.del_flag == "0",
                    (
                        (SysUser.user_name == normalized_name)
                        | (SysUser.nick_name == normalized_name)
                        | (func.lower(SysUser.email) == normalized_name.lower())
                    ),
                )
                .first()
            )
            if user:
                return user.user_id, user.user_name or user.nick_name or normalized_name
        return None, normalized_name or normalized_email

    @classmethod
    def _extract_email_from_bitable_value(cls, value: Any) -> str:
        """
        从飞书多维表格字段值中提取邮箱，兼容人员字段、文本字段和数组字段。
        :param value: 多维表格字段值
        :return: 邮箱，未命中返回空字符串
        """
        if isinstance(value, list):
            for item in value:
                email = cls._extract_email_from_bitable_value(item)
                if email:
                    return email
            return ""
        if isinstance(value, dict):
            for key in (
                "email",
                "mail",
                "userEmail",
                "user_email",
                "workEmail",
                "work_email",
                "text",
                "value",
            ):
                email = cls._extract_email_from_bitable_value(value.get(key))
                if email:
                    return email
            return ""
        text = str(value or "").strip().lower()
        if "@" not in text:
            return ""
        matched = re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", text)
        return matched.group(0).lower() if matched else ""

    @classmethod
    def _mask_email_for_log(cls, email: str) -> str:
        """
        将邮箱脱敏后写入日志，避免排查同步链路时泄露完整邮箱。
        :param email: 原始邮箱
        :return: 脱敏后的邮箱
        """
        normalized_email = str(email or "").strip().lower()
        if "@" not in normalized_email:
            return normalized_email
        local_part, domain = normalized_email.split("@", 1)
        if len(local_part) <= 2:
            masked_local = f"{local_part[:1]}*"
        else:
            masked_local = f"{local_part[:2]}***{local_part[-1:]}"
        if "." in domain:
            domain_name, domain_suffix = domain.rsplit(".", 1)
            masked_domain = f"{domain_name[:1]}***.{domain_suffix}"
        else:
            masked_domain = f"{domain[:1]}***"
        return f"{masked_local}@{masked_domain}"

    @classmethod
    def _describe_bitable_field_value_for_log(cls, value: Any) -> dict[str, Any]:
        """
        生成多维表格字段值的日志摘要，只记录类型、结构和是否像邮箱，不记录原始字段值。
        :param value: 多维表格字段值
        :return: 字段值摘要
        """
        if value is None:
            return {"type": "missing", "empty": True}
        if isinstance(value, list):
            return {
                "type": "list",
                "empty": len(value) == 0,
                "length": len(value),
                "itemTypes": sorted({type(item).__name__ for item in value}),
            }
        if isinstance(value, dict):
            return {
                "type": "dict",
                "empty": len(value) == 0,
                "keys": list(value.keys())[:20],
            }
        text = str(value or "").strip()
        return {
            "type": type(value).__name__,
            "empty": not bool(text),
            "length": len(text),
            "hasEmailPattern": "@" in text,
        }

    @classmethod
    def _normalize_bitable_record_scalar(
        cls,
        value: Any,
        *,
        join_separator: str = ",",
    ) -> Any:
        """
        将飞书多维表格字段值归一化为适合外部同步入参的标量。

        :param value: 多维表格原始字段值。
        :param join_separator: 列表字段拼接分隔符。
        :return: 归一化后的字段值。
        """
        if value is None:
            return None
        if isinstance(value, list):
            if cls._is_bitable_rich_text_list(value):
                return "".join(
                    cls._normalize_bitable_rich_text_segment(item, join_separator=join_separator) for item in value
                )
            normalized_items: list[str] = []
            for item in value:
                normalized_item = cls._normalize_bitable_record_scalar(item, join_separator=join_separator)
                text = str(normalized_item or "").strip()
                if text and text not in normalized_items:
                    normalized_items.append(text)
            return join_separator.join(normalized_items)
        if isinstance(value, dict):
            if cls._is_bitable_rich_text_segment(value):
                return cls._normalize_bitable_rich_text_segment(value, join_separator=join_separator)
            for key in ("text", "name", "value", "email", "link", "title"):
                if key in value:
                    normalized_value = cls._normalize_bitable_record_scalar(
                        value.get(key),
                        join_separator=join_separator,
                    )
                    if normalized_value not in (None, ""):
                        return normalized_value
            return json.dumps(value, ensure_ascii=False, sort_keys=True)
        if isinstance(value, (int, float, bool)):
            return value
        text = str(value).strip()
        return text

    @classmethod
    def _is_bitable_rich_text_segment(cls, value: Any) -> bool:
        """
        判断字段值是否为飞书多维表格富文本片段。

        :param value: 多维表格字段中的单个值。
        :return: 是富文本片段返回 True，否则返回 False。
        """
        return isinstance(value, dict) and "text" in value and (
            "type" in value or "link" in value or "mention_user_id" in value
        )

    @classmethod
    def _is_bitable_rich_text_list(cls, value: Any) -> bool:
        """
        判断字段值是否为飞书多维表格富文本片段数组。

        :param value: 多维表格字段值。
        :return: 是富文本片段数组返回 True，否则返回 False。
        """
        return (
            isinstance(value, list)
            and bool(value)
            and all(cls._is_bitable_rich_text_segment(item) for item in value)
        )

    @classmethod
    def _normalize_bitable_rich_text_segment(
        cls,
        value: Any,
        *,
        join_separator: str = ",",
    ) -> str:
        """
        将飞书富文本片段归一化为原始文本，保留换行等排版字符。

        :param value: 单个富文本片段，通常包含 text/type/link 等字段。
        :param join_separator: 嵌套列表值的拼接分隔符。
        :return: 片段文本，空片段返回空字符串。
        """
        if not isinstance(value, dict):
            return str(value or "")
        raw_text = value.get("text")
        if raw_text is None:
            raw_text = value.get("name") or value.get("value") or value.get("title") or value.get("link")
        if isinstance(raw_text, str):
            return raw_text
        normalized_text = cls._normalize_bitable_record_scalar(raw_text, join_separator=join_separator)
        return str(normalized_text or "")

    @classmethod
    def _extract_bitable_person_text(
        cls,
        value: Any,
        *,
        preferred_keys: tuple[str, ...],
        join_separator: str = ",",
    ) -> str:
        """
        从飞书多维表格人员字段中提取指定文本。

        :param value: 多维表格原始字段值，支持人员对象、数组或普通文本。
        :param preferred_keys: 优先提取的字段键，例如 email/name/text。
        :param join_separator: 多个人员值的拼接分隔符。
        :return: 去重后的文本，未提取到时返回空字符串。
        """
        if value is None:
            return ""
        if isinstance(value, list):
            result_items: list[str] = []
            for item in value:
                item_text = cls._extract_bitable_person_text(
                    item,
                    preferred_keys=preferred_keys,
                    join_separator=join_separator,
                )
                if item_text and item_text not in result_items:
                    result_items.append(item_text)
            return join_separator.join(result_items)
        if isinstance(value, dict):
            for key in preferred_keys:
                if key not in value:
                    continue
                item_text = cls._extract_bitable_person_text(
                    value.get(key),
                    preferred_keys=preferred_keys,
                    join_separator=join_separator,
                )
                if item_text:
                    return item_text
            return ""
        return str(value or "").strip()

    @classmethod
    def _extract_bitable_person_email(cls, value: Any, *, join_separator: str = ",") -> str:
        """
        从飞书多维表格人员字段中提取邮箱。

        :param value: 多维表格原始字段值。
        :param join_separator: 多个邮箱的拼接分隔符。
        :return: 邮箱文本，未提取到时返回空字符串。
        """
        return cls._extract_bitable_person_text(
            value,
            preferred_keys=("email", "mail"),
            join_separator=join_separator,
        )

    @classmethod
    def _extract_bitable_person_name(cls, value: Any, *, join_separator: str = ",") -> str:
        """
        从飞书多维表格人员字段中提取人员名称。

        :param value: 多维表格原始字段值。
        :param join_separator: 多个人员名的拼接分隔符。
        :return: 人员名称文本，未提取到时返回空字符串。
        """
        return cls._extract_bitable_person_text(
            value,
            preferred_keys=("name", "text", "value", "en_name", "nickname"),
            join_separator=join_separator,
        )

    @classmethod
    def _normalize_bitable_record_datetime_text(cls, value: Any) -> str:
        """
        将多维表格时间字段归一化为接口可消费的时间文本。

        :param value: 原始时间字段值。
        :return: `YYYY-MM-DD HH:MM:SS` 格式文本，失败时返回原始文本。
        """
        parsed = cls._parse_datetime_value(value)
        if parsed:
            return parsed.strftime("%Y-%m-%d %H:%M:%S")
        return str(value or "").strip()

    @classmethod
    def _build_bitable_record_url(
        cls,
        config: dict[str, Any],
        *,
        record_id: str,
        record_url: str | None = None,
    ) -> str:
        """
        根据多维表格配置构建记录详情 URL。

        :param config: 多维配置。
        :param record_id: 记录ID。
        :param record_url: 飞书接口直接返回的记录详情 URL。
        :return: 记录详情地址。
        """
        return TicketSyncNotifyService.get_bitable_record_url(config, record_id, record_url=record_url)

    @classmethod
    def _build_bitable_pull_field_mapping_from_record(
        cls,
        fields: dict[str, Any],
        *,
        field_mappings: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        根据多维表格字段映射生成外部同步字段字典。

        :param fields: 多维表格 fields。
        :param field_mappings: 可视化或任务参数配置的字段映射。
        :return: 同步字段字典。
        """
        payload: dict[str, Any] = {}
        for mapping in field_mappings:
            source_field = str(mapping.get("sourceField") or "").strip()
            target_field = cls._normalize_bitable_pull_target_field(mapping.get("targetField"))
            if not source_field or not target_field:
                continue
            raw_value = fields.get(source_field)
            join_separator = str(mapping.get("joinSeparator") or ",").strip() or ","
            if target_field in {
                "reporterEmail",
                "currentAssigneeEmail",
                "ticketAssigneeEmail",
                "internalOwnerEmail",
            }:
                normalized_value = cls._extract_bitable_person_email(raw_value, join_separator=join_separator)
            elif target_field in {
                "reporterName",
                "currentAssigneeName",
                "ticketAssignee",
                "internalOwner",
            }:
                normalized_value = (
                    cls._extract_bitable_person_name(raw_value, join_separator=join_separator)
                    or cls._normalize_bitable_record_scalar(raw_value, join_separator=join_separator)
                )
            else:
                normalized_value = cls._normalize_bitable_record_scalar(
                    raw_value,
                    join_separator=join_separator,
                )
            if normalized_value in (None, "", []):
                default_value = mapping.get("defaultValue")
                normalized_value = default_value if default_value not in ("", None) else None
            if normalized_value in (None, "", []):
                continue
            if target_field in {"createTime"}:
                payload[target_field] = cls._normalize_bitable_record_datetime_text(normalized_value)
            else:
                payload[target_field] = normalized_value
        return payload

    @classmethod
    def _build_bitable_pull_snapshot_hash(
        cls,
        *,
        source_payload: dict[str, Any],
        field_mapping_snapshot: dict[str, str],
    ) -> str:
        """
        计算主动拉取记录快照哈希，用于判断记录内容是否变化。

        :param source_payload: 归一化后的同步负载。
        :param field_mapping_snapshot: 字段映射快照。
        :return: SHA256 哈希。
        """
        raw = {
            "payload": source_payload,
            "mapping": field_mapping_snapshot,
        }
        return hashlib.sha256(json.dumps(raw, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()

    @classmethod
    def _build_bitable_pull_sync_object(
        cls,
        *,
        record: dict[str, Any],
        config: dict[str, Any],
        field_mappings: list[dict[str, Any]],
        required_fields: list[str] | None = None,
    ) -> TicketExternalSyncUpsertModel | None:
        """
        将飞书多维表格记录转换为外部工单同步模型。

        :param record: 飞书多维表格记录。
        :param config: 主动拉取配置。
        :param field_mappings: 字段映射关系。
        :param required_fields: 外部同步必填字段列表，来源于外部字段模型。
        :return: 外部同步模型，缺少关键字段时返回 None。
        """
        fields = record.get("fields") if isinstance(record.get("fields"), dict) else {}
        record_id = str(record.get("record_id") or record.get("recordId") or "").strip()
        record_url = str(
            record.get("record_url")
            or record.get("recordUrl")
            or record.get("shared_url")
            or record.get("sharedUrl")
            or ""
        ).strip()
        payload = cls._build_bitable_pull_field_mapping_from_record(fields, field_mappings=field_mappings)
        if not payload:
            return None
        # 主动拉取不经过外部推送 controller 的兼容层，这里补齐同等字段语义，避免优先级和人员字段丢失。
        if payload.get("internalPriority") in (None, "", []) and payload.get("customerPriority") not in (None, "", []):
            payload["internalPriority"] = payload.get("customerPriority")
        if payload.get("customerPriority") in (None, "", []) and payload.get("internalPriority") not in (None, "", []):
            payload["customerPriority"] = payload.get("internalPriority")
        if payload.get("currentAssigneeName") in (None, "", []) and payload.get("ticketAssignee") not in (None, "", []):
            payload["currentAssigneeName"] = payload.get("ticketAssignee")
        if (
            payload.get("currentAssigneeEmail") in (None, "", [])
            and payload.get("ticketAssigneeEmail") not in (None, "", [])
        ):
            payload["currentAssigneeEmail"] = payload.get("ticketAssigneeEmail")
        if payload.get("ticketAssignee") in (None, "", []) and payload.get("currentAssigneeName") not in (None, "", []):
            payload["ticketAssignee"] = payload.get("currentAssigneeName")
        if (
            payload.get("ticketAssigneeEmail") in (None, "", [])
            and payload.get("currentAssigneeEmail") not in (None, "", [])
        ):
            payload["ticketAssigneeEmail"] = payload.get("currentAssigneeEmail")
        mapping_payload = dict(payload)
        top_level_alias_map = {
            "ticketVender": "projectName",
            "ticketModle": "moduleName",
            "internalOwner": "internalOwnerName",
            "internalOwnerEmail": "internalOwnerEmail",
            "reporterName": "reporterName",
            "reporterEmail": "reporterEmail",
            "currentAssigneeName": "currentAssigneeName",
            "currentAssigneeEmail": "currentAssigneeEmail",
            "ticketStatus": "status",
            "ticketStore": "ticketStore",
            "ticketPos": "ticketPos",
            "ticketSco": "ticketSco",
            "stepReason": "stepReason",
            "customerPriority": "customerPriority",
            "internalPriority": "internalPriority",
        }
        for source_key, target_key in top_level_alias_map.items():
            if source_key in payload and payload.get(source_key) not in (None, "", []):
                payload.setdefault(target_key, payload.get(source_key))
        field_mapping_snapshot = {
            cls._normalize_bitable_pull_target_field(item.get("targetField")): str(
                item.get("sourceField") or ""
            ).strip()
            for item in field_mappings
            if str(item.get("targetField") or "").strip() and str(item.get("sourceField") or "").strip()
        }
        payload["recordId"] = payload.get("recordId") or record_id
        normalized_required_fields = [
            str(item or "").strip()
            for item in required_fields or cls.DEFAULT_EXTERNAL_SYNC_REQUIRED_FIELDS
            if str(item or "").strip()
        ]
        missing_required_fields = [
            field_name
            for field_name in normalized_required_fields
            if payload.get(field_name) in (None, "", [])
        ]
        if missing_required_fields:
            logger.warning(
                f"飞书多维表格记录转换外部同步模型失败: record_id={record_id or '-'}, "
                f"missing_required_fields={missing_required_fields}"
            )
            return None
        if config.get("includeRecordUrl", True):
            payload["ticketUrl"] = payload.get("ticketUrl") or cls._build_bitable_record_url(
                config,
                record_id=record_id,
                record_url=record_url,
            )
        payload["source"] = {
            "system": str(config.get("sourceSystem") or "feishu_bitable_pull").strip() or "feishu_bitable_pull",
            "recordId": payload.get("recordId") or record_id,
            "recordUrl": payload.get("ticketUrl") or cls._build_bitable_record_url(
                config,
                record_id=record_id,
                record_url=record_url,
            ),
            "pushedAt": cls._normalize_bitable_record_datetime_text(
                fields.get(str(config.get("updatedAtField") or "").strip()) or record.get("created_time")
            )
            or None,
        }
        payload["raw_payload"] = {
            "recordId": record_id,
            "recordUrl": record_url or None,
            "fields": fields,
            "createdTime": record.get("created_time"),
            "lastModifiedTime": record.get("last_modified_time"),
        }
        extra_data = payload.get("extraData") if isinstance(payload.get("extraData"), dict) else {}
        extra_data = dict(extra_data or {})
        external_field_mapping = (
            dict(extra_data.get("external_field_mapping"))
            if isinstance(extra_data.get("external_field_mapping"), dict)
            else {}
        )
        external_field_mapping.update(mapping_payload)
        external_field_mapping["bitableRecordId"] = record_id
        if record_url:
            external_field_mapping["bitableRecordUrl"] = record_url
        extra_data["external_field_mapping"] = external_field_mapping
        extra_data["bitable_pull"] = {
            "recordId": record_id,
            "snapshotHash": cls._build_bitable_pull_snapshot_hash(
                source_payload=payload,
                field_mapping_snapshot=field_mapping_snapshot,
            ),
            "fieldMappings": field_mapping_snapshot,
            "sourceSystem": payload["source"]["system"],
            "pulledAt": cls._now_iso(),
        }
        payload["extraData"] = extra_data
        try:
            return TicketExternalSyncUpsertModel.model_validate(payload)
        except Exception as exc:
            logger.warning(f"飞书多维表格记录转换外部同步模型失败: record_id={record_id or '-'}, error={exc}")
            return None

    @classmethod
    def _should_skip_bitable_pull_record(
        cls,
        *,
        existing_ticket: Ticket | None,
        sync_object: TicketExternalSyncUpsertModel,
    ) -> tuple[bool, str]:
        """
        判断主动拉取记录是否因快照未变化而跳过入库。

        :param existing_ticket: 已存在工单。
        :param sync_object: 当前转换后的同步对象。
        :return: (是否跳过, 原因)。
        """
        if not existing_ticket or not isinstance(existing_ticket.extra_data, dict):
            return False, ""
        bitable_pull_meta = existing_ticket.extra_data.get("bitable_pull")
        if not isinstance(bitable_pull_meta, dict):
            return False, ""
        current_pull_meta = (
            sync_object.extra_data.get("bitable_pull") if isinstance(sync_object.extra_data, dict) else {}
        )
        existing_hash = str(bitable_pull_meta.get("snapshotHash") or "").strip()
        current_hash = str((current_pull_meta or {}).get("snapshotHash") or "").strip()
        existing_record_id = str(bitable_pull_meta.get("recordId") or "").strip()
        current_record_id = str((current_pull_meta or {}).get("recordId") or "").strip()
        if existing_hash and current_hash and existing_hash == current_hash and existing_record_id == current_record_id:
            return True, "snapshot_not_changed"
        return False, ""

    @classmethod
    def _query_external_sync_bitable_record_fields(
        cls,
        config: dict[str, Any],
        *,
        record_id: str,
    ) -> dict[str, Any]:
        """
        根据外部推送 recordId 查询飞书多维表格记录字段。
        :param config: 同步配置
        :param record_id: 飞书多维表格记录 ID
        :return: 记录 fields 字典，查询失败返回空字典
        """
        bitable_config = cls._resolve_bitable_runtime_config(
            config,
            "externalSyncBitable",
            cls._default_external_sync_bitable_config(),
            keep_filter_formula=False,
        )
        if not bool(bitable_config.get("enabled")):
            logger.info("外部同步多维表格邮箱查询跳过: reason=externalSyncBitable 未启用")
            return {}
        app_id, app_secret = TicketSyncNotifyService._resolve_feishu_auth(bitable_config)
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
            token = TicketSyncNotifyService._get_tenant_access_token(app_id, app_secret)
            url = (
                f"{TicketSyncNotifyService.FEISHU_BASE_URL}/bitable/v1/apps/"
                f"{app_token}/tables/{table_id}/records/{normalized_record_id}"
            )
            response_data = TicketSyncNotifyService._request_feishu_json(
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
    def _enrich_external_person_emails_from_bitable(
        cls,
        config: dict[str, Any],
        sync_object: TicketExternalSyncUpsertModel,
        existing_ticket: Ticket | None = None,
    ) -> TicketExternalSyncUpsertModel:
        """
        外部推送时按 recordId 查询多维表格人员邮箱，并写入 external_field_mapping 快照供落库和群 @ 复用。
        :param config: 同步配置
        :param sync_object: 外部同步入库模型
        :param existing_ticket: 已存在的工单，用于判断同一 recordId 是否已成功补齐过邮箱
        :return: 补齐邮箱快照后的同步模型
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
        existing_meta = cls._build_meta(existing_extra) if existing_extra else {}
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
        fields = cls._query_external_sync_bitable_record_fields(config, record_id=record_id)
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
            email = cls._extract_email_from_bitable_value(field_value)
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
                    "email": cls._mask_email_for_log(email),
                    "fieldSummary": cls._describe_bitable_field_value_for_log(field_value),
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
        external_mapping["bitableEmailSyncedAt"] = cls._now_iso()
        external_mapping["bitableEmailSyncStatus"] = "success"
        extra_data["external_field_mapping"] = external_mapping
        extra_data["_bitable_email_sync"] = {
            "status": "success",
            "recordId": record_id,
            "emailKeys": list(email_map.keys()),
            "syncedAt": external_mapping["bitableEmailSyncedAt"],
        }
        masked_emails = {key: cls._mask_email_for_log(value) for key, value in email_map.items()}
        logger.info(
            f"外部同步多维表格邮箱补齐结束: ticket_no={ticket_no or '-'}, "
            f"record_id={record_id}, updated=true, email_keys={list(email_map.keys())}, "
            f"masked_emails={masked_emails}"
        )
        return sync_object.model_copy(update={"extra_data": extra_data})

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

        log_pull_payload = (
            dict(sync_object.log_pull_config or {})
            if isinstance(sync_object.log_pull_config, dict)
            else {}
        )
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
        first_line_assignee_id = cls._safe_int(detected.get("firstLineAssigneeId"))
        first_line_assignee_name = str(detected.get("firstLineAssigneeName") or "").strip()
        internal_owner_id = cls._safe_int(detected.get("internalOwnerId"))
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
        logger.info(
            f"工单自动分类开始: ticket_id={ticket.ticket_id}, ticket_no={ticket.ticket_no}, "
            f"source_type={source_type}, source_ref={source_ref}, strategy={classification_strategy}, "
            f"force_reclassify={bool(force_reclassify)}, existing_category={existing_category or '-'}, "
            f"title_len={len(str(title or '').strip())}, description_len={len(str(description or '').strip())}"
        )
        if existing_category and not force_reclassify:
            logger.info(
                f"工单自动分类跳过: ticket_id={ticket.ticket_id}, ticket_no={ticket.ticket_no}, "
                f"reason=工单已归类且未开启强制重归类, category={existing_category}"
            )
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
            logger.info(
                f"工单自动分类开始正则匹配: ticket_id={ticket.ticket_id}, ticket_no={ticket.ticket_no}, "
                f"rule_count={len(regex_rules or [])}, title_len={len(str(title or '').strip())}, "
                f"description_len={len(str(description or '').strip())}"
            )
            normalized_category, regex_meta = cls._classify_ticket_category_by_regex(
                title=title,
                description=description,
                regex_rules=regex_rules,
            )
            category_meta = {**category_meta, **regex_meta}
        if not normalized_category:
            if prefer_no_ai_fallback:
                logger.info(
                    f"工单自动分类跳过二次AI: ticket_id={ticket.ticket_id}, ticket_no={ticket.ticket_no}, "
                    f"reason=统一提取未返回分类且配置禁止二次AI调用"
                )
                return ticket, {
                    "skipped": True,
                    "skipReason": "统一提取未返回分类，已按配置跳过二次分类AI调用",
                    "categoryName": existing_category,
                    "meta": category_meta,
                }
            config = cls._load_sync_config(db)
            ai_config = config.get("aiClassification") if isinstance(config.get("aiClassification"), dict) else {}
            stat_options = (
                config.get("statClassification") if isinstance(config.get("statClassification"), dict) else {}
            )
            legacy_prompt_content = cls._resolve_legacy_ai_classification_prompt_content(
                ai_config,
                prompt_code=ai_prompt_code or str(ai_config.get("promptCode") or "").strip() or None,
            )
            logger.info(
                f"工单AI分类统计调用轻量AI: ticket_id={ticket.ticket_id}, ticket_no={ticket.ticket_no}, "
                f"source_type={source_type}, source_ref={source_ref}, strategy={normalized_strategy}, "
                f"provider_code={category_meta.get('provider_code') or '-'}, "
                f"prompt_code={category_meta.get('prompt_code') or '-'}"
            )
            result_payload, category_meta = TicketLightAiService.classify_ticket_statistics(
                db,
                title=title,
                description=description,
                comments=cls._build_ticket_comment_context(db, ticket_id=ticket.ticket_id),
                current_fields=cls._build_ticket_stat_current_fields(ticket),
                stat_options=stat_options,
                override_provider_code=str(ai_config.get("providerCode") or "").strip() or None,
                override_prompt_code=ai_prompt_code or str(ai_config.get("promptCode") or "").strip() or None,
                override_prompt_content=legacy_prompt_content,
                source_type=source_type,
                source_id=ticket.ticket_id,
                source_ref=source_ref,
                current_user_name=current_user_name,
            )
            normalized_category = str(
                result_payload.get("categoryName") or result_payload.get("issueTypeName") or ""
            ).strip()
        if not normalized_category:
            logger.info(
                f"工单自动分类未返回结果: ticket_id={ticket.ticket_id}, ticket_no={ticket.ticket_no}, "
                f"reason={str(category_meta.get('error') or '未返回可识别分类').strip()}"
            )
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
            logger.info(
                f"工单自动分类完成: ticket_id={ticket.ticket_id}, ticket_no={ticket.ticket_no}, "
                f"category={normalized_category}, strategy={category_meta.get('strategy') or normalized_strategy}, "
                f"force_reclassify={bool(force_reclassify)}"
            )
            return ticket, {
                "skipped": False,
                "categoryName": normalized_category,
                "meta": category_meta,
            }
        except Exception:
            db.rollback()
            raise

    @classmethod
    def _merge_legacy_ai_classification_prompt_content(
        cls,
        current_config: dict[str, Any],
        next_config: dict[str, Any],
    ) -> dict[str, Any]:
        """
        保存同步配置时保留旧版内联 AI 分类提示词正文。

        新版页面只保存 Provider/Prompt 编码，但旧环境可能依赖 `aiClassification.promptContent`
        作为默认模板为空时的兜底。当前端提交空正文时保留旧值，避免保存其他配置导致分类 AI 行为突变。
        :param current_config: 当前已生效配置。
        :param next_config: 本次待保存配置。
        :return: 合并后的配置。
        """
        current_ai_config = (
            current_config.get("aiClassification")
            if isinstance(current_config.get("aiClassification"), dict)
            else {}
        )
        next_ai_config = (
            next_config.get("aiClassification")
            if isinstance(next_config.get("aiClassification"), dict)
            else {}
        )
        legacy_prompt_content = str(current_ai_config.get("promptContent") or "").strip()
        next_prompt_content = str(next_ai_config.get("promptContent") or "").strip()
        if legacy_prompt_content and not next_prompt_content:
            next_ai_config["promptContent"] = legacy_prompt_content
            next_config["aiClassification"] = next_ai_config
        return next_config

    @classmethod
    def _run_auto_ticket_ai_classification(
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
        ai_prompt_code: str | None = None,
        enabled_by_scene: bool = True,
    ) -> tuple[Ticket, dict[str, Any]]:
        """
        执行工单 AI 分类统计并回填统计字段。

        :param db: 数据库会话。
        :param ticket: 工单对象。
        :param title: 工单标题。
        :param description: 工单描述。
        :param current_user_name: 当前用户名。
        :param source_type: 分类来源类型。
        :param source_ref: 分类来源引用。
        :param force_reclassify: 是否强制重新分类。
        :param ai_prompt_code: 可选覆盖提示词编码。
        :param enabled_by_scene: 当前场景是否启用。
        :return: (最新工单对象, 分类摘要)。
        """
        logger.info(
            f"工单AI分类统计流程开始: ticket_id={ticket.ticket_id}, ticket_no={ticket.ticket_no}, "
            f"source_type={source_type}, source_ref={source_ref}, enabled_by_scene={enabled_by_scene}, "
            f"force_reclassify={bool(force_reclassify)}, ai_prompt_code={ai_prompt_code or '-'}"
        )
        if not enabled_by_scene and not force_reclassify:
            logger.info(
                f"工单AI分类统计跳过: ticket_id={ticket.ticket_id}, ticket_no={ticket.ticket_no}, "
                f"reason=当前场景入参未启用且未强制重归类, source_type={source_type}"
            )
            return ticket, {"skipped": True, "skipReason": "当前场景未启用AI分类统计"}
        config = cls._load_sync_config(db)
        if not cls._should_run_ai_classification_for_scene(config, source_type) and not force_reclassify:
            logger.info(
                f"工单AI分类统计跳过: ticket_id={ticket.ticket_id}, ticket_no={ticket.ticket_no}, "
                f"reason=同步配置未开启当前场景AI分类统计, source_type={source_type}"
            )
            return ticket, {"skipped": True, "skipReason": "当前场景未开启AI分类统计"}
        title_text = str(title or "").strip()
        description_text = str(description or "").strip()
        comment_context = cls._build_ticket_comment_context(db, ticket_id=ticket.ticket_id)
        logger.info(
            f"工单AI分类统计上下文: ticket_id={ticket.ticket_id}, ticket_no={ticket.ticket_no}, "
            f"title_len={len(title_text)}, description_len={len(description_text)}, "
            f"comment_count={len(comment_context)}"
        )
        if not force_reclassify and cls._has_successful_ai_classification(
            ticket,
            title=title_text,
            description=description_text,
            comments=comment_context,
        ):
            logger.info(
                f"工单AI分类统计跳过: ticket_id={ticket.ticket_id}, ticket_no={ticket.ticket_no}, "
                f"reason=已有相同标题描述评论的成功AI分类结果"
            )
            return ticket, {"skipped": True, "skipReason": "已有相同文本的成功AI分类结果"}

        ai_config = config.get("aiClassification") if isinstance(config.get("aiClassification"), dict) else {}
        stat_options = config.get("statClassification") if isinstance(config.get("statClassification"), dict) else {}
        logger.info(
            f"工单AI分类统计调用轻量AI: ticket_id={ticket.ticket_id}, ticket_no={ticket.ticket_no}, "
            f"provider_code={str(ai_config.get('providerCode') or '').strip() or '-'}, "
            f"prompt_code={ai_prompt_code or str(ai_config.get('promptCode') or '').strip() or '-'}, "
            f"has_prompt_content={bool(str(ai_config.get('promptContent') or '').strip())}"
        )
        legacy_prompt_content = cls._resolve_legacy_ai_classification_prompt_content(
            ai_config,
            prompt_code=ai_prompt_code or str(ai_config.get("promptCode") or "").strip() or None,
        )
        result_payload, meta = TicketLightAiService.classify_ticket_statistics(
            db,
            title=title_text,
            description=description_text,
            comments=comment_context,
            current_fields=cls._build_ticket_stat_current_fields(ticket),
            stat_options=stat_options,
            override_provider_code=str(ai_config.get("providerCode") or "").strip() or None,
            override_prompt_code=ai_prompt_code or str(ai_config.get("promptCode") or "").strip() or None,
            override_prompt_content=legacy_prompt_content,
            source_type=source_type,
            source_id=ticket.ticket_id,
            source_ref=source_ref,
            current_user_name=current_user_name,
        )
        if not result_payload:
            logger.info(
                f"工单AI分类统计无结果: ticket_id={ticket.ticket_id}, ticket_no={ticket.ticket_no}, "
                f"reason={str(meta.get('error') or meta.get('skipReason') or 'AI未返回分类统计结果').strip()}"
            )
            return ticket, {
                "skipped": True,
                "skipReason": str(meta.get("error") or meta.get("skipReason") or "AI未返回分类统计结果").strip(),
                "meta": meta,
            }

        source_hash = cls._build_ai_classification_source_hash(
            title=title_text,
            description=description_text,
            comments=comment_context,
        )
        next_extra_data = dict(ticket.extra_data or {}) if isinstance(ticket.extra_data, dict) else {}
        next_extra_data["ai_classification"] = {
            "success": True,
            "sourceType": source_type,
            "sourceRef": source_ref,
            "sourceHash": source_hash,
            "commentCount": len(comment_context),
            "providerCode": meta.get("provider_code"),
            "promptCode": meta.get("prompt_code"),
            "classifiedAt": cls._now_iso(),
            "forceReclassify": bool(force_reclassify),
            "confidence": result_payload.get("confidence"),
            "reason": result_payload.get("reason"),
            "needRnd": result_payload.get("needRnd"),
            "needMonitor": result_payload.get("needMonitor"),
            "needKb": result_payload.get("needKb"),
            "rawPayload": result_payload.get("rawPayload"),
        }
        update_data: dict[str, Any] = {
            "extra_data": next_extra_data,
            "update_by": str(current_user_name or "").strip() or "system",
            "update_time": datetime.now(),
        }
        field_map = {
            "categoryName": "category_name",
            "issueTypeId": "issue_type_id",
            "issueTypeName": "issue_type_name",
            "moduleName": "module_name",
            "severity": "severity",
            "rootCauseType": "root_cause_type",
            "solutionType": "solution_type",
            "resolutionCode": "resolution_code",
            "resolutionName": "resolution_name",
            "rootCause": "root_cause",
            "solution": "solution",
        }
        for result_key, db_field in field_map.items():
            value = result_payload.get(result_key)
            if value not in (None, ""):
                update_data[db_field] = value
        if result_payload.get("isProblem") is not None:
            update_data["is_problem"] = bool(result_payload.get("isProblem"))

        TicketDao.update_ticket(db, ticket.ticket_id, update_data)
        db.commit()
        ticket = TicketDao.get_ticket_by_id(db, ticket.ticket_id) or ticket
        logger.info(
            f"工单AI分类统计回填完成: ticket_id={ticket.ticket_id}, ticket_no={ticket.ticket_no}, "
            f"category={result_payload.get('categoryName') or '-'}, "
            f"issue_type={result_payload.get('issueTypeName') or '-'}, "
            f"is_problem={result_payload.get('isProblem')}, "
            f"root_cause_type={result_payload.get('rootCauseType') or '-'}, "
            f"solution_type={result_payload.get('solutionType') or '-'}"
        )
        return ticket, {
            "skipped": False,
            "categoryName": result_payload.get("categoryName"),
            "issueTypeName": result_payload.get("issueTypeName"),
            "isProblem": result_payload.get("isProblem"),
            "rootCauseType": result_payload.get("rootCauseType"),
            "solutionType": result_payload.get("solutionType"),
            "resolutionName": result_payload.get("resolutionName"),
            "meta": meta,
        }

    @classmethod
    def _resolve_legacy_ai_classification_prompt_content(
        cls,
        ai_config: dict[str, Any],
        *,
        prompt_code: str | None,
    ) -> str | None:
        """
        解析旧版同步配置内联提示词正文，仅作为历史兼容兜底。

        新版配置统一在 AI 提示词模板中维护正文，同步配置只保存模板编码。为避免旧环境中
        `ticket_stat_classify_default` 模板为空导致现有业务异常，历史 `promptContent` 仍在模板缺失或为空时可参与兜底。
        :param ai_config: 同步配置中的 AI 分类配置。
        :param prompt_code: 本次选择的提示词编码。
        :return: 需要覆盖的提示词正文；不需要覆盖时返回 None。
        """
        legacy_content = str((ai_config or {}).get("promptContent") or "").strip()
        if not legacy_content:
            return None
        normalized_prompt_code = str(prompt_code or "").strip()
        if normalized_prompt_code and normalized_prompt_code != "ticket_stat_classify_default":
            return None
        return legacy_content

    @classmethod
    def _build_ticket_stat_current_fields(cls, ticket: Ticket) -> dict[str, Any]:
        """
        构建 AI 分类统计需要的当前工单字段。

        :param ticket: 工单对象。
        :return: 当前字段字典。
        """
        return {
            "ticketNo": ticket.ticket_no,
            "categoryName": ticket.category_name,
            "issueTypeId": ticket.issue_type_id,
            "issueTypeName": ticket.issue_type_name,
            "moduleName": ticket.module_name,
            "status": ticket.status,
            "isProblem": ticket.is_problem,
            "rootCauseType": ticket.root_cause_type,
            "solutionType": ticket.solution_type,
            "resolutionCode": ticket.resolution_code,
            "resolutionName": ticket.resolution_name,
            "severity": ticket.severity,
            "rootCause": ticket.root_cause,
            "solution": ticket.solution,
        }

    @classmethod
    def _build_ticket_comment_context(cls, db: Session, *, ticket_id: int, limit: int = 30) -> list[str]:
        """
        构建 AI 分类统计使用的评论上下文。

        :param db: 数据库会话。
        :param ticket_id: 工单ID。
        :param limit: 最多取最近评论数量。
        :return: 按时间升序排列的评论文本。
        """
        rows = (
            db.query(TicketComment)
            .filter(TicketComment.ticket_id == ticket_id)
            .order_by(TicketComment.create_time.desc(), TicketComment.id.desc())
            .limit(max(int(limit or 30), 1))
            .all()
        )
        comment_lines: list[str] = []
        for comment in reversed(rows):
            content = str(getattr(comment, "content", "") or "").strip()
            if not content:
                continue
            created_at = getattr(comment, "create_time", None)
            created_text = created_at.strftime("%Y-%m-%d %H:%M:%S") if isinstance(created_at, datetime) else ""
            user_name = str(getattr(comment, "user_name", "") or "").strip() or "未知人员"
            prefix_parts = [item for item in (created_text, user_name) if item]
            prefix = " ".join(prefix_parts)
            comment_lines.append(f"{prefix}：{content}" if prefix else content)
        return comment_lines

    @classmethod
    def _build_ai_classification_source_hash(
        cls,
        *,
        title: str,
        description: str,
        comments: list[str] | None = None,
    ) -> str:
        """
        构建 AI 分类防重用来源摘要。

        :param title: 工单标题。
        :param description: 工单描述。
        :param comments: 工单评论上下文。
        :return: 来源内容 SHA256。
        """
        comment_text = "\n".join(str(item or "").strip() for item in comments or [] if str(item or "").strip())
        return cls._text_sha256("\n\n".join([str(title or "").strip(), str(description or "").strip(), comment_text]))

    @classmethod
    def _has_successful_ai_classification(
        cls,
        ticket: Ticket,
        *,
        title: str,
        description: str,
        comments: list[str] | None = None,
    ) -> bool:
        """
        判断工单是否已经基于相同文本完成过 AI 分类统计。

        :param ticket: 工单对象。
        :param title: 当前标题。
        :param description: 当前描述。
        :param comments: 当前评论上下文。
        :return: 已成功分类且文本未变化时返回 True。
        """
        extra_data = ticket.extra_data if isinstance(ticket.extra_data, dict) else {}
        ai_meta = extra_data.get("ai_classification") if isinstance(extra_data.get("ai_classification"), dict) else {}
        source_hash = cls._build_ai_classification_source_hash(
            title=title,
            description=description,
            comments=comments,
        )
        return bool(ai_meta.get("success")) and str(ai_meta.get("sourceHash") or "") == source_hash

    @classmethod
    def _should_run_ai_classification_for_scene(cls, config: dict[str, Any], scene: str) -> bool:
        """
        判断指定入库场景是否启用 AI 分类统计。

        :param config: 同步自动化配置。
        :param scene: 场景 external_sync/remote_pull/manual_create/batch_reclassify。
        :return: 是否启用。
        """
        ai_config = config.get("aiClassification") if isinstance(config.get("aiClassification"), dict) else {}
        if not bool(ai_config.get("enabled")):
            return False
        normalized_scene = str(scene or "").strip()
        if normalized_scene == "external_sync" or normalized_scene.startswith("external_sync"):
            return bool(ai_config.get("runOnExternalSync"))
        if normalized_scene == "remote_pull" or normalized_scene.startswith("remote_pull"):
            return bool(ai_config.get("runOnRemotePull"))
        if normalized_scene == "manual_create" or normalized_scene.startswith("ticket_manual_create"):
            return bool(ai_config.get("runOnManualCreate"))
        if normalized_scene == "batch_reclassify" or normalized_scene.startswith("ticket_batch_reclassify"):
            return True
        return False

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
        apply_external_mappings: bool = True,
    ) -> dict[str, Any]:
        """
        解析同步入库所需的内部字段。
        :param db: 数据库会话
        :param sync_object: 同步入库模型
        :param config: 同步配置
        :param apply_external_mappings: 是否应用外部字段映射；仅第三方直推允许，远端拉取使用远端内部字段
        :return: 标准化后的内部字段候选值
        """
        text = cls._collect_text(sync_object).lower()
        external_fields = cls._extract_external_mapping_fields(sync_object)
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
            module = cls._resolve_module_by_ticket_modle(
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
            module = cls._resolve_module_by_ticket_modle(
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
            vendor_id, vendor_name = cls._resolve_vendor_by_ticket_vender(
                ticket_vender=ticket_vender,
                vendor_mappings=config.get("vendorMappings") or [],
            )
        else:
            vendor_id, vendor_name = None, ""
        if apply_external_mappings and not vendor_id:
            vendor_id = cls._resolve_vendor_by_project(db, project_id=getattr(project, "project_id", None))
        if not vendor_id:
            vendor_id = cls._safe_int(log_pull_hints.get("vendorId") or log_pull_hints.get("vendor_id"))
        if not vendor_id:
            vendor_id = cls._safe_int((sync_object.log_pull_config or {}).get("vendorId"))
        if vendor_id and not vendor_name:
            vendor_name = (
                ticket_vender
                or project_name_by_vendor
                or str(getattr(project, "project_name", "") or "").strip()
            )
        if apply_external_mappings:
            store_id, store_name = cls._resolve_store_by_external_value(
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
            status_code = cls._resolve_status_by_external_value(
                status_text=ticket_status or str(sync_object.status or "").strip(),
                status_mappings=config.get("statusMappings") or [],
            )
            assignee_id, assignee_name = cls._resolve_external_person_by_mapping_or_email(
                db,
                person_text=current_assignee or str(sync_object.current_assignee_name or "").strip(),
                person_email=current_assignee_email,
                assignee_mappings=config.get("assigneeMappings") or [],
            )
            first_line_assignee_id, first_line_assignee_name = cls._resolve_external_person_by_mapping_or_email(
                db,
                person_text=reporter_person,
                person_email=reporter_email,
                assignee_mappings=config.get("assigneeMappings") or [],
            )
            internal_owner_id, internal_owner_name = cls._resolve_external_person_by_mapping_or_email(
                db,
                person_text=internal_owner,
                person_email=internal_owner_email,
                assignee_mappings=config.get("assigneeMappings") or [],
            )
        else:
            # 远端拉取不复用公网项目/模块/用户 ID，但状态与人员文本仍允许按内网本地配置映射。
            status_code = cls._resolve_status_by_external_value(
                status_text=ticket_status or str(sync_object.status or "").strip(),
                status_mappings=config.get("statusMappings") or [],
            )
            assignee_email = str(
                current_assignee_email or cls._payload_field_value(
                    raw_payload,
                    "currentAssigneeEmail",
                    "current_assignee_email",
                    default=cls._payload_field_value(
                        raw_payload,
                        "ticketAssigneeEmail",
                        "ticket_assignee_email",
                        default=cls._payload_field_value(
                            raw_payload,
                            "assigneeEmail",
                            "assignee_email",
                            default=cls._payload_field_value(
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
            assignee_id, assignee_name = cls._resolve_external_person_by_mapping_or_email(
                db,
                person_text=assignee_name,
                person_email=assignee_email,
                assignee_mappings=config.get("assigneeMappings") or [],
            )
            first_line_assignee_id, first_line_assignee_name = cls._resolve_external_person_by_mapping_or_email(
                db,
                person_text=reporter_person,
                person_email=reporter_email,
                assignee_mappings=config.get("assigneeMappings") or [],
            )
            internal_owner_id, internal_owner_name = cls._resolve_external_person_by_mapping_or_email(
                db,
                person_text=internal_owner,
                person_email=internal_owner_email,
                assignee_mappings=config.get("assigneeMappings") or [],
            )
        if apply_external_mappings and not assignee_id:
            assignee_id = cls._safe_int(sync_object.current_assignee_id)
        if not assignee_name:
            assignee_name = str(sync_object.current_assignee_name or "").strip()
        if apply_external_mappings and not first_line_assignee_id:
            first_line_assignee_id = cls._safe_int(getattr(sync_object, "first_line_assignee_id", None))
        if not first_line_assignee_name:
            first_line_assignee_name = str(
                getattr(sync_object, "first_line_assignee_name", "")
                or getattr(sync_object, "reporter_name", "")
                or ""
            ).strip()
        if apply_external_mappings and not internal_owner_id:
            internal_owner_id = cls._safe_int(getattr(sync_object, "internal_owner_id", None))
        if not internal_owner_name:
            internal_owner_name = str(getattr(sync_object, "internal_owner_name", "") or "").strip()
        version_key = (
            str(sync_object.version_key or "").strip()
            or _extract_ticket_version_key(sync_object.extra_data)
            or str(cls._extract_pattern(text, config.get("versionPatterns")) or "").strip()
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
            "posNo": cls._safe_int(ticket_pos)
            or cls._safe_int(log_pull_hints.get("posNo"))
            or cls._safe_int(log_pull_hints.get("pos_no"))
            or cls._safe_int((sync_object.log_pull_config or {}).get("posNo"))
            or cls._safe_int((sync_object.log_pull_config or {}).get("pos_id"))
            or cls._safe_int((sync_object.log_pull_config or {}).get("posId"))
            or cls._safe_int(cls._extract_pattern(text, config.get("posPatterns"))),
            "scoNo": cls._safe_int(ticket_sco)
            or cls._safe_int(log_pull_hints.get("scoNo"))
            or cls._safe_int(log_pull_hints.get("sco_no"))
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
        """
        更新消费者同步状态。
        :param meta: 同步元数据
        :param consumer: 消费者标识
        :param revision: 本次交付版本
        :param batch_id: 批次ID
        :param status: 交付状态，pulled 表示已返回但待回执，只有 delivered/success 才确认交付
        :param message: 回执说明
        :param detail: 回执明细
        :return: 更新后的同步元数据
        """
        sync_state = meta.get("sync_state") if isinstance(meta.get("sync_state"), dict) else {}
        consumers = sync_state.get("consumers") if isinstance(sync_state.get("consumers"), dict) else {}
        previous_consumer_state = consumers.get(consumer) if isinstance(consumers.get(consumer), dict) else {}
        normalized_status = str(status or "").strip().lower() or "delivered"
        delivered_revision = int(previous_consumer_state.get("delivered_revision") or 0)
        if normalized_status in {"delivered", "success", "succeeded"}:
            delivered_revision = max(delivered_revision, int(revision or 0))
        elif int(revision or 0) > 0 and delivered_revision == int(revision or 0):
            delivered_revision = max(int(revision or 0) - 1, 0)
        consumers[consumer] = {
            "status": status,
            "delivered_revision": delivered_revision,
            "last_revision": int(revision or 0),
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
        sync_scene: str = "external_sync",
    ) -> tuple[dict[str, Any], dict[str, Any], int]:
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
        is_remote_pull = sync_scene == "remote_pull"
        resolved_assignee_id = cls._safe_int((detected or {}).get("assigneeId"))
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
            "root_cause": sync_object.root_cause or (ticket.root_cause if ticket else None),
            "solution": sync_object.solution or (ticket.solution if ticket else None),
            "tags": sync_object.tags or (ticket.tags if ticket else None),
            "ticket_url": resolved_ticket_url or None,
            "update_by": _user_name(current_user),
            "update_time": now,
        }
        project_id = cls._safe_int((detected or {}).get("projectId")) or (
            None if is_remote_pull else sync_object.project_id
        )
        module_id = cls._safe_int((detected or {}).get("moduleId")) or (
            None if is_remote_pull else sync_object.module_id
        )
        raw_project_name = str(
            sync_object.project_name
            or sync_object.merchant_name
            or str((detected or {}).get("projectName") or "").strip()
            or ""
        ).strip()
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
        incoming_project_name = (
            str((detected or {}).get("projectName") or "").strip()
            or str(sync_object.project_name or "").strip()
            or str(sync_object.merchant_name or "").strip()
        )
        if incoming_project_name and not project_id and not is_remote_pull:
            payload["project_id"] = None
            payload["merchant_name"] = incoming_project_name
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
        elif ticket:
            payload["module_id"] = ticket.module_id
            payload["module_name"] = ticket.module_name
        else:
            payload["module_name"] = (
                sync_object.module_name
                or str((detected or {}).get("moduleName") or "").strip()
                or ""
            )
        module_name_fallback = (
            str((detected or {}).get("moduleName") or "").strip()
            or str(sync_object.module_name or "").strip()
            or (str(ticket.module_name or "").strip() if ticket else "")
        )
        incoming_module_name = (
            str((detected or {}).get("moduleName") or "").strip()
            or str(sync_object.module_name or "").strip()
        )
        if incoming_module_name and not module_id and not is_remote_pull:
            payload["module_id"] = None
            payload["module_name"] = incoming_module_name
        if module_name_fallback and not str(payload.get("module_name") or "").strip():
            payload["module_name"] = module_name_fallback
        if module_name_fallback:
            meta_source = meta.get("source") if isinstance(meta.get("source"), dict) else {}
            meta_source["moduleName"] = module_name_fallback
            meta["source"] = meta_source
        payload = cls._merge_external_text_fields(payload, detected or {}, sync_object)
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
        vendor_id_hint = cls._safe_int((detected or {}).get("vendorId"))
        store_id_hint = str((detected or {}).get("storeId") or "").strip()
        pos_no_hint = cls._safe_int((detected or {}).get("posNo")) or cls._safe_int((detected or {}).get("scoNo"))
        modify_time_hint = cls._resolve_auto_log_pull_modify_time(
            sync_object=sync_object,
            log_pull_payload=sync_object.log_pull_config,
        )
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
        bitable_email_sync = (
            dict(extra_data.pop("_bitable_email_sync"))
            if isinstance(extra_data.get("_bitable_email_sync"), dict)
            else {}
        )
        if bitable_email_sync:
            meta["bitableEmailSync"] = bitable_email_sync
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
        if sync_scene == "external_sync":
            sync_object = cls._enrich_external_person_emails_from_bitable(config, sync_object, ticket)
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
                    f"外部工单同步跳过统一提取与标题AI：更新场景且已携带标题, "
                    f"ticket_no={sync_object.ticket_no}"
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
                        f"外部工单同步统一提取执行失败，已继续后续流程: ticket_no={sync_object.ticket_no}, error={exc}"
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
        apply_external_mappings = sync_scene != "remote_pull"
        detected = cls._detect_fields(
            db,
            sync_object,
            config,
            apply_external_mappings=apply_external_mappings,
        )
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
                sync_translate_enabled = bool(
                    automation.auto_translate if automation is not None else config.get("autoTranslateOnSync", True)
                )
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
                    "外部工单同步翻译异常，已回退原文: "
                    f"ticket_no={sync_object.ticket_no}, scene={sync_scene}, error={exc}"
                )
                translated_description = str(sync_object.description or "").strip()
                translation_meta = {"translated_text": "", "skipped": True, "error": str(exc)}
                origin_description = str(sync_object.description or "").strip()
            if should_translate:
                sync_object = sync_object.model_copy(update={"description": translated_description})
        payload, meta, revision = cls._build_upsert_payload(
            db,
            ticket,
            sync_object,
            detected,
            current_user,
            sync_scene=sync_scene,
        )
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
                extra_data = (
                    dict(payload.get("extra_data") or {})
                    if isinstance(payload.get("extra_data"), dict)
                    else {}
                )
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

        step_reason_summary = None
        try:
            ticket = TicketDao.get_ticket_by_id(db, ticket.ticket_id) or ticket
            if sync_scene == "remote_pull":
                step_reason_summary = cls.sync_remote_payload_comments(db, ticket=ticket, sync_object=sync_object)
                if step_reason_summary.get("skipped"):
                    step_reason_summary = cls.sync_step_reason_comments(db, ticket=ticket, sync_object=sync_object)
            else:
                step_reason_summary = cls.sync_step_reason_comments(db, ticket=ticket, sync_object=sync_object)
            if step_reason_summary and not step_reason_summary.get("skipped"):
                db.commit()
        except Exception as exc:
            db.rollback()
            logger.warning(
                f"外部工单同步排查过程入库失败: ticket_no={sync_object.ticket_no}, "
                f"scene={sync_scene}, error={exc}"
            )

        if defer_post_process:
            result = (
                TicketService.get_ticket_detail_services(db, ticket.ticket_id)
                or CamelCaseUtil.transform_result(ticket)
            )
            result["syncSummary"] = cls.extract_sync_summary(result.get("extraData"))
            result["syncDeferred"] = True
            if step_reason_summary:
                result["syncStepReason"] = step_reason_summary
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
                ticket, category_summary = cls._run_auto_ticket_ai_classification(
                    db,
                    ticket=ticket,
                    title=str(sync_object.title or ticket.title or "").strip(),
                    description=str(sync_object.description or ticket.description or "").strip(),
                    current_user_name=_user_name(current_user),
                    source_type=f"{sync_scene}_auto_category",
                    source_ref=sync_object.ticket_no,
                    force_reclassify=False,
                    enabled_by_scene=cls._should_run_ai_classification_for_scene(config, sync_scene),
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
        if step_reason_summary:
            result["syncStepReason"] = step_reason_summary
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
            current_user = CurrentUserModel.model_validate(cls._normalize_current_user_payload(current_user_payload))
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
                f"外部工单同步延后处理跳过统一提取与分类AI：更新场景且已携带标题, "
                f"ticket_no={sync_object.ticket_no}"
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
                sync_object, ai_extract_apply_meta = cls._apply_ai_extract_to_sync_object(
                    sync_object,
                    ai_extract_result,
                )
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
                sync_translate_enabled = bool(
                    automation.auto_translate if automation is not None else config.get("autoTranslateOnSync", True)
                )
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
            if (
                should_translate
                and translated_description
                and translated_description != str(ticket.description or "").strip()
            ):
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
                cls._run_auto_ticket_ai_classification(
                    db,
                    ticket=ticket,
                    title=str(update_data.get("title") or ticket.title or "").strip(),
                    description=str(
                        update_data.get("description")
                        or sync_object.description
                        or ticket.description
                        or ""
                    ).strip(),
                    current_user_name=_user_name(current_user),
                    source_type=f"{sync_scene}_auto_category",
                    source_ref=sync_object.ticket_no,
                    force_reclassify=False,
                    enabled_by_scene=cls._should_run_ai_classification_for_scene(config, sync_scene),
                )
            except Exception as exc:
                logger.warning(f"外部工单同步延后自动分类失败: ticket_no={sync_object.ticket_no}, error={exc}")

        apply_external_mappings = sync_scene != "remote_pull"
        detected = cls._detect_fields(
            db,
            sync_object,
            config,
            apply_external_mappings=apply_external_mappings,
        )

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
            vector_scene = "remotePull" if sync_scene == "remote_pull" else "externalSync"
            TicketEmbeddingService.vectorize_ticket_for_scene(db, ticket, vector_scene)
            db.commit()
        except Exception as exc:
            db.rollback()
            logger.warning(
                f"外部工单同步延后向量刷新失败: ticket_no={sync_object.ticket_no}, "
                f"scene={sync_scene}, error={exc}"
            )
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
                            cls._mark_automation_step(
                                meta,
                                step="log_pull",
                                status="submitted",
                                detail=log_result.result,
                            )
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
            logger.exception(f"工单[{ticket_id}]同步自动化执行异常: {exc}")
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
            ticket, meta, _ = cls._ensure_publish_ready_for_pull(db, ticket=ticket, current_user=current_user)
            if not cls._is_publish_ready(meta):
                continue
            extra_data = dict(ticket.extra_data or {}) if isinstance(ticket.extra_data, dict) else {}
            revision = int(meta.get("revision") or 0)
            meta = cls._update_consumer_state(
                meta,
                consumer=query.consumer,
                revision=revision,
                batch_id=batch_id,
                status="pulled",
                message="已返回给消费者，等待成功回执确认",
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
        logger.info(
            f"工单批量重归类开始: user={current_user_name}, strategy={strategy}, "
            f"only_uncategorized={only_uncategorized}, all_tickets={all_tickets}, "
            f"force_reclassify={bool(getattr(request, 'force_reclassify', False))}, "
            f"page_num={int(getattr(request, 'page_num', 1) or 1)}, "
            f"page_size={int(getattr(request, 'page_size', 100) or 100)}, "
            f"ticket_ids_count={len(getattr(request, 'ticket_ids', None) or [])}, "
            f"regex_rules_count={len(regex_rules or [])}, "
            f"ai_prompt_code={ai_prompt_code or '-'}"
        )

        base_query = db.query(Ticket).filter(Ticket.del_flag == "0")
        if only_uncategorized:
            base_query = base_query.filter(
                Ticket.is_problem.is_(None),
                or_(Ticket.category_name.is_(None), Ticket.category_name == ""),
                or_(Ticket.issue_type_name.is_(None), Ticket.issue_type_name == ""),
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
        logger.info(
            f"工单批量重归类筛选完成: total={total}, selected={len(tickets)}, strategy={strategy}, "
            f"only_uncategorized={only_uncategorized}, all_tickets={all_tickets}"
        )

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
            logger.info(
                f"工单批量重归类跳过: strategy=regex 但未配置正则规则, selected={len(tickets)}, "
                f"only_uncategorized={only_uncategorized}, all_tickets={all_tickets}"
            )
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
                logger.info(
                    f"工单批量重归类处理开始: ticket_id={ticket.ticket_id}, ticket_no={ticket.ticket_no}, "
                    f"title_len={len(str(ticket.title or '').strip())}, "
                    f"description_len={len(str(ticket.description or '').strip())}, "
                    f"strategy={strategy}, force_reclassify={bool(getattr(request, 'force_reclassify', False))}"
                )
                if strategy == "regex":
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
                else:
                    _, category_result = cls._run_auto_ticket_ai_classification(
                        db,
                        ticket=ticket,
                        title=str(ticket.title or "").strip(),
                        description=str(ticket.description or "").strip(),
                        current_user_name=current_user_name,
                        source_type="ticket_batch_reclassify",
                        source_ref=str(ticket.ticket_no or ticket.ticket_id),
                        force_reclassify=bool(getattr(request, "force_reclassify", False)),
                        ai_prompt_code=ai_prompt_code,
                        enabled_by_scene=True,
                    )
                detail = {
                    "ticketId": ticket.ticket_id,
                    "ticketNo": ticket.ticket_no,
                    **category_result,
                }
                summary["details"].append(detail)
                if category_result.get("skipped"):
                    logger.info(
                        f"工单批量重归类跳过: ticket_id={ticket.ticket_id}, ticket_no={ticket.ticket_no}, "
                        f"reason={detail.get('skipReason') or category_result.get('skipReason') or '未说明'}"
                    )
                    summary["skippedCount"] += 1
                else:
                    logger.info(
                        f"工单批量重归类成功: ticket_id={ticket.ticket_id}, ticket_no={ticket.ticket_no}, "
                        f"category={category_result.get('categoryName') or '-'}, "
                        f"issue_type={category_result.get('issueTypeName') or '-'}, "
                        f"is_problem={category_result.get('isProblem')}"
                    )
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
        logger.info(
            f"工单批量重归类结束: total={summary['total']}, selected={summary['selectedCount']}, "
            f"success={summary['successCount']}, skipped={summary['skippedCount']}, failed={summary['failedCount']}"
        )
        return summary

    @classmethod
    def get_uncategorized_ticket_statistics_services(cls, db: Session) -> dict[str, Any]:
        """
        统计当前工单中未归类数量。

        :param db: 数据库会话。
        :return: 未归类统计结果。
        """
        logger.info("工单未归类统计开始: 仅执行统计查询，不触发自动归类")
        total_count = db.query(Ticket).filter(Ticket.del_flag == "0").count()
        uncategorized_count = (
            db.query(Ticket)
            .filter(
                Ticket.del_flag == "0",
                Ticket.is_problem.is_(None),
                or_(
                    Ticket.category_name.is_(None),
                    Ticket.category_name == "",
                ),
                or_(
                    Ticket.issue_type_name.is_(None),
                    Ticket.issue_type_name == "",
                ),
            )
            .count()
        )
        categorized_count = max(total_count - uncategorized_count, 0)
        uncategorized_ratio = round((uncategorized_count / total_count) * 100, 2) if total_count else 0
        logger.info(
            f"工单未归类统计完成: total_count={total_count}, categorized_count={categorized_count}, "
            f"uncategorized_count={uncategorized_count}, uncategorized_ratio={uncategorized_ratio}"
        )
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
        remote_comments = item.get("comments") if isinstance(item.get("comments"), list) else []
        if remote_comments:
            sync_extra_data["_remote_sync_comments"] = remote_comments
        external_field_mapping = (
            sync_extra_data.get("external_field_mapping")
            if isinstance(sync_extra_data.get("external_field_mapping"), dict)
            else {}
        )
        ticket_status = str(
            item.get("ticketStatus")
            or item.get("ticket_status")
            or item.get("status")
            or external_field_mapping.get("ticketStatus")
            or ""
        ).strip()
        module_name = str(
            item.get("moduleName")
            or item.get("module_name")
            or item.get("ticketModle")
            or item.get("ticketModel")
            or item.get("ticket_model")
            or external_field_mapping.get("ticketModle")
            or external_field_mapping.get("ticketModel")
            or ""
        ).strip()
        log_pull_hints = (
            sync_extra_data.get("log_pull_hints")
            if isinstance(sync_extra_data.get("log_pull_hints"), dict)
            else {}
        )
        log_pull_config = {
            "vendorId": log_pull_hints.get("vendorId") or log_pull_hints.get("vendor_id"),
            "storeId": log_pull_hints.get("storeId") or log_pull_hints.get("store_id"),
            "storeName": log_pull_hints.get("storeName") or log_pull_hints.get("store_name"),
            "posNo": log_pull_hints.get("posNo") or log_pull_hints.get("pos_no"),
            "scoNo": log_pull_hints.get("scoNo") or log_pull_hints.get("sco_no"),
            "modifyTime": log_pull_hints.get("modifyTime") or log_pull_hints.get("modify_time"),
        }
        log_pull_config = {key: value for key, value in log_pull_config.items() if value not in (None, "", [])}
        internal_owner_name = str(
            item.get("internalOwner")
            or item.get("internal_owner")
            or item.get("internalOwnerName")
            or item.get("internal_owner_name")
            or external_field_mapping.get("internalOwner")
            or external_field_mapping.get("internalOwnerName")
            or ""
        ).strip()
        internal_owner_email = str(
            item.get("internalOwnerEmail")
            or item.get("internal_owner_email")
            or external_field_mapping.get("internalOwnerEmail")
            or ""
        ).strip()
        step_reason = str(
            item.get("stepReason")
            or item.get("step_reason")
            or sync_extra_data.get("step_reason")
            or external_field_mapping.get("stepReason")
            or ""
        ).strip()
        sync_payload = {
            "source": source_payload,
            "syncConsumer": str(remote_sync.get("consumer") or "").strip() or None,
            "rawPayload": item,
            "ticketNo": ticket_no,
            "ticketUrl": remote_ticket_url,
            "title": title,
            "description": description,
            "createTime": external_create_time or source_payload.get("pushedAt"),
            "projectId": None,
            "projectName": item.get("projectName") or item.get("project_name") or item.get("merchantName") or "",
            "projectCode": item.get("projectCode") or item.get("project_code") or "",
            "merchantName": item.get("merchantName") or item.get("projectName") or item.get("project_name") or "",
            "moduleId": None,
            "moduleName": module_name,
            "moduleCode": item.get("moduleCode") or item.get("module_code") or "",
            "versionKey": item.get("versionKey") or item.get("version_key") or "",
            "status": ticket_status,
            "issueTypeId": item.get("issueTypeId") or item.get("issue_type_id") or "",
            "issueTypeName": item.get("issueTypeName") or item.get("issue_type_name") or "",
            "isProblem": item.get("isProblem") if item.get("isProblem") is not None else item.get("is_problem"),
            "rootCauseType": item.get("rootCauseType") or item.get("root_cause_type") or "",
            "solutionType": item.get("solutionType") or item.get("solution_type") or "",
            "resolutionCode": item.get("resolutionCode") or item.get("resolution_code") or "",
            "resolutionName": item.get("resolutionName") or item.get("resolution_name") or "",
            "customerPriority": item.get("customerPriority") or item.get("customer_priority") or "P3",
            "internalPriority": item.get("internalPriority") or item.get("internal_priority") or "P3",
            "severity": item.get("severity") or "",
            "reporterId": item.get("reporterId") or item.get("reporter_id"),
            "reporterName": item.get("reporterName") or item.get("reporter_name") or "",
            "currentAssigneeId": None,
            "currentAssigneeName": item.get("currentAssigneeName") or item.get("current_assignee_name") or "",
            "internalOwnerId": item.get("internalOwnerId") or item.get("internal_owner_id"),
            "internalOwnerName": internal_owner_name,
            "internalOwnerEmail": internal_owner_email,
            "rootCause": item.get("rootCause") or item.get("root_cause") or "",
            "solution": item.get("solution") or "",
            "tags": item.get("tags"),
            "extraData": sync_extra_data,
            "stepReason": step_reason,
            "logPullConfig": log_pull_config or None,
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
