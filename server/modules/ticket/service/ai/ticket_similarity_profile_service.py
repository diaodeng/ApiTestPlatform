"""工单相似检索画像和精确信号服务。"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from sqlalchemy.orm import Session

from modules.ticket.dao.ticket_dao import TicketDao
from modules.ticket.entity.do.ticket_do import Ticket, TicketSimilarityProfile, TicketSimilaritySignal
from modules.ticket.util.ticket_common_util import normalize_ticket_version_key
from utils.log_util import logger


class TicketSimilarityProfileService:
    """提取并持久化工单相似检索所需的结构化画像。"""

    SIGNAL_PATTERNS = {
        "error_code": re.compile(
            r"(?:错误码|error(?:\s*code)?|exception|code)\s*[:：=]?\s*"
            r"([A-Za-z][A-Za-z0-9_-]{2,31}|\d{3,8})",
            re.IGNORECASE,
        ),
        "trace_id": re.compile(r"(?:trace[_ -]?id|trace)\s*[:：=]\s*([\w-]{8,})", re.IGNORECASE),
        "request_id": re.compile(r"(?:request[_ -]?id|request)\s*[:：=]\s*([\w-]{8,})", re.IGNORECASE),
    }
    ENVIRONMENT_PATTERN = re.compile(r"(?:环境|env|environment)\s*[:：=]\s*([\w.-]+)", re.IGNORECASE)

    @classmethod
    def _source_text(cls, ticket: Ticket) -> str:
        """组合可用于规则提取的工单事实文本，不包含评论全文。"""
        extra_data = ticket.extra_data if isinstance(ticket.extra_data, dict) else {}
        raw_payload = extra_data.get("raw_payload")
        raw_text = json.dumps(raw_payload, ensure_ascii=False, default=str) if isinstance(raw_payload, dict) else ""
        return "\n".join(
            str(item).strip() for item in (ticket.title, ticket.description, raw_text) if str(item or "").strip()
        )

    @classmethod
    def _extract_values(cls, ticket: Ticket) -> tuple[str, str, list[tuple[str, str, str]]]:
        """提取环境、版本和常见精确信号，无法识别时返回空结果。"""
        text = cls._source_text(ticket)
        profile = ticket.extra_data if isinstance(ticket.extra_data, dict) else {}
        signals: list[tuple[str, str, str]] = []
        for key in ("error_codes", "errorCodes", "trace_ids", "traceIds", "request_ids", "requestIds"):
            values = profile.get(key)
            if values:
                items = values if isinstance(values, list) else [values]
                for item in items:
                    value = str(item or "").strip().casefold()
                    if value and len(value) <= 512:
                        signal_type = {
                            "error_codes": "error_code",
                            "errorCodes": "error_code",
                            "trace_ids": "trace_id",
                            "traceIds": "trace_id",
                            "request_ids": "request_id",
                            "requestIds": "request_id",
                        }[key]
                        signals.append((signal_type, value, str(item).strip()))
        environment = str(
            profile.get("environment")
            or profile.get("env")
            or (
                (profile.get("log_pull_hints") or {}).get("environment")
                if isinstance(profile.get("log_pull_hints"), dict)
                else ""
            )
            or ""
        ).strip()
        if not environment:
            matched_environment = cls.ENVIRONMENT_PATTERN.search(text)
            environment = matched_environment.group(1).strip() if matched_environment else ""
        version_value = ""
        for value in (profile.get("version_key"), profile.get("versionKey")):
            if value:
                version_value = normalize_ticket_version_key(str(value)) or str(value).strip()
                if version_value:
                    break
        if not version_value and getattr(ticket, "affected_version_id", None):
            version_value = str(ticket.affected_version_id).strip()
        for signal_type, pattern in cls.SIGNAL_PATTERNS.items():
            for match in pattern.finditer(text):
                value = (match.group(1) if match.lastindex else match.group(0)).strip().casefold()
                if value and len(value) <= 512 and (signal_type, value) not in {(item[0], item[1]) for item in signals}:
                    signals.append((signal_type, value, match.group(0).strip()))
        extra_signals = profile.get("similarity_signals")
        if isinstance(extra_signals, dict):
            for signal_type, values in extra_signals.items():
                items = values if isinstance(values, list) else [values]
                for item in items:
                    value = str(item or "").strip().casefold()
                    if value and len(value) <= 512:
                        signals.append((str(signal_type).strip(), value, str(item).strip()))
        return environment, version_value, signals

    @classmethod
    def upsert_profile(cls, db: Session, ticket: Ticket, source: str = "rule") -> TicketSimilarityProfile:
        """提取并幂等更新工单画像及精确信号；失败不阻塞主工单流程。"""
        environment, version_value, signals = cls._extract_values(ticket)
        payload = {"environment": environment, "version": version_value, "signals": sorted(signals)}
        content_hash = hashlib.sha256(
            json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()
        existing = TicketDao.get_ticket_similarity_profile(db, ticket.ticket_id)
        revision = (
            (int(existing.profile_revision or 0) + 1)
            if existing and existing.content_hash != content_hash
            else int(existing.profile_revision or 1)
            if existing
            else 1
        )
        profile = TicketSimilarityProfile(
            ticket_id=ticket.ticket_id,
            environment=environment,
            normalized_version_key=version_value,
            extraction_source=source,
            extraction_confidence=1.0 if environment or version_value or signals else None,
            profile_revision=revision,
            content_hash=content_hash,
        )
        saved = TicketDao.upsert_ticket_similarity_profile(db, profile)
        old_signals = {
            (row.signal_type, row.signal_value): row
            for row in TicketDao.list_ticket_similarity_signals(db, ticket.ticket_id)
        }
        current_keys = {(signal_type, value) for signal_type, value, _raw in signals}
        for key, row in old_signals.items():
            if key not in current_keys:
                db.delete(row)
        for signal_type, value, raw_value in signals:
            row = old_signals.get((signal_type, value)) or TicketSimilaritySignal(
                ticket_id=ticket.ticket_id, signal_type=signal_type, signal_value=value
            )
            row.raw_value = raw_value
            row.source = source
            row.confidence = 1.0
            if not row.signal_id:
                db.add(row)
        db.flush()
        logger.info(
            f"工单相似画像更新完成: ticket_id={ticket.ticket_id}, profileRevision={saved.profile_revision}, "
            f"environment={environment or '-'}, version={version_value or '-'}, signalCount={len(signals)}"
        )
        return saved

    @classmethod
    def get_metadata(cls, db: Session, ticket: Ticket) -> dict[str, Any]:
        """读取工单当前相似检索元数据，供重排和结果解释使用。"""
        profile = TicketDao.get_ticket_similarity_profile(db, ticket.ticket_id)
        signals = TicketDao.list_ticket_similarity_signals(db, ticket.ticket_id)
        return {
            "projectId": str(ticket.project_id) if ticket.project_id is not None else None,
            "moduleId": str(ticket.module_id) if ticket.module_id is not None else None,
            "version": getattr(ticket, "affected_version_id", None),
            "environment": getattr(profile, "environment", "") if profile else "",
            "signals": {"error_code": [], "trace_id": [], "request_id": []},
            "profileRevision": getattr(profile, "profile_revision", 0) if profile else 0,
        } | {
            "signals": {
                signal_type: [row.signal_value for row in signals if signal_type == row.signal_type]
                for signal_type in {row.signal_type for row in signals}
            }
        }
