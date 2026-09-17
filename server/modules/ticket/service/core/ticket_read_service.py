import hashlib
from typing import Any

from sqlalchemy.orm import Session

from module_admin.dao.config_dao import ConfigDao
from module_hrm.entity.do.module_do import HrmModule
from module_hrm.entity.do.project_do import HrmProject
from module_hrm.enums.enums import QtrDataStatusEnum
from modules.ticket.dao.ticket_ai_dao import TicketAiDao
from modules.ticket.dao.ticket_dao import TicketDao
from modules.ticket.dao.ticket_issue_dao import TicketIssueDao
from modules.ticket.entity.do.ticket_do import Ticket
from modules.ticket.entity.vo.ticket_read_vo import (
    TicketEditModel,
    TicketMessagePageItemModel,
    TicketMessagesPageResponseModel,
    TicketSimilarItemModel,
    TicketSimilarResponseModel,
    TicketSnapshotPageItemModel,
    TicketSnapshotsPageResponseModel,
    TicketSummaryModel,
)
from modules.ticket.service.ai.ticket_ai_analysis_service import TicketAiAnalysisService
from modules.ticket.service.ai.ticket_embedding_service import TicketEmbeddingService
from modules.ticket.service.ai.ticket_prompt_service import TicketPromptService
from modules.ticket.service.ai.ticket_similar_result_cache_service import TicketSimilarResultCacheService
from modules.ticket.service.ai.ticket_similarity_query_service import TicketSimilarityQueryService
from modules.ticket.service.core.ticket_version_service import TicketVersionService
from modules.ticket.service.log_pull.ticket_log_pull_service import TicketLogPullService
from utils.common_util import CamelCaseUtil
from utils.log_util import logger


