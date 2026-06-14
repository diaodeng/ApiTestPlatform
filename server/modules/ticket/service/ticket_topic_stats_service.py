from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import urllib.request
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any

from utils.log_util import logger

SHANGHAI_TZ = timezone(timedelta(hours=8))
STATUS_ORDER = ("有结论", "无结论")
CATEGORY_ORDER = ("促销", "券", "会员", "印花")
TICKET_PATTERNS = (
    re.compile(r"(?im)^\s*/?\s*Ticket:\s*([^\r\n]+)"),
    re.compile(r"(?im)^\s*Ticket:\s*([^\r\n]+)"),
    re.compile(r"(?i)\b(INC\d+[A-Z]?)\b"),
    re.compile(r"(?i)\b(SCTASK\d+)\b"),
)
TOPIC_BLOCK_PATTERN = re.compile(
    r"(?ims)^\s*/?\s*主题:\s*(.*?)(?:\r?\n\s*/?\s*(?:商家|门店|1线|1\.5|当前处理人|Details)\s*:|\Z)"
)
TOPIC_LINE_PATTERN = re.compile(r"^\s*/?\s*主题:\s*(.*)$", re.MULTILINE)


@dataclass(frozen=True)
class TopicTicketSource:
    """工单专题统计的数据源配置。"""

    name: str
    chat_id: str
    priority: str


@dataclass(frozen=True)
class TopicTicketRecord:
    """单条专题工单统计记录。"""

    ticket_key: str
    group_name: str
    priority: str
    category: str
    status: str
    topic: str


