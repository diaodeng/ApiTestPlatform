"""工单相似处理案例生命周期服务。"""

from __future__ import annotations

import hashlib
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from config.database import SessionLocal
from modules.ticket.dao.ticket_dao import TicketDao
from modules.ticket.entity.do.ticket_do import Ticket, TicketEvent, TicketRca, TicketSimilarityCase
from modules.ticket.enums.ticket_enums import TicketEventType
from modules.ticket.service.ai.ticket_embedding_service import TicketEmbeddingService
from utils.log_util import logger


class TicketSimilarityCaseService:
    """管理草稿案例、已验证案例和案例索引状态。"""

    _index_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="ticket-case-index")

    @classmethod
    def build_case_payload(cls, ticket: Ticket, rca: TicketRca | None = None) -> dict[str, str]:
        """从工单 RCA 和 AI 结果读取可复用案例事实。"""
        ai_payload = ticket.ai_analysis if isinstance(ticket.ai_analysis, dict) else {}
        extra_data = ticket.extra_data if isinstance(ticket.extra_data, dict) else {}
        return {
            "symptom": str(getattr(rca, "symptom", None) or ticket.description or "").strip(),
            "evidence": str(getattr(rca, "impact_scope", None) or "\n".join(ai_payload.get("evidence") or [])).strip(),
            "investigation": str(
                getattr(rca, "investigation_process", None) or "\n".join(ai_payload.get("investigation_steps") or [])
            ).strip(),
            "rootCause": str(
                getattr(rca, "root_cause_detail", None) or ticket.root_cause or ai_payload.get("root_cause") or ""
            ).strip(),
            "solution": str(
                getattr(rca, "fix_solution", None) or ticket.solution or ai_payload.get("fix_suggestion") or ""
            ).strip(),
            "verify": str(getattr(rca, "verify_method", None) or "\n".join(ai_payload.get("next_steps") or [])).strip(),
            "version": str(extra_data.get("version_key") or extra_data.get("versionKey") or "").strip(),
            "environment": str(extra_data.get("environment") or extra_data.get("env") or "").strip(),
        }

    @classmethod
    def build_case_text(cls, payload: dict[str, str], ticket: Ticket) -> str:
        """构建案例向量文本，保留症状、证据和处理条件。"""
        return "\n".join(
            f"{label}：{payload.get(key) or ''}"
            for label, key in (
                ("问题症状", "symptom"),
                ("关键证据", "evidence"),
                ("排查过程", "investigation"),
                ("确认根因", "rootCause"),
                ("解决方案", "solution"),
                ("验证方式", "verify"),
                ("适用版本", "version"),
                ("适用环境", "environment"),
            )
            if payload.get(key) or (key == "version" and getattr(ticket, "affected_version_id", None))
        )

    @classmethod
    def upsert_draft(
        cls, db: Session, ticket: Ticket, rca: TicketRca | None = None, source: str = "ai"
    ) -> TicketSimilarityCase | None:
        """结论形成后创建或更新草稿案例；信息不足时不创建。"""
        payload = cls.build_case_payload(ticket, rca)
        if not payload["rootCause"] and not payload["solution"]:
            logger.info(f"跳过相似案例草稿: ticket_id={ticket.ticket_id}, reason=缺少根因和解决方案")
            return None
        existing = TicketDao.get_ticket_similarity_case(db, ticket.ticket_id)
        text = cls.build_case_text(payload, ticket)
        content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        status = existing.case_status if existing and existing.case_status == "verified" else "draft"
        if existing and existing.case_status == "verified" and existing.content_hash != content_hash:
            status = "draft"
        revision = (
            (int(existing.case_revision or 0) + 1)
            if existing and existing.content_hash != content_hash
            else int(existing.case_revision or 1)
            if existing
            else 1
        )
        case = TicketSimilarityCase(
            ticket_id=ticket.ticket_id,
            case_status=status,
            case_source=source,
            case_revision=revision,
            content_hash=content_hash,
            root_cause_summary=payload["rootCause"],
            solution_summary=payload["solution"],
            evidence_summary=payload["evidence"],
            investigation_summary=payload["investigation"],
            verify_summary=payload["verify"],
            reusable=status == "verified",
            last_index_status="pending",
        )
        saved = TicketDao.upsert_ticket_similarity_case(db, case)
        logger.info(
            f"相似案例草稿已更新: ticket_id={ticket.ticket_id}, status={saved.case_status}, "
            f"revision={saved.case_revision}"
        )
        return saved

    @classmethod
    def update_status(
        cls, db: Session, ticket: Ticket, status: str, operator_name: str, remark: str = ""
    ) -> TicketSimilarityCase:
        """更新案例状态；verified 需要根因、方案、证据或验证信息完整。"""
        normalized = str(status or "").strip().lower()
        if normalized not in {"draft", "verified", "rejected"}:
            raise ValueError("案例状态只支持 draft、verified 或 rejected")
        case = TicketDao.get_ticket_similarity_case(db, ticket.ticket_id) or cls.upsert_draft(db, ticket)
        if not case:
            raise ValueError("当前工单缺少可沉淀的根因或解决方案")
        if normalized == "verified" and not (
            case.root_cause_summary and case.solution_summary and (case.evidence_summary or case.verify_summary)
        ):
            raise ValueError("案例确认需要根因、解决方案以及证据或验证方式")
        now = datetime.now()
        case.case_status = normalized
        case.reusable = normalized == "verified"
        case.last_index_status = "pending"
        case.last_index_error = None
        if normalized == "verified":
            case.verified_by = operator_name or "system"
            case.verified_at = now
            case.rejected_by = None
            case.rejected_at = None
            case.reject_reason = None
        elif normalized == "rejected":
            case.reusable = False
            case.rejected_by = operator_name or "system"
            case.rejected_at = now
            case.reject_reason = remark[:2000]
        db.flush()
        logger.info(
            f"相似案例状态更新: ticket_id={ticket.ticket_id}, status={normalized}, operator={operator_name or 'system'}"
        )
        return case

    @classmethod
    def update_status_with_event(
        cls,
        db: Session,
        ticket: Ticket,
        status: str,
        operator_name: str,
        operator_id: int | None = None,
        remark: str = "",
    ) -> TicketSimilarityCase:
        """更新案例状态并写入人工操作事件，保持控制器只负责协议适配。"""
        case = cls.update_status(db, ticket, status, operator_name, remark)
        TicketDao.add_event(
            db,
            TicketEvent(
                ticket_id=ticket.ticket_id,
                event_type=TicketEventType.AI_RECOMMENDED.value,
                operator_id=operator_id,
                operator_name=operator_name,
                content=f"相似案例状态更新为 {case.case_status}",
                event_data={"caseStatus": case.case_status, "remark": remark},
            ),
        )
        db.flush()
        return case

    @classmethod
    def enqueue_index_for_ticket(cls, ticket_id: int, case_status: str | None = None) -> None:
        """事务提交后按工单投递案例索引；未指定状态时读取提交后的最新状态。"""
        cls._index_executor.submit(
            cls.index_case_with_independent_session,
            int(ticket_id),
            str(case_status) if case_status else None,
        )

    @classmethod
    def index_case_with_independent_session(
        cls, ticket_id: int, case_status: str | None, trace_id: str | None = None
    ) -> None:
        """使用独立会话生成案例向量，避免外部 Embedding 阻塞业务事务。"""
        del trace_id
        with SessionLocal() as db:
            ticket = TicketDao.get_ticket_by_id(db, ticket_id)
            case = TicketDao.get_ticket_similarity_case(db, ticket_id)
            if not ticket or not case or (case_status and case.case_status != case_status):
                logger.info(
                    f"跳过相似案例异步索引: ticket_id={ticket_id}, reason=案例不存在或状态已变化"
                )
                return
            try:
                cls.index_case(db, ticket, case)
                db.commit()
                logger.info(f"相似案例异步索引完成: ticket_id={ticket_id}, status={case.case_status}")
            except Exception as exc:
                db.rollback()
                failed_case = TicketDao.get_ticket_similarity_case(db, ticket_id)
                if failed_case:
                    failed_case.last_index_status = "failed"
                    failed_case.last_index_error = str(exc)[:2000]
                    db.commit()
                logger.warning(
                    f"相似案例异步索引失败: ticket_id={ticket_id}, status={case_status or 'latest'}, error={exc}"
                )

    @classmethod
    def index_case(
        cls, db: Session, ticket: Ticket, case: TicketSimilarityCase, config: dict[str, Any] | None = None
    ) -> bool:
        """按案例状态生成 MySQL 向量；Qdrant 本轮不参与案例生产链路。"""
        if case.case_status not in {"draft", "verified"} or (
            not case.reusable and case.case_status != "draft"
        ):
            case.last_index_status = "skipped"
            db.flush()
            return False
        scope = (
            TicketEmbeddingService.SCOPE_CASE_VERIFIED
            if case.case_status == "verified"
            else TicketEmbeddingService.SCOPE_CASE_DRAFT
        )
        rca = TicketDao.list_rca_by_ticket_ids(db, [ticket.ticket_id]).get(ticket.ticket_id)
        TicketEmbeddingService.vectorize_ticket(
            db,
            ticket,
            rca=rca,
            config=config,
            embedding_scope=scope,
            sync_qdrant=False,
        )
        case.last_index_status = "ready"
        case.last_indexed_at = datetime.now()
        case.last_index_error = None
        db.flush()
        return True