class TicketReadService:
    """工单只读拆分服务，提供轻量概览、相似工单和按需消息/快照读取。"""

    @staticmethod
    def _stringify_id(value: Any) -> str | None:
        """将可能超出 JavaScript 安全整数范围的主键序列化为字符串。"""
        if value is None or value == "":
            return None
        return str(value)

    @classmethod
    def _stringify_nested_ids(cls, value: Any) -> Any:
        """递归序列化响应中名称明确表示主键的字段。"""
        if isinstance(value, dict):
            return {
                key: (
                    cls._stringify_id(item)
                    if key == "id" or key.endswith("Id") or key.endswith("_id")
                    else cls._stringify_nested_ids(item)
                )
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [cls._stringify_nested_ids(item) for item in value]
        return value

    @classmethod
    def _attach_relation_codes(cls, db: Session, data: dict[str, Any], ticket: Ticket) -> None:
        """只读查询项目和模块业务码，不修改工单实体。"""
        if ticket.project_id:
            project = (
                db.query(HrmProject)
                .filter(
                    HrmProject.project_id == ticket.project_id,
                    HrmProject.status == QtrDataStatusEnum.normal.value,
                    HrmProject.del_flag == "0",
                )
                .first()
            )
            data["projectCode"] = str(getattr(project, "project_code", "") or "") if project else ""
        if ticket.module_id:
            module = (
                db.query(HrmModule)
                .filter(HrmModule.module_id == ticket.module_id, HrmModule.status == QtrDataStatusEnum.normal.value)
                .first()
            )
            data["moduleCode"] = str(getattr(module, "module_code", "") or "") if module else ""

    @classmethod
    def _attach_issue(cls, db: Session, data: dict[str, Any], ticket: Ticket) -> None:
        """组装当前工单的 Issue 摘要，未归因时保留空字段。"""
        issue = TicketIssueDao.get_issue_by_id(db, ticket.issue_id)
        if not issue:
            data.setdefault("issueNo", "")
            data.setdefault("issueTitle", "")
            return
        issue_data = cls._stringify_nested_ids(CamelCaseUtil.transform_result(issue))
        # Issue 摘要中的主键同样按字符串输出，避免前端精度丢失。
        for key in ("issueId", "firstTicketId", "ownerId", "projectId", "moduleId"):
            if key in issue_data:
                issue_data[key] = cls._stringify_id(issue_data[key])
        data.update(
            {
                "issueNo": issue.issue_no,
                "issueTitle": issue.title,
                "issueStatus": issue.status,
                "issueAffectedTicketCount": issue.affected_ticket_count,
                "issue": issue_data,
            }
        )

    @classmethod
    def _attach_similarity_case(cls, db: Session, data: dict[str, Any], ticket_id: int) -> None:
        """组装当前工单自身的相似处理案例摘要，供详情页展示案例状态和人工确认入口。"""
        case = TicketDao.get_ticket_similarity_case(db, ticket_id)
        if not case:
            data["similarityCase"] = {"caseStatus": "none"}
            return
        data["similarityCase"] = {
            "caseStatus": case.case_status,
            "caseSource": case.case_source,
            "caseRevision": case.case_revision,
            "reusable": bool(case.reusable),
            "rootCauseSummary": case.root_cause_summary,
            "solutionSummary": case.solution_summary,
            "evidenceSummary": case.evidence_summary,
            "investigationSummary": case.investigation_summary,
            "verifySummary": case.verify_summary,
            "verifiedBy": case.verified_by,
            "verifiedAt": case.verified_at,
            "rejectedBy": case.rejected_by,
            "rejectedAt": case.rejected_at,
            "rejectReason": case.reject_reason,
            "lastIndexStatus": case.last_index_status,
            "lastIndexError": case.last_index_error,
        }

    @classmethod
    def get_summary(cls, db: Session, ticket_id: int) -> TicketSummaryModel | None:
        """查询轻量工单概览，并返回当前三层 AI 提示词摘要。"""
        ticket = TicketDao.get_ticket_by_id(db, ticket_id)
        if not ticket:
            logger.info(f"工单概览未查询到工单 | ticket_id={ticket_id}")
            return None
        data = CamelCaseUtil.transform_result(ticket)
        data["projectName"] = str(data.get("projectName") or data.get("merchantName") or "").strip()
        data["merchantName"] = data.get("merchantName") or data["projectName"]
        TicketVersionService.attach_ticket_version_labels(db, [data])
        cls._attach_issue(db, data, ticket)
        cls._attach_relation_codes(db, data, ticket)
        cls._attach_similarity_case(db, data, ticket_id)
        # 仅读取已有摘要表中的最新一条，不触发日志、AI、向量或提示词计算。
        data["latestLogPull"] = TicketLogPullService.get_latest_summary(db, ticket_id)
        data["latestAiAnalysis"] = TicketAiAnalysisService.get_latest_summary(db, ticket_id)
        data["aiTokenSummary"] = TicketAiDao.get_ticket_token_summary(db, ticket_id)
        data["aiPromptLayers"] = TicketPromptService.resolve_prompt_layers(db, ticket)
        for key in (
            "ticketId",
            "projectId",
            "moduleId",
            "issueId",
            "reporterId",
            "currentAssigneeId",
            "firstLineAssigneeId",
            "internalOwnerId",
        ):
            if key in data:
                data[key] = cls._stringify_id(data[key])
        logger.info(f"工单轻量概览查询完成 | ticket_id={ticket_id} 未加载消息快照相似度提示词")
        return TicketSummaryModel.model_validate(data)

    @classmethod
    def get_edit_detail(cls, db: Session, ticket_id: int) -> TicketEditModel | None:
        """
        查询工单编辑回填数据。
        只保留编辑表单需要的字段：工单本体 + 版本标签 + 项目/模块业务码 + 最近一次日志拉取摘要；
        不读取消息、快照、相似检索和 AI 提示词分层，保证编辑弹窗快速打开。
        :param db: 数据库会话
        :param ticket_id: 工单ID
        :return: 工单编辑回填模型
        """
        ticket = TicketDao.get_ticket_by_id(db, ticket_id)
        if not ticket:
            logger.info(f"工单编辑详情未查询到工单 | ticket_id={ticket_id}")
            return None
        data = CamelCaseUtil.transform_result(ticket)
        # 项目名称兜底与原始描述还原，装饰口径与全量详情保持一致
        project_name = str(data.get("projectName") or data.get("merchantName") or "").strip()
        data["projectName"] = project_name
        data["merchantName"] = data.get("merchantName") or project_name
        extra_data = data.get("extraData") or {}
        description = str(data.get("description") or "").strip()
        origin_description = str(
            extra_data.get("origin_description") or extra_data.get("original_description") or ""
        ).strip()
        if not origin_description and "【AI翻译】" in description:
            origin_description = description.split("【AI翻译】", 1)[0].strip()
        data["originalDescription"] = origin_description or description
        data["aiTranslation"] = extra_data.get("ai_translation") or ""
        TicketVersionService.attach_ticket_version_labels(db, [data])
        cls._attach_relation_codes(db, data, ticket)
        # 最近一次日志拉取摘要：单条摘要表查询，供日志拉取记录页预填兜底使用
        data["latestLogPull"] = TicketLogPullService.get_latest_summary(db, ticket_id)
        # 主键与关联 ID 统一转字符串，避免前端 Number 精度失真；更新模型负责解析回整数
        for key in (
            "ticketId",
            "projectId",
            "moduleId",
            "categoryId",
            "issueId",
            "reporterId",
            "currentAssigneeId",
            "firstLineAssigneeId",
            "internalOwnerId",
            "affectedVersionId",
            "plannedFixVersionId",
            "fixedVersionId",
            "releasedVersionId",
        ):
            if key in data:
                data[key] = cls._stringify_id(data[key])
        logger.info(f"工单编辑详情查询完成 | ticket_id={ticket_id} 未加载消息快照相似度提示词")
        return TicketEditModel.model_validate(data)

    @classmethod
    def _project_similar_item(cls, item: dict[str, Any]) -> TicketSimilarItemModel:
        """将完整相似工单结果投影为允许对外返回的摘要字段。"""
        allowed = {
            "ticket_id": cls._stringify_id(item.get("ticketId") or item.get("ticket_id")) or "",
            "ticket_no": item.get("ticketNo") or item.get("ticket_no"),
            "ticket_url": item.get("ticketUrl") or item.get("ticket_url"),
            "title": item.get("title"),
            "status": item.get("status"),
            "project_name": item.get("projectName") or item.get("project_name"),
            "module_name": item.get("moduleName") or item.get("module_name"),
            "issue_type_id": cls._stringify_id(item.get("issueTypeId") or item.get("issue_type_id")),
            "issue_type_name": item.get("issueTypeName") or item.get("issue_type_name"),
            "problem_pattern_code": item.get("problemPatternCode") or item.get("problem_pattern_code"),
            "problem_pattern_name": item.get("problemPatternName") or item.get("problem_pattern_name"),
            "customer_priority": item.get("customerPriority") or item.get("customer_priority"),
            "internal_priority": item.get("internalPriority") or item.get("internal_priority"),
            "severity": item.get("severity"),
            "root_cause_type": item.get("rootCauseType") or item.get("root_cause_type"),
            "solution_type": item.get("solutionType") or item.get("solution_type"),
            "resolution_code": item.get("resolutionCode") or item.get("resolution_code"),
            "resolution_name": item.get("resolutionName") or item.get("resolution_name"),
            "root_cause": item.get("rootCause") or item.get("root_cause"),
            "solution": item.get("solution"),
            "score": float(item.get("score") or 0),
            "semantic_score": float(item.get("semanticScore") or item.get("semantic_score") or 0),
            "keyword_score": float(item.get("keywordScore") or item.get("keyword_score") or 0),
            "exact_signal_score": float(item.get("exactSignalScore") or item.get("exact_signal_score") or 0),
            "context_score": float(item.get("contextScore") or item.get("context_score") or 0),
            "match_type": item.get("matchType") or item.get("match_type") or "symptom",
            "case_status": item.get("caseStatus") or item.get("case_status") or "none",
            "match_reasons": item.get("matchReasons") or item.get("match_reasons") or [],
            "conflicts": item.get("conflicts") or [],
        }
        return TicketSimilarItemModel.model_validate(allowed)

    @classmethod
    def _build_similar_cache_key(cls, db: Session, ticket_id: int, limit: int) -> str:
        """
        构建相似结果缓存键。
        配置指纹取 sys_config 原始值哈希：相似度配置变更后自然产生新键，旧键随 TTL 淘汰。
        :param db: 数据库会话
        :param ticket_id: 源工单ID
        :param limit: 查询数量
        :return: 缓存键
        """
        fingerprint = "default"
        try:
            config_info = ConfigDao.get_config_detail_by_key(db, TicketEmbeddingService.CONFIG_KEY)
            raw_value = getattr(config_info, "config_value", None)
            # 指纹只取字符串类型的配置原文；非字符串（如 Mock、异常对象）一律回退默认指纹
            if isinstance(raw_value, str) and raw_value.strip():
                fingerprint = hashlib.sha256(raw_value.encode("utf-8")).hexdigest()[:16]
        except Exception as exc:
            logger.warning(f"相似结果缓存配置指纹获取失败，使用默认指纹: ticket_id={ticket_id}, error={exc}")
        return TicketSimilarResultCacheService.build_key(ticket_id, limit, fingerprint)

    @classmethod
    def get_similar_tickets(cls, db: Session, ticket_id: int, limit: int) -> TicketSimilarResponseModel | None:
        """查询相似工单并使用白名单字段投影，先查缓存，未命中再执行完整相似链路。"""
        if not TicketDao.get_ticket_by_id(db, ticket_id):
            logger.info(f"相似工单未查询到源工单 | ticket_id={ticket_id}")
            return None
        cache_key = cls._build_similar_cache_key(db, ticket_id, limit)
        cached = TicketSimilarResultCacheService.get(cache_key)
        if cached is not None:
            logger.info(f"相似工单查询命中缓存 | ticket_id={ticket_id} limit={limit}")
            return TicketSimilarResponseModel.model_validate(cached)
        result = TicketSimilarityQueryService.search_similar_tickets_by_ticket(db, ticket_id, limit=limit)
        items = [cls._project_similar_item(item) for item in result.get("similarTickets") or []]
        symptom_items = [cls._project_similar_item(item) for item in result.get("symptomTickets") or []]
        case_items = [cls._project_similar_item(item) for item in result.get("caseTickets") or []]
        response = TicketSimilarResponseModel(
            status=str(result.get("similarEmbeddingStatus") or "disabled"),
            message=str(result.get("similarEmbeddingMessage") or ""),
            items=items,
            symptom_tickets=symptom_items,
            case_tickets=case_items,
        )
        # 只有查询成功（非 error）才缓存；missing/stale 等待向量刷新的结果每次都重查
        if str(result.get("similarEmbeddingStatus") or "") != "error":
            TicketSimilarResultCacheService.set(cache_key, response.model_dump(by_alias=True))
        logger.info(
            f"相似工单查询完成 | ticket_id={ticket_id} limit={limit} status={response.status} count={len(items)}"
        )
        return response

    @classmethod
    def get_messages_page(cls, db: Session, ticket_id: int, limit: int) -> TicketMessagesPageResponseModel | None:
        """按需查询最近消息，保留旧消息接口的完整返回契约。"""
        if not TicketDao.get_ticket_by_id(db, ticket_id):
            return None
        rows = TicketDao.list_messages(db, ticket_id, limit=limit + 1)
        has_more = len(rows) > limit
        items = rows[-limit:] if has_more else rows
        logger.info(
            f"工单消息按需查询完成 | ticket_id={ticket_id} limit={limit} count={len(items)} has_more={has_more}"
        )
        return TicketMessagesPageResponseModel(
            items=[TicketMessagePageItemModel.model_validate(row) for row in items],
            limit=limit,
            has_more=has_more,
        )

    @classmethod
    def get_snapshots_page(cls, db: Session, ticket_id: int, limit: int) -> TicketSnapshotsPageResponseModel | None:
        """按需查询最近 ACR 快照，返回最新版本优先。"""
        if not TicketDao.get_ticket_by_id(db, ticket_id):
            return None
        rows = TicketDao.list_snapshots(db, ticket_id, limit=limit + 1)
        has_more = len(rows) > limit
        items = rows[:limit]
        logger.info(
            f"工单快照按需查询完成 | ticket_id={ticket_id} limit={limit} count={len(items)} has_more={has_more}"
        )
        return TicketSnapshotsPageResponseModel(
            items=[TicketSnapshotPageItemModel.model_validate(row) for row in items],
            limit=limit,
            has_more=has_more,
        )
