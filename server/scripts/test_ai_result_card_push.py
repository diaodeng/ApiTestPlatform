"""
AI 分析结果回帖卡片真实发送验证脚本。

用途：构造一张 AI 分析结果卡片（成功/失败各一张），通过 .env 中配置的
飞书自定义群机器人 webhook 真实发送到测试群，验证卡片结构在飞书客户端的渲染效果。

说明：
- 正式链路（aiResultFollowUp 回帖）通过飞书应用身份 im/v1 messages reply 发送
  msg_type=interactive，卡片 JSON 与本脚本构造的完全一致；
- 本脚本仅借助群机器人 webhook 通道做渲染验证，不影响正式链路。

使用方式（在 server 目录执行）：
  uv run python scripts/test_ai_result_card_push.py            # 发送成功 + 失败两张卡片
  uv run python scripts/test_ai_result_card_push.py success    # 只发成功卡片
  uv run python scripts/test_ai_result_card_push.py failed     # 只发失败卡片
  uv run python scripts/test_ai_result_card_push.py trimmed    # 发送字段裁剪卡片（只展示结论/根因/建议）
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import httpx

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from config.env import FeishuBotConfig  # noqa: E402  需先注入 server 根路径
from modules.ticket.entity.do.ticket_do import Ticket  # noqa: E402
from modules.ticket.service.sync.ticket_ai_result_reply_card_service import (  # noqa: E402
    TicketAiResultReplyCardService,
)
from utils.log_util import logger  # noqa: E402


def build_mock_ticket() -> Ticket:
    """
    构造用于验证的模拟工单对象（不落库）。

    :return: 填充了示例字段的工单 ORM 实例。
    """
    ticket = Ticket()
    ticket.ticket_no = "TICKET-20260911-0001"
    ticket.title = "【示例】订单列表接口偶发超时"
    ticket.module_name = "订单中心"
    ticket.merchant_name = "示例商家"
    ticket.ticket_url = "https://example.com/ticket/TICKET-20260911-0001"
    return ticket


def success_payload() -> dict:
    """
    构造成功态 AI 分析结果示例载荷。

    :return: 分析结果字典。
    """
    return {
        "analysis_summary": "订单列表接口在高峰期出现 P99 超时，超时请求集中在按商家维度的大分页查询，"
        "初步判定为慢查询导致的连接池耗尽，属于服务端性能问题而非网络抖动。",
        "root_cause": "order_list 接口的分页查询未命中 merchant_id + created_at 组合索引，"
        "高峰期全表扫描使单次查询耗时升至 3s 以上，占满数据库连接池后引发连锁超时。",
        "fix_suggestion": "1. 为订单表补充 merchant_id + created_at 组合索引；\n"
        "2. 分页查询增加最大页深限制，禁止深翻页；\n"
        "3. 连接池上限临时上调并补充慢查询告警。",
        "confidence": 0.86,
        "evidence": [
            "慢查询日志：SELECT ... ORDER BY created_at DESC LIMIT 10000, 20 耗时 3.2s",
            "DB 连接池监控峰值 100%",
        ],
        "risk_items": ["加索引期间大表 DDL 可能引发主从延迟"],
        "next_steps": ["DBA 评审索引变更窗口", "低峰期执行 DDL 并观察 P99"],
    }


def failed_payload() -> dict:
    """
    构造失败态示例载荷。

    :return: 失败信息字典。
    """
    return {"error_message": "AI 服务调用超时（重试 3 次后仍失败）"}


def send_card(card: dict, *, tag: str) -> None:
    """
    通过 .env 配置的飞书群机器人 webhook 真实发送卡片。

    群机器人若开启关键词安全校验，消息必须命中关键词才能发出；
    这里按项目既有推送习惯在卡片标题前加「【QTR测试】」关键词前缀，
    仅测试脚本需要，正式链路（飞书应用回帖）无该限制。

    :param card: 卡片 JSON（TicketAiResultReplyCardService 构造产物）。
    :param tag: 日志标记，用于区分成功/失败样例。
    :return: 无。
    """
    keyword = "【QTR测试】"
    origin_title = (card.get("header", {}).get("title", {}) or {}).get("content", "")
    card = {**card, "header": {**card.get("header", {}),
                               "title": {"tag": "plain_text", "content": f"{keyword}{origin_title}"}}}
    # 补充群机器人关键词「TRunner」备注，与既有 QTR 推送文案保持一致，确保通过关键词校验。
    elements = list(card.get("elements") or [])
    elements.append({"tag": "note", "elements": [{"tag": "plain_text", "content": "【TRunner】AI 回帖卡片渲染验证"}]})
    card = {**card, "elements": elements}
    token = str(FeishuBotConfig.feishu_bot_token or "").strip()
    if not token:
        raise RuntimeError("FeishuBotConfig.feishu_bot_token 未配置，请检查 .env")
    url = token if token.startswith("https:") else f"https://open.feishu.cn/open-apis/bot/v2/hook/{token}"
    body = {"msg_type": "interactive", "card": card}
    with httpx.Client(verify=False, timeout=15.0) as client:
        response = client.post(url=url, content=json.dumps(body, ensure_ascii=False),
                               headers={"Content-Type": "application/json"})
    logger.info(f"卡片发送结果 [{tag}]: status={response.status_code}, body={response.text}")
    if response.status_code != 200:
        raise RuntimeError(f"飞书 webhook 返回 {response.status_code}")


def main() -> None:
    """脚本入口：按命令行参数选择发送成功/失败样例卡片。"""
    parser = argparse.ArgumentParser(description="AI 分析结果回帖卡片真实发送验证")
    parser.add_argument(
        "scene", nargs="?", default="all",
        choices=["all", "success", "failed", "trimmed"],
        help="发送场景；trimmed 验证卡片展示字段白名单（仅结论/根因/建议）",
    )
    args = parser.parse_args()

    ticket = build_mock_ticket()
    if args.scene in {"all", "success"}:
        card = TicketAiResultReplyCardService.build_ai_result_reply_card(
            ticket=ticket,
            ai_task_status="success",
            ai_result_payload=success_payload(),
        )
        send_card(card, tag="success")
    if args.scene in {"all", "failed"}:
        card = TicketAiResultReplyCardService.build_ai_result_reply_card(
            ticket=ticket,
            ai_task_status="failed",
            ai_error_message=failed_payload()["error_message"],
        )
        send_card(card, tag="failed")
    if args.scene == "trimmed":
        card = TicketAiResultReplyCardService.build_ai_result_reply_card(
            ticket=ticket,
            ai_task_status="success",
            ai_result_payload=success_payload(),
            card_fields=["analysis_summary", "root_cause", "fix_suggestion"],
        )
        send_card(card, tag="trimmed")
    logger.info(f"卡片发送验证完成: scene={args.scene}")


if __name__ == "__main__":
    main()
