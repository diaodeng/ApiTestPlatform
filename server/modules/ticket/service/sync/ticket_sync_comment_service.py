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
from modules.ticket.service.collaboration.ticket_comment_core_service import TicketCommentCoreService
from modules.ticket.util.sync_util import SyncUtil
from utils.log_util import logger


class TicketSyncCommentService:
    """stepReason/L1Response 排查过程评论同步。"""

    SOURCE_CODE = "external_sync"
    # 支持分段解析为评论的外部字段名，新增字段时同步扩展此处与 build_segment_field_key。
    SUPPORTED_SEGMENT_FIELDS = ("stepReason", "l1Response")

    @classmethod
    def parse_step_reason_date(cls, value: str) -> datetime | None:
        """
        解析 stepReason/L1Response 分段开头的日期并应用时间边界规则。

        边界规则：解析出的日期等于服务器本地"今天"时返回 None，
        评论时间由入库时刻兜底（避免当天记录出现 00:00:00 误导时间线）；
        非当天日期返回当天 00:00:00（表格中只写了日期，时间不可知）。

        :param value: 日期文本，支持 yyyyMMdd
        :return: 日期时间；当天日期或解析失败返回 None
        """
        text = str(value or "").strip()
        if not re.fullmatch(r"\d{8}", text):
            return None
        try:
            parsed_date = datetime.strptime(text, "%Y%m%d").date()
        except Exception:
            return None
        if parsed_date == datetime.now().date():
            logger.info(
                f"排查过程分段日期为当天，使用入库时间作为评论时间: date={text}"
            )
            return None
        return datetime.combine(parsed_date, time.min)

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
        source_field: str = "stepReason",
    ) -> str:
        """
        构建排查过程评论分段幂等键。

        stepReason 保持历史键结构（不拼字段名）以兼容已入库评论；
        其他字段（如 l1Response）把字段名拼入键，避免与 stepReason 同序号段冲突。

        :param source_system: 来源系统
        :param source_record_id: 来源记录ID
        :param segment_index: 分段序号
        :param source_field: 来源字段名
        :return: 稳定幂等键
        """
        normalized_field = str(source_field or "").strip() or "stepReason"
        key_parts = [
            str(source_system or "").strip() or cls.SOURCE_CODE,
            str(source_record_id or "").strip(),
        ]
        if normalized_field != "stepReason":
            key_parts.append(normalized_field)
        key_parts.append("stepReason" if normalized_field == "stepReason" else "segment")
        key_parts.append(str(int(segment_index or 0)))
        raw_key = "|".join(key_parts)
        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    @classmethod
    def get_step_reason_content_segments(
        cls,
        sync_object: TicketExternalSyncUpsertModel,
        *,
        source_field: str = "stepReason",
    ) -> list[dict[str, Any]]:
        """
        从同步模型中读取指定来源字段对应的富文本片段。

        :param sync_object: 外部同步入参。
        :param source_field: 来源字段名，如 stepReason/l1Response。
        :return: text/mention 片段列表。
        """
        extra_data = sync_object.extra_data if isinstance(sync_object.extra_data, dict) else {}
        field_segments = (
            extra_data.get("_bitable_field_segments")
            if isinstance(extra_data.get("_bitable_field_segments"), dict)
            else {}
        )
        candidate_keys = [source_field]
        # 驼峰转下划线：l1Response -> l1_response，兼容 extra_data 中两种键写法。
        snake_field = re.sub(r"(?<=[a-z0-9])([A-Z])", r"_\1", source_field).lower()
        if snake_field and snake_field != source_field:
            candidate_keys.append(snake_field)
        if source_field == "stepReason":
            candidate_keys.append("step_reason")
        for key in candidate_keys:
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
    def _resolve_field_text(
        cls,
        sync_object: TicketExternalSyncUpsertModel,
        *,
        source_field: str,
    ) -> str:
        """
        从同步模型中读取指定外部字段的原始文本。

        读取顺序：模型同名属性 -> extra_data（驼峰/下划线键）-> raw_payload。

        :param sync_object: 外部同步入参。
        :param source_field: 外部字段名，如 stepReason/l1Response。
        :return: 字段文本，缺失返回空字符串。
        """
        snake_field = re.sub(r"(?<=[a-z0-9])([A-Z])", r"_\1", source_field).lower()
        attr_text = str(getattr(sync_object, snake_field, "") or "").strip()
        if attr_text:
            return attr_text
        extra_data = sync_object.extra_data if isinstance(sync_object.extra_data, dict) else {}
        for key in (source_field, snake_field):
            text = str(extra_data.get(key) or "").strip()
            if text:
                return text
        raw_payload = sync_object.raw_payload if isinstance(sync_object.raw_payload, dict) else {}
        for key in (source_field, snake_field):
            text = str(raw_payload.get(key) or "").strip()
            if text:
                return text
        return ""

    @classmethod
    def sync_step_reason_comments(
        cls,
        db: Session,
        *,
        ticket: Ticket,
        sync_object: TicketExternalSyncUpsertModel,
    ) -> dict[str, Any]:
        """
        将外部排查过程类字段（stepReason/l1Response）幂等同步为工单评论。

        每个字段独立解析、独立幂等键；l1Response 评论追加一线回复标识文案。
        :param db: 数据库会话
        :param ticket: 工单对象
        :param sync_object: 外部同步入参
        :return: 同步结果摘要，按来源字段分组。
        """
        summary: dict[str, Any] = {"skipped": False, "fields": {}, "created": 0, "updated": 0, "skippedCount": 0}
        for source_field in cls.SUPPORTED_SEGMENT_FIELDS:
            field_text = cls._resolve_field_text(sync_object, source_field=source_field)
            if not field_text:
                continue
            field_summary = cls._sync_single_segment_field(
                db,
                ticket=ticket,
                sync_object=sync_object,
                source_field=source_field,
                field_text=field_text,
            )
            summary["fields"][source_field] = field_summary
            summary["created"] += field_summary.get("created") or 0
            summary["updated"] += field_summary.get("updated") or 0
            summary["skippedCount"] += field_summary.get("skippedCount") or 0
        if not summary["fields"]:
            return {
                "skipped": True,
                "reason": "empty_segment_fields",
                "created": 0,
                "updated": 0,
                "skippedCount": 0,
            }
        return summary

    @classmethod
    def _sync_single_segment_field(
        cls,
        db: Session,
        *,
        ticket: Ticket,
        sync_object: TicketExternalSyncUpsertModel,
        source_field: str,
        field_text: str,
    ) -> dict[str, Any]:
        """
        将单个排查过程类字段的分段文本幂等同步为工单评论。

        :param db: 数据库会话
        :param ticket: 工单对象
        :param sync_object: 外部同步入参
        :param source_field: 外部字段名
        :param field_text: 字段原始文本
        :return: 单字段同步结果摘要。
        """
        source_system = str(getattr(sync_object.source, "system", "") or "").strip() or cls.SOURCE_CODE
        source_record_id = str(getattr(sync_object.source, "record_id", "") or "").strip() or str(
            sync_object.ticket_no or ""
        ).strip()
        segments = cls.parse_step_reason_segments(field_text)
        rich_text_segments = cls.get_step_reason_content_segments(sync_object, source_field=source_field)
        is_l1_response = source_field == "l1Response"
        summary = {"skipped": False, "total": len(segments), "created": 0, "updated": 0, "skippedCount": 0}
        for segment in segments:
            segment_index = int(segment.get("segmentIndex") or 0)
            content = str(segment.get("content") or "").strip()
            if not content:
                continue
            segment_key = cls.build_step_reason_segment_key(
                source_system=source_system,
                source_record_id=source_record_id,
                segment_index=segment_index,
                source_field=source_field,
            )
            comment_segments = cls.slice_content_segments_for_text(
                full_text=field_text,
                content=content,
                content_segments=rich_text_segments,
            )
            # 一线回复标识：l1Response 字段产生的评论在正文末尾追加文案，随内容哈希幂等。
            display_content = f"{content}\n【一线回复】" if is_l1_response else content
            attachments: dict[str, Any] | None = None
            if comment_segments or is_l1_response:
                attachments = {
                    "sourceFieldLabel": "一线回复" if is_l1_response else "排查过程",
                }
                if comment_segments:
                    attachments["content_segments"] = comment_segments
            _, action = TicketCommentCoreService.upsert_synced_comment(
                db,
                ticket_id=ticket.ticket_id,
                content=display_content,
                user_name=str(segment.get("personName") or "").strip() or "外部同步",
                source_type="feishu_bitable",
                source_system=source_system,
                source_record_id=source_record_id,
                source_field=source_field,
                source_segment_key=segment_key,
                source_segment_index=segment_index,
                source_content_hash=str(segment.get("contentHash") or "").strip(),
                external_created_at=segment.get("externalCreatedAt"),
                attachments=attachments,
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
            _, action = TicketCommentCoreService.upsert_synced_comment(
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
