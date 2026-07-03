"""
工单 stepReason 评论同步服务：解析排查过程文本、幂等分段、同步为工单评论。
从 TicketSyncService 中提取。
"""
import hashlib
import re
from datetime import datetime, time
from typing import Any

from sqlalchemy.orm import Session

from modules.ticket.entity.do.ticket_do import Ticket
from modules.ticket.entity.vo.ticket_vo import TicketExternalSyncUpsertModel
from modules.ticket.service.ticket_service import TicketService
from modules.ticket.util.sync_util import SyncUtil


class TicketSyncCommentService:
    """stepReason 排查过程评论同步。"""

    SOURCE_CODE = "external_sync"

    @classmethod
    def parse_step_reason_date(cls, value: str) -> datetime | None:
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
            content_hash = SyncUtil.text_sha256(text)
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
                    "contentHash": SyncUtil.text_sha256(prefix),
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
                    "contentHash": SyncUtil.text_sha256(content),
                    "externalCreatedAt": cls.parse_step_reason_date(date_text),
                }
            )
        return segments

    @classmethod
    def build_step_reason_segment_key(
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
    def get_step_reason_content_segments(cls, sync_object: TicketExternalSyncUpsertModel) -> list[dict[str, Any]]:
        """
        从同步模型中读取 stepReason 对应的富文本片段。

        :param sync_object: 外部同步入参。
        :return: text/mention 片段列表。
        """
        extra_data = sync_object.extra_data if isinstance(sync_object.extra_data, dict) else {}
        field_segments = (
            extra_data.get("_bitable_field_segments")
            if isinstance(extra_data.get("_bitable_field_segments"), dict)
            else {}
        )
        for key in ("stepReason", "step_reason"):
            segments = field_segments.get(key)
            if isinstance(segments, list):
                return [item for item in segments if isinstance(item, dict)]
        return []

    @classmethod
    def slice_content_segments_for_text(
        cls,
        *,
        full_text: str,
        content: str,
        content_segments: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        从完整富文本片段中截取某段评论对应的片段。

        :param full_text: 完整 stepReason 文本。
        :param content: 当前评论正文。
        :param content_segments: 完整 stepReason 的 text/mention 片段。
        :return: 当前评论正文对应片段。
        """
        if not content or not content_segments:
            return []
        start = str(full_text or "").find(content)
        if start < 0:
            return []
        end = start + len(content)
        cursor = 0
        result: list[dict[str, Any]] = []
        for item in content_segments:
            text = str(item.get("text") or "")
            if not text:
                continue
            item_start = cursor
            item_end = cursor + len(text)
            cursor = item_end
            overlap_start = max(start, item_start)
            overlap_end = min(end, item_end)
            if overlap_start >= overlap_end:
                continue
            sliced = dict(item)
            sliced["text"] = text[overlap_start - item_start : overlap_end - item_start]
            result.append(sliced)
        return result

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
        rich_text_segments = cls.get_step_reason_content_segments(sync_object)
        summary = {"skipped": False, "total": len(segments), "created": 0, "updated": 0, "skippedCount": 0}
        for segment in segments:
            segment_index = int(segment.get("segmentIndex") or 0)
            content = str(segment.get("content") or "").strip()
            segment_key = cls.build_step_reason_segment_key(
                source_system=source_system,
                source_record_id=source_record_id,
                segment_index=segment_index,
            )
            comment_segments = cls.slice_content_segments_for_text(
                full_text=step_reason,
                content=content,
                content_segments=rich_text_segments,
            )
            _, action = TicketService.upsert_synced_comment(
                db,
                ticket_id=ticket.ticket_id,
                content=content,
                user_name=str(segment.get("personName") or "").strip() or "外部同步",
                source_type="feishu_bitable",
                source_system=source_system,
                source_record_id=source_record_id,
                source_field="stepReason",
                source_segment_key=segment_key,
                source_segment_index=segment_index,
                source_content_hash=str(segment.get("contentHash") or "").strip(),
                external_created_at=segment.get("externalCreatedAt"),
                attachments={"content_segments": comment_segments} if comment_segments else None,
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
            external_created_at = SyncUtil.parse_datetime_value(
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
                or SyncUtil.text_sha256(content),
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
