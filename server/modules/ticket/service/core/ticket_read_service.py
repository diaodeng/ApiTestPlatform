from typing import Any

from sqlalchemy.orm import Session

from module_hrm.entity.do.module_do import HrmModule
from module_hrm.entity.do.project_do import HrmProject
from module_hrm.enums.enums import QtrDataStatusEnum
from modules.ticket.dao.ticket_ai_dao import TicketAiDao
from modules.ticket.dao.ticket_dao import TicketDao
from modules.ticket.dao.ticket_issue_dao import TicketIssueDao
from modules.ticket.entity.do.ticket_do import Ticket
from modules.ticket.entity.vo.ticket_read_vo import (
    TicketMessagePageItemModel,
    TicketMessagesPageResponseModel,
    TicketSimilarItemModel,
    TicketSimilarResponseModel,
    TicketSnapshotPageItemModel,
    TicketSnapshotsPageResponseModel,
    TicketSummaryModel,
)
from modules.ticket.service.ai.ticket_ai_analysis_service import TicketAiAnalysisService
from modules.ticket.service.ai.ticket_prompt_service import TicketPromptService
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
    def get_similar_tickets(cls, db: Session, ticket_id: int, limit: int) -> TicketSimilarResponseModel | None:
        """查询相似工单并使用白名单字段投影，避免复用完整详情数据。"""
        if not TicketDao.get_ticket_by_id(db, ticket_id):
            logger.info(f"相似工单未查询到源工单 | ticket_id={ticket_id}")
            return None
        result = TicketSimilarityQueryService.search_similar_tickets_by_ticket(db, ticket_id, limit=limit)
        items = [cls._project_similar_item(item) for item in result.get("similarTickets") or []]
        response = TicketSimilarResponseModel(
            status=str(result.get("similarEmbeddingStatus") or "disabled"),
            message=str(result.get("similarEmbeddingMessage") or ""),
            items=items,
        )
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
