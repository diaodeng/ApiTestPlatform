import json
from datetime import datetime
from typing import Any

from fastapi import HTTPException, Request
from sqlalchemy import or_
from sqlalchemy.orm import Session

from module_admin.entity.vo.user_vo import CurrentUserModel
from module_hrm.entity.vo.common_vo import CrudResponseModel
from modules.ticket.dao.ticket_dao import TicketDao
from modules.ticket.entity.do.ticket_do import Ticket, TicketEvent, TicketMessage, TicketStatusHistory
from modules.ticket.entity.vo.ticket_vo import (
    TicketBatchReclassifyRequestModel,
    TicketExternalSyncUpsertModel,
)
from modules.ticket.enums.ticket_enums import TicketAiAnalysisStatus, TicketEventType
from modules.ticket.service.ai.ticket_auto_classification_service import TicketAutoClassificationService
from modules.ticket.service.ai.ticket_light_ai_service import TicketLightAiService
from modules.ticket.service.core.ticket_service import TicketService
from modules.ticket.service.sync.ticket_external_bitable_email_service import TicketExternalBitableEmailService
from modules.ticket.service.sync.ticket_sync_automation_service import TicketSyncAutomationService
from modules.ticket.service.sync.ticket_sync_comment_service import TicketSyncCommentService
from modules.ticket.service.sync.ticket_sync_config_service import TicketSyncConfigService
from modules.ticket.service.sync.ticket_sync_delivery_service import TicketSyncDeliveryService
from modules.ticket.service.sync.ticket_sync_group_push_service import TicketSyncGroupPushService
from modules.ticket.service.sync.ticket_sync_payload_service import TicketSyncPayloadService
from modules.ticket.util.sync_util import SyncUtil
from modules.ticket.util.ticket_common_util import (
    user_id as _user_id,
)
from modules.ticket.util.ticket_common_util import (
    user_name as _user_name,
)
from utils.common_util import CamelCaseUtil
from utils.field_util import compatible_field_value, extract_person_name_email, normalize_email_text
from utils.log_util import logger


class TicketSyncService:
    """
    工单外部同步服务，统一处理外部推送、内网拉取和同步后自动化状态追踪。

    已提取的子服务（见对应文件，调用方应直接依赖对应子服务）：
    - TicketSyncConfigService (ticket_sync_config_service.py): 配置管理
    - SyncUtil (util/sync_util.py): 通用工具方法
    TODO: 后续提取 bitable / payload / remote 子服务，继续压缩本编排类职责。
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
        log_date = TicketSyncPayloadService.normalize_auto_log_pull_date_text(result.get("logDate"))

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
            previous_date = TicketSyncPayloadService.normalize_auto_log_pull_date_text(
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
                "modifyTime": TicketSyncPayloadService.normalize_auto_log_pull_date_text(
                    log_pull_payload.get("modifyTime")
                ),
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
            config = TicketSyncConfigService.load_sync_config(db)
            ai_config = config.get("aiClassification") if isinstance(config.get("aiClassification"), dict) else {}
            stat_options = (
                config.get("statClassification") if isinstance(config.get("statClassification"), dict) else {}
            )
            legacy_prompt_content = TicketAutoClassificationService.resolve_legacy_ai_classification_prompt_content(
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
                comments=TicketAutoClassificationService.build_ticket_comment_context(db, ticket_id=ticket.ticket_id),
                current_fields=TicketAutoClassificationService.build_ticket_stat_current_fields(ticket),
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
            TicketAutoClassificationService.should_run_ai_classification_for_scene(config, sync_scene),
            False,
            "sync_scene",
        )

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
        config = TicketSyncConfigService.load_sync_config(db)
        automation = sync_object.automation
        if sync_scene == "external_sync":
            sync_object = TicketExternalBitableEmailService.enrich_person_emails(config, sync_object, ticket)
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
        detected = TicketSyncAutomationService.detect_fields(
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
        payload, meta, revision = TicketSyncPayloadService.build_upsert_payload(
            db,
            ticket,
            sync_object,
            detected,
            current_user,
            sync_scene=sync_scene,
        )
        if defer_post_process:
            meta["sourceStatusBefore"] = previous_status
            meta = TicketSyncGroupPushService.set_publish_state(
                meta,
                ready=False,
                status=cls.PUBLISH_STATUS_PROCESSING_AI,
                reason="工单已入库，等待后台后处理完成",
                ai_task_status="pending",
            )
            extra_data = dict(payload.get("extra_data") or {}) if isinstance(payload.get("extra_data"), dict) else {}
            extra_data = TicketSyncPayloadService.attach_meta(extra_data, meta)
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
                step_reason_summary = TicketSyncCommentService.sync_remote_payload_comments(
                    db,
                    ticket=ticket,
                    sync_object=sync_object,
                )
                if step_reason_summary.get("skipped"):
                    step_reason_summary = TicketSyncCommentService.sync_step_reason_comments(
                        db,
                        ticket=ticket,
                        sync_object=sync_object,
                    )
            else:
                step_reason_summary = TicketSyncCommentService.sync_step_reason_comments(
                    db,
                    ticket=ticket,
                    sync_object=sync_object,
                )
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
            result["syncSummary"] = TicketSyncDeliveryService.extract_sync_summary(result.get("extraData"))
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
                ticket, category_summary = TicketAutoClassificationService.run_auto_ticket_ai_classification(
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
            automation_summary = TicketSyncAutomationService.run_sync_automation(
                db,
                ticket.ticket_id,
                sync_object,
                detected,
                current_user,
            )

        group_push_summary = None
        try:
            ticket = TicketDao.get_ticket_by_id(db, ticket.ticket_id) or ticket
            ticket, _, group_push_summary = TicketSyncGroupPushService.finalize_publish_state_after_post_process(
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
        result["syncSummary"] = TicketSyncDeliveryService.extract_sync_summary(result.get("extraData"))
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
                    _, category_result = TicketAutoClassificationService.run_auto_ticket_ai_classification(
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
