"""
工单多维表格记录评论拉取服务：把飞书多维表格记录自带的评论同步为本系统工单评论。

设计要点：
- 独立拉取通道：记录评论的新增不会改变记录字段内容，无法依赖主动拉取的
  快照哈希/更新时间过滤感知，因此本服务直接按本地已带 bitableRecordId 的工单
  逐条调用飞书"记录评论列表"接口拉取。
- 幂等：source_segment_key = sha256("bitable_comment|{record_id}|{comment_id}")，
  与表唯一约束 (ticket_id, source_segment_key) 共同保证评论不重复；
  评论被编辑时同键更新（复用 TicketCommentCoreService.upsert_synced_comment）。
- 评论人解析：接口只返回 open_id/user_id，复用 query_feishu_user_by_open_id 解析姓名。
- 评论中的附件元素只保存 fileToken 元信息，查看时由 TicketAttachmentUrlService 换临时链接。
"""
import hashlib
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from modules.ticket.entity.do.ticket_do import Ticket
from modules.ticket.service.collaboration.ticket_comment_core_service import TicketCommentCoreService
from modules.ticket.service.sync.ticket_sync_config_service import TicketSyncConfigService
from modules.ticket.service.sync.ticket_sync_notify_service import TicketSyncNotifyService
from modules.ticket.util.sync_util import SyncUtil
from utils.log_util import logger


