"""工单混合相似召回和可解释重排。"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from modules.ticket.dao.ticket_dao import TicketDao
from modules.ticket.entity.do.ticket_do import Ticket
from modules.ticket.service.ai.ticket_embedding_service import TicketEmbeddingService
from modules.ticket.service.ai.ticket_similarity_profile_service import TicketSimilarityProfileService
from utils.common_util import CamelCaseUtil


class TicketHybridSimilarityService:
    """在现有 MySQL 向量扫描基础上叠加精确信号和案例质量分。"""

    @classmethod
    def search_by_vector(
        cls,
        db: Session,
        source_ticket: Ticket,
        vector: list[float],
        limit: int,
        config: dict[str, Any],
        *,
        embedding_scopes: tuple[str, ...] | None = None,
        match_type: str = "symptom",
        include_exact_signal_candidates: bool = True,
    ) -> list[dict[str, Any]]:
        """按指定向量用途查询候选并执行可解释重排。"""
        candidate_limit = min(max(int(limit or 5) * 5, 10), 100)
        scopes = embedding_scopes or (TicketEmbeddingService.SCOPE_SYMPTOM,)
        provider = TicketEmbeddingService._normalize_provider(config.get("provider"))
        if provider == TicketEmbeddingService.PROVIDER_QDRANT:
            if match_type == "case":
                return []
            return TicketEmbeddingService.search_tickets_by_vector(
                db, vector, limit, config, exclude_ticket_id=source_ticket.ticket_id
            )
        scored: dict[int, float] = {}
        for scope in scopes:
            scope_scored = TicketEmbeddingService.search_embedding_records_by_vector(
                db, vector, candidate_limit, config, provider, embedding_scope=scope
            )
            for ticket_id, score in scope_scored.items():
                scored[ticket_id] = max(scored.get(ticket_id, 0.0), score)
        source_meta = TicketSimilarityProfileService.get_metadata(db, source_ticket)
        if include_exact_signal_candidates:
            source_signals = source_meta.get("signals") if isinstance(source_meta.get("signals"), dict) else {}
            for signal_type in ("trace_id", "request_id", "error_code"):
                signal_hits = TicketDao.list_ticket_ids_by_similarity_signals(
                    db, signal_type, list(source_signals.get(signal_type) or [])
                )
                for ticket_id in signal_hits:
                    if ticket_id != source_ticket.ticket_id:
                        scored.setdefault(ticket_id, 0.0)
        ticket_map = {row.ticket_id: row for row in TicketDao.get_tickets_by_ids(db, list(scored.keys()))}
        result: list[dict[str, Any]] = []
        for ticket_id, semantic_score in scored.items():
            candidate = ticket_map.get(ticket_id)
            if not candidate:
                continue
            candidate_meta = TicketSimilarityProfileService.get_metadata(db, candidate)
            exact_score, reasons, conflicts = cls._compare_metadata(source_meta, candidate_meta)
            case = TicketDao.get_ticket_similarity_case(db, ticket_id)
            case_status = str(case.case_status if case else "none")
            case_quality = 1.0 if case_status == "verified" else 0.45 if case_status == "draft" else 0.0
            keyword_score = cls._keyword_score(source_ticket, candidate)
            context_score = cls._context_score(source_ticket, candidate)
            final_score = (
                float(config.get("vectorWeight", 0.85)) * float(semantic_score)
                + float(config.get("keywordWeight", 0.15)) * keyword_score
                + 0.20 * exact_score
                + 0.10 * context_score
                + 0.05 * case_quality
                - 0.10 * len(conflicts)
            )
            result.append(
                {
                    **CamelCaseUtil.transform_result(candidate),
                    "ticketId": ticket_id,
                    "score": round(max(min(final_score, 1.0), -1.0), 4),
                    "semanticScore": round(float(semantic_score), 4),
                    "keywordScore": round(keyword_score, 4),
                    "exactSignalScore": round(exact_score, 4),
                    "contextScore": round(context_score, 4),
                    "caseStatus": case_status,
                    "matchType": match_type,
                    "matchReasons": reasons,
                    "conflicts": conflicts,
                }
            )
        result.sort(key=lambda item: (item["score"], item["semanticScore"]), reverse=True)
        return result[:limit]

    @staticmethod
    def _compare_metadata(source: dict[str, Any], candidate: dict[str, Any]) -> tuple[float, list[str], list[str]]:
        """比较精确信号，缺失不惩罚，明确冲突才降低分数。"""
        reasons: list[str] = []
        conflicts: list[str] = []
        exact_score = 0.0
        source_signals = source.get("signals") if isinstance(source.get("signals"), dict) else {}
        candidate_signals = candidate.get("signals") if isinstance(candidate.get("signals"), dict) else {}
        for signal_type, label, weight in (
            ("trace_id", "Trace ID", 0.55),
            ("request_id", "Request ID", 0.45),
            ("error_code", "错误码", 0.35),
        ):
            left = set(source_signals.get(signal_type) or [])
            right = set(candidate_signals.get(signal_type) or [])
            if left and right and left & right:
                exact_score += weight
                reasons.append(f"{label}一致")
            elif left and right and not left & right and signal_type == "error_code":
                conflicts.append(f"{label}不同")
        if source.get("environment") and candidate.get("environment"):
            if source["environment"] == candidate["environment"]:
                exact_score += 0.20
                reasons.append("环境一致")
            else:
                conflicts.append("环境不同")
        if source.get("projectId") and candidate.get("projectId"):
            if source["projectId"] == candidate["projectId"]:
                exact_score += 0.20
                reasons.append("项目一致")
            else:
                conflicts.append("项目不同")
        if source.get("moduleId") and candidate.get("moduleId"):
            if source["moduleId"] == candidate["moduleId"]:
                exact_score += 0.15
                reasons.append("模块一致")
            else:
                conflicts.append("模块不同")
        return min(exact_score, 1.0), reasons, conflicts

    @staticmethod
    def _keyword_score(source: Ticket, candidate: Ticket) -> float:
        """用稳定的标题/描述词集合计算轻量关键词重合度。"""

        def words(ticket: Ticket) -> set[str]:
            text = f"{ticket.title or ''} {ticket.description or ''}".casefold()
            return {item for item in text.split() if len(item) >= 2}

        left, right = words(source), words(candidate)
        return round(len(left & right) / max(len(left | right), 1), 4)

    @staticmethod
    def _context_score(source: Ticket, candidate: Ticket) -> float:
        """按项目、模块和版本主数据计算可解释上下文分。"""
        values = []
        for left, right in (
            (source.project_id, candidate.project_id),
            (source.module_id, candidate.module_id),
            (getattr(source, "affected_version_id", None), getattr(candidate, "affected_version_id", None)),
        ):
            if left is not None and right is not None:
                values.append(1.0 if left == right else 0.0)
        return sum(values) / len(values) if values else 0.0