class TicketTopicStatsService:
    """飞书群专题工单统计服务。"""

    DEFAULT_LARK_CLI_CANDIDATES = (
        os.environ.get("LARK_CLI_BIN", "").strip(),
        "lark-cli.cmd",
        "lark-cli",
        r"C:\nvm4w\nodejs\lark-cli.cmd",
    )

    @classmethod
    def run_topic_stats(
        cls,
        *,
        start_date: str | None = None,
        end_date: str | None = None,
        sources: list[dict[str, Any]] | None = None,
        webhook: str | None = None,
        send: bool = False,
        keyword: str = "TRunner",
        lark_cli_bin: str | None = None,
        page_size: int = 50,
    ) -> dict[str, Any]:
        """
        执行专题工单统计，并按需发送飞书卡片。

        :param start_date: 统计开始日期，格式为 YYYY-MM-DD；为空时取上海时区当天。
        :param end_date: 统计结束日期，格式为 YYYY-MM-DD；为空时取上海时区当天。
        :param sources: 飞书群来源列表，每项包含 name、chatId/chat_id、priority。
        :param webhook: 飞书机器人 webhook，send 为 True 时必填。
        :param send: 是否发送飞书卡片。
        :param keyword: 卡片副标题关键字。
        :param lark_cli_bin: lark-cli 可执行文件路径或命令名。
        :param page_size: 单页拉取消息数量。
        :return: 统计结果和发送结果摘要。
        """
        today = datetime.now(SHANGHAI_TZ).date()
        resolved_start_date = cls.parse_iso_date(start_date) if start_date else today
        resolved_end_date = cls.parse_iso_date(end_date) if end_date else today
        if resolved_end_date < resolved_start_date:
            raise ValueError("end_date 不能早于 start_date")

        normalized_sources = cls.normalize_sources(sources)
        if send and not str(webhook or "").strip():
            raise ValueError("send=true 时必须配置 webhook")

        logger.info(
            f"开始执行专题工单统计 | start_date={resolved_start_date.isoformat()} "
            f"end_date={resolved_end_date.isoformat()} source_count={len(normalized_sources)} "
            f"send={bool(send)} keyword={keyword or '-'}"
        )
        records = cls.collect_topic_records(
            start_date=resolved_start_date,
            end_date=resolved_end_date,
            sources=normalized_sources,
            lark_cli_bin=lark_cli_bin,
            page_size=page_size,
        )
        result = cls.build_result(
            start_date=resolved_start_date,
            end_date=resolved_end_date,
            records=records,
        )
        if send:
            card = cls.build_feishu_card(result=result, records=records, keyword=keyword)
            result["response"] = cls.send_feishu_card(card=card, webhook=str(webhook or "").strip())
            logger.info(
                f"专题工单统计卡片发送完成 | total={result['summary']['total']} "
                f"webhook_configured={bool(webhook)} response={result.get('response')}"
            )
        logger.info(
            f"专题工单统计执行完成 | total={result['summary']['total']} "
            f"status={result['summary']['status']} category={result['summary']['category']}"
        )
        return result

    @classmethod
    def parse_iso_date(cls, value: str) -> date:
        """
        解析 YYYY-MM-DD 日期字符串。

        :param value: 日期字符串。
        :return: 日期对象。
        """
        return datetime.strptime(str(value).strip(), "%Y-%m-%d").date()

    @classmethod
    def normalize_sources(cls, sources: list[dict[str, Any]] | None) -> list[TopicTicketSource]:
        """
        归一化飞书群来源配置。

        :param sources: 原始来源配置。
        :return: 来源配置对象列表。
        """
        if not isinstance(sources, list) or not sources:
            raise ValueError("sources 不能为空，请通过定时任务参数配置飞书群来源")

        normalized_sources: list[TopicTicketSource] = []
        for index, item in enumerate(sources, start=1):
            if not isinstance(item, dict):
                raise ValueError(f"sources[{index}] 必须是对象")
            name = str(item.get("name") or "").strip()
            chat_id = str(item.get("chatId") or item.get("chat_id") or "").strip()
            priority = str(item.get("priority") or "").strip()
            if not name or not chat_id or not priority:
                raise ValueError(f"sources[{index}] 必须包含 name、chatId/chat_id、priority")
            normalized_sources.append(TopicTicketSource(name=name, chat_id=chat_id, priority=priority))
        return normalized_sources

    @classmethod
    def cell_text(cls, value: Any) -> str:
        """
        将 Lark 字段值统一转成纯文本。

        :param value: Lark 返回的原始字段值。
        :return: 归一化后的文本。
        """
        if value is None:
            return ""
        if isinstance(value, list):
            return "" if not value else str(value[0])
        return str(value)

    @classmethod
    def get_date_only(cls, date_text: str) -> date | None:
        """
        提取时间字符串中的自然日日期。

        :param date_text: 飞书消息时间字符串。
        :return: 日期对象；解析失败时返回 None。
        """
        if not date_text or not date_text.strip():
            return None
        try:
            return datetime.fromisoformat(date_text).date()
        except ValueError:
            pass
        try:
            return datetime.strptime(date_text[:10], "%Y-%m-%d").date()
        except ValueError:
            return None

    @classmethod
    def text_contains_any(cls, text: str, needles: Iterable[str]) -> bool:
        """
        判断文本是否命中任一关键字。

        :param text: 待检查文本。
        :param needles: 关键字列表。
        :return: 命中任意关键字时返回 True。
        """
        return any(needle in text for needle in needles)

    @classmethod
    def extract_ticket_key(cls, content: str) -> str | None:
        """
        从根消息中提取 Ticket 编号。

        :param content: 根消息全文。
        :return: Ticket 编号；未命中时返回 None。
        """
        if not content or not content.strip():
            return None
        for pattern in TICKET_PATTERNS:
            match = pattern.search(content)
            if match:
                return match.group(1).strip()
        return None

    @classmethod
    def extract_topic(cls, content: str) -> str:
        """
        从根消息中提取主题文本。

        :param content: 根消息全文。
        :return: 主题文本；未命中时返回空字符串。
        """
        if not content or not content.strip():
            return ""
        block_match = TOPIC_BLOCK_PATTERN.search(content)
        if block_match:
            return block_match.group(1).strip()
        line_match = TOPIC_LINE_PATTERN.search(content)
        if line_match:
            return line_match.group(1).strip()
        return ""

    @classmethod
    def get_category_bucket(cls, topic: str) -> str:
        """
        按主题归类为促销、券、会员、印花。

        :param topic: 工单主题文本。
        :return: 分类结果。
        """
        text = (topic or "").lower()
        if cls.text_contains_any(
            text,
            ("gv", "coupon", "voucher", "gift card", "礼物卡", "禮物卡", "礼券", "禮券", "券"),
        ):
            return "券"
        if cls.text_contains_any(text, ("stamp", "印花")):
            return "印花"
        if cls.text_contains_any(text, ("member", "会员", "积分", "points", "point")):
            return "会员"
        if cls.text_contains_any(
            text,
            (
                "promo",
                "promotion",
                "offer",
                "offers",
                "yuu promotion",
                "促销",
                "优惠",
                "折扣",
                "normal price",
                "20% off",
                "discount",
            ),
        ):
            return "促销"
        return "其他"

    @classmethod
    def get_session_status(cls, content: str, replies: list[dict[str, Any]] | None) -> str:
        """
        根据根消息和线程回复判断会话状态。

        :param content: 根消息全文。
        :param replies: 线程回复列表。
        :return: 有结论或无结论。
        """
        all_text = [content or ""]
        all_text.extend(cls.cell_text(reply.get("content")) for reply in replies or [])
        joined = "\n".join(all_text).lower()

        closed_keywords = (
            "已关闭",
            "关闭工单",
            "关闭",
            "已处理",
            "已修正",
            "已修复",
            "已解决",
            "解决了",
            "可以关闭",
            "close",
            "closed",
            "resolved",
            "fixed",
            "done",
        )
        if cls.text_contains_any(joined, closed_keywords):
            return "有结论"

        conclusion_keywords = (
            "因为",
            "所以",
            "因此",
            "看起来",
            "确认",
            "结论",
            "原因",
            "已知问题",
            "known issue",
            "known issues",
            "手误",
            "不满足",
            "同工单",
            "同一个问题",
            "历史问题",
            "是一个问题",
            "调用支付接口超时",
            "超时",
            "已经定位",
            "已定位",
            "已经确认",
            "已确认",
            "问题跟之前的问题一样",
            "跟之前的问题一样",
            "与之前的问题一样",
            "是同一个问题",
            "same issue",
            "same as previous issue",
            "建议",
            "已经回复",
            "已经回复了",
            "已在工单中回复",
            "导致",
            "修复中",
            "后续版本",
            "三方",
            "三方系统",
            "第三方",
            "vms",
            "external system",
            "third party",
            "not our issue",
            "found",
            "no related promotion",
            "no promotion found",
            "cannot be applied",
            "please assign",
            "relevant team",
            "indicates",
        )
        if cls.text_contains_any(joined, conclusion_keywords):
            return "有结论"
        return "无结论"

    @classmethod
    def resolve_lark_cli(cls, lark_cli_bin: str | None = None) -> str:
        """
        解析可执行的 lark-cli 命令路径。

        :param lark_cli_bin: 指定的 lark-cli 路径或命令名。
        :return: 可执行命令路径。
        """
        candidates = (str(lark_cli_bin or "").strip(), *cls.DEFAULT_LARK_CLI_CANDIDATES)
        for candidate in candidates:
            if not candidate:
                continue
            if os.path.isabs(candidate) and os.path.exists(candidate):
                logger.info(f"已解析 lark-cli 绝对路径 | path={candidate}")
                return candidate
            resolved = shutil.which(candidate)
            if resolved:
                logger.info(f"已解析 lark-cli 命令 | candidate={candidate} resolved={resolved}")
                return resolved
        raise FileNotFoundError("未找到可执行的 lark-cli，请通过参数 larkCliBin 或环境变量 LARK_CLI_BIN 配置")

    @classmethod
    def run_lark_cli(cls, command: list[str], *, lark_cli_bin: str | None = None) -> dict[str, Any]:
        """
        执行 lark-cli 命令并返回 JSON。

        :param command: 命令参数列表，不包含解释器名。
        :param lark_cli_bin: lark-cli 可执行文件路径或命令名。
        :return: 解析后的 JSON 对象。
        """
        lark_cli = cls.resolve_lark_cli(lark_cli_bin)
        display_command = " ".join(command)
        logger.info(f"开始执行 lark-cli 命令 | command={display_command}")
        completed = subprocess.run(
            [lark_cli, *command],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        logger.info(f"lark-cli 命令执行完成 | command={display_command} stdout_length={len(completed.stdout or '')}")
        return json.loads(completed.stdout)

    @classmethod
    def list_chat_messages(
        cls,
        *,
        chat_id: str,
        start_date: date,
        end_date: date,
        lark_cli_bin: str | None = None,
        page_size: int = 50,
    ) -> list[dict[str, Any]]:
        """
        分页拉取指定群在日期范围内的消息。

        :param chat_id: 飞书群 chat_id。
        :param start_date: 起始日期，闭区间。
        :param end_date: 结束日期，闭区间。
        :param lark_cli_bin: lark-cli 可执行文件路径或命令名。
        :param page_size: 单页数量。
        :return: 原始消息列表。
        """
        query_end = end_date + timedelta(days=1)
        start_text = f"{start_date.isoformat()}T00:00:00+08:00"
        end_text = f"{query_end.isoformat()}T00:00:00+08:00"
        page_token = None
        messages: list[dict[str, Any]] = []
        resolved_page_size = max(1, min(int(page_size or 50), 100))
        page_index = 1

        while True:
            command = [
                "im",
                "+chat-messages-list",
                "--as",
                "user",
                "--chat-id",
                chat_id,
                "--start",
                start_text,
                "--end",
                end_text,
                "--page-size",
                str(resolved_page_size),
                "--json",
                "--no-reactions",
            ]
            if page_token:
                command.extend(["--page-token", page_token])

            logger.info(
                f"开始拉取飞书群消息 | chat_id={chat_id} page_index={page_index} "
                f"start={start_text} end={end_text}"
            )
            payload = cls.run_lark_cli(command, lark_cli_bin=lark_cli_bin)
            data = payload.get("data", {})
            page_messages = data.get("messages") or []
            messages.extend(page_messages)
            logger.info(
                f"飞书群消息页拉取完成 | chat_id={chat_id} page_index={page_index} "
                f"page_count={len(page_messages)} total_count={len(messages)} has_more={bool(data.get('has_more'))}"
            )
            if not data.get("has_more"):
                break
            page_token = data.get("page_token")
            page_index += 1
        return messages

    @classmethod
    def collect_topic_records(
        cls,
        *,
        start_date: date,
        end_date: date,
        sources: list[TopicTicketSource],
        lark_cli_bin: str | None = None,
        page_size: int = 50,
    ) -> list[TopicTicketRecord]:
        """
        采集并过滤专题工单记录。

        :param start_date: 统计起始日期。
        :param end_date: 统计结束日期。
        :param sources: 飞书群来源配置。
        :param lark_cli_bin: lark-cli 可执行文件路径或命令名。
        :param page_size: 单页拉取消息数量。
        :return: 已去重、分类和状态判断的工单记录。
        """
        records: list[TopicTicketRecord] = []
        seen_ticket_keys: set[str] = set()

        for source in sources:
            logger.info(
                f"开始处理专题工单来源 | group_name={source.name} chat_id={source.chat_id} priority={source.priority}"
            )
            messages = cls.list_chat_messages(
                chat_id=source.chat_id,
                start_date=start_date,
                end_date=end_date,
                lark_cli_bin=lark_cli_bin,
                page_size=page_size,
            )
            logger.info(f"专题工单来源消息拉取完成 | group_name={source.name} raw_count={len(messages)}")

            for message in messages:
                if message.get("msg_type") != "post":
                    continue
                if str(message.get("thread_message_position")) != "-1":
                    continue

                content = cls.cell_text(message.get("content"))
                if "Ticket:" not in content and "主题:" not in content:
                    continue

                message_date = cls.get_date_only(cls.cell_text(message.get("create_time")))
                if message_date is None or message_date < start_date or message_date > end_date:
                    continue

                ticket_key = cls.extract_ticket_key(content)
                if not ticket_key:
                    logger.info(f"专题工单消息跳过：未提取到 Ticket 编号 | group_name={source.name}")
                    continue
                if ticket_key in seen_ticket_keys:
                    logger.info(f"专题工单消息跳过：重复 Ticket | ticket_key={ticket_key} group_name={source.name}")
                    continue

                topic = cls.extract_topic(content)
                category = cls.get_category_bucket(topic)
                if category == "其他":
                    logger.info(
                        f"专题工单消息跳过：主题未命中分类 | ticket_key={ticket_key} "
                        f"group_name={source.name} topic={topic}"
                    )
                    continue

                status = cls.get_session_status(content, message.get("thread_replies") or [])
                seen_ticket_keys.add(ticket_key)
                records.append(
                    TopicTicketRecord(
                        ticket_key=ticket_key,
                        group_name=source.name,
                        priority=source.priority,
                        category=category,
                        status=status,
                        topic=topic,
                    )
                )
                logger.info(
                    f"专题工单记录命中 | ticket_key={ticket_key} group_name={source.name} "
                    f"priority={source.priority} category={category} status={status}"
                )
        return records

    @classmethod
    def build_summary(cls, records: list[TopicTicketRecord]) -> dict[str, Any]:
        """
        按固定口径生成汇总结果。

        :param records: 工单明细列表。
        :return: 汇总对象。
        """
        status = dict.fromkeys(STATUS_ORDER, 0)
        category = dict.fromkeys(CATEGORY_ORDER, 0)
        for record in records:
            if record.status in status:
                status[record.status] += 1
            if record.category in category:
                category[record.category] += 1
        return {"status": status, "category": category, "total": len(records)}

    @classmethod
    def build_result(
        cls,
        *,
        start_date: date,
        end_date: date,
        records: list[TopicTicketRecord],
    ) -> dict[str, Any]:
        """
        构造最终输出对象。

        :param start_date: 统计起始日期。
        :param end_date: 统计结束日期。
        :param records: 工单明细列表。
        :return: 统计结果。
        """
        return {
            "range": {"start": start_date.isoformat(), "end": end_date.isoformat()},
            "summary": cls.build_summary(records),
            "records": [asdict(record) for record in records],
        }

    @classmethod
    def build_ticket_join(cls, records: list[TopicTicketRecord], field_name: str, field_value: str) -> str:
        """
        按筛选条件拼接 Ticket 编号列表。

        :param records: 工单明细列表。
        :param field_name: 筛选字段名。
        :param field_value: 字段目标值。
        :return: 命中的 Ticket 编号，空时返回 -。
        """
        ticket_list = [record.ticket_key for record in records if getattr(record, field_name) == field_value]
        return "、".join(ticket_list) if ticket_list else "-"

    @classmethod
    def build_feishu_card(
        cls,
        *,
        result: dict[str, Any],
        records: list[TopicTicketRecord],
        keyword: str,
    ) -> dict[str, Any]:
        """
        构造飞书机器人卡片结构。

        :param result: 最终统计结果。
        :param records: 工单明细列表。
        :param keyword: 副标题关键字。
        :return: 可发送到飞书 webhook 的卡片对象。
        """
        summary = result["summary"]
        subtitle = (
            f"{keyword or 'TRunner'} | 有结论 {summary['status']['有结论']} 单 | "
            f"无结论 {summary['status']['无结论']} 单"
        )
        status_rows = [
            {
                "status": status_name,
                "count": summary["status"][status_name],
                "tickets": cls.build_ticket_join(records, "status", status_name),
            }
            for status_name in STATUS_ORDER
        ]
        category_rows = [
            {
                "category": category_name,
                "count": summary["category"][category_name],
                "tickets": cls.build_ticket_join(records, "category", category_name),
            }
            for category_name in CATEGORY_ORDER
        ]
        return {
            "msg_type": "interactive",
            "card": {
                "schema": "2.0",
                "config": {"wide_screen_mode": True, "update_multi": True},
                "header": {
                    "title": {
                        "tag": "plain_text",
                        "content": f"工单会话状态 {result['range']['start']} ~ {result['range']['end']}",
                    },
                    "subtitle": {"tag": "plain_text", "content": subtitle},
                    "template": "blue",
                    "padding": "12px 12px 12px 12px",
                },
                "body": {
                    "direction": "vertical",
                    "padding": "12px 12px 12px 12px",
                    "elements": [
                        {
                            "tag": "markdown",
                            "content": "促销、券、会员、印花工单情况统计情况",
                            "text_align": "left",
                            "text_size": "normal_v2",
                            "margin": "0px 0px 8px 0px",
                        },
                        {
                            "tag": "markdown",
                            "content": "### 状态汇总",
                            "text_align": "left",
                            "text_size": "normal_v2",
                            "margin": "0px 0px 8px 0px",
                        },
                        cls.build_feishu_table(
                            columns=[
                                ("status", "状态", "text", "left"),
                                ("count", "数量", "number", "right"),
                                ("tickets", "Ticket 汇总", "text", "left"),
                            ],
                            rows=status_rows,
                        ),
                        {
                            "tag": "markdown",
                            "content": "### 分类汇总",
                            "text_align": "left",
                            "text_size": "normal_v2",
                            "margin": "8px 0px 8px 0px",
                        },
                        cls.build_feishu_table(
                            columns=[
                                ("category", "分类", "text", "left"),
                                ("count", "数量", "number", "right"),
                                ("tickets", "Ticket 汇总", "text", "left"),
                            ],
                            rows=category_rows,
                        ),
                    ],
                },
            },
        }

    @classmethod
    def build_feishu_table(
        cls,
        *,
        columns: list[tuple[str, str, str, str]],
        rows: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        构造飞书卡片表格元素。

        :param columns: 列配置，元素为 name、display_name、data_type、horizontal_align。
        :param rows: 表格行数据。
        :return: 飞书表格元素。
        """
        return {
            "tag": "table",
            "columns": [
                {
                    "data_type": data_type,
                    "vertical_align": "top",
                    "name": name,
                    "display_name": display_name,
                    "horizontal_align": horizontal_align,
                }
                for name, display_name, data_type, horizontal_align in columns
            ],
            "rows": rows,
            "row_height": "low",
            "page_size": 10,
            "header_style": {
                "background_style": "none",
                "text_size": "normal",
                "bold": True,
                "text_color": "grey",
                "text_align": "left",
                "lines": 1,
            },
        }

    @classmethod
    def send_feishu_card(cls, *, card: dict[str, Any], webhook: str) -> dict[str, Any]:
        """
        发送飞书卡片消息。

        :param card: 飞书卡片对象。
        :param webhook: 飞书机器人 webhook 地址。
        :return: 飞书接口返回结果。
        """
        logger.info(f"开始发送专题工单统计卡片 | webhook_configured={bool(webhook)}")
        request = urllib.request.Request(
            url=webhook,
            data=json.dumps(card, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
        logger.info(f"专题工单统计卡片发送接口返回 | response={payload}")
        return payload
