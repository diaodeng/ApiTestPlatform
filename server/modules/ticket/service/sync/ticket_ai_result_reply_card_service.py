"""AI 分析结果飞书卡片消息构造服务。

AI 分析结果话题回帖（aiResultFollowUp）默认从纯文本改为飞书交互卡片：
结论、根因、修复建议等区块在卡片中独立展示，提升群内可读性。

边界说明：
- 本服务只做"结果载荷 -> 卡片 JSON"的纯格式化构造，不访问数据库、不发网络请求；
- 卡片 JSON 由调用方（ticket_sync_group_push_service）经
  TicketSyncNotifyService.send_feishu_thread_reply(card=...) 投递；
- 用户配置了自定义回帖模板（aiResultFollowUp.template）时，调用方继续走纯文本，
  保证已有自定义模板行为不变。
"""

from __future__ import annotations

from typing import Any

from modules.ticket.entity.do.ticket_do import Ticket
from utils.log_util import logger

# 卡片单区块文本最大长度：超出截断，防止个别超长 AI 结果撑爆飞书卡片（卡片整体上限 30k 字符）
_SECTION_MAX_CHARS = 3000


class TicketAiResultReplyCardService:
    """
    AI 分析结果飞书卡片构造服务。
    """

    # 卡片可配置展示字段全集（顺序即卡片渲染顺序）；配置留空时默认全量展示。
    CARD_FIELD_KEYS = (
        "ticket_info",       # 工单基础信息（工单号/标题/模块/商家）
        "analysis_summary",  # 结论
        "root_cause",        # 根因分析
        "fix_suggestion",    # 修复建议
        "evidence",          # 依据
        "risk_items",        # 风险项
        "next_steps",        # 后续动作
        "confidence",        # 置信度备注
        "ticket_link",       # 查看工单按钮
    )

    @classmethod
    def normalize_card_fields(cls, value: Any) -> list[str]:
        """
        归一化卡片展示字段配置。

        :param value: 原始字段配置，可为列表或逗号分隔文本。
        :return: 归一化后的有效字段列表；未配置返回空列表（代表默认全量展示）。
        """
        if isinstance(value, str):
            source_list = [item.strip() for item in value.split(",")]
        elif isinstance(value, list):
            source_list = value
        else:
            source_list = []
        result: list[str] = []
        for item in source_list:
            key = str(item or "").strip()
            if key and key in cls.CARD_FIELD_KEYS and key not in result:
                result.append(key)
        return result

    @classmethod
    def build_ai_result_reply_card(
        cls,
        *,
        ticket: Ticket,
        ai_task_status: str,
        ai_result_payload: dict[str, Any] | None = None,
        ai_error_message: str = "",
        card_fields: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        构造 AI 分析结果回帖卡片（飞书经典 interactive 卡片结构）。

        成功卡片按"工单信息 / 结论 / 根因 / 修复建议"等区块展示，展示哪些区块由
        card_fields 决定（留空展示全部；配置了字段则只渲染对应区块）；
        失败卡片展示工单信息与失败原因（失败原因是失败卡片的唯一内容，始终展示）。

        :param ticket: 工单 ORM 实体。
        :param ai_task_status: AI 任务终态状态（success/failed 等）。
        :param ai_result_payload: AI 分析结果载荷（成功时）。
        :param ai_error_message: AI 失败原因（失败时）。
        :param card_fields: 卡片展示字段白名单（取值见 CARD_FIELD_KEYS），空表示全部展示。
        :return: 可直接经 im/v1 messages reply（msg_type=interactive）发送的卡片字典。
        """
        payload = ai_result_payload if isinstance(ai_result_payload, dict) else {}
        is_failed = str(ai_task_status or "").strip().lower() != "success"
        ticket_no = str(getattr(ticket, "ticket_no", "") or "-")
        ticket_title = str(getattr(ticket, "title", "") or "-")
        ticket_url = str(getattr(ticket, "ticket_url", "") or "").strip()
        module_name = str(getattr(ticket, "module_name", "") or "").strip()
        merchant_name = str(getattr(ticket, "merchant_name", "") or "").strip()

        # 字段白名单过滤：未知字段丢弃并留痕；配置为空时回退全量字段。
        selected_fields = cls.normalize_card_fields(card_fields)
        if card_fields and not selected_fields:
            logger.warning(
                f"AI结果回帖卡片字段配置全部无效，回退默认全量展示: card_fields={card_fields}"
            )
        if not selected_fields:
            selected_fields = list(cls.CARD_FIELD_KEYS)
        show = {key: key in selected_fields for key in cls.CARD_FIELD_KEYS}

        elements: list[dict[str, Any]] = []
        if show["ticket_info"]:
            elements.append(cls._build_ticket_info_element(ticket_no=ticket_no, ticket_title=ticket_title,
                                                           ticket_url=ticket_url, module_name=module_name,
                                                           merchant_name=merchant_name))
            elements.append({"tag": "hr"})
        if is_failed:
            error_text = str(ai_error_message or payload.get("error_message") or "").strip() or "-"
            elements.append(cls._build_markdown_element("❌ 失败原因", error_text))
        else:
            # 结论、根因、修复建议各自独立区块；字段已配置但结果载荷为空时不渲染，
            # 避免卡片出现大段"-"占位。
            summary = str(payload.get("analysis_summary") or "").strip()
            root_cause = str(payload.get("root_cause") or "").strip()
            fix_suggestion = str(payload.get("fix_suggestion") or "").strip()
            if show["analysis_summary"] and summary:
                elements.append(cls._build_markdown_element("📌 结论", summary))
            if show["root_cause"] and root_cause:
                elements.append(cls._build_markdown_element("🔍 根因分析", root_cause))
            if show["fix_suggestion"] and fix_suggestion:
                elements.append(cls._build_markdown_element("🛠 修复建议", fix_suggestion))
            # 补充区块：依据、风险、后续动作仅在字段已配置且结果中给出时展示。
            if show["evidence"]:
                evidence = cls._join_list_fields(payload.get("evidence"))
                if evidence:
                    elements.append(cls._build_markdown_element("📎 依据", evidence))
            if show["risk_items"]:
                risk_items = cls._join_list_fields(payload.get("risk_items"))
                if risk_items:
                    elements.append(cls._build_markdown_element("⚠️ 风险项", risk_items))
            if show["next_steps"]:
                next_steps = cls._join_list_fields(payload.get("next_steps"))
                if next_steps:
                    elements.append(cls._build_markdown_element("➡️ 后续动作", next_steps))
            if not (summary or root_cause or fix_suggestion):
                # 结果载荷缺少核心字段时兜底提示，避免发送一张只有工单信息的空卡片。
                elements.append(cls._build_markdown_element("📌 结论", "AI 结果未包含分析内容"))
            if show["confidence"]:
                elements.append(cls._build_note_element(payload))
        if show["ticket_link"] and ticket_url and ticket_url.startswith(("http://", "https://")):
            elements.append({"tag": "hr"})
            elements.append(
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "查看工单"},
                            "type": "primary",
                            "url": ticket_url,
                        }
                    ],
                }
            )

        header_template = "red" if is_failed else "green"
        header_title = "🤖 AI 分析失败" if is_failed else "🤖 AI 分析成功"
        return {
            "config": {"wide_screen_mode": True},
            "header": {
                "template": header_template,
                "title": {"tag": "plain_text", "content": header_title},
            },
            "elements": elements,
        }

    @classmethod
    def _build_ticket_info_element(
        cls,
        *,
        ticket_no: str,
        ticket_title: str,
        ticket_url: str,
        module_name: str,
        merchant_name: str,
    ) -> dict[str, Any]:
        """
        构造卡片顶部工单基础信息区块（两列字段布局）。

        :param ticket_no: 工单号，配置了工单链接时会渲染为可点击链接。
        :param ticket_title: 工单标题。
        :param ticket_url: 工单详情链接。
        :param module_name: 模块名称。
        :param merchant_name: 商家名称。
        :return: 飞书卡片 div 元素。
        """
        if ticket_url and ticket_url.startswith(("http://", "https://")):
            ticket_no_text = f"[{ticket_no}]({ticket_url})"
        else:
            ticket_no_text = ticket_no
        fields: list[dict[str, Any]] = [
            {
                "is_short": True,
                "text": {"tag": "lark_md", "content": f"**工单号**\n{ticket_no_text}"},
            },
            {
                "is_short": True,
                "text": {"tag": "lark_md", "content": f"**标题**\n{cls._truncate(ticket_title)}"},
            },
        ]
        if module_name and module_name != "-":
            fields.append(
                {"is_short": True, "text": {"tag": "lark_md", "content": f"**模块**\n{module_name}"}}
            )
        if merchant_name and merchant_name != "-":
            fields.append(
                {"is_short": True, "text": {"tag": "lark_md", "content": f"**商家**\n{merchant_name}"}}
            )
        return {"tag": "div", "fields": fields}

    @classmethod
    def _build_markdown_element(cls, section_title: str, content: str) -> dict[str, Any]:
        """
        构造卡片正文 Markdown 区块元素。

        :param section_title: 区块标题（含 emoji 前缀）。
        :param content: 区块正文，超长时截断。
        :return: 飞书卡片 div 元素。
        """
        return {
            "tag": "div",
            "text": {"tag": "lark_md", "content": f"**{section_title}**\n{cls._truncate(content)}"},
        }

    @classmethod
    def _build_note_element(cls, payload: dict[str, Any]) -> dict[str, Any]:
        """
        构造卡片底部备注元素（置信度等补充信息）。

        :param payload: AI 分析结果载荷。
        :return: 飞书卡片 note 元素。
        """
        note_parts: list[str] = []
        confidence = payload.get("confidence")
        if confidence is not None:
            note_parts.append(f"置信度：{cls._format_confidence(confidence)}")
        if not note_parts:
            return {"tag": "note", "elements": [{"tag": "plain_text", "content": "由 AI 自动生成，仅供参考"}]}
        return {"tag": "note", "elements": [{"tag": "plain_text", "content": " · ".join(note_parts)}]}

    @classmethod
    def _join_list_fields(cls, value: Any, *, max_items: int = 5) -> str:
        """
        把 AI 结果中的列表字段转为 Markdown 行文本（超出条数截断）。

        :param value: 列表或字符串。
        :param max_items: 最多展示条数。
        :return: 拼接文本；空返回空字符串。
        """
        if isinstance(value, str):
            return value.strip()
        if not isinstance(value, list):
            return ""
        items = [str(item).strip() for item in value if str(item or "").strip()]
        if not items:
            return ""
        if len(items) > max_items:
            items = items[:max_items] + [f"...等共 {len(value)} 条"]
        return "\n".join(f"- {item}" for item in items)

    @classmethod
    def _format_confidence(cls, value: Any) -> str:
        """
        格式化置信度展示文本。

        :param value: 原始置信度，可能是小数、百分数或文本。
        :return: 可读置信度文本。
        """
        if isinstance(value, (int, float)):
            if 0 < value <= 1:
                return f"{round(float(value) * 100)}%"
            return f"{value}"
        return str(value)

    @classmethod
    def _truncate(cls, text: str, *, max_chars: int = _SECTION_MAX_CHARS) -> str:
        """
        截断超长文本，防止撑爆飞书卡片。

        :param text: 原始文本。
        :param max_chars: 最大字符数。
        :return: 截断后的文本。
        """
        normalized = str(text or "").strip() or "-"
        if len(normalized) <= max_chars:
            return normalized
        logger.info(f"AI结果回帖卡片区块文本超长已截断: len={len(normalized)}, max_chars={max_chars}")
        return f"{normalized[:max_chars]}…（已截断）"