class TicketBitableRecordCommentService:
    """多维表格记录评论拉取与评论入库。"""

    SOURCE_TYPE = "feishu_bitable_comment"
    SOURCE_SYSTEM = "feishu_bitable"
    # 记录评论接口路径模板。注意：截至 2026-09，飞书开放平台 bitable-v1 服务端 API
    # （官方 SDK 1.6.9 与概览文档均确认只有 app/table/view/field/form/record/role/member/dashboard
    # 八类资源）尚未公开"记录评论"接口，本服务按预期形态预留，端点可在 messageSync 中配置。
    # API 正式上线后在 messageSync.bitableRecordCommentApiPath 配置真实路径即可，无需改代码。
    DEFAULT_API_PATH_TEMPLATE = (
        "/bitable/v1/apps/{app_token}/tables/{table_id}/records/{record_id}/comments"
    )

    @classmethod
    def build_comment_segment_key(cls, *, record_id: str, comment_id: str) -> str:
        """
        构建记录评论幂等键。
        :param record_id: 多维表格记录ID
        :param comment_id: 记录评论ID
        :return: 稳定幂等键
        """
        raw_key = "|".join(["bitable_comment", str(record_id or "").strip(), str(comment_id or "").strip()])
        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    @classmethod
    def iter_record_comments(
        cls,
        *,
        config: dict[str, Any],
        record_id: str,
        api_path_template: str = "",
    ) -> list[dict[str, Any]]:
        """
        调用飞书"列出记录评论"接口，分页拉取一条记录的全部评论。

        端点通过 api_path_template 配置（默认按预期形态预留）。
        服务端 API 未上线时飞书返回 404（非 JSON），本方法捕获后记录日志并返回空列表，
        不中断整体拉取任务；待接口正式上线后配置路径即可启用。

        预期响应形态：
        GET {路径}?page_size=&page_token=
        返回 items: [{comment_id, creator_id, create_time, update_time, content: {elements: [...]}}]

        :param config: 多维表格运行时配置（appId/appSecret/appToken/tableId）。
        :param record_id: 记录ID。
        :param api_path_template: 可配置的接口路径模板，空时使用默认预留路径。
        :return: 评论原始对象列表；接口不可用或失败返回空列表。
        """
        app_id, app_secret = TicketSyncNotifyService.resolve_feishu_auth(config)
        app_token = str(config.get("appToken") or "").strip()
        table_id = str(config.get("tableId") or "").strip()
        if not app_id or not app_secret or not app_token or not table_id:
            logger.warning(f"记录评论拉取跳过: 多维表格配置不完整, record_id={record_id or '-'}")
            return []
        token = TicketSyncNotifyService._get_tenant_access_token(app_id, app_secret)
        path_tpl = str(api_path_template or "").strip() or cls.DEFAULT_API_PATH_TEMPLATE
        url = (
            f"{TicketSyncNotifyService.FEISHU_BASE_URL}"
            + path_tpl.format(app_token=app_token, table_id=table_id, record_id=record_id)
        )
        comments: list[dict[str, Any]] = []
        page_token = ""
        seen_page_tokens: set[str] = set()
        for _ in range(50):
            query: dict[str, Any] = {"page_size": 100}
            if page_token:
                query["page_token"] = page_token
                if page_token in seen_page_tokens:
                    break
                seen_page_tokens.add(page_token)
            try:
                response = TicketSyncNotifyService.request_feishu_json(
                    method="GET",
                    url=url,
                    tenant_access_token=token,
                    params=query,
                )
            except RuntimeError as exc:
                # 飞书未上线该接口时返回纯文本 404，会在这里抛 RuntimeError；
                # 记录一次即可返回，避免对每条记录重复请求浪费时间。
                logger.warning(
                    f"记录评论接口暂不可用（若飞书尚未上线该API可忽略）: record_id={record_id}, error={exc}"
                )
                break
            code = response.get("code")
            if code not in (0, None):
                logger.warning(
                    f"记录评论拉取失败: record_id={record_id}, code={code}, msg={response.get('msg')}"
                )
                break
            data = response.get("data") if isinstance(response.get("data"), dict) else {}
            items = data.get("items") if isinstance(data.get("items"), list) else []
            comments.extend(item for item in items if isinstance(item, dict))
            has_more = bool(data.get("has_more"))
            next_token = str(data.get("page_token") or "").strip()
            if not has_more or not next_token:
                break
            page_token = next_token
        return comments

    @classmethod
    def parse_comment_time(cls, value: Any) -> datetime | None:
        """
        解析记录评论时间（飞书返回毫秒时间戳或字符串）。
        :param value: 原始时间值。
        :return: 本地时间；解析失败返回 None。
        """
        if value in (None, ""):
            return None
        try:
            timestamp = float(value)
        except (TypeError, ValueError):
            return SyncUtil.parse_datetime_value(value)
        if timestamp > 10_000_000_000:
            timestamp = timestamp / 1000.0
        try:
            return datetime.fromtimestamp(timestamp, tz=timezone.utc).replace(tzinfo=None)
        except Exception:
            return None

    @classmethod
    def parse_comment_content(cls, comment: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
        """
        解析记录评论正文与附件元素。

        评论 content.elements 常见元素形态：
        - 文本：{"type": "text", "text": "..."}
        - 附件：{"type": "attachment", "name"/"file_token"/"size"/"type": ...}

        :param comment: 评论原始对象。
        :return: (正文文本, 附件元信息列表)。
        """
        content = comment.get("content") if isinstance(comment.get("content"), dict) else {}
        raw_elements = content.get("elements") if isinstance(content.get("elements"), list) else content.get("items")
        elements = raw_elements if isinstance(raw_elements, list) else []
        text_parts: list[str] = []
        attachments: list[dict[str, Any]] = []
        for element in elements:
            if isinstance(element, str):
                text_parts.append(element)
                continue
            if not isinstance(element, dict):
                continue
            element_type = str(element.get("type") or "").strip().lower()
            if element_type == "attachment" or ("file_token" in element and "text" not in element):
                file_token = str(element.get("file_token") or element.get("fileToken") or "").strip()
                if file_token:
                    attachment = {
                        "fileToken": file_token,
                        "name": str(element.get("name") or element.get("fileName") or "").strip() or file_token,
                    }
                    size = element.get("size")
                    if isinstance(size, (int, float)):
                        attachment["size"] = int(size)
                    # type 字段可能是元素类型 attachment，真正文件类型在 fileType/type 附加字段中。
                    raw_file_type = str(element.get("fileType") or "").strip()
                    if not raw_file_type and element_type != "attachment":
                        raw_file_type = str(element.get("type") or "").strip()
                    if raw_file_type and raw_file_type.lower() != "attachment":
                        attachment["type"] = raw_file_type
                    if all(item.get("fileToken") != file_token for item in attachments):
                        attachments.append(attachment)
                continue
            text = str(element.get("text") or "").strip()
            if text:
                text_parts.append(text)
        return "\n".join(part for part in text_parts if part), attachments

    @classmethod
    def resolve_creator_name(cls, *, config: dict[str, Any], creator_id: str) -> str:
        """
        将评论创建者 open_id 解析为姓名，失败时回退 open_id。
        :param config: 多维表格运行时配置。
        :param creator_id: 创建者 open_id/user_id。
        :return: 展示名称。
        """
        normalized_id = str(creator_id or "").strip()
        if not normalized_id:
            return "外部同步"
        app_id, app_secret = TicketSyncNotifyService.resolve_feishu_auth(config)
        if app_id and app_secret:
            try:
                feishu_user = TicketSyncNotifyService.query_feishu_user_by_open_id(
                    app_id=app_id,
                    app_secret=app_secret,
                    open_id=normalized_id,
                )
                name = str((feishu_user or {}).get("name") or "").strip()
                if name:
                    return name
            except Exception as exc:
                logger.warning(f"记录评论创建者姓名解析失败: open_id={normalized_id[:8]}***, error={exc}")
        return normalized_id

    @classmethod
    def sync_record_comments_for_ticket(
        cls,
        db: Session,
        *,
        ticket: Ticket,
        config: dict[str, Any],
        api_path_template: str = "",
    ) -> dict[str, Any]:
        """
        拉取单张工单对应多维表格记录的评论并幂等入库。
        :param db: 数据库会话。
        :param ticket: 本地工单对象。
        :param config: 多维表格运行时配置。
        :param api_path_template: 可配置的记录评论接口路径模板。
        :return: 单工单同步结果摘要。
        """
        record_id = cls._resolve_bitable_record_id(ticket)
        if not record_id:
            return {"skipped": True, "reason": "missing_bitable_record_id", "ticketNo": ticket.ticket_no}
        comments = cls.iter_record_comments(
            config=config,
            record_id=record_id,
            api_path_template=api_path_template,
        )
        result = {
            "skipped": False,
            "ticketNo": ticket.ticket_no,
            "recordId": record_id,
            "total": len(comments),
            "created": 0,
            "updated": 0,
            "skippedCount": 0,
        }
        for comment in comments:
            comment_id = str(comment.get("comment_id") or comment.get("commentId") or "").strip()
            if not comment_id:
                result["skippedCount"] += 1
                continue
            content, attachments = cls.parse_comment_content(comment)
            if not content and not attachments:
                result["skippedCount"] += 1
                continue
            display_content = content if content else f"[附件评论] {attachments[0].get('name') or ''}".strip()
            external_created_at = cls.parse_comment_time(comment.get("create_time") or comment.get("createTime"))
            creator_id = str(comment.get("creator_id") or comment.get("creatorId") or "").strip()
            creator_name = cls.resolve_creator_name(config=config, creator_id=creator_id) if creator_id else "外部同步"
            comment_attachments: dict[str, Any] = {}
            if attachments:
                comment_attachments["comment_attachments"] = attachments
            _, action = TicketCommentCoreService.upsert_synced_comment(
                db,
                ticket_id=ticket.ticket_id,
                content=display_content,
                user_name=creator_name,
                source_type=cls.SOURCE_TYPE,
                source_system=cls.SOURCE_SYSTEM,
                source_record_id=record_id,
                source_field="record_comment",
                source_segment_key=cls.build_comment_segment_key(record_id=record_id, comment_id=comment_id),
                source_segment_index=0,
                source_content_hash=SyncUtil.text_sha256(display_content),
                external_created_at=external_created_at,
                attachments=comment_attachments or None,
                is_internal=False,
            )
            if action == "created":
                result["created"] += 1
            elif action == "updated":
                result["updated"] += 1
            else:
                result["skippedCount"] += 1
        return result

    @classmethod
    def run_record_comment_pull_services(
        cls,
        db: Session,
        *,
        trigger_source: str,
        max_tickets: int = 200,
    ) -> dict[str, Any]:
        """
        执行记录评论拉取任务：扫描本地带 bitableRecordId 的工单，逐条同步记录评论。

        :param db: 数据库会话。
        :param trigger_source: 触发来源（manual/scheduler）。
        :param max_tickets: 单次最大处理工单数，控制飞书 API 用量。
        :return: 执行结果摘要。
        """
        config = TicketSyncConfigService.load_sync_config(db)
        message_sync = config.get("messageSync") if isinstance(config.get("messageSync"), dict) else {}
        if not SyncUtil.to_bool(message_sync.get("syncBitableRecordComments"), False):
            logger.info(f"多维表格记录评论拉取已跳过: syncBitableRecordComments=false, trigger={trigger_source}")
            return {
                "triggerSource": trigger_source,
                "skipped": True,
                "skipReason": "记录评论同步未启用",
            }
        bitable_config = TicketSyncConfigService.resolve_bitable_runtime_config(
            config,
            "bitablePull",
            TicketSyncConfigService.default_bitable_pull_config(),
        )
        has_bitable_config = bool(
            str(bitable_config.get("appToken") or "").strip() and str(bitable_config.get("tableId") or "").strip()
        )
        if not has_bitable_config:
            return {
                "triggerSource": trigger_source,
                "skipped": True,
                "skipReason": "多维表格配置不完整",
            }
        tickets = cls._list_tickets_with_bitable_record(db, limit=max(1, min(int(max_tickets or 200), 1000)))
        api_path_template = str(message_sync.get("bitableRecordCommentApiPath") or "").strip()
        summary = {
            "triggerSource": trigger_source,
            "skipped": False,
            "ticketCount": len(tickets),
            "created": 0,
            "updated": 0,
            "skippedCount": 0,
            "failures": [],
        }
        logger.info(
            f"多维表格记录评论拉取开始: trigger={trigger_source}, tickets={len(tickets)}, "
            f"max_tickets={max_tickets}, api_path={'custom' if api_path_template else 'default'}"
        )
        for ticket in tickets:
            try:
                result = cls.sync_record_comments_for_ticket(
                    db,
                    ticket=ticket,
                    config=bitable_config,
                    api_path_template=api_path_template,
                )
                if result.get("skipped"):
                    summary["skippedCount"] += 1
                    continue
                summary["created"] += int(result.get("created") or 0)
                summary["updated"] += int(result.get("updated") or 0)
            except Exception as exc:
                logger.exception(
                    f"记录评论同步失败: ticket_no={getattr(ticket, 'ticket_no', '-')}, error={exc}"
                )
                summary["failures"].append({"ticketNo": getattr(ticket, "ticket_no", ""), "reason": str(exc)})
        db.commit()
        logger.info(
            f"多维表格记录评论拉取完成: trigger={trigger_source}, created={summary['created']}, "
            f"updated={summary['updated']}, failures={len(summary['failures'])}"
        )
        return summary

    @classmethod
    def _resolve_bitable_record_id(cls, ticket: Ticket) -> str:
        """
        从工单扩展信息中解析多维表格记录ID。
        :param ticket: 工单对象。
        :return: record_id；缺失返回空字符串。
        """
        extra_data = ticket.extra_data if isinstance(ticket.extra_data, dict) else {}
        for key in ("bitable_pull", "external_field_mapping"):
            payload = extra_data.get(key) if isinstance(extra_data.get(key), dict) else {}
            record_id = str(
                payload.get("recordId")
                or payload.get("record_id")
                or payload.get("bitableRecordId")
                or ""
            ).strip()
            if record_id:
                return record_id
        return ""

    @classmethod
    def _list_tickets_with_bitable_record(cls, db: Session, *, limit: int) -> list[Ticket]:
        """
        查询本地带 bitableRecordId 的未删除工单（按更新时间倒序）。

        bitableRecordId 存储 JSON 的键无法直接走索引，这里先粗筛 extra_data 含
        bitable_pull/external_field_mapping 键的行，再在内存精确过滤，limit 控制规模。

        :param db: 数据库会话。
        :param limit: 最大返回数量。
        :return: 工单列表。
        """
        rows = (
            db.query(Ticket)
            .filter(Ticket.del_flag == "0")
            .order_by(Ticket.update_time.desc())
            .limit(limit * 4)
            .all()
        )
        result: list[Ticket] = []
        for ticket in rows:
            if not cls._resolve_bitable_record_id(ticket):
                continue
            result.append(ticket)
            if len(result) >= limit:
                break
        return result
