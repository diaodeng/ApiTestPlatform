from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any

import httpx
from sqlalchemy.orm import Session

from module_admin.dao.ai_provider_dao import AiProviderDao
from module_admin.service.ai_prompt_template_service import AiPromptTemplateService
from module_admin.service.user_config_service import UserConfigService
from utils.api_key_util import ApiKeyUtil
from utils.log_util import logger

SHANGHAI_TZ = timezone(timedelta(hours=8))
STATUS_ORDER = ("有结论", "无结论")
CATEGORY_ORDER = ("促销", "券", "会员", "印花")
DEFAULT_CATEGORY_KEYWORDS = {
    "券": {
        "word_keywords": ("gv", "coupon", "voucher", "gift card"),
        "text_keywords": ("礼物卡", "禮物卡", "礼券", "禮券", "券"),
    },
    "印花": {
        "word_keywords": ("stamp",),
        "text_keywords": ("印花",),
    },
    "会员": {
        "word_keywords": ("member", "points", "point"),
        "text_keywords": ("会员", "积分"),
    },
    "促销": {
        "word_keywords": (
            "promo",
            "promotion",
            "offer",
            "offers",
            "yuu promotion",
            "normal price",
            "20% off",
            "discount",
        ),
        "text_keywords": ("促销", "优惠", "折扣"),
    },
}
DEFAULT_STATUS_KEYWORDS = {
    "closed": (
        "已关闭",
        "关闭工单",
        "关闭",
        "已处理",
        "已修正",
        "已修复",
        "已解决",
        "解决了",
        "可以关闭",
        "不是问题",
        "非问题",
        "设计如此",
        "close",
        "closed",
        "resolved",
        "fixed",
        "done",
    ),
    "conclusion": (
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
    ),
}
TICKET_PATTERNS = (
    re.compile(r"(?im)^\s*/?\s*Ticket:\s*([^\r\n]+)"),
    re.compile(r"(?im)^\s*Ticket:\s*([^\r\n]+)"),
    re.compile(r"(?i)\b(INC\d+[A-Z]?)\b"),
    re.compile(r"(?i)\b(SCTASK\d+)\b"),
)
TOPIC_BLOCK_PATTERN = re.compile(
    r"(?ims)^\s*/?\s*主题[:：]\s*(.*?)(?:\r?\n\s*/?\s*(?:商家|门店|1线|1\.5|当前处理人|Details)\s*[:：]|\Z)"
)
TOPIC_LINE_PATTERN = re.compile(r"^\s*/?\s*主题[:：]\s*(.*)$", re.MULTILINE)


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

    FEISHU_BASE_URL = "https://open.feishu.cn/open-apis"
    _tenant_token_cache: dict[str, dict[str, Any]] = {}
    DEFAULT_TOPIC_CLASSIFY_PROMPT = (
        "你是专题工单分类助手。请根据下面的飞书工单根消息，判断这张工单是否属于专题工单，并输出一个严格 JSON 对象，"
        "不要输出 Markdown、代码块或额外解释。\n\n"
        "分类规则：\n"
        "1. 只在明确识别出专题时返回分类；无法判断时 category 输出 \"其他\"。\n"
        "2. category 仅允许输出 \"促销\"、\"券\"、\"会员\"、\"印花\" 或 \"其他\"。\n"
        "3. status 仅允许输出 \"有结论\" 或 \"无结论\"。\n"
        "4. topic 输出根消息中的主题文本，尽量保留原始主题内容。\n"
        "5. 如果消息里没有有效主题或 Ticket 编号，直接返回 \"其他\"。\n\n"
        "输出 JSON 字段：\n"
        "{\n"
        '  "category": "促销/券/会员/印花/其他",\n'
        '  "status": "有结论/无结论",\n'
        '  "topic": "主题文本",\n'
        '  "reason": "一句话说明判断依据"\n'
        "}\n"
    )
    DEFAULT_TOPIC_CLASSIFY_TASK_PROVIDER_CODE = ""
    DEFAULT_TOPIC_CLASSIFY_TASK_PROMPT_CODE = "ticket_stat_classify_default"
    USER_CONFIG_TYPE = "ticket"
    USER_CONFIG_KEY = "ticket_topic_stats_report"
    TASK_MODE_KEYWORDS = "keywords"
    TASK_MODE_AI = "ai"

    @classmethod
    def run_topic_stats(
        cls,
        db: Session,
        *,
        start_date: str | None = None,
        end_date: str | None = None,
        sources: list[dict[str, Any]] | None = None,
        app_id: str | None = None,
        app_secret: str | None = None,
        receive_chat_ids: list[str] | str | None = None,
        send: bool = False,
        keyword: str = "TRunner",
        category_mode: str = "keywords",
        ai_provider_code: str | None = None,
        ai_prompt_code: str | None = None,
        ai_prompt_content: str | None = None,
        coupon_keywords: list[str] | str | None = None,
        stamp_keywords: list[str] | str | None = None,
        member_keywords: list[str] | str | None = None,
        promo_keywords: list[str] | str | None = None,
        closed_keywords: list[str] | str | None = None,
        conclusion_keywords: list[str] | str | None = None,
        page_size: int = 50,
    ) -> dict[str, Any]:
        """
        执行专题工单统计，并按需发送飞书卡片。

        :param start_date: 统计开始日期，格式为 YYYY-MM-DD；为空时取上海时区当天。
        :param end_date: 统计结束日期，格式为 YYYY-MM-DD；为空时取上海时区当天。
        :param sources: 飞书群来源列表，每项包含 name、chatId/chat_id、priority。
        :param app_id: 飞书应用 app_id，用于获取群消息与发送消息。
        :param app_secret: 飞书应用 app_secret，用于获取群消息与发送消息。
        :param receive_chat_ids: 发送统计卡片的飞书群 chat_id 列表。
        :param send: 是否发送飞书卡片。
        :param keyword: 卡片副标题关键字。
        :param category_mode: 分类模式，keywords 表示关键词模式，ai 表示 AI 自动处理模式。
        :param ai_provider_code: AI 分类使用的 Provider 编码，未传时回退任务参数默认或用户配置。
        :param ai_prompt_code: AI 分类使用的提示词模板编码，未传时回退任务参数默认或用户配置。
        :param ai_prompt_content: AI 分类使用的提示词正文，优先级高于提示词模板编码。
        :param coupon_keywords: 专题分类“券”的补充关键词。
        :param stamp_keywords: 专题分类“印花”的补充关键词。
        :param member_keywords: 专题分类“会员”的补充关键词。
        :param promo_keywords: 专题分类“促销”的补充关键词。
        :param closed_keywords: 状态判断“有结论”中的关闭类补充关键词。
        :param conclusion_keywords: 状态判断“有结论”中的结论类补充关键词。
        :param page_size: 单页拉取消息数量。
        :return: 统计结果和发送结果摘要。
        """
        today = datetime.now(SHANGHAI_TZ).date()
        resolved_start_date = cls.parse_iso_date(start_date) if start_date else today
        resolved_end_date = cls.parse_iso_date(end_date) if end_date else today
        if resolved_end_date < resolved_start_date:
            raise ValueError("end_date 不能早于 start_date")

        normalized_sources = cls.normalize_sources(sources)
        resolved_app_id = str(app_id or "").strip()
        resolved_app_secret = str(app_secret or "").strip()
        if not resolved_app_id or not resolved_app_secret:
            raise ValueError("必须配置飞书应用 appId/appSecret")
        normalized_receive_chat_ids = cls.normalize_receive_chat_ids(receive_chat_ids)
        if send and not normalized_receive_chat_ids:
            normalized_receive_chat_ids = cls.normalize_receive_chat_ids(
                [source.chat_id for source in normalized_sources]
            )
        if send and not normalized_receive_chat_ids:
            raise ValueError("send=true 时必须配置接收群列表")

        resolved_category_mode = cls.normalize_category_mode(category_mode)
        resolved_ai_provider_code, resolved_ai_prompt_code, resolved_ai_prompt_content = cls.resolve_ai_classify_config(
            db,
            ai_provider_code=ai_provider_code,
            ai_prompt_code=ai_prompt_code,
            ai_prompt_content=ai_prompt_content,
        )
        logger.info(
            f"开始执行专题工单统计 | start_date={resolved_start_date.isoformat()} "
            f"end_date={resolved_end_date.isoformat()} source_count={len(normalized_sources)} "
            f"send={bool(send)} keyword={keyword or '-'} category_mode={resolved_category_mode}"
        )
        records = cls.collect_topic_records(
            start_date=resolved_start_date,
            end_date=resolved_end_date,
            sources=normalized_sources,
            app_id=resolved_app_id,
            app_secret=resolved_app_secret,
            category_mode=resolved_category_mode,
            db=db,
            ai_provider_code=resolved_ai_provider_code,
            ai_prompt_code=resolved_ai_prompt_code,
            ai_prompt_content=resolved_ai_prompt_content,
            coupon_keywords=coupon_keywords,
            stamp_keywords=stamp_keywords,
            member_keywords=member_keywords,
            promo_keywords=promo_keywords,
            closed_keywords=closed_keywords,
            conclusion_keywords=conclusion_keywords,
            page_size=page_size,
        )
        result = cls.build_result(
            start_date=resolved_start_date,
            end_date=resolved_end_date,
            records=records,
        )
        if send:
            card = cls.build_feishu_card(result=result, records=records, keyword=keyword)
            result["response"] = cls.send_feishu_card(
                card=card,
                app_id=resolved_app_id,
                app_secret=resolved_app_secret,
                receive_chat_ids=normalized_receive_chat_ids,
            )
            logger.info(
                f"专题工单统计卡片发送完成 | total={result['summary']['total']} "
                f"receive_chat_count={len(normalized_receive_chat_ids)} response={result.get('response')}"
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
    def normalize_receive_chat_ids(cls, value: list[str] | str | None) -> list[str]:
        """
        归一化飞书应用发送目标群列表。

        :param value: 群 chat_id 列表或逗号分隔字符串。
        :return: 去重后的 chat_id 列表。
        """
        if isinstance(value, str):
            source_list = [item.strip() for item in value.split(",")]
        elif isinstance(value, list):
            source_list = value
        else:
            source_list = []

        result: list[str] = []
        for item in source_list:
            chat_id = str(item or "").strip()
            if chat_id and chat_id not in result:
                result.append(chat_id)
        return result

    @classmethod
    def normalize_category_mode(cls, value: str | None) -> str:
        """
        归一化专题分类模式。

        :param value: 任务参数或用户配置中的模式值。
        :return: keywords 或 ai。
        """
        normalized = str(value or "").strip().lower()
        if normalized in {"ai", "auto", "llm", "model"}:
            return cls.TASK_MODE_AI
        return cls.TASK_MODE_KEYWORDS

    @classmethod
    def _normalize_prompt_content(cls, value: Any) -> str:
        """
        归一化提示词正文。

        :param value: 原始提示词内容。
        :return: 清理后的提示词正文。
        """
        return str(value or "").strip()

    @classmethod
    def _load_user_ai_classify_config(cls, db: Session, user_id: int | None) -> dict[str, Any]:
        """
        读取当前用户的专题统计 AI 配置。

        :param db: 数据库会话。
        :param user_id: 用户ID。
        :return: 用户配置字典。
        """
        if not user_id:
            return {}
        config_model = UserConfigService.get_current_user_config_services(
            db,
            int(user_id),
            cls.USER_CONFIG_TYPE,
            cls.USER_CONFIG_KEY,
        )
        if not config_model or not isinstance(config_model.config_value, dict):
            return {}
        return dict(config_model.config_value)

    @classmethod
    def resolve_ai_classify_config(
        cls,
        db: Session,
        *,
        ai_provider_code: str | None = None,
        ai_prompt_code: str | None = None,
        ai_prompt_content: str | None = None,
        user_id: int | None = None,
    ) -> tuple[str, str, str]:
        """
        解析专题统计 AI 配置，优先使用任务参数，其次使用用户配置，最后回退系统参数默认值。

        :param db: 数据库会话。
        :param ai_provider_code: 任务参数 Provider 编码。
        :param ai_prompt_code: 任务参数提示词编码。
        :param ai_prompt_content: 任务参数提示词正文。
        :param user_id: 用户ID，用于读取当前用户单独配置。
        :return: (provider_code, prompt_code, prompt_content)。
        """
        user_config = cls._load_user_ai_classify_config(db, user_id)
        config_provider_code = str(user_config.get("providerCode") or user_config.get("provider_code") or "").strip()
        config_prompt_code = str(user_config.get("promptCode") or user_config.get("prompt_code") or "").strip()
        config_prompt_content = cls._normalize_prompt_content(
            user_config.get("promptContent") or user_config.get("prompt_content")
        )
        resolved_provider_code = str(ai_provider_code or "").strip() or config_provider_code
        resolved_prompt_code = str(ai_prompt_code or "").strip() or config_prompt_code
        resolved_prompt_content = cls._normalize_prompt_content(ai_prompt_content) or config_prompt_content
        if not resolved_provider_code:
            resolved_provider_code = cls.DEFAULT_TOPIC_CLASSIFY_TASK_PROVIDER_CODE
        if not resolved_prompt_code:
            resolved_prompt_code = cls.DEFAULT_TOPIC_CLASSIFY_TASK_PROMPT_CODE
        if not resolved_prompt_content:
            prompt_templates = AiPromptTemplateService.get_prompt_template_texts_by_codes(db, [resolved_prompt_code])
            if prompt_templates:
                resolved_prompt_content = cls._normalize_prompt_content(prompt_templates[0].get("promptContent"))
        return resolved_provider_code, resolved_prompt_code, resolved_prompt_content

    @classmethod
    def _resolve_provider_headers(cls, provider) -> dict[str, str]:
        """
        构建 AI Provider 请求头。

        :param provider: Provider 数据库对象。
        :return: 请求头字典。
        """
        headers = {"Content-Type": "application/json"}
        api_key = ApiKeyUtil.decrypt_api_key(getattr(provider, "api_key_cipher_text", None))
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return headers

    @classmethod
    def _resolve_provider_url(cls, provider) -> str:
        """
        解析 AI Provider 调用地址。

        :param provider: Provider 数据库对象。
        :return: 完整接口地址。
        """
        base_url = str(getattr(provider, "base_url", "") or "").strip().rstrip("/")
        if not base_url:
            raise ValueError("Provider基础地址不能为空")
        if base_url.endswith("/chat/completions") or base_url.endswith("/responses"):
            return base_url
        return f"{base_url}/chat/completions"

    @classmethod
    def _extract_response_text(cls, response_data: dict[str, Any]) -> str:
        """
        从 OpenAI 兼容响应中提取正文。

        :param response_data: 接口响应 JSON。
        :return: 模型输出文本。
        """
        if not isinstance(response_data, dict):
            return ""
        output_text = str(response_data.get("output_text") or "").strip()
        if output_text:
            return output_text
        choices = response_data.get("choices")
        if isinstance(choices, list) and choices:
            first_choice = choices[0] if isinstance(choices[0], dict) else {}
            message = first_choice.get("message") if isinstance(first_choice, dict) else {}
            content = message.get("content") if isinstance(message, dict) else None
            if isinstance(content, list):
                content_parts: list[str] = []
                for item in content:
                    if not isinstance(item, dict):
                        continue
                    if str(item.get("type") or "").lower() == "text":
                        text = str(item.get("text") or "").strip()
                        if text:
                            content_parts.append(text)
                return "\n".join(content_parts).strip()
            if str(content or "").strip():
                return str(content).strip()
        output = response_data.get("output")
        if isinstance(output, list):
            content_parts: list[str] = []
            for item in output:
                if not isinstance(item, dict):
                    continue
                if str(item.get("type") or "").lower() != "message":
                    continue
                content = item.get("content")
                if isinstance(content, list):
                    for part in content:
                        if not isinstance(part, dict):
                            continue
                        if str(part.get("type") or "").lower() == "output_text":
                            text = str(part.get("text") or "").strip()
                            if text:
                                content_parts.append(text)
                elif str(content or "").strip():
                    content_parts.append(str(content).strip())
            return "\n".join(content_parts).strip()
        return ""

    @classmethod
    def _call_model_api(cls, *, provider, system_prompt: str, user_prompt: str, temperature: float = 0.2) -> str:
        """
        调用兼容 OpenAI 的模型接口。

        :param provider: Provider 数据库对象。
        :param system_prompt: 系统提示词。
        :param user_prompt: 用户提示词。
        :param temperature: 采样温度。
        :return: 模型返回文本。
        """
        url = cls._resolve_provider_url(provider)
        model_name = str(getattr(provider, "model_name", "") or "").strip()
        if not model_name:
            raise ValueError("Provider模型名称不能为空")
        is_responses_api = url.endswith("/responses")
        if is_responses_api:
            payload = {
                "model": model_name,
                "input": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": temperature,
            }
        else:
            payload = {
                "model": model_name,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": temperature,
            }
        with httpx.Client(timeout=60) as client:
            response = client.post(url, json=payload, headers=cls._resolve_provider_headers(provider))
            response.raise_for_status()
            response_data = response.json()
        content = cls._extract_response_text(response_data)
        if not str(content or "").strip():
            raise ValueError("AI接口未返回可解析的内容")
        return str(content).strip()

    @classmethod
    def _build_ai_category_system_prompt(cls, prompt_content: str | None) -> str:
        """
        构建专题统计 AI 的系统提示词。

        :param prompt_content: 手动配置的提示词正文。
        :return: 系统提示词文本。
        """
        prompt_text = cls._normalize_prompt_content(prompt_content)
        if prompt_text:
            return prompt_text
        return cls.DEFAULT_TOPIC_CLASSIFY_PROMPT

    @classmethod
    def _build_ai_category_user_prompt(
        cls,
        *,
        content: str,
        ticket_key: str,
        group_name: str,
        priority: str,
        topic: str,
    ) -> str:
        """
        构建专题统计 AI 的用户提示词。

        :param content: 根消息全文。
        :param ticket_key: Ticket 编号。
        :param group_name: 群名称。
        :param priority: 优先级。
        :param topic: 主题文本。
        :return: 用户提示词文本。
        """
        return (
            "请根据下面的飞书工单消息判断专题分类和会话状态，并返回 JSON。\n"
            f"Ticket: {ticket_key}\n"
            f"群名称: {group_name}\n"
            f"优先级: {priority}\n"
            f"主题: {topic or '-'}\n"
            f"原始消息:\n{content}"
        )

    @classmethod
    def classify_category_with_ai(
        cls,
        db: Session,
        *,
        content: str,
        ticket_key: str,
        group_name: str,
        priority: str,
        topic: str,
        provider_code: str | None = None,
        prompt_code: str | None = None,
        prompt_content: str | None = None,
    ) -> tuple[str, str, str]:
        """
        使用 AI 解析专题分类和状态。

        :param db: 数据库会话。
        :param content: 根消息全文。
        :param ticket_key: Ticket 编号。
        :param group_name: 群名称。
        :param priority: 优先级。
        :param topic: 主题文本。
        :param provider_code: Provider 编码。
        :param prompt_code: 提示词编码。
        :param prompt_content: 提示词正文。
        :return: (category, status, topic)。
        """
        resolved_provider_code = str(provider_code or "").strip()
        resolved_prompt_code = str(prompt_code or "").strip()
        if not resolved_provider_code:
            raise ValueError("AI 分类 Provider 未配置")
        provider = AiProviderDao.get_ai_provider_by_code(db, resolved_provider_code)
        if not provider or not bool(getattr(provider, "enabled", True)):
            raise ValueError(f"Provider不存在或已停用: {resolved_provider_code}")

        system_prompt = cls._build_ai_category_system_prompt(prompt_content)
        user_prompt = cls._build_ai_category_user_prompt(
            content=content,
            ticket_key=ticket_key,
            group_name=group_name,
            priority=priority,
            topic=topic,
        )
        response_text = cls._call_model_api(provider=provider, system_prompt=system_prompt, user_prompt=user_prompt)
        try:
            response_data = json.loads(response_text)
        except Exception:
            response_data = {}
        if not isinstance(response_data, dict):
            response_data = {}
        category = str(response_data.get("category") or "其他").strip() or "其他"
        status = str(response_data.get("status") or "无结论").strip() or "无结论"
        topic_text = str(response_data.get("topic") or topic or "").strip()
        if category not in CATEGORY_ORDER and category != "其他":
            category = "其他"
        if status not in STATUS_ORDER:
            status = "无结论"
        logger.info(
            f"专题工单AI分类完成 | ticket_key={ticket_key} group_name={group_name} "
            f"provider_code={resolved_provider_code} prompt_code={resolved_prompt_code or '-'} "
            f"category={category} status={status}"
        )
        return category, status, topic_text

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
        if isinstance(value, dict):
            if "content" in value:
                return cls.cell_text(value.get("content"))
            return json.dumps(value, ensure_ascii=False)
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
        if date_text.isdigit():
            timestamp = int(date_text)
            if timestamp > 10_000_000_000:
                timestamp = timestamp / 1000
            return datetime.fromtimestamp(timestamp, tz=SHANGHAI_TZ).date()
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
    def text_matches_any_word(cls, text: str, words: Iterable[str]) -> bool:
        """
        判断文本是否命中任一英文词或英文短语，避免命中其他单词内部片段。

        :param text: 已归一化的小写文本。
        :param words: 英文词或短语列表。
        :return: 命中任一完整词或短语时返回 True。
        """
        for word in words:
            keyword = str(word or "").strip().lower()
            if not keyword:
                continue
            escaped_keyword = re.escape(keyword).replace(r"\ ", r"\s+")
            pattern = rf"(?<![a-z0-9]){escaped_keyword}(?![a-z0-9])"
            if re.search(pattern, text):
                return True
        return False

    @classmethod
    def normalize_keywords(cls, value: Any) -> tuple[str, ...]:
        """
        将任务参数中的关键词值归一化为去重后的字符串元组。

        :param value: 任务参数中的关键词值，支持字符串、列表、元组或集合。
        :return: 去重后的关键词元组。
        """
        if value is None:
            return ()
        if isinstance(value, str):
            raw_items = re.split(r"[,\n，；;]+", value)
        elif isinstance(value, dict):
            raw_items = []
            for item in value.values():
                raw_items.extend(cls.normalize_keywords(item))
        elif isinstance(value, Iterable):
            raw_items = list(value)
        else:
            raw_items = [value]

        keywords: list[str] = []
        for item in raw_items:
            keyword = str(item or "").strip()
            if keyword and keyword not in keywords:
                keywords.append(keyword)
        return tuple(keywords)

    @classmethod
    def merge_keywords(cls, defaults: Iterable[str], *extra_values: Any) -> tuple[str, ...]:
        """
        合并代码内置关键词与任务参数关键词。

        :param defaults: 代码内置关键词。
        :param extra_values: 任务参数中传入的补充关键词。
        :return: 合并并去重后的关键词元组。
        """
        merged: list[str] = []
        for keyword in defaults:
            normalized = str(keyword or "").strip()
            if normalized and normalized not in merged:
                merged.append(normalized)
        for extra_value in extra_values:
            for keyword in cls.normalize_keywords(extra_value):
                if keyword not in merged:
                    merged.append(keyword)
        return tuple(merged)

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
    def get_category_bucket(
        cls,
        topic: str,
        *,
        coupon_keywords: list[str] | str | None = None,
        stamp_keywords: list[str] | str | None = None,
        member_keywords: list[str] | str | None = None,
        promo_keywords: list[str] | str | None = None,
    ) -> str:
        """
        按主题归类为促销、券、会员、印花。

        :param topic: 工单主题文本。
        :param coupon_keywords: “券”分类的补充关键词。
        :param stamp_keywords: “印花”分类的补充关键词。
        :param member_keywords: “会员”分类的补充关键词。
        :param promo_keywords: “促销”分类的补充关键词。
        :return: 分类结果。
        """
        text = (topic or "").lower()
        coupon_word_keywords = cls.merge_keywords(DEFAULT_CATEGORY_KEYWORDS["券"]["word_keywords"], coupon_keywords)
        coupon_text_keywords = cls.merge_keywords(DEFAULT_CATEGORY_KEYWORDS["券"]["text_keywords"], coupon_keywords)
        if cls.text_matches_any_word(text, coupon_word_keywords) or cls.text_contains_any(text, coupon_text_keywords):
            return "券"
        stamp_word_keywords = cls.merge_keywords(DEFAULT_CATEGORY_KEYWORDS["印花"]["word_keywords"], stamp_keywords)
        stamp_text_keywords = cls.merge_keywords(DEFAULT_CATEGORY_KEYWORDS["印花"]["text_keywords"], stamp_keywords)
        if cls.text_matches_any_word(text, stamp_word_keywords) or cls.text_contains_any(text, stamp_text_keywords):
            return "印花"
        member_word_keywords = cls.merge_keywords(DEFAULT_CATEGORY_KEYWORDS["会员"]["word_keywords"], member_keywords)
        member_text_keywords = cls.merge_keywords(DEFAULT_CATEGORY_KEYWORDS["会员"]["text_keywords"], member_keywords)
        if cls.text_matches_any_word(text, member_word_keywords) or cls.text_contains_any(text, member_text_keywords):
            return "会员"
        promo_word_keywords = cls.merge_keywords(DEFAULT_CATEGORY_KEYWORDS["促销"]["word_keywords"], promo_keywords)
        promo_text_keywords = cls.merge_keywords(DEFAULT_CATEGORY_KEYWORDS["促销"]["text_keywords"], promo_keywords)
        if cls.text_matches_any_word(text, promo_word_keywords) or cls.text_contains_any(text, promo_text_keywords):
            return "促销"
        return "其他"

    @classmethod
    def get_session_status(
        cls,
        content: str,
        replies: list[dict[str, Any]] | None,
        *,
        closed_keywords: list[str] | str | None = None,
        conclusion_keywords: list[str] | str | None = None,
    ) -> str:
        """
        根据根消息和线程回复判断会话状态。

        :param content: 根消息全文。
        :param replies: 线程回复列表。
        :param closed_keywords: “有结论”中的关闭类补充关键词。
        :param conclusion_keywords: “有结论”中的结论类补充关键词。
        :return: 有结论或无结论。
        """
        all_text = [content or ""]
        all_text.extend(cls.cell_text(reply.get("content")) for reply in replies or [])
        joined = "\n".join(all_text).lower()

        merged_closed_keywords = cls.merge_keywords(DEFAULT_STATUS_KEYWORDS["closed"], closed_keywords)
        if cls.text_contains_any(joined, merged_closed_keywords):
            return "有结论"
        merged_conclusion_keywords = cls.merge_keywords(DEFAULT_STATUS_KEYWORDS["conclusion"], conclusion_keywords)
        if cls.text_contains_any(joined, merged_conclusion_keywords):
            return "有结论"
        return "无结论"

    @classmethod
    def request_feishu_json(
        cls,
        *,
        method: str,
        path: str,
        tenant_access_token: str | None = None,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        timeout_sec: int = 30,
    ) -> dict[str, Any]:
        """
        调用飞书开放平台接口并返回 JSON。

        :param method: HTTP 方法。
        :param path: 以 /open-apis 开头之后的接口路径。
        :param tenant_access_token: 飞书 tenant_access_token。
        :param params: 查询参数。
        :param json_body: JSON 请求体。
        :param timeout_sec: 超时时间，单位秒。
        :return: 飞书接口返回 JSON。
        """
        normalized_path = path if path.startswith("/") else f"/{path}"
        url = f"{cls.FEISHU_BASE_URL}{normalized_path}"
        if params:
            query = urllib.parse.urlencode(
                {key: value for key, value in params.items() if value not in (None, "")}
            )
            if query:
                url = f"{url}?{query}"

        headers = {"Content-Type": "application/json; charset=utf-8"}
        if tenant_access_token:
            headers["Authorization"] = f"Bearer {tenant_access_token}"
        data = json.dumps(json_body or {}, ensure_ascii=False).encode("utf-8") if json_body is not None else None
        request = urllib.request.Request(url=url, data=data, headers=headers, method=method.upper())
        try:
            with urllib.request.urlopen(request, timeout=timeout_sec) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            raise RuntimeError(f"飞书接口请求失败: {url}, error={exc}") from exc

        if int(payload.get("code") or 0) != 0:
            raise RuntimeError(f"飞书接口返回失败: {payload.get('msg') or payload}")
        return payload

    @classmethod
    def get_tenant_access_token(cls, app_id: str, app_secret: str) -> str:
        """
        获取飞书 tenant_access_token，并按 app_id 做内存缓存。

        :param app_id: 飞书应用 app_id。
        :param app_secret: 飞书应用 app_secret。
        :return: tenant_access_token。
        """
        normalized_app_id = str(app_id or "").strip()
        normalized_secret = str(app_secret or "").strip()
        if not normalized_app_id or not normalized_secret:
            raise ValueError("飞书应用 appId/appSecret 未配置")

        now = datetime.now(SHANGHAI_TZ)
        cached = cls._tenant_token_cache.get(normalized_app_id)
        if isinstance(cached, dict):
            expire_at = cached.get("expire_at")
            token = str(cached.get("token") or "").strip()
            if isinstance(expire_at, datetime) and expire_at > now and token:
                return token

        payload = cls.request_feishu_json(
            method="POST",
            path="/auth/v3/tenant_access_token/internal",
            json_body={"app_id": normalized_app_id, "app_secret": normalized_secret},
        )
        token = str(
            payload.get("tenant_access_token")
            or payload.get("data", {}).get("tenant_access_token")
            or ""
        ).strip()
        expire = int(payload.get("expire") or payload.get("data", {}).get("expire") or 7200)
        if not token:
            raise RuntimeError("飞书 tenant_access_token 为空")
        cls._tenant_token_cache[normalized_app_id] = {
            "token": token,
            "expire_at": now + timedelta(seconds=max(expire - 120, 60)),
        }
        return token

    @classmethod
    def parse_message_content(cls, message: dict[str, Any]) -> str:
        """
        从飞书消息结构中提取可统计的正文文本。

        :param message: 飞书消息对象。
        :return: 消息正文文本。
        """
        raw_content = message.get("content")
        body = message.get("body") if isinstance(message.get("body"), dict) else {}
        if raw_content in (None, ""):
            raw_content = body.get("content")
        content_text = cls.cell_text(raw_content)
        try:
            content_json = json.loads(content_text)
        except Exception:
            return content_text

        if isinstance(content_json, dict):
            if isinstance(content_json.get("title"), str) or isinstance(content_json.get("content"), list):
                text_parts: list[str] = []
                title = str(content_json.get("title") or "").strip()
                if title:
                    text_parts.append(title)
                for line in content_json.get("content") or []:
                    for item in line if isinstance(line, list) else []:
                        if isinstance(item, dict):
                            text = str(item.get("text") or item.get("content") or "").strip()
                            if text:
                                text_parts.append(text)
                return "\n".join(text_parts).strip() or content_text
            for key in ("text", "content"):
                if isinstance(content_json.get(key), str):
                    return str(content_json.get(key) or "")
        return content_text

    @classmethod
    def normalize_feishu_message(cls, message: dict[str, Any]) -> dict[str, Any]:
        """
        将飞书开放 API 消息结构归一化为统计逻辑使用的字段。

        :param message: 飞书开放 API 原始消息。
        :return: 归一化后的消息字段。
        """
        message_id = str(message.get("message_id") or message.get("messageId") or "").strip()
        root_id = str(message.get("root_id") or message.get("rootId") or "").strip()
        parent_id = str(message.get("parent_id") or message.get("parentId") or "").strip()
        thread_id = str(message.get("thread_id") or message.get("threadId") or "").strip()
        create_time = str(message.get("create_time") or message.get("createTime") or "").strip()
        content = cls.parse_message_content(message)
        return {
            **message,
            "message_id": message_id,
            "msg_type": message.get("msg_type") or message.get("msgType"),
            "content": content,
            "create_time": create_time,
            "root_id": root_id,
            "parent_id": parent_id,
            "thread_id": thread_id,
            "thread_message_position": message.get("thread_message_position") or message.get("threadMessagePosition"),
            "thread_replies": [],
        }

    @classmethod
    def is_root_message(cls, message: dict[str, Any]) -> bool:
        """
        判断消息是否为群会话根消息。

        :param message: 归一化后的飞书消息。
        :return: 根消息返回 True。
        """
        position = str(message.get("thread_message_position") or "").strip()
        if position:
            return position == "-1"
        message_id = str(message.get("message_id") or "").strip()
        root_id = str(message.get("root_id") or "").strip()
        parent_id = str(message.get("parent_id") or "").strip()
        return not root_id or root_id == message_id or not parent_id

    @classmethod
    def list_thread_replies(
        cls,
        *,
        tenant_access_token: str,
        message: dict[str, Any],
        page_size: int,
    ) -> list[dict[str, Any]]:
        """
        通过飞书开放 API 拉取单条根消息的会话回复。

        :param tenant_access_token: 飞书 tenant_access_token。
        :param message: 根消息。
        :param page_size: 单页拉取数量。
        :return: 归一化后的回复消息列表。
        """
        message_id = str(message.get("message_id") or "").strip()
        thread_id = str(message.get("thread_id") or message_id).strip()
        if not thread_id:
            return []

        replies: list[dict[str, Any]] = []
        page_token = None
        page_index = 1
        resolved_page_size = max(1, min(int(page_size or 50), 100))
        while True:
            params = {
                "container_id_type": "thread",
                "container_id": thread_id,
                "page_size": resolved_page_size,
                "sort_type": "ByCreateTimeAsc",
                "page_token": page_token,
            }
            logger.info(f"开始拉取飞书消息回复 | message_id={message_id} thread_id={thread_id} page_index={page_index}")
            payload = cls.request_feishu_json(
                method="GET",
                path="/im/v1/messages",
                tenant_access_token=tenant_access_token,
                params=params,
            )
            data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
            page_items = data.get("items") or data.get("messages") or []
            normalized_items = [cls.normalize_feishu_message(item) for item in page_items if isinstance(item, dict)]
            replies.extend(
                item for item in normalized_items if str(item.get("message_id") or "") != message_id
            )
            logger.info(
                f"飞书消息回复页拉取完成 | message_id={message_id} page_index={page_index} "
                f"page_count={len(page_items)} total_count={len(replies)} has_more={bool(data.get('has_more'))}"
            )
            if not data.get("has_more"):
                break
            page_token = data.get("page_token")
            page_index += 1
        return replies

    @classmethod
    def list_chat_messages(
        cls,
        *,
        chat_id: str,
        start_date: date,
        end_date: date,
        tenant_access_token: str,
        page_size: int = 50,
    ) -> list[dict[str, Any]]:
        """
        通过飞书开放 API 分页拉取指定群在日期范围内的消息。

        :param chat_id: 飞书群 chat_id。
        :param start_date: 起始日期，闭区间。
        :param end_date: 结束日期，闭区间。
        :param tenant_access_token: 飞书 tenant_access_token。
        :param page_size: 单页数量。
        :return: 归一化后的消息列表。
        """
        start_time = datetime.combine(start_date, datetime.min.time(), tzinfo=SHANGHAI_TZ)
        end_time = datetime.combine(end_date + timedelta(days=1), datetime.min.time(), tzinfo=SHANGHAI_TZ)
        start_timestamp = int(start_time.timestamp())
        end_timestamp = int(end_time.timestamp())
        page_token = None
        messages: list[dict[str, Any]] = []
        resolved_page_size = max(1, min(int(page_size or 50), 100))
        page_index = 1

        while True:
            logger.info(
                f"开始拉取飞书群消息 | chat_id={chat_id} page_index={page_index} "
                f"start_timestamp={start_timestamp} end_timestamp={end_timestamp}"
            )
            payload = cls.request_feishu_json(
                method="GET",
                path="/im/v1/messages",
                tenant_access_token=tenant_access_token,
                params={
                    "container_id_type": "chat",
                    "container_id": chat_id,
                    "start_time": start_timestamp,
                    "end_time": end_timestamp,
                    "page_size": resolved_page_size,
                    "sort_type": "ByCreateTimeAsc",
                    "page_token": page_token,
                },
            )
            data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
            page_messages = data.get("items") or data.get("messages") or []
            normalized_messages = [
                cls.normalize_feishu_message(message) for message in page_messages if isinstance(message, dict)
            ]
            for message in normalized_messages:
                if cls.is_root_message(message):
                    message["thread_replies"] = cls.list_thread_replies(
                        tenant_access_token=tenant_access_token,
                        message=message,
                        page_size=page_size,
                    )
            messages.extend(normalized_messages)
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
        db: Session,
        start_date: date,
        end_date: date,
        sources: list[TopicTicketSource],
        app_id: str,
        app_secret: str,
        category_mode: str = "keywords",
        ai_provider_code: str | None = None,
        ai_prompt_code: str | None = None,
        ai_prompt_content: str | None = None,
        coupon_keywords: list[str] | str | None = None,
        stamp_keywords: list[str] | str | None = None,
        member_keywords: list[str] | str | None = None,
        promo_keywords: list[str] | str | None = None,
        closed_keywords: list[str] | str | None = None,
        conclusion_keywords: list[str] | str | None = None,
        page_size: int = 50,
    ) -> list[TopicTicketRecord]:
        """
        采集并过滤专题工单记录。

        :param start_date: 统计起始日期。
        :param end_date: 统计结束日期。
        :param sources: 飞书群来源配置。
        :param app_id: 飞书应用 app_id。
        :param app_secret: 飞书应用 app_secret。
        :param category_mode: 分类模式。
        :param ai_provider_code: AI 分类 Provider 编码。
        :param ai_prompt_code: AI 分类提示词编码。
        :param ai_prompt_content: AI 分类提示词正文。
        :param coupon_keywords: “券”分类的补充关键词。
        :param stamp_keywords: “印花”分类的补充关键词。
        :param member_keywords: “会员”分类的补充关键词。
        :param promo_keywords: “促销”分类的补充关键词。
        :param closed_keywords: “有结论”中的关闭类补充关键词。
        :param conclusion_keywords: “有结论”中的结论类补充关键词。
        :param page_size: 单页拉取消息数量。
        :return: 已去重、分类和状态判断的工单记录。
        """
        records: list[TopicTicketRecord] = []
        seen_ticket_keys: set[str] = set()
        tenant_access_token = cls.get_tenant_access_token(app_id, app_secret)

        for source in sources:
            logger.info(
                f"开始处理专题工单来源 | group_name={source.name} chat_id={source.chat_id} priority={source.priority}"
            )
            messages = cls.list_chat_messages(
                chat_id=source.chat_id,
                start_date=start_date,
                end_date=end_date,
                tenant_access_token=tenant_access_token,
                page_size=page_size,
            )
            logger.info(f"专题工单来源消息拉取完成 | group_name={source.name} raw_count={len(messages)}")

            for message in messages:
                if message.get("msg_type") not in ("post", "text"):
                    continue
                if not cls.is_root_message(message):
                    continue

                content = cls.cell_text(message.get("content"))
                if (
                    "Ticket:" not in content
                    and "Ticket：" not in content
                    and "主题:" not in content
                    and "主题：" not in content
                ):
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
                if category_mode == cls.TASK_MODE_AI:
                    category, status, topic = cls.classify_category_with_ai(
                        db,
                        content=content,
                        ticket_key=ticket_key,
                        group_name=source.name,
                        priority=source.priority,
                        topic=topic,
                        provider_code=ai_provider_code,
                        prompt_code=ai_prompt_code,
                        prompt_content=ai_prompt_content,
                    )
                else:
                    category = cls.get_category_bucket(
                        topic,
                        coupon_keywords=coupon_keywords,
                        stamp_keywords=stamp_keywords,
                        member_keywords=member_keywords,
                        promo_keywords=promo_keywords,
                    )
                    status = cls.get_session_status(
                        content,
                        message.get("thread_replies") or [],
                        closed_keywords=closed_keywords,
                        conclusion_keywords=conclusion_keywords,
                    )
                if category == "其他":
                    logger.info(
                        f"专题工单消息跳过：主题未命中分类 | ticket_key={ticket_key} "
                        f"group_name={source.name} topic={topic or '-'}"
                    )
                    continue

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
        :return: 可发送到飞书应用的卡片对象。
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
    def send_feishu_card(
        cls,
        *,
        card: dict[str, Any],
        app_id: str,
        app_secret: str,
        receive_chat_ids: list[str],
    ) -> dict[str, Any]:
        """
        通过飞书应用发送卡片消息。

        :param card: 飞书卡片对象。
        :param app_id: 飞书应用 app_id。
        :param app_secret: 飞书应用 app_secret。
        :param receive_chat_ids: 接收群 chat_id 列表。
        :return: 飞书接口返回结果。
        """
        tenant_access_token = cls.get_tenant_access_token(app_id, app_secret)
        result = {"sentCount": 0, "responses": []}
        for chat_id in receive_chat_ids:
            logger.info(f"开始发送专题工单统计卡片 | chat_id={chat_id}")
            payload = cls.request_feishu_json(
                method="POST",
                path="/im/v1/messages",
                tenant_access_token=tenant_access_token,
                params={"receive_id_type": "chat_id"},
                json_body={
                    "receive_id": chat_id,
                    "msg_type": "interactive",
                    "content": json.dumps(card.get("card") or card, ensure_ascii=False),
                },
            )
            result["sentCount"] += 1
            result["responses"].append({"chat_id": chat_id, "response": payload})
            logger.info(f"专题工单统计卡片发送接口返回 | chat_id={chat_id} response={payload}")
        return result
