import hashlib
import json
import re
from datetime import datetime, timedelta
from typing import Any

import requests
from fastapi import HTTPException, Request
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from config.database import SessionLocal
from context.request_context import get_current_trace_id, trace_context
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
from modules.ticket.service.ticket_sync_comment_service import TicketSyncCommentService
from modules.ticket.service.ticket_sync_config_service import TicketSyncConfigService
from modules.ticket.service.ticket_sync_field_mapping_service import TicketSyncFieldMappingService
from modules.ticket.service.ticket_sync_group_push_service import TicketSyncGroupPushService
from modules.ticket.service.ticket_sync_notify_service import TicketSyncNotifyService
from modules.ticket.util.sync_util import SyncUtil
from modules.ticket.util.ticket_feishu_bitable_util import FeishuBitableUtil
from utils.common_util import CamelCaseUtil
from utils.field_util import compatible_field_value, extract_person_name_email, normalize_email_text
from utils.log_util import logger


class TicketSyncService:
    """
    工单外部同步服务，统一处理外部推送、内网拉取和同步后自动化状态追踪。

    已提取的子服务（见对应文件，本类中保留原方法以保证向后兼容）：
    - TicketSyncConfigService (ticket_sync_config_service.py): 配置管理
    - SyncUtil (util/sync_util.py): 通用工具方法
    TODO: 后续提取 bitable / mapping / ai / publish 子服务
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
        "problemPatterns": [
            {
                "value": "memory_leak",
                "label": "内存泄露",
                "moduleCode": "",
                "issueTypeId": "performance_issue",
                "isProblem": True,
                "rootCauseType": "code_defect",
                "resolutionCode": "fixed",
                "description": "进程内存持续增长、未释放或最终 OOM 的问题模式。",
                "positiveExamples": ["内存泄露", "内存泄漏", "memory leak", "OOM"],
                "negativeExamples": ["单次内存高峰", "磁盘空间不足"],
                "enabled": True,
            },
            {
                "value": "coupon_280_paper_rule",
                "label": "280开头券为纸质券规则说明",
                "moduleCode": "coupon",
                "issueTypeId": "support_consulting",
                "isProblem": False,
                "rootCauseType": "requirement_design",
                "resolutionCode": "as_designed",
                "description": "用户反馈 280 开头券不能按电子券处理，实际业务规则定义为纸质券。",
                "positiveExamples": ["280开头券", "纸质券", "券规则说明"],
                "negativeExamples": ["电子券接口报错", "券配置错误"],
                "enabled": True,
            },
        ],
    }
    GROUP_PUSH_LOCK_TIMEOUT_SECONDS = 300

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
    def _parse_step_reason_date(cls, value: str):
        """委托到 TicketSyncCommentService._parse_step_reason_date。"""
        return TicketSyncCommentService._parse_step_reason_date(value)

    @classmethod
    def parse_step_reason_segments(cls, step_reason):
        """委托到 TicketSyncCommentService.parse_step_reason_segments。"""
        return TicketSyncCommentService.parse_step_reason_segments(step_reason)

    @classmethod
    def _build_step_reason_segment_key(cls, *, source_system, source_record_id, segment_index):
        """委托到 TicketSyncCommentService._build_step_reason_segment_key。"""
        return TicketSyncCommentService._build_step_reason_segment_key(
            source_system=source_system, source_record_id=source_record_id, segment_index=segment_index)

    @classmethod
    def _get_step_reason_content_segments(cls, sync_object):
        """委托到 TicketSyncCommentService._get_step_reason_content_segments。"""
        return TicketSyncCommentService._get_step_reason_content_segments(sync_object)

    @classmethod
    def _slice_content_segments_for_text(cls, *, full_text, content, content_segments):
        """委托到 TicketSyncCommentService._slice_content_segments_for_text。"""
        return TicketSyncCommentService._slice_content_segments_for_text(
            full_text=full_text, content=content, content_segments=content_segments)

    @classmethod
    def sync_step_reason_comments(cls, db, *, ticket, sync_object):
        """委托到 TicketSyncCommentService.sync_step_reason_comments。"""
        return TicketSyncCommentService.sync_step_reason_comments(
            db, ticket=ticket, sync_object=sync_object)

    @classmethod
    def sync_remote_payload_comments(cls, db, *, ticket, sync_object):
        """委托到 TicketSyncCommentService.sync_remote_payload_comments。"""
        return TicketSyncCommentService.sync_remote_payload_comments(
            db, ticket=ticket, sync_object=sync_object)

    @classmethod
    def _set_publish_state(cls, meta, *, ready, status, reason="", ai_task_status=None):
        """委托到 TicketSyncGroupPushService。"""
        return TicketSyncGroupPushService._set_publish_state(meta, ready=ready, status=status, reason=reason, ai_task_status=ai_task_status)

    @classmethod
    def _is_publish_ready(cls, meta):
        """委托到 TicketSyncGroupPushService。"""
        return TicketSyncGroupPushService._is_publish_ready(meta)

    @classmethod
    def _can_recover_publish_state(cls, db, *, ticket, meta):
        """委托到 TicketSyncGroupPushService。"""
        return TicketSyncGroupPushService._can_recover_publish_state(db, ticket=ticket, meta=meta)

    @classmethod
    def _ensure_publish_ready_for_pull(cls, db, *, ticket, current_user):
        """委托到 TicketSyncGroupPushService。"""
        return TicketSyncGroupPushService._ensure_publish_ready_for_pull(db, ticket=ticket, current_user=current_user)

    @classmethod
    def _is_group_push_sent_once(cls, meta):
        """委托到 TicketSyncGroupPushService。"""
        return TicketSyncGroupPushService._is_group_push_sent_once(meta)

    @classmethod
    def _mark_group_push_sent_once(cls, meta, *, scene, revision):
        """委托到 TicketSyncGroupPushService。"""
        return TicketSyncGroupPushService._mark_group_push_sent_once(meta, scene=scene, revision=revision)

    @classmethod
    def _append_group_push_message_refs(cls, meta, message_refs):
        """委托到 TicketSyncGroupPushService。"""
        return TicketSyncGroupPushService._append_group_push_message_refs(meta, message_refs)

    @classmethod
    def _mark_group_push_processing(cls, meta, *, scene, revision):
        """委托到 TicketSyncGroupPushService。"""
        return TicketSyncGroupPushService._mark_group_push_processing(meta, scene=scene, revision=revision)

    @classmethod
    def _clear_group_push_processing(cls, meta):
        """委托到 TicketSyncGroupPushService。"""
        return TicketSyncGroupPushService._clear_group_push_processing(meta)

    @classmethod
    def _is_group_push_processing_locked(cls, meta):
        """委托到 TicketSyncGroupPushService。"""
        return TicketSyncGroupPushService._is_group_push_processing_locked(meta)

    @classmethod
    def _persist_group_push_meta_state(cls, db, *, ticket_id, update_by, scene, acquire_lock=False, clear_lock=False, mark_sent_once=False, message_refs=None):
        """委托到 TicketSyncGroupPushService。"""
        return TicketSyncGroupPushService._persist_group_push_meta_state(db, ticket_id=ticket_id, update_by=update_by, scene=scene, acquire_lock=acquire_lock, clear_lock=clear_lock, mark_sent_once=mark_sent_once, message_refs=message_refs)

    @classmethod
    def _resolve_ai_pending_state(cls, db, *, ticket_id, meta):
        """委托到 TicketSyncGroupPushService。"""
        return TicketSyncGroupPushService._resolve_ai_pending_state(db, ticket_id=ticket_id, meta=meta)

    @classmethod
    def _persist_sync_meta(cls, db, *, ticket, meta, update_by):
        """委托到 TicketSyncGroupPushService。"""
        return TicketSyncGroupPushService._persist_sync_meta(db, ticket=ticket, meta=meta, update_by=update_by)

    @classmethod
    def _send_auto_group_message_once(cls, db, *, ticket, meta, group_config, scene, update_by):
        """委托到 TicketSyncGroupPushService。"""
        return TicketSyncGroupPushService._send_auto_group_message_once(db, ticket=ticket, meta=meta, group_config=group_config, scene=scene, update_by=update_by)

    @classmethod
    def _finalize_publish_state_after_post_process(cls, db, ticket, meta, scene, update_by):
        """委托到 TicketSyncGroupPushService。"""
        return TicketSyncGroupPushService._finalize_publish_state_after_post_process(db, ticket, meta, scene, update_by)

    @classmethod
    def finalize_sync_after_ai(cls, db, ticket_id, ai_task_status, sync_scene):
        """委托到 TicketSyncGroupPushService。"""
        return TicketSyncGroupPushService.finalize_sync_after_ai(db, ticket_id, ai_task_status, sync_scene)

    @classmethod
    def _resolve_external_create_time(
        cls,
        *,
        sync_object,
        existing_meta,
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
    def _resolve_ticket_submit_time(cls, *, ticket, meta):
        """委托到 TicketSyncGroupPushService。"""
        return TicketSyncGroupPushService._resolve_ticket_submit_time(ticket=ticket, meta=meta)

    @classmethod
    def _resolve_group_push_auto_send_after_time(cls, group_config):
        """委托到 TicketSyncGroupPushService。"""
        return TicketSyncGroupPushService._resolve_group_push_auto_send_after_time(group_config)

    @classmethod
    def _normalize_group_push_auto_statuses(cls, value, *, fallback=None):
        """委托到 TicketSyncGroupPushService。"""
        return TicketSyncGroupPushService._normalize_group_push_auto_statuses(value, fallback=fallback)

    @classmethod
    def _should_skip_auto_group_push_by_status(cls, *, ticket, group_config):
        """委托到 TicketSyncGroupPushService。"""
        return TicketSyncGroupPushService._should_skip_auto_group_push_by_status(ticket=ticket, group_config=group_config)

    @classmethod
    def _should_skip_auto_group_push_by_submit_time(cls, *, ticket, meta, group_config):
        """委托到 TicketSyncGroupPushService。"""
        return TicketSyncGroupPushService._should_skip_auto_group_push_by_submit_time(ticket=ticket, meta=meta, group_config=group_config)

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
        source_hash = SyncUtil.text_sha256(normalized_source)
        stored_source_hash = str(extra_data.get("ai_translation_source_hash") or "").strip()
        if stored_source_hash:
            return stored_source_hash == source_hash
        origin_description = str(extra_data.get("origin_description") or "").strip()
        if origin_description:
            return SyncUtil.text_sha256(origin_description) == source_hash
        legacy_source_description = str(extra_data.get("ai_translation_source_description") or "").strip()
        if legacy_source_description:
            return SyncUtil.text_sha256(legacy_source_description) == source_hash
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
        local_source_revision = SyncUtil.safe_int(local_meta.get("sourceRevision"))
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
        parsed_remote_time = SyncUtil.parse_datetime_value(remote_pushed_at)
        parsed_local_time = SyncUtil.parse_datetime_value(local_pushed_at)
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
    def _default_sync_config(cls):
        """委托到 TicketSyncConfigService._default_sync_config。"""
        return TicketSyncConfigService._default_sync_config()


    @classmethod
    def _default_feishu_auth_config(cls) -> dict[str, Any]:
        """委托到 TicketSyncConfigService。"""
        return TicketSyncConfigService._default_feishu_auth_config()

    @classmethod
    def _default_bitable_common_config(cls) -> dict[str, Any]:
        """委托到 TicketSyncConfigService。"""
        return TicketSyncConfigService._default_bitable_common_config()

    @classmethod
    def _default_external_field_model_config(cls) -> dict[str, Any]:
        """委托到 TicketSyncConfigService。"""
        return TicketSyncConfigService._default_external_field_model_config()

    @classmethod
    def _default_external_sync_bitable_config(cls):
        """委托到 TicketSyncConfigService._default_external_sync_bitable_config。"""
        return TicketSyncConfigService._default_external_sync_bitable_config()

    @classmethod
    def _default_bitable_pull_config(cls):
        """委托到 TicketSyncConfigService._default_bitable_pull_config。"""
        return TicketSyncConfigService._default_bitable_pull_config()


    @classmethod
    def _default_group_push_config(cls):
        """委托到 TicketSyncConfigService._default_group_push_config。"""
        return TicketSyncConfigService._default_group_push_config()

    @classmethod
    def _default_message_sync_config(cls):
        """委托到 TicketSyncConfigService._default_message_sync_config。"""
        return TicketSyncConfigService._default_message_sync_config()


    @classmethod
    def _default_person_reminder_config(cls):
        """委托到 TicketSyncConfigService._default_person_reminder_config。"""
        return TicketSyncConfigService._default_person_reminder_config()

    @classmethod
    def _default_summary_report_config(cls):
        """委托到 TicketSyncConfigService._default_summary_report_config。"""
        return TicketSyncConfigService._default_summary_report_config()


    @classmethod
    def _default_remote_sync_config(cls):
        """委托到 TicketSyncConfigService._default_remote_sync_config。"""
        return TicketSyncConfigService._default_remote_sync_config()

    @classmethod
    def _default_stat_classification_config(cls):
        """委托到 TicketSyncConfigService._default_stat_classification_config。"""
        return TicketSyncConfigService._default_stat_classification_config()


    @classmethod
    def _default_ai_classification_config(cls):
        """委托到 TicketSyncConfigService._default_ai_classification_config。"""
        return TicketSyncConfigService._default_ai_classification_config()

    @classmethod
    def _normalize_stat_option_rows(cls, value, default_rows):
        """委托到 TicketSyncConfigService._normalize_stat_option_rows。"""
        return TicketSyncConfigService._normalize_stat_option_rows(value, default_rows)

    @classmethod
    def _normalize_ai_classification_config(cls, value):
        """委托到 TicketSyncConfigService._normalize_ai_classification_config。"""
        return TicketSyncConfigService._normalize_ai_classification_config(value)

    @classmethod
    def _normalize_external_field_model_config(cls, value):
        """委托到 TicketSyncConfigService._normalize_external_field_model_config。"""
        return TicketSyncConfigService._normalize_external_field_model_config(value)

    @classmethod
    def _normalize_bitable_filter_config(cls, value):
        """委托到 TicketSyncConfigService._normalize_bitable_filter_config。"""
        return TicketSyncConfigService._normalize_bitable_filter_config(value)

    @classmethod
    def _format_bitable_filter_config(cls, value):
        """委托到 TicketSyncConfigService._format_bitable_filter_config。"""
        return TicketSyncConfigService._format_bitable_filter_config(value)

    @classmethod
    def _apply_bitable_common_defaults(cls, config, *, bitable_common, keep_filter_formula=True):
        """委托到 TicketSyncConfigService._apply_bitable_common_defaults。"""
        return TicketSyncConfigService._apply_bitable_common_defaults(config, bitable_common=bitable_common, keep_filter_formula=keep_filter_formula)

    @classmethod
    def _merge_non_empty_runtime_override(cls, base_config, override_config):
        """委托到 TicketSyncConfigService._merge_non_empty_runtime_override。"""
        return TicketSyncConfigService._merge_non_empty_runtime_override(base_config, override_config)

    @classmethod
    def _normalize_bitable_pull_target_field(cls, value: Any) -> str:
        """委托到 FeishuBitableUtil.normalize_pull_target_field。"""
        return FeishuBitableUtil.normalize_pull_target_field(value)

    @classmethod
    def _normalize_bitable_pull_config(cls, value, *, feishu_auth, bitable_common):
        """委托到 TicketSyncConfigService._normalize_bitable_pull_config。"""
        return TicketSyncConfigService._normalize_bitable_pull_config(value, feishu_auth=feishu_auth, bitable_common=bitable_common)

    @classmethod
    def _datetime_to_bitable_filter_millis(cls, value):
        """委托到 TicketSyncConfigService._datetime_to_bitable_filter_millis。"""
        return TicketSyncConfigService._datetime_to_bitable_filter_millis(value)

    @classmethod
    def _condition_needs_dynamic_time_value(cls, condition, *, time_field_names):
        """委托到 TicketSyncConfigService._condition_needs_dynamic_time_value。"""
        return TicketSyncConfigService._condition_needs_dynamic_time_value(condition, time_field_names=time_field_names)

    @classmethod
    def _build_bitable_pull_time_filters(cls, *, filter_formula, created_after, created_before=None, updated_at_field="", auto_append_time_filter=True):
        """委托到 TicketSyncConfigService._build_bitable_pull_time_filters。"""
        return TicketSyncConfigService._build_bitable_pull_time_filters(filter_formula=filter_formula, created_after=created_after, created_before=created_before, updated_at_field=updated_at_field, auto_append_time_filter=auto_append_time_filter)

    @classmethod
    def _normalize_sync_config(cls, config: dict[str, Any] | None) -> dict[str, Any]:
        """委托到 TicketSyncConfigService._normalize_sync_config。"""
        return TicketSyncConfigService._normalize_sync_config(config)

    @classmethod
    def _resolve_bitable_runtime_config(cls, config, section_key, default_config, *, keep_filter_formula=True):
        """委托到 TicketSyncConfigService。"""
        return TicketSyncConfigService._resolve_bitable_runtime_config(config, section_key, default_config, keep_filter_formula=keep_filter_formula)

    @classmethod
    def _resolve_bitable_pull_created_after(cls, value):
        """委托到 TicketSyncConfigService。"""
        return TicketSyncConfigService._resolve_bitable_pull_created_after(value)

    @classmethod
    def _query_bitable_pull_records(cls, pull_config, filters):
        """委托到 TicketSyncConfigService。"""
        return TicketSyncConfigService._query_bitable_pull_records(pull_config, filters)

    @classmethod
    def _derive_required_fields_from_external_field_model(cls, value):
        """委托到 TicketSyncConfigService。"""
        return TicketSyncConfigService._derive_required_fields_from_external_field_model(value)

    @classmethod
    def ensure_param_config_rows(cls, db: Session):
        """委托到 TicketSyncConfigService.ensure_param_config_rows。"""
        return TicketSyncConfigService.ensure_param_config_rows(db)

    @classmethod
    def _load_sync_config(cls, db: Session) -> dict[str, Any]:
        """委托到 TicketSyncConfigService._load_sync_config。"""
        return TicketSyncConfigService._load_sync_config(db)

    @classmethod
    def get_sync_automation_config_services(cls, db: Session):
        """委托到 TicketSyncConfigService.get_sync_automation_config_services。"""
        return TicketSyncConfigService.get_sync_automation_config_services(db)


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
    def get_ticket_stat_classification_options(cls, db: Session):
        """委托到 TicketSyncConfigService.get_ticket_stat_classification_options。"""
        return TicketSyncConfigService.get_ticket_stat_classification_options(db)


    @classmethod
    def update_sync_automation_config_services(
        cls,
        db: Session,
        config_value: dict[str, Any],
        current_user_name: str,
    ) -> CrudResponseModel:
        """委托到 TicketSyncConfigService.update_sync_automation_config_services。"""
        return TicketSyncConfigService.update_sync_automation_config_services(db, config_value, current_user_name)

    @classmethod
    def get_sync_notify_push_options_services(cls, db: Session):
        """委托到 TicketSyncConfigService.get_sync_notify_push_options_services。"""
        return TicketSyncConfigService.get_sync_notify_push_options_services(db)


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

        auto_append = SyncUtil.to_bool(pull_config.get("autoAppendTimeFilter"), True)
        raw_created_after = str(pull_config.get("createdAfter") or "").strip() if not auto_append else None
        raw_created_before = str(pull_config.get("createdBefore") or "").strip() if not auto_append else None

        created_after = cls._resolve_bitable_pull_created_after(raw_created_after) if raw_created_after else None
        created_before = cls._resolve_bitable_pull_created_after(raw_created_before) if raw_created_before else None

        if raw_created_after and not created_after:
            return {
                "triggerSource": trigger_source,
                "skipped": True,
                "skipReason": "主动拉取开始时间格式错误",
                "configErrors": ["createdAfter"],
                "createdAfter": raw_created_after,
            }
        if raw_created_before and not created_before:
            return {
                "triggerSource": trigger_source,
                "skipped": True,
                "skipReason": "主动拉取结束时间格式错误",
                "configErrors": ["createdBefore"],
                "createdBefore": raw_created_before,
            }

        if auto_append:
            # 现有行为：无显式时间时默认过滤过去 1 小时
            if not created_after and not created_before:
                created_after = datetime.now() - timedelta(hours=1)
                pull_config["createdAfter"] = created_after.strftime("%Y-%m-%d %H:%M:%S")
        else:
            # 精确模式：不自动追加，仅使用显式传入的时间参数
            if not created_after and not created_before:
                created_after = None

        pull_filters: list[dict[str, Any]] = []
        if created_after or created_before:
            updated_at_field = str(pull_config.get("updatedAtField") or "").strip() or "更新时间"
            try:
                pull_filters = cls._build_bitable_pull_time_filters(
                    filter_formula=pull_config.get("filterFormula"),
                    created_after=created_after,
                    created_before=created_before,
                    updated_at_field=updated_at_field,
                    auto_append_time_filter=auto_append,
                )
            except ValueError as exc:
                return {
                    "triggerSource": trigger_source,
                    "skipped": True,
                    "skipReason": str(exc),
                    "configErrors": ["filterFormula"],
                    "createdAfter": created_after.strftime("%Y-%m-%d %H:%M:%S") if created_after else "",
                    "createdBefore": created_before.strftime("%Y-%m-%d %H:%M:%S") if created_before else "",
                }
            time_info_parts = []
            if created_after:
                time_info_parts.append(f"created_after={created_after.strftime('%Y-%m-%d %H:%M:%S')}")
            if created_before:
                time_info_parts.append(f"created_before={created_before.strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info(
                f"飞书多维表格主动拉取云端时间过滤: trigger={trigger_source}, "
                f"{', '.join(time_info_parts)}, auto_append={auto_append}, "
                f"updated_at_field={updated_at_field}"
            )
        else:
            try:
                pull_filters = cls._build_bitable_pull_time_filters(
                    filter_formula=pull_config.get("filterFormula"),
                    created_after=None,
                    created_before=None,
                    updated_at_field="",
                    auto_append_time_filter=auto_append,
                )
            except ValueError as exc:
                return {
                    "triggerSource": trigger_source,
                    "skipped": True,
                    "skipReason": str(exc),
                    "configErrors": ["filterFormula"],
                    "createdAfter": "",
                    "createdBefore": "",
                }
            logger.info(
                f"飞书多维表格主动拉取无时间过滤: trigger={trigger_source}, auto_append={auto_append}"
            )
        records = cls._query_bitable_pull_records(pull_config, pull_filters)
        queried_count = len(records)
        force_sync = SyncUtil.to_bool(pull_config.get("forceSync"), False)
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
    def send_group_push_by_ticket_no_services(cls, db, *, ticket_no, push_ids=None, message_template=None, force_push=False, update_by="system"):
        """委托到 TicketSyncGroupPushService。"""
        return TicketSyncGroupPushService.send_group_push_by_ticket_no_services(db, ticket_no=ticket_no, push_ids=push_ids, message_template=message_template, force_push=force_push, update_by=update_by)

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
            "sourceRevision": SyncUtil.safe_int(meta.get("sourceRevision")) or 0,
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
    def _extract_external_mapping_fields(cls, sync_object):
        """委托到 TicketSyncFieldMappingService。"""
        return TicketSyncFieldMappingService._extract_external_mapping_fields(sync_object)

    @classmethod
    def _has_incoming_project_value(cls, sync_object, mapping_payload):
        """委托到 TicketSyncFieldMappingService。"""
        return TicketSyncFieldMappingService._has_incoming_project_value(sync_object, mapping_payload)

    @classmethod
    def _has_incoming_module_value(cls, sync_object, mapping_payload):
        """委托到 TicketSyncFieldMappingService。"""
        return TicketSyncFieldMappingService._has_incoming_module_value(sync_object, mapping_payload)

    @classmethod
    def _match_mapping_exact(cls, field_value, mappings):
        """委托到 TicketSyncFieldMappingService。"""
        return TicketSyncFieldMappingService._match_mapping_exact(field_value, mappings)

    @classmethod
    def _match_mapping_contains(cls, field_value, mappings):
        """委托到 TicketSyncFieldMappingService。"""
        return TicketSyncFieldMappingService._match_mapping_contains(field_value, mappings)

    @classmethod
    def _resolve_project_by_ticket_vender(cls, db, *, ticket_vender, project_mappings):
        """委托到 TicketSyncFieldMappingService。"""
        return TicketSyncFieldMappingService._resolve_project_by_ticket_vender(
            db, ticket_vender=ticket_vender, project_mappings=project_mappings)

    @classmethod
    def _resolve_module_by_ticket_modle(cls, db, *, ticket_modle, module_mappings, project_id=None):
        """委托到 TicketSyncFieldMappingService。"""
        return TicketSyncFieldMappingService._resolve_module_by_ticket_modle(
            db, ticket_modle=ticket_modle, module_mappings=module_mappings, project_id=project_id)

    @classmethod
    def _resolve_status_by_external_value(cls, ticket_status, status_mappings):
        """委托到 TicketSyncFieldMappingService。"""
        return TicketSyncFieldMappingService._resolve_status_by_external_value(ticket_status, status_mappings)

    @classmethod
    def _resolve_vendor_by_ticket_vender(cls, ticket_vender, vendor_mappings):
        """委托到 TicketSyncFieldMappingService。"""
        return TicketSyncFieldMappingService._resolve_vendor_by_ticket_vender(ticket_vender, vendor_mappings)

    @classmethod
    def _resolve_vendor_by_project(cls, db, *, project_id):
        """委托到 TicketSyncFieldMappingService。"""
        return TicketSyncFieldMappingService._resolve_vendor_by_project(db, project_id=project_id)

    @classmethod
    def _resolve_store_by_external_value(cls, db, *, store_text):
        """委托到 TicketSyncFieldMappingService。"""
        return TicketSyncFieldMappingService._resolve_store_by_external_value(db, store_text=store_text)

    @classmethod
    def _match_assignee_mapping_exact(cls, assignee_text, assignee_mappings):
        """委托到 TicketSyncFieldMappingService。"""
        return TicketSyncFieldMappingService._match_assignee_mapping_exact(assignee_text, assignee_mappings)

    @classmethod
    def _resolve_assignee_by_external_value(cls, db, *, assignee_text, assignee_mappings):
        """委托到 TicketSyncFieldMappingService。"""
        return TicketSyncFieldMappingService._resolve_assignee_by_external_value(
            db, assignee_text=assignee_text, assignee_mappings=assignee_mappings)

    @classmethod
    def _resolve_sys_user_by_email(cls, db, email):
        """委托到 TicketSyncFieldMappingService。"""
        return TicketSyncFieldMappingService._resolve_sys_user_by_email(db, email)

    @classmethod
    def _resolve_external_person_by_mapping_or_email(cls, db, *, person_text, assignee_mappings, email_hint=None):
        """委托到 TicketSyncFieldMappingService。"""
        return TicketSyncFieldMappingService._resolve_external_person_by_mapping_or_email(
            db, person_text=person_text, assignee_mappings=assignee_mappings, email_hint=email_hint)

    @classmethod
    def _resolve_remote_assignee_by_email_or_name(cls, db, *, assignee_text, email_hint=None):
        """委托到 TicketSyncFieldMappingService。"""
        return TicketSyncFieldMappingService._resolve_remote_assignee_by_email_or_name(
            db, assignee_text=assignee_text, email_hint=email_hint)


    @classmethod
    def _describe_bitable_field_value_for_log(cls, value: Any) -> dict[str, Any]:
        """委托到 FeishuBitableUtil.describe_field_value_for_log。"""
        return FeishuBitableUtil.describe_field_value_for_log(value)

    @classmethod
    def _extract_email_from_bitable_value(cls, value):
        """委托到 FeishuBitableUtil.extract_email。"""
        return FeishuBitableUtil.extract_email(value)

    @classmethod
    def _mask_email_for_log(cls, email):
        """委托到 FeishuBitableUtil.mask_email_for_log。"""
        return FeishuBitableUtil.mask_email_for_log(email)

    @classmethod
    def _normalize_bitable_record_scalar(
        cls,
        value: Any,
        *,
        join_separator: str = ",",
    ) -> Any:
        """委托到 FeishuBitableUtil.normalize_record_scalar。"""
        return FeishuBitableUtil.normalize_record_scalar(value, join_separator=join_separator)

    @classmethod
    def _is_bitable_rich_text_segment(cls, value: Any) -> bool:
        """委托到 FeishuBitableUtil.is_rich_text_segment。"""
        return FeishuBitableUtil.is_rich_text_segment(value)

    @classmethod
    def _is_bitable_rich_text_list(cls, value: Any) -> bool:
        """委托到 FeishuBitableUtil.is_rich_text_list。"""
        return FeishuBitableUtil.is_rich_text_list(value)

    @classmethod
    def _normalize_bitable_rich_text_segment(
        cls,
        value: Any,
        *,
        join_separator: str = ",",
    ) -> str:
        """委托到 FeishuBitableUtil.normalize_rich_text_segment。"""
        return FeishuBitableUtil.normalize_rich_text_segment(value, join_separator=join_separator)

    @classmethod
    def _normalize_bitable_rich_text_segments_for_comment(cls, value: Any) -> list[dict[str, Any]]:
        """委托到 FeishuBitableUtil.normalize_rich_text_segments_for_comment。"""
        return FeishuBitableUtil.normalize_rich_text_segments_for_comment(value)

    @classmethod
    def _extract_bitable_person_text(
        cls,
        value: Any,
        *,
        preferred_keys: tuple[str, ...],
        join_separator: str = ",",
    ) -> str:
        """委托到 FeishuBitableUtil.extract_person_text。"""
        return FeishuBitableUtil.extract_person_text(
            value, preferred_keys=preferred_keys, join_separator=join_separator
        )

    @classmethod
    def _extract_bitable_person_email(cls, value: Any, *, join_separator: str = ",") -> str:
        """委托到 FeishuBitableUtil.extract_person_email。"""
        return FeishuBitableUtil.extract_person_email(value, join_separator=join_separator)

    @classmethod
    def _extract_bitable_person_name(cls, value: Any, *, join_separator: str = ",") -> str:
        """委托到 FeishuBitableUtil.extract_person_name。"""
        return FeishuBitableUtil.extract_person_name(value, join_separator=join_separator)

    @classmethod
    def _normalize_bitable_record_datetime_text(cls, value: Any) -> str:
        """委托到 FeishuBitableUtil.normalize_record_datetime_text。"""
        return FeishuBitableUtil.normalize_record_datetime_text(value)

    @classmethod
    def _build_bitable_record_url(
        cls,
        config: dict[str, Any],
        *,
        record_id: str,
        record_url: str | None = None,
    ) -> str:
        """委托到 FeishuBitableUtil.build_record_url。"""
        return FeishuBitableUtil.build_record_url(config, record_id=record_id, record_url=record_url)

    @classmethod
    def _build_bitable_pull_field_mapping_from_record(
        cls,
        fields: dict[str, Any],
        *,
        field_mappings: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """委托到 FeishuBitableUtil.build_pull_field_mapping_from_record。"""
        return FeishuBitableUtil.build_pull_field_mapping_from_record(
            fields, field_mappings=field_mappings
        )

    @classmethod
    def _build_bitable_pull_snapshot_hash(
        cls,
        *,
        source_payload: dict[str, Any],
        field_mapping_snapshot: dict[str, str],
    ) -> str:
        """委托到 FeishuBitableUtil.build_pull_snapshot_hash。"""
        return FeishuBitableUtil.build_pull_snapshot_hash(
            source_payload=source_payload,
            field_mapping_snapshot=field_mapping_snapshot,
        )

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
        bitable_pull_meta: dict[str, Any] = {
            "recordId": record_id,
            "snapshotHash": cls._build_bitable_pull_snapshot_hash(
                source_payload=payload,
                field_mapping_snapshot=field_mapping_snapshot,
            ),
            "stepReasonHash": SyncUtil.text_sha256(payload.get("stepReason")),
            "fieldMappings": field_mapping_snapshot,
            "sourceSystem": payload["source"]["system"],
            "pulledAt": SyncUtil.now_iso(),
        }
        send_group_override = config.get("sendGroupMessage") if isinstance(config, dict) else None
        if send_group_override is not None:
            bitable_pull_meta["sendGroupMessage"] = bool(send_group_override)
        extra_data["bitable_pull"] = bitable_pull_meta
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
        external_mapping["bitableEmailSyncedAt"] = SyncUtil.now_iso()
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
        revision = SyncUtil.safe_int((meta or {}).get("revision"))
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
        pos_no = SyncUtil.safe_int(result.get("posNo"))
        sco_no = SyncUtil.safe_int(result.get("scoNo"))
        log_date = cls._normalize_auto_log_pull_date_text(result.get("logDate"))

        log_pull_payload = (
            dict(sync_object.log_pull_config or {})
            if isinstance(sync_object.log_pull_config, dict)
            else {}
        )
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
                "posNo": SyncUtil.safe_int(log_pull_payload.get("posNo")),
                "scoNo": SyncUtil.safe_int(log_pull_payload.get("scoNo")),
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
            "executedAt": SyncUtil.now_iso(),
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
    def _mapping_keywords(cls, mapping):
        """委托到 TicketSyncFieldMappingService._mapping_keywords。"""
        return TicketSyncFieldMappingService._mapping_keywords(mapping)


    @classmethod
    def _merge_external_text_fields(
        cls,
        base_data: dict[str, Any],
        detected: dict[str, Any],
        sync_object: TicketExternalSyncUpsertModel,
    ) -> dict[str, Any]:
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
            SyncUtil.payload_field_value(payload, "modifyTime", "modify_time", default="")
            or SyncUtil.payload_field_value(payload, "logDate", "log_date", default="")
            or SyncUtil.payload_field_value(payload, "ticketDate", "ticket_date", default="")
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
            candidate = SyncUtil.payload_field_value(raw_payload, camel_key, snake_key, default="")
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
            "classifiedAt": SyncUtil.now_iso(),
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

        新版页面只保存 Provider/Prompt 编码，提示词正文统一由 SysAiPromptTemplate 管理。
        仅在前端未显式提交 promptContent 字段时才保留旧值，避免字段缺失导致的历史数据丢失。
        如果前端显式提交了 promptContent（包括空字符串），则以前端值为准。
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
        # 仅在前端未显式提交 promptContent 字段时才保留旧值
        if "promptContent" not in next_ai_config:
            legacy_prompt_content = str(current_ai_config.get("promptContent") or "").strip()
            if legacy_prompt_content:
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
        if not force_reclassify and cls._has_complete_ticket_classification_fields(ticket):
            if cls._has_successful_ai_classification(
                ticket,
                title=title_text,
                description=description_text,
                comments=comment_context,
            ):
                logger.info(
                    f"工单AI分类统计跳过: ticket_id={ticket.ticket_id}, ticket_no={ticket.ticket_no}, "
                    f"reason=核心分类字段完整且内容未变化, source_type={source_type}"
                )
                return ticket, {"skipped": True, "skipReason": "核心分类字段完整且内容未变化"}
            logger.info(
                f"工单AI分类统计继续执行: ticket_id={ticket.ticket_id}, ticket_no={ticket.ticket_no}, "
                f"reason=核心分类字段完整但内容已变化, source_type={source_type}"
            )
        elif not force_reclassify:
            logger.info(
                f"工单AI分类统计继续执行: ticket_id={ticket.ticket_id}, ticket_no={ticket.ticket_no}, "
                f"reason=存在核心分类字段缺失, source_type={source_type}"
            )
        ai_config = config.get("aiClassification") if isinstance(config.get("aiClassification"), dict) else {}
        stat_options = config.get("statClassification") if isinstance(config.get("statClassification"), dict) else {}
        if isinstance(stat_options.get("problemPatterns"), list):
            stat_options = dict(stat_options)
            stat_options["problemPatterns"] = [
                item
                for item in stat_options["problemPatterns"]
                if not isinstance(item, dict) or item.get("enabled") is not False
            ]
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
            root_cause=str(getattr(ticket, "root_cause", "") or "").strip(),
            solution=str(getattr(ticket, "solution", "") or "").strip(),
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
            "classifiedAt": SyncUtil.now_iso(),
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
            "problemPatternCode": "problem_pattern_code",
            "problemPatternName": "problem_pattern_name",
            "rootCause": "root_cause",
            "solution": "solution",
        }
        for result_key, db_field in field_map.items():
            if db_field.startswith("problem_pattern_") and getattr(ticket, "problem_pattern_verified", None) is True:
                continue
            value = result_payload.get(result_key)
            if value not in (None, ""):
                update_data[db_field] = value
        if result_payload.get("isProblem") is not None:
            update_data["is_problem"] = bool(result_payload.get("isProblem"))
        if (
            result_payload.get("problemPatternConfidence") is not None
            and getattr(ticket, "problem_pattern_verified", None) is not True
        ):
            pattern_confidence = float(result_payload.get("problemPatternConfidence") or 0)
            update_data["problem_pattern_confidence"] = int(
                min(max(pattern_confidence * 100 if pattern_confidence <= 1 else pattern_confidence, 0), 100)
            )
        if result_payload.get("problemPatternCode") and getattr(ticket, "problem_pattern_verified", None) is not True:
            update_data["problem_pattern_source"] = "ai"
            if getattr(ticket, "problem_pattern_verified", None) is None:
                update_data["problem_pattern_verified"] = False

        TicketDao.update_ticket(db, ticket.ticket_id, update_data)
        db.commit()
        ticket = TicketDao.get_ticket_by_id(db, ticket.ticket_id) or ticket
        logger.info(
            f"工单AI分类统计回填完成: ticket_id={ticket.ticket_id}, ticket_no={ticket.ticket_no}, "
            f"category={result_payload.get('categoryName') or '-'}, "
            f"issue_type={result_payload.get('issueTypeName') or '-'}, "
            f"is_problem={result_payload.get('isProblem')}, "
            f"root_cause_type={result_payload.get('rootCauseType') or '-'}, "
            f"solution_type={result_payload.get('solutionType') or '-'}, "
            f"problem_pattern={result_payload.get('problemPatternName') or '-'}"
        )
        return ticket, {
            "skipped": False,
            "categoryName": result_payload.get("categoryName"),
            "issueTypeName": result_payload.get("issueTypeName"),
            "isProblem": result_payload.get("isProblem"),
            "rootCauseType": result_payload.get("rootCauseType"),
            "solutionType": result_payload.get("solutionType"),
            "resolutionName": result_payload.get("resolutionName"),
            "problemPatternName": result_payload.get("problemPatternName"),
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
            "problemPatternCode": ticket.problem_pattern_code,
            "problemPatternName": ticket.problem_pattern_name,
            "problemPatternVerified": ticket.problem_pattern_verified,
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
        root_cause: str | None = None,
        solution: str | None = None,
    ) -> str:
        """
        构建 AI 分类防重用来源摘要。

        :param title: 工单标题。
        :param description: 工单描述。
        :param comments: 工单评论上下文。
        :param root_cause: 当前根因。
        :param solution: 当前解决方案。
        :return: 来源内容 SHA256。
        """
        comment_text = "\n".join(str(item or "").strip() for item in comments or [] if str(item or "").strip())
        return SyncUtil.text_sha256(
            "\n\n".join(
                [
                    str(title or "").strip(),
                    str(description or "").strip(),
                    comment_text,
                    str(root_cause or "").strip(),
                    str(solution or "").strip(),
                ]
            )
        )

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
            root_cause=str(getattr(ticket, "root_cause", "") or "").strip(),
            solution=str(getattr(ticket, "solution", "") or "").strip(),
        )
        return bool(ai_meta.get("success")) and str(ai_meta.get("sourceHash") or "") == source_hash

    @classmethod
    def _has_complete_ticket_classification_fields(cls, ticket: Ticket) -> bool:
        """
        判断工单是否已经具备完整的核心分类统计结果。

        `module_name` 来自项目/模块映射，`severity` 是工单自身严重程度属性，二者不作为
        自动归类完整性的判断条件。任一核心字段缺失时允许继续调用 AI 补齐。
        :param ticket: 工单对象。
        :return: 核心分类字段均有值时返回 True。
        """
        return all(
            [
                str(getattr(ticket, "category_name", "") or "").strip(),
                str(getattr(ticket, "issue_type_id", "") or "").strip(),
                str(getattr(ticket, "issue_type_name", "") or "").strip(),
                str(getattr(ticket, "root_cause_type", "") or "").strip(),
                str(getattr(ticket, "solution_type", "") or "").strip(),
                str(getattr(ticket, "resolution_code", "") or "").strip(),
                str(getattr(ticket, "resolution_name", "") or "").strip(),
                str(getattr(ticket, "problem_pattern_code", "") or "").strip(),
                str(getattr(ticket, "problem_pattern_name", "") or "").strip(),
                getattr(ticket, "is_problem", None) is not None,
            ]
        )

    @classmethod
    def _resolve_ai_classification_scene_for_sync_status(
        cls,
        config: dict[str, Any],
        *,
        sync_scene: str,
        previous_status: str,
        current_status: str,
    ) -> tuple[str, bool, bool, str]:
        """
        解析同步入库后应使用的 AI 分类场景。

        外部同步和远端入库也可能带来状态变更。若目标状态命中状态变更自动归类配置，则优先
        使用状态变更场景；否则继续按原入库场景执行。
        :param config: 同步自动化配置。
        :param sync_scene: 原始入库场景。
        :param previous_status: 入库前状态。
        :param current_status: 入库后状态。
        :return: (source_type, enabled_by_scene, force_reclassify, reason)。
        """
        ai_config = config.get("aiClassification") if isinstance(config.get("aiClassification"), dict) else {}
        old_status = str(previous_status or "").strip()
        new_status = str(current_status or "").strip()
        trigger_statuses = [
            str(item or "").strip()
            for item in (ai_config.get("statusChangeTriggerStatuses") or [])
            if str(item or "").strip()
        ]
        if (
            old_status
            and new_status
            and old_status != new_status
            and bool(ai_config.get("runOnStatusChange"))
            and new_status in trigger_statuses
        ):
            return (
                f"{sync_scene}_status_change_auto_category",
                True,
                bool(ai_config.get("statusChangeForceReclassify")),
                f"status_changed:{old_status}->{new_status}",
            )
        return (
            f"{sync_scene}_auto_category",
            cls._should_run_ai_classification_for_scene(config, sync_scene),
            False,
            "sync_scene",
        )

    @classmethod
    def _should_run_ai_classification_for_scene(cls, config: dict[str, Any], scene: str) -> bool:
        """
        判断指定入库场景是否启用 AI 分类统计。

        :param config: 同步自动化配置。
        :param scene: 场景 external_sync/remote_pull/manual_create/status_change/batch_reclassify。
        :return: 是否启用。
        """
        ai_config = config.get("aiClassification") if isinstance(config.get("aiClassification"), dict) else {}
        if not bool(ai_config.get("enabled")):
            return False
        normalized_scene = str(scene or "").strip()
        if (
            normalized_scene == "status_change"
            or normalized_scene.startswith("ticket_status_change")
            or "_status_change" in normalized_scene
        ):
            return bool(ai_config.get("runOnStatusChange"))
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
            "posNo": SyncUtil.safe_int(ticket_pos)
            or SyncUtil.safe_int(log_pull_hints.get("posNo"))
            or SyncUtil.safe_int(log_pull_hints.get("pos_no"))
            or SyncUtil.safe_int((sync_object.log_pull_config or {}).get("posNo"))
            or SyncUtil.safe_int((sync_object.log_pull_config or {}).get("pos_id"))
            or SyncUtil.safe_int((sync_object.log_pull_config or {}).get("posId"))
            or SyncUtil.safe_int(cls._extract_pattern(text, config.get("posPatterns"))),
            "scoNo": SyncUtil.safe_int(ticket_sco)
            or SyncUtil.safe_int(log_pull_hints.get("scoNo"))
            or SyncUtil.safe_int(log_pull_hints.get("sco_no"))
            or SyncUtil.safe_int((sync_object.log_pull_config or {}).get("scoNo"))
            or SyncUtil.safe_int((sync_object.log_pull_config or {}).get("sco_no"))
            or SyncUtil.safe_int((sync_object.log_pull_config or {}).get("scoId"))
            or SyncUtil.safe_int((sync_object.log_pull_config or {}).get("sco_id"))
            or SyncUtil.safe_int(cls._extract_pattern(text, config.get("scoPatterns"))),
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
            "delivered_at": SyncUtil.now_iso(),
            "batch_id": batch_id,
            "message": message,
            "detail": detail,
        }
        sync_state.update(
            {
                "status": status,
                "last_pulled_at": SyncUtil.now_iso(),
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
            "pushedAt": sync_object.source.pushed_at.isoformat() if sync_object.source.pushed_at else SyncUtil.now_iso(),
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
        external_fields = cls._extract_external_mapping_fields(sync_object)
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
        incoming_project_value = cls._has_incoming_project_value(sync_object, detected)
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
        incoming_module_value = cls._has_incoming_module_value(sync_object, detected)
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
        vendor_id_hint = SyncUtil.safe_int((detected or {}).get("vendorId"))
        store_id_hint = str((detected or {}).get("storeId") or "").strip()
        pos_no_hint = SyncUtil.safe_int((detected or {}).get("posNo")) or SyncUtil.safe_int((detected or {}).get("scoNo"))
        modify_time_hint = cls._resolve_auto_log_pull_modify_time(
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
        previous_status = str(getattr(ticket, "status", "") or "").strip() if ticket else ""
        payload, meta, revision = cls._build_upsert_payload(
            db,
            ticket,
            sync_object,
            detected,
            current_user,
            sync_scene=sync_scene,
        )
        if defer_post_process:
            meta["sourceStatusBefore"] = previous_status
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
            extra_data["ai_translation_source_hash"] = SyncUtil.text_sha256(origin_description)
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
        try:
            ticket = TicketDao.get_ticket_by_id(db, ticket.ticket_id) or ticket
            source_type, enabled_by_scene, force_reclassify, classify_reason = (
                cls._resolve_ai_classification_scene_for_sync_status(
                    config,
                    sync_scene=sync_scene,
                    previous_status=previous_status,
                    current_status=str(ticket.status or "").strip(),
                )
            )
            if skip_ai_analysis_due_to_update_title and not classify_reason.startswith("status_changed:"):
                category_summary = {"skipped": True, "skipReason": "更新场景且已携带标题，跳过AI分类"}
                logger.info(
                    f"外部工单同步自动分类跳过: ticket_no={sync_object.ticket_no}, "
                    f"reason=更新场景且已携带标题，未命中状态变更分类"
                )
            else:
                logger.info(
                    f"外部工单同步自动分类场景: ticket_no={sync_object.ticket_no}, "
                    f"source_type={source_type}, enabled_by_scene={enabled_by_scene}, "
                    f"force_reclassify={force_reclassify}, reason={classify_reason}"
                )
                ticket, category_summary = cls._run_auto_ticket_ai_classification(
                    db,
                    ticket=ticket,
                    title=str(sync_object.title or ticket.title or "").strip(),
                    description=str(sync_object.description or ticket.description or "").strip(),
                    current_user_name=_user_name(current_user),
                    source_type=source_type,
                    source_ref=sync_object.ticket_no,
                    force_reclassify=force_reclassify,
                    enabled_by_scene=enabled_by_scene,
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
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        """
        分发外部工单延后后处理任务。

        优先在 Celery Worker 可用时投递 Celery 任务；不可用或投递失败时由调用方回退本地后台任务。

        :param sync_payload: 外部同步入参字典。
        :param current_user_payload: 当前用户字典。
        :param sync_scene: 同步触发场景。
        :param trace_id: 日志追踪ID，用于串联入库请求与延后后处理。
        :return: 分发结果摘要。
        """
        ticket_no = str(sync_payload.get("ticketNo") or sync_payload.get("ticket_no") or "").strip()
        resolved_trace_id = str(trace_id or "").strip() or get_current_trace_id(default="")
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
                args=[sync_payload, current_user_payload, sync_scene, resolved_trace_id],
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
        trace_id: str | None = None,
    ) -> None:
        """
        执行外部工单同步的延后后处理任务（AI、自动化、群推送）。
        :param sync_payload: 外部同步入参字典。
        :param current_user_payload: 当前用户字典。
        :param sync_scene: 同步触发场景。
        :param trace_id: 日志追踪ID，用于本地后台任务日志串联。
        :return: 无。
        """
        if trace_id:
            with trace_context(trace_id):
                cls.run_deferred_sync_post_process(sync_payload, current_user_payload, sync_scene)
            return

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
                extra_data["ai_translation_source_hash"] = SyncUtil.text_sha256(origin_description)
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

        try:
            ticket = TicketDao.get_ticket_by_id(db, ticket.ticket_id) or ticket
            meta = cls._build_meta(ticket.extra_data if isinstance(ticket.extra_data, dict) else {})
            previous_status = str(meta.get("sourceStatusBefore") or "").strip()
            source_type, enabled_by_scene, force_reclassify, classify_reason = (
                cls._resolve_ai_classification_scene_for_sync_status(
                    config,
                    sync_scene=sync_scene,
                    previous_status=previous_status,
                    current_status=str(ticket.status or "").strip(),
                )
            )
            if skip_ai_analysis_due_to_update_title and not classify_reason.startswith("status_changed:"):
                logger.info(
                    f"外部工单同步延后自动分类跳过: ticket_no={sync_object.ticket_no}, "
                    f"reason=更新场景且已携带标题，未命中状态变更分类"
                )
            else:
                logger.info(
                    f"外部工单同步延后自动分类场景: ticket_no={sync_object.ticket_no}, "
                    f"source_type={source_type}, enabled_by_scene={enabled_by_scene}, "
                    f"force_reclassify={force_reclassify}, reason={classify_reason}"
                )
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
                    source_type=source_type,
                    source_ref=sync_object.ticket_no,
                    force_reclassify=force_reclassify,
                    enabled_by_scene=enabled_by_scene,
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
                resolved_vendor_id = SyncUtil.safe_int(detected.get("vendorId") or log_pull_payload.get("vendorId"))
                resolved_store_id = str(detected.get("storeId") or log_pull_payload.get("storeId") or "").strip()
                resolved_pos_no = SyncUtil.safe_int(
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
            f"ticket_nos_count={len(getattr(request, 'ticket_nos', None) or [])}, "
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

        if getattr(request, "ticket_nos", None):
            query = base_query.filter(Ticket.ticket_no.in_(request.ticket_nos))
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

    @classmethod
    def normalize_external_sync_payload(cls, payload: dict, required_fields: list[str] | None = None) -> dict:
        """
        将外部同步请求体归一化为内部同步模型入参。
        :param payload: 外部请求体，仅支持约定字段的驼峰/下划线写法
        :param required_fields: 必填字段列表，未传时使用默认外部同步契约
        :return: 可用于 TicketExternalSyncUpsertModel 校验的字典
        """
        data = dict(payload or {})
        raw_payload = dict(data)

        source = data.get("source") if isinstance(data.get("source"), dict) else {}
        ticket_no = str(compatible_field_value(data, "ticketNo", "ticket_no", default="") or "").strip()
        description = str(compatible_field_value(data, "description", "description", default="") or "").strip()
        internal_priority = str(
            compatible_field_value(data, "internalPriority", "internal_priority", default="")
            or ""
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
            "ticketStatus": str(compatible_field_value(data, "ticketStatus", "ticket_status", default="") or "").strip(),
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
        default_required_fields = [
            "ticketNo",
            "description",
            "internalPriority",
            "ticketVender",
            "ticketModle",
            "createTime",
            "reporterName",
        ]
        normalized_required_fields: list[str] = []
        for item in required_fields or default_required_fields:
            field_name = str(item or "").strip()
            if field_name and field_name not in normalized_required_fields:
                normalized_required_fields.append(field_name)
        missing_fields = [field for field in normalized_required_fields if field_value_map.get(field) in (None, "", [])]
        if missing_fields:
            raise ValueError(f"外部同步缺少必填字段: {', '.join(missing_fields)}")

        record_id = str(
            compatible_field_value(data, "recordId", "record_id", default=ticket_no) or ""
        ).strip()
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

        assignee_raw = current_assignee_raw
        assignee_name, assignee_email_from_name = extract_person_name_email(assignee_raw)
        assignee_email = current_assignee_email or assignee_email_from_name

        external_field_mapping = {
            "ticketVender": ticket_vender,
            "ticketModle": ticket_modle,
            "ticketStatus": str(compatible_field_value(data, "ticketStatus", "ticket_status", default="") or "").strip(),
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

    @staticmethod
    async def load_external_sync_payload(request: Request) -> dict:
        """
        读取外部工单同步请求体，兼容 JSON 和表单提交。
        :param request: 当前请求对象。
        :return: 原始请求数据字典。
        """
        content_type = (request.headers.get("content-type") or "").lower()
        raw_payload: dict | None = None
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
