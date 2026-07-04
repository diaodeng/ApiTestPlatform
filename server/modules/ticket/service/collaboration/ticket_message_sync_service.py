import hashlib
import json
import re
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from modules.ticket.dao.ticket_dao import TicketDao
from modules.ticket.entity.do.ticket_do import Ticket
from modules.ticket.service.collaboration.ticket_comment_core_service import TicketCommentCoreService
from modules.ticket.service.sync.ticket_sync_config_service import TicketSyncConfigService
from modules.ticket.service.sync.ticket_sync_notify_service import TicketSyncNotifyService
from modules.ticket.util.ticket_feishu_bitable_util import FeishuBitableUtil
from utils.log_util import logger


class TicketMessageSyncService:
    """
    工单评论多端同步服务，处理飞书话题消息入站、评论幂等和可选多维表格回写。
    """

    SOURCE_TYPE_FEISHU_THREAD = "feishu_thread"
    META_KEY = "external_sync"

    @classmethod
    def _safe_getattr(cls, target: Any, name: str, default: Any = None) -> Any:
        """
        安全读取 SDK 对象或字典字段。
        :param target: SDK 模型对象或字典
        :param name: 字段名
        :param default: 字段不存在时的默认值
        :return: 字段值
        """
        if isinstance(target, dict):
            return target.get(name, default)
        return getattr(target, name, default)

    @classmethod
    def _build_payload_from_lark_sdk_event(cls, sdk_event: Any) -> dict[str, Any]:
        """
        将飞书官方 SDK 长连接事件转换为 webhook 等价事件体。
        :param sdk_event: lark_oapi 推送的 P2ImMessageReceiveV1 事件对象
        :return: 可复用 handle_feishu_message_event 的标准事件字典
        """
        header = cls._safe_getattr(sdk_event, "header", None)
        event_data = cls._safe_getattr(sdk_event, "event", None)
        sender = cls._safe_getattr(event_data, "sender", None)
        sender_id = cls._safe_getattr(sender, "sender_id", None)
        message = cls._safe_getattr(event_data, "message", None)
        message_mentions = cls._safe_getattr(message, "mentions", [])
        return {
            "schema": cls._safe_getattr(sdk_event, "schema", ""),
            "header": {
                "event_id": cls._safe_getattr(header, "event_id", ""),
                "token": cls._safe_getattr(header, "token", ""),
                "create_time": cls._safe_getattr(header, "create_time", ""),
                "event_type": cls._safe_getattr(header, "event_type", "im.message.receive_v1"),
                "tenant_key": cls._safe_getattr(header, "tenant_key", ""),
                "app_id": cls._safe_getattr(header, "app_id", ""),
            },
            "event": {
                "sender": {
                    "sender_id": {
                        "user_id": cls._safe_getattr(sender_id, "user_id", ""),
                        "open_id": cls._safe_getattr(sender_id, "open_id", ""),
                        "union_id": cls._safe_getattr(sender_id, "union_id", ""),
                    },
                    "sender_type": cls._safe_getattr(sender, "sender_type", ""),
                    "tenant_key": cls._safe_getattr(sender, "tenant_key", ""),
                },
                "message": {
                    "message_id": cls._safe_getattr(message, "message_id", ""),
                    "root_id": cls._safe_getattr(message, "root_id", ""),
                    "parent_id": cls._safe_getattr(message, "parent_id", ""),
                    "create_time": cls._safe_getattr(message, "create_time", ""),
                    "update_time": cls._safe_getattr(message, "update_time", ""),
                    "chat_id": cls._safe_getattr(message, "chat_id", ""),
                    "thread_id": cls._safe_getattr(message, "thread_id", ""),
                    "chat_type": cls._safe_getattr(message, "chat_type", ""),
                    "message_type": cls._safe_getattr(message, "message_type", ""),
                    "content": cls._safe_getattr(message, "content", ""),
                    "mentions": message_mentions if isinstance(message_mentions, list) else [],
                },
            },
        }

    @classmethod
    def handle_feishu_sdk_message_event(cls, db: Session, sdk_event: Any) -> dict[str, Any]:
        """
        处理飞书官方 SDK 长连接消息事件。
        :param db: 数据库会话
        :param sdk_event: lark_oapi 长连接回调事件对象
        :return: 处理结果摘要
        """
        payload = cls._build_payload_from_lark_sdk_event(sdk_event)
        return cls.handle_feishu_message_event(db, payload, inbound_channel="ws")

    @classmethod
    def _text_sha256(cls, value: Any) -> str:
        """
        计算评论内容哈希，用于跨来源去重。
        :param value: 原始内容
        :return: SHA256 摘要
        """
        normalized = str(value or "").strip()
        if not normalized:
            return ""
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    @classmethod
    def _extract_mention_key(cls, value: Any) -> str:
        """
        从飞书 mention 对象中提取正文占位符 key。
        :param value: mention 原始对象
        :return: `@_user_1` 这类占位符；缺失返回空字符串
        """
        if not isinstance(value, dict):
            return ""
        return str(value.get("key") or value.get("mention_key") or value.get("mentionKey") or "").strip()

    @classmethod
    def _extract_mention_name(cls, value: Any) -> str:
        """
        从飞书 mention 对象中提取展示名称。
        :param value: mention 原始对象
        :return: 用户展示名称；缺失返回空字符串
        """
        if not isinstance(value, dict):
            return ""
        raw_id = value.get("id") if isinstance(value.get("id"), dict) else {}
        for item in (
            value.get("name"),
            value.get("user_name"),
            value.get("userName"),
            raw_id.get("name"),
            raw_id.get("user_name"),
            raw_id.get("userName"),
        ):
            text = str(item or "").strip()
            if text:
                return text
        return ""

    @classmethod
    def _extract_mention_open_id(cls, value: Any) -> str:
        """
        从飞书 mention 对象中提取 open_id。
        :param value: mention 原始对象
        :return: open_id；缺失返回空字符串
        """
        if not isinstance(value, dict):
            return ""
        raw_id = value.get("id") if isinstance(value.get("id"), dict) else {}
        return str(
            value.get("open_id")
            or value.get("openId")
            or raw_id.get("open_id")
            or raw_id.get("openId")
            or ""
        ).strip()

    @classmethod
    def _extract_mention_user_id(cls, value: Any) -> str:
        """
        从飞书 mention 对象中提取 user_id。
        :param value: mention 原始对象
        :return: user_id；缺失返回空字符串
        """
        if not isinstance(value, dict):
            return ""
        raw_id = value.get("id") if isinstance(value.get("id"), dict) else {}
        return str(
            value.get("user_id")
            or value.get("userId")
            or raw_id.get("user_id")
            or raw_id.get("userId")
            or ""
        ).strip()

    @classmethod
    def _extract_mention_union_id(cls, value: Any) -> str:
        """
        从飞书 mention 对象中提取 union_id。
        :param value: mention 原始对象
        :return: union_id；缺失返回空字符串
        """
        if not isinstance(value, dict):
            return ""
        raw_id = value.get("id") if isinstance(value.get("id"), dict) else {}
        return str(
            value.get("union_id")
            or value.get("unionId")
            or raw_id.get("union_id")
            or raw_id.get("unionId")
            or ""
        ).strip()

    @classmethod
    def _normalize_message_mentions(cls, mentions: Any) -> list[dict[str, Any]]:
        """
        归一化飞书消息 mentions，建立正文占位符到用户信息的映射。
        :param mentions: 飞书 message.mentions 原始值
        :return: 归一化后的 mention 列表
        """
        if not isinstance(mentions, list):
            return []
        result: list[dict[str, Any]] = []
        seen_keys: set[str] = set()
        for item in mentions:
            if not isinstance(item, dict):
                continue
            key = cls._extract_mention_key(item)
            if not key or key in seen_keys:
                continue
            open_id = cls._extract_mention_open_id(item)
            name = cls._extract_mention_name(item) or open_id or key
            result.append(
                {
                    "key": key,
                    "name": name,
                    "openId": open_id,
                    "userId": cls._extract_mention_user_id(item),
                    "unionId": cls._extract_mention_union_id(item),
                }
            )
            seen_keys.add(key)
        return result

    @classmethod
    def _replace_mention_keys_with_names(cls, text: str, mentions: list[dict[str, Any]]) -> str:
        """
        将飞书正文里的 `@_user_1` 占位符替换为 `@用户名`。
        :param text: 原始消息文本
        :param mentions: 归一化 mention 列表
        :return: 可读文本
        """
        result = str(text or "")
        for mention in mentions:
            key = str(mention.get("key") or "").strip()
            name = str(mention.get("name") or "").strip()
            if key and name:
                result = result.replace(key, f"@{name}")
        return result.strip()

    @classmethod
    def _build_text_segments_from_mentions(cls, text: str, mentions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        根据可读文本和 mention 元数据构建内部片段，便于外发时恢复 @。
        :param text: 可读文本
        :param mentions: 归一化 mention 列表
        :return: text/mention 片段列表
        """
        source = str(text or "")
        if not source:
            return []
        segments: list[dict[str, Any]] = []
        position = 0
        while position < len(source):
            next_match: tuple[int, dict[str, Any], str] | None = None
            for mention in mentions:
                name = str(mention.get("name") or "").strip()
                if not name:
                    continue
                token = f"@{name}"
                index = source.find(token, position)
                if index >= 0 and (next_match is None or index < next_match[0]):
                    next_match = (index, mention, token)
            if next_match is None:
                segments.append({"type": "text", "text": source[position:]})
                break
            index, mention, token = next_match
            if index > position:
                segments.append({"type": "text", "text": source[position:index]})
            segments.append(
                {
                    "type": "mention",
                    "text": token,
                    "name": mention.get("name"),
                    "openId": mention.get("openId"),
                    "userId": mention.get("userId"),
                    "unionId": mention.get("unionId"),
                    "key": mention.get("key"),
                }
            )
            position = index + len(token)
        return [item for item in segments if str(item.get("text") or "")]

    @classmethod
    def _build_bitable_text_value_from_segments(cls, segments: list[dict[str, Any]]) -> str | list[dict[str, Any]]:
        """
        将内部片段转换为多维表格文本字段值。
        :param segments: text/mention 片段列表
        :return: 含 mention_user_id 的富文本片段数组；无 mention 时返回纯文本
        """
        if not segments:
            return ""
        has_mentions = any(item.get("type") == "mention" for item in segments)
        if not has_mentions:
            return "".join(str(item.get("text") or "") for item in segments)
        result: list[dict[str, Any]] = []
        for item in segments:
            text = str(item.get("text") or "")
            if not text:
                continue
            if item.get("type") == "mention":
                segment = {"type": "mention", "text": text}
                mention_user_id = str(item.get("openId") or item.get("userId") or "").strip()
                if mention_user_id:
                    segment["mention_user_id"] = mention_user_id
                result.append(segment)
            else:
                result.append({"type": "text", "text": text})
        return result

    @classmethod
    def _build_feishu_text_from_segments(cls, segments: list[dict[str, Any]]) -> str:
        """
        将内部片段转换为飞书文本消息正文。
        :param segments: text/mention 片段列表
        :return: 包含 `<at user_id="..."></at>` 的飞书文本
        """
        parts: list[str] = []
        for item in segments:
            text = str(item.get("text") or "")
            if item.get("type") == "mention":
                open_id = str(item.get("openId") or "").strip()
                parts.append(f'<at user_id="{open_id}"></at>' if open_id else text)
            else:
                parts.append(text)
        return "".join(parts).strip()

    @classmethod
    def _extract_content_segments_from_attachments(cls, attachments: Any) -> list[dict[str, Any]]:
        """
        从评论附件或消息附件中读取正文片段。
        :param attachments: 评论 attachments 字段
        :return: text/mention 片段列表
        """
        if not isinstance(attachments, dict):
            return []
        for key in ("content_segments", "contentSegments"):
            value = attachments.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        comment_attachments = attachments.get("comment_attachments")
        if isinstance(comment_attachments, dict):
            return cls._extract_content_segments_from_attachments(comment_attachments)
        return []

    @classmethod
    def _parse_datetime_value(cls, value: Any) -> datetime | None:
        """
        解析飞书事件时间。
        :param value: 秒/毫秒时间戳、datetime 或字符串
        :return: datetime；解析失败返回 None
        """
        if isinstance(value, datetime):
            return value
        if value in (None, ""):
            return None
        if isinstance(value, (int, float)):
            timestamp = float(value)
            if timestamp > 10_000_000_000:
                timestamp = timestamp / 1000
            try:
                return datetime.fromtimestamp(timestamp)
            except Exception:
                return None
        text = str(value or "").strip()
        if not text:
            return None
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).replace(tzinfo=None)
        except Exception:
            return None

    @classmethod
    def _extract_sender_open_id(cls, event: dict[str, Any]) -> str:
        """
        从飞书事件中提取发送人 open_id。
        :param event: 飞书事件体
        :return: open_id，缺失返回空字符串
        """
        sender = event.get("sender") if isinstance(event.get("sender"), dict) else {}
        sender_id = sender.get("sender_id") if isinstance(sender.get("sender_id"), dict) else {}
        return str(sender_id.get("open_id") or sender_id.get("openId") or "").strip()

    @classmethod
    def _extract_sender_name(cls, event: dict[str, Any]) -> str:
        """
        从飞书事件中提取发送人名称。
        :param event: 飞书事件体
        :return: 发送人名称
        """
        sender = event.get("sender") if isinstance(event.get("sender"), dict) else {}
        sender_id = sender.get("sender_id") if isinstance(sender.get("sender_id"), dict) else {}
        return str(
            sender.get("sender_name")
            or sender.get("name")
            or sender_id.get("union_id")
            or sender_id.get("open_id")
            or "飞书用户"
        ).strip()

    @classmethod
    def _resolve_sender_display_name(
        cls,
        *,
        sync_config: dict[str, Any],
        event: dict[str, Any],
        sender_open_id: str,
    ) -> str:
        """
        将飞书消息发送人解析为可读用户名，避免把 open_id/union_id 直接写入评论。

        :param sync_config: 工单同步配置。
        :param event: 飞书消息事件。
        :param sender_open_id: 发送人 open_id。
        :return: 可读用户名；查询失败时返回事件自带名称或 ID 兜底。
        """
        event_name = cls._extract_sender_name(event)
        if not sender_open_id:
            return event_name

        feishu_auth = sync_config.get("feishuAuth") if isinstance(sync_config.get("feishuAuth"), dict) else {}
        group_config = sync_config.get("groupPush") if isinstance(sync_config.get("groupPush"), dict) else {}
        bitable_config = TicketSyncConfigService.resolve_bitable_runtime_config(
            sync_config,
            "bitablePull",
            TicketSyncConfigService.default_bitable_pull_config(),
        )
        app_id, app_secret = TicketSyncNotifyService.resolve_feishu_auth(
            {**bitable_config, **group_config, **feishu_auth}
        )
        if not app_id or not app_secret:
            return event_name

        feishu_user = TicketSyncNotifyService.query_feishu_user_by_open_id(
            app_id=app_id,
            app_secret=app_secret,
            open_id=sender_open_id,
        )
        resolved_name = str((feishu_user or {}).get("name") or "").strip()
        if resolved_name:
            return resolved_name
        return event_name

    @classmethod
    def _extract_message_text(cls, message: dict[str, Any]) -> str:
        """
        从飞书 text/post 消息中提取纯文本内容。
        :param message: 飞书 message 对象
        :return: 纯文本内容
        """
        msg_type = str(message.get("message_type") or message.get("messageType") or "").strip()
        raw_content = message.get("content")
        try:
            content = json.loads(raw_content) if isinstance(raw_content, str) else raw_content
        except Exception:
            content = raw_content
        if msg_type == "text":
            if isinstance(content, dict):
                return str(content.get("text") or "").strip()
            return str(content or "").strip()
        if msg_type == "post" and isinstance(content, dict):
            return cls._parse_post_text(content).strip()
        if isinstance(content, dict):
            return json.dumps(content, ensure_ascii=False)
        return str(content or "").strip()

    @classmethod
    def _extract_message_text_bundle(cls, message: dict[str, Any]) -> dict[str, Any]:
        """
        提取飞书消息正文和 mentions，生成系统展示与外部写回共用的文本结构。
        :param message: 飞书 message 对象
        :return: 包含 text/rawText/mentions/segments 的消息文本包
        """
        raw_text = cls._extract_message_text(message)
        mentions = cls._normalize_message_mentions(message.get("mentions"))
        display_text = cls._replace_mention_keys_with_names(raw_text, mentions)
        return {
            "text": display_text,
            "rawText": raw_text,
            "mentions": mentions,
            "segments": cls._build_text_segments_from_mentions(display_text, mentions),
        }

    @classmethod
    def _parse_post_text(cls, post: dict[str, Any]) -> str:
        """
        将飞书富文本 post 消息解析为纯文本。
        :param post: post 消息 JSON
        :return: 拼接后的文本
        """
        content = post.get("content")
        if isinstance(content, dict):
            content = content.get("content")
        text_parts: list[str] = []
        for paragraph in content if isinstance(content, list) else []:
            if not isinstance(paragraph, list):
                continue
            for element in paragraph:
                if not isinstance(element, dict):
                    continue
                tag = str(element.get("tag") or "").strip()
                if tag == "text":
                    text_parts.append(str(element.get("text") or ""))
                elif tag == "at":
                    text_parts.append(f"@{element.get('user_name') or element.get('userName') or 'unknown'}")
                elif tag in {"a", "link"}:
                    text_parts.append(str(element.get("text") or element.get("href") or ""))
            text_parts.append("\n")
        return "".join(text_parts).strip()

    @classmethod
    def _extract_ticket_no_from_text(cls, text: str) -> str:
        """
        从消息文本中识别工单号。
        :param text: 消息文本
        :return: 工单号；未命中返回空字符串
        """
        match = re.search(r"\b(?:INC|TK|JD|TI)[A-Z0-9_-]*\d{3,}\b", str(text or ""), flags=re.IGNORECASE)
        return match.group(0).strip() if match else ""

    @classmethod
    def _iter_ticket_group_message_refs(cls, ticket: Ticket) -> list[dict[str, Any]]:
        """
        读取工单已记录的飞书群消息锚点。
        :param ticket: 工单对象
        :return: 消息锚点列表
        """
        extra_data = ticket.extra_data if isinstance(ticket.extra_data, dict) else {}
        raw_meta = extra_data.get(cls.META_KEY)
        meta = raw_meta if isinstance(raw_meta, dict) else {}
        sync_state = meta.get("sync_state") if isinstance(meta.get("sync_state"), dict) else {}
        raw_refs = sync_state.get("group_push_message_refs")
        refs = raw_refs if isinstance(raw_refs, list) else []
        return [item for item in refs if isinstance(item, dict)]

    @classmethod
    def _match_ticket_by_message_context(
        cls,
        db: Session,
        *,
        chat_id: str,
        root_id: str,
        thread_id: str,
        text: str,
    ) -> Ticket | None:
        """
        根据飞书消息上下文匹配本地工单。
        :param db: 数据库会话
        :param chat_id: 飞书群 chat_id
        :param root_id: 飞书根消息 ID
        :param thread_id: 飞书话题 ID
        :param text: 消息文本
        :return: 匹配到的工单
        """
        candidates = []
        if root_id:
            candidates.append(root_id)
        if thread_id:
            candidates.append(thread_id)
        if chat_id:
            candidates.append(chat_id)
        if candidates:
            rows = db.query(Ticket).filter(Ticket.del_flag == "0").all()
            for ticket in rows:
                for ref in cls._iter_ticket_group_message_refs(ticket):
                    ref_values = {
                        str(ref.get("messageId") or "").strip(),
                        str(ref.get("rootId") or "").strip(),
                        str(ref.get("threadId") or "").strip(),
                    }
                    ref_chat_id = str(ref.get("chatId") or ref.get("receiveId") or "").strip()
                    if ref_chat_id and chat_id and ref_chat_id != chat_id:
                        continue
                    if any(candidate and candidate in ref_values for candidate in candidates):
                        return ticket
        ticket_no = cls._extract_ticket_no_from_text(text)
        if ticket_no:
            return TicketDao.get_ticket_by_no(db, ticket_no)
        return None

    @classmethod
    def _build_feishu_source_segment_key(cls, message_id: str) -> str:
        """
        构建飞书消息评论幂等键。
        :param message_id: 飞书消息 ID
        :return: 幂等键
        """
        normalized_message_id = str(message_id or "").strip()
        if not normalized_message_id:
            return ""
        return hashlib.sha256(f"feishu_thread|{normalized_message_id}".encode()).hexdigest()

    @classmethod
    def _resolve_bitable_record_id(cls, ticket: Ticket) -> str:
        """
        从工单扩展信息中解析多维表格记录 ID。
        :param ticket: 工单对象
        :return: record_id；缺失返回空字符串
        """
        extra_data = ticket.extra_data if isinstance(ticket.extra_data, dict) else {}
        for key in ("bitable_pull", "external_field_mapping"):
            payload = extra_data.get(key) if isinstance(extra_data.get(key), dict) else {}
            record_id = str(
                payload.get("recordId")
                or payload.get("record_id")
                or payload.get("bitableRecordId")
                or payload.get("bitable_record_id")
                or ""
            ).strip()
            if record_id:
                return record_id
        raw_meta = extra_data.get(cls.META_KEY)
        meta = raw_meta if isinstance(raw_meta, dict) else {}
        source = meta.get("source") if isinstance(meta.get("source"), dict) else {}
        return str(source.get("recordId") or source.get("record_id") or "").strip()

    @classmethod
    def _format_step_reason_line(
        cls,
        *,
        config: dict[str, Any],
        user_name: str,
        content: str,
        created_at: datetime | None,
    ) -> str:
        """
        按配置格式化追加到多维表格排查过程的单行内容。
        :param config: messageSync 配置
        :param user_name: 评论人
        :param content: 评论内容
        :param created_at: 评论时间
        :return: 格式化后的文本
        """
        date_text = (created_at or datetime.now()).strftime("%Y%m%d")
        template = str(config.get("appendStepReasonFormat") or "{date} {user}：{content}").strip()
        try:
            return template.format(date=date_text, user=user_name or "飞书用户", content=content)
        except Exception:
            return f"{date_text} {user_name or '飞书用户'}：{content}"

    @classmethod
    def _build_step_reason_segments(
        cls,
        *,
        line_text: str,
        content: str,
        content_segments: list[dict[str, Any]] | None,
    ) -> list[dict[str, Any]]:
        """
        将排查过程追加行拆成多维表格可写片段，保留正文中的 @ 人员信息。
        :param line_text: 已格式化的完整追加行
        :param content: 评论正文
        :param content_segments: 评论正文的 text/mention 片段
        :return: 完整追加行片段
        """
        normalized_content = str(content or "")
        segments = content_segments if isinstance(content_segments, list) else []
        if not normalized_content or not segments:
            return [{"type": "text", "text": line_text}]
        prefix, matched, suffix = str(line_text or "").partition(normalized_content)
        if not matched:
            return [{"type": "text", "text": line_text}]
        result: list[dict[str, Any]] = []
        if prefix:
            result.append({"type": "text", "text": prefix})
        result.extend(segments)
        if suffix:
            result.append({"type": "text", "text": suffix})
        return result

    @classmethod
    def append_comment_to_bitable_step_reason(
        cls,
        db: Session,
        *,
        ticket: Ticket,
        content: str,
        user_name: str,
        created_at: datetime | None,
        content_segments: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """
        将评论追加写回飞书多维表格排查过程字段。
        :param db: 数据库会话
        :param ticket: 工单对象
        :param content: 评论内容
        :param user_name: 评论人
        :param created_at: 评论时间
        :param content_segments: 评论正文片段，用于恢复多维表格 @ 人员样式
        :return: 写回结果摘要
        """
        sync_config = TicketSyncConfigService.load_sync_config(db)
        message_config = sync_config.get("messageSync") if isinstance(sync_config.get("messageSync"), dict) else {}
        bitable_config = TicketSyncConfigService.resolve_bitable_runtime_config(
            sync_config,
            "bitablePull",
            TicketSyncConfigService.default_bitable_pull_config(),
        )
        record_id = cls._resolve_bitable_record_id(ticket)
        field_name = str(message_config.get("bitableStepReasonField") or "stepReason").strip() or "stepReason"
        if not record_id:
            return {"skipped": True, "reason": "missing_bitable_record_id"}
        if not bool(bitable_config.get("appToken")) or not bool(bitable_config.get("tableId")):
            return {"skipped": True, "reason": "missing_bitable_config"}
        try:
            current_fields = TicketSyncNotifyService.get_bitable_record_fields(
                config=bitable_config,
                record_id=record_id,
            )
            old_text = FeishuBitableUtil.normalize_record_scalar(
                current_fields.get(field_name),
                join_separator="\n",
            )
            append_line = cls._format_step_reason_line(
                config=message_config,
                user_name=user_name,
                content=content,
                created_at=created_at,
            )
            if append_line and append_line in old_text:
                return {"skipped": True, "reason": "line_already_exists", "recordId": record_id}
            if content_segments:
                append_segments = cls._build_step_reason_segments(
                    line_text=append_line,
                    content=content,
                    content_segments=content_segments,
                )
                merged_segments: list[dict[str, Any]] = []
                if old_text:
                    merged_segments.append({"type": "text", "text": f"{old_text.rstrip()}\n"})
                merged_segments.extend(append_segments)
                new_text = cls._build_bitable_text_value_from_segments(merged_segments)
            else:
                new_text = f"{old_text.rstrip()}\n{append_line}".strip() if old_text else append_line
            TicketSyncNotifyService.update_bitable_record_fields(
                config=bitable_config,
                record_id=record_id,
                fields={field_name: new_text},
            )
            logger.info(
                f"飞书评论已写回多维表格: ticket_no={ticket.ticket_no}, record_id={record_id}, field={field_name}"
            )
            return {"skipped": False, "recordId": record_id, "field": field_name}
        except Exception as exc:
            logger.warning(
                f"飞书评论写回多维表格失败: ticket_no={ticket.ticket_no}, "
                f"record_id={record_id}, error={exc}"
            )
            return {"skipped": True, "reason": str(exc), "recordId": record_id}

    @classmethod
    def _resolve_feishu_reply_anchor(cls, ticket: Ticket) -> str:
        """
        从工单群推送锚点中解析可回复的飞书消息 ID。
        :param ticket: 工单对象
        :return: 根消息 ID 或消息 ID；缺失返回空字符串
        """
        refs = cls._iter_ticket_group_message_refs(ticket)
        if not refs:
            return ""
        latest = refs[-1]
        return str(latest.get("rootId") or latest.get("messageId") or "").strip()

    @classmethod
    def sync_local_comment_outbound(
        cls,
        db: Session,
        *,
        ticket: Ticket,
        content: str,
        user_name: str,
        created_at: datetime | None = None,
        attachments: dict[str, Any] | list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """
        本地工单评论创建后，按配置同步到多维表格和飞书话题。
        :param db: 数据库会话
        :param ticket: 工单对象
        :param content: 评论内容
        :param user_name: 评论人
        :param created_at: 评论创建时间
        :param attachments: 评论附件或引用信息
        :return: 出站同步结果摘要
        """
        sync_config = TicketSyncConfigService.load_sync_config(db)
        message_config = sync_config.get("messageSync") if isinstance(sync_config.get("messageSync"), dict) else {}
        if not bool(message_config.get("enabled")):
            return {"skipped": True, "reason": "message_sync_disabled"}

        bitable_result = {"skipped": True, "reason": "syncTicketCommentToBitable=false"}
        if bool(message_config.get("syncTicketCommentToBitable")):
            bitable_result = cls.append_comment_to_bitable_step_reason(
                db,
                ticket=ticket,
                content=content,
                user_name=user_name,
                created_at=created_at,
            )

        feishu_result = {"skipped": True, "reason": "syncTicketCommentToFeishuThread=false"}
        if bool(message_config.get("syncTicketCommentToFeishuThread")):
            group_config = sync_config.get("groupPush") if isinstance(sync_config.get("groupPush"), dict) else {}
            app_id, app_secret = TicketSyncNotifyService.resolve_feishu_auth(group_config)
            anchor_message_id = cls._resolve_feishu_reply_anchor(ticket)
            if not anchor_message_id:
                feishu_result = {"skipped": True, "reason": "missing_group_message_anchor"}
            elif not app_id or not app_secret:
                feishu_result = {"skipped": True, "reason": "missing_feishu_app_config"}
            else:
                content_segments = cls._extract_content_segments_from_attachments(attachments)
                feishu_content = cls._build_feishu_text_from_segments(content_segments) if content_segments else content
                reply_content = f"{user_name or '系统用户'}：{feishu_content}"
                try:
                    feishu_result = TicketSyncNotifyService.send_feishu_thread_reply(
                        app_id=app_id,
                        app_secret=app_secret,
                        message_id=anchor_message_id,
                        content=reply_content,
                        reply_in_thread=True,
                    )
                    feishu_result["skipped"] = False
                except Exception as exc:
                    logger.warning(f"系统评论同步飞书话题失败: ticket_no={ticket.ticket_no}, error={exc}")
                    feishu_result = {"skipped": True, "reason": str(exc)}

        return {"skipped": False, "bitableSync": bitable_result, "feishuThreadSync": feishu_result}

    @classmethod
    def handle_feishu_message_event(
        cls,
        db: Session,
        payload: dict[str, Any],
        inbound_channel: str = "webhook",
    ) -> dict[str, Any]:
        """
        处理飞书消息事件，按配置同步话题评论到工单评论和多维表格。
        :param db: 数据库会话
        :param payload: 飞书事件订阅请求体
        :param inbound_channel: 入站通道，webhook 表示公网回调，ws 表示 SDK 长连接
        :return: 处理结果摘要
        """
        if "challenge" in payload:
            return {"challenge": payload.get("challenge")}
        header = payload.get("header") if isinstance(payload.get("header"), dict) else {}
        event = payload.get("event") if isinstance(payload.get("event"), dict) else {}
        message = event.get("message") if isinstance(event.get("message"), dict) else {}
        if not message:
            return {"skipped": True, "reason": "empty_message"}

        sync_config = TicketSyncConfigService.load_sync_config(db)
        message_config = sync_config.get("messageSync") if isinstance(sync_config.get("messageSync"), dict) else {}
        channel_enabled = bool(message_config.get("feishuWsEnabled")) if inbound_channel == "ws" else bool(
            message_config.get("feishuEventEnabled")
        )
        if not bool(message_config.get("enabled")) or not channel_enabled:
            return {"skipped": True, "reason": "message_sync_disabled"}

        chat_id = str(message.get("chat_id") or message.get("chatId") or "").strip()
        raw_allowed_chat_ids = message_config.get("allowedChatIds")
        allowed_chat_ids = raw_allowed_chat_ids if isinstance(raw_allowed_chat_ids, list) else []
        if allowed_chat_ids and chat_id not in allowed_chat_ids:
            return {"skipped": True, "reason": "chat_not_allowed", "chatId": chat_id}

        sender_open_id = cls._extract_sender_open_id(event)
        raw_ignored_open_ids = message_config.get("ignoreBotOpenIds")
        ignored_open_ids = raw_ignored_open_ids if isinstance(raw_ignored_open_ids, list) else []
        if sender_open_id and sender_open_id in ignored_open_ids:
            return {"skipped": True, "reason": "sender_ignored", "senderOpenId": sender_open_id}

        message_id = str(message.get("message_id") or message.get("messageId") or "").strip()
        root_id = str(message.get("root_id") or message.get("rootId") or "").strip()
        thread_id = str(message.get("thread_id") or message.get("threadId") or "").strip()
        parent_id = str(message.get("parent_id") or message.get("parentId") or "").strip()
        text_bundle = cls._extract_message_text_bundle(message)
        text = str(text_bundle.get("text") or "").strip()
        if not message_id or not text:
            return {"skipped": True, "reason": "empty_message_id_or_text"}

        ticket = cls._match_ticket_by_message_context(
            db,
            chat_id=chat_id,
            root_id=root_id,
            thread_id=thread_id,
            text=text,
        )
        if not ticket:
            return {"skipped": True, "reason": "ticket_not_matched", "messageId": message_id}

        comment_action = "skipped"
        comment_id = None
        external_created_at = cls._parse_datetime_value(
            message.get("create_time")
            or message.get("createTime")
            or header.get("create_time")
            or header.get("createTime")
        )
        sender_display_name = ""
        if bool(message_config.get("syncFeishuCommentToTicket", True)):
            sender_display_name = cls._resolve_sender_display_name(
                sync_config=sync_config,
                event=event,
                sender_open_id=sender_open_id,
            )
            comment, comment_action = TicketCommentCoreService.upsert_synced_comment(
                db,
                ticket_id=ticket.ticket_id,
                content=text,
                user_name=sender_display_name,
                source_type=cls.SOURCE_TYPE_FEISHU_THREAD,
                source_system="feishu_im",
                source_record_id=message_id,
                source_field="thread_message",
                source_segment_key=cls._build_feishu_source_segment_key(message_id),
                source_segment_index=0,
                source_content_hash=cls._text_sha256(text),
                external_created_at=external_created_at,
                attachments={
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "root_id": root_id,
                    "thread_id": thread_id,
                    "parent_id": parent_id,
                    "sender_open_id": sender_open_id,
                    "event_id": header.get("event_id") or header.get("eventId"),
                    "mentions": text_bundle.get("mentions") or [],
                    "content_segments": text_bundle.get("segments") or [],
                    "raw_content_text": text_bundle.get("rawText") or "",
                },
                is_internal=False,
            )
            comment_id = getattr(comment, "id", None) if comment else None

        bitable_result = {"skipped": True, "reason": "syncFeishuCommentToBitable=false"}
        if bool(message_config.get("syncFeishuCommentToBitable")) and comment_action in {"created", "updated"}:
            if not sender_display_name:
                sender_display_name = cls._resolve_sender_display_name(
                    sync_config=sync_config,
                    event=event,
                    sender_open_id=sender_open_id,
                )
            bitable_result = cls.append_comment_to_bitable_step_reason(
                db,
                ticket=ticket,
                content=text,
                user_name=sender_display_name,
                created_at=external_created_at,
                content_segments=text_bundle.get("segments") or [],
            )

        db.commit()
        return {
            "skipped": False,
            "ticketId": ticket.ticket_id,
            "ticketNo": ticket.ticket_no,
            "messageId": message_id,
            "commentAction": comment_action,
            "commentId": comment_id,
            "bitableSync": bitable_result,
        }

