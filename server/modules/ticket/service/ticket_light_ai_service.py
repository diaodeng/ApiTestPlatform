from __future__ import annotations

import json
import re
from datetime import date, datetime
from typing import Any

import httpx
from sqlalchemy.orm import Session

from config.database import SessionLocal
from module_admin.dao.ai_provider_dao import AiProviderDao
from module_admin.entity.do.config_do import SysConfig
from module_admin.service.ai_prompt_template_service import AiPromptTemplateService
from module_admin.service.ai_task_execution_service import AiTaskExecutionService
from utils.api_key_util import ApiKeyUtil
from utils.log_util import logger


class TicketLightAiService:
    """
    工单轻量 AI 任务服务，负责翻译、规则提取等无需 Codex 的接口调用。
    """

    DEFAULT_TIMEOUT_SEC = 60
    VERSION_PATTERN = re.compile(r"(?:版本号|版本|version|app[_\s-]*version)[:：\s-]*([A-Za-z0-9._/-]+)", re.IGNORECASE)
    JSON_BLOCK_PATTERN = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.IGNORECASE | re.DOTALL)
    CONFIG_TRANSLATE_ENABLED = "ticket.ai.translate.enabled"
    CONFIG_TRANSLATE_PROVIDER = "ticket.ai.translate.provider.code"
    CONFIG_TRANSLATE_PROMPT = "ticket.ai.translate.prompt.code"
    CONFIG_TITLE_SUMMARY_ENABLED = "ticket.ai.title.summary.enabled"
    CONFIG_TITLE_SUMMARY_PROVIDER = "ticket.ai.title.summary.provider.code"
    CONFIG_TITLE_SUMMARY_PROMPT = "ticket.ai.title.summary.prompt.code"
    CONFIG_CATEGORY_CLASSIFY_ENABLED = "ticket.ai.category.classify.enabled"
    CONFIG_CATEGORY_CLASSIFY_PROVIDER = "ticket.ai.category.classify.provider.code"
    CONFIG_CATEGORY_CLASSIFY_PROMPT = "ticket.ai.category.classify.prompt.code"
    CONFIG_LOG_EXTRACT_ENABLED = "ticket.ai.log_extract.enabled"
    CONFIG_LOG_EXTRACT_PROVIDER = "ticket.ai.log_extract.provider.code"
    CONFIG_LOG_EXTRACT_PROMPT = "ticket.ai.log_extract.prompt.code"
    TICKET_CATEGORY_CANDIDATES = (
        "促销",
        "券",
        "会员",
        "取单挂单",
        "eservice",
        "POS卡死",
        "POS客户端",
        "现金管理",
        "销售回传",
        "日结",
        "支持类",
    )
    TICKET_CATEGORY_ALIASES = {
        "促销": "促销",
        "promotion": "促销",
        "券": "券",
        "优惠券": "券",
        "coupon": "券",
        "会员": "会员",
        "member": "会员",
        "取单挂单": "取单挂单",
        "挂单": "取单挂单",
        "取单": "取单挂单",
        "eservice": "eservice",
        "e-service": "eservice",
        "pos卡死": "POS卡死",
        "卡死": "POS卡死",
        "死机": "POS卡死",
        "pos客户端": "POS客户端",
        "客户端": "POS客户端",
        "cash": "现金管理",
        "现金管理": "现金管理",
        "销售回传": "销售回传",
        "销售上传": "销售回传",
        "sale upload": "销售回传",
        "日结": "日结",
        "日结算": "日结",
        "支持类": "支持类",
        "support": "支持类",
    }

    @classmethod
    def is_translation_enabled(cls, db: Session) -> bool:
        """
        读取工单轻量翻译总开关。
        :param db: 数据库会话
        :return: 是否启用翻译
        """
        config_row = db.query(SysConfig).filter(SysConfig.config_key == cls.CONFIG_TRANSLATE_ENABLED).first()
        return str(getattr(config_row, "config_value", "false") or "false").strip().lower() == "true"

    @classmethod
    def is_title_summary_enabled(cls, db: Session) -> bool:
        """
        读取工单标题总结总开关。
        :param db: 数据库会话
        :return: 是否启用标题总结
        """
        config_row = db.query(SysConfig).filter(SysConfig.config_key == cls.CONFIG_TITLE_SUMMARY_ENABLED).first()
        return str(getattr(config_row, "config_value", "false") or "false").strip().lower() == "true"

    @classmethod
    def is_category_classification_enabled(cls, db: Session) -> bool:
        """
        读取工单自动分类总开关。
        :param db: 数据库会话
        :return: 是否启用自动分类
        """
        config_row = db.query(SysConfig).filter(SysConfig.config_key == cls.CONFIG_CATEGORY_CLASSIFY_ENABLED).first()
        return str(getattr(config_row, "config_value", "false") or "false").strip().lower() == "true"

    @classmethod
    def is_log_extract_enabled(cls, db: Session) -> bool:
        """
        读取工单日志参数提取总开关。
        :param db: 数据库会话
        :return: 是否启用日志参数提取
        """
        config_row = db.query(SysConfig).filter(SysConfig.config_key == cls.CONFIG_LOG_EXTRACT_ENABLED).first()
        return str(getattr(config_row, "config_value", "false") or "false").strip().lower() == "true"

    @classmethod
    def extract_version_key_from_text(cls, text: str | None) -> str:
        """
        从文本中提取版本号。
        :param text: 待分析文本
        :return: 版本号，未命中返回空字符串
        """
        if not text:
            return ""
        match = cls.VERSION_PATTERN.search(text)
        if not match:
            return ""
        return str(match.group(1) or "").strip()

    @staticmethod
    def _build_translation_prompt(title: str, content: str) -> str:
        """
        构建工单翻译请求内容。
        :param title: 工单标题
        :param content: 工单原文
        :return: 请求文本
        """
        parts = [f"标题：{title}".strip(), f"原文：\n{content}".strip()]
        return "\n\n".join([part for part in parts if part.strip()])

    @staticmethod
    def _build_title_summary_prompt(content: str) -> str:
        """
        构建工单标题总结请求内容。
        :param content: 工单描述
        :return: 请求文本
        """
        return f"工单描述：\n{content}".strip()

    @classmethod
    def _build_category_classification_prompt(cls, title: str, content: str) -> str:
        """
        构建工单自动分类请求内容。
        :param title: 工单标题
        :param content: 工单描述
        :return: 请求文本
        """
        categories = "、".join(cls.TICKET_CATEGORY_CANDIDATES)
        parts = [
            f"可选分类：{categories}",
            f"工单标题：{title}".strip(),
            f"工单描述：\n{content}".strip(),
            "请仅输出最匹配的一个分类名称。",
        ]
        return "\n\n".join([part for part in parts if str(part or "").strip()])

    @classmethod
    def _build_sync_extract_prompt(cls, title: str, content: str, raw_payload: dict[str, Any] | None = None) -> str:
        """
        构建工单同步统一提取请求内容。
        :param title: 工单标题
        :param content: 工单描述
        :param raw_payload: 原始外部入参
        :return: 请求文本
        """
        categories = "、".join(cls.TICKET_CATEGORY_CANDIDATES)
        raw_payload_text = (
            json.dumps(raw_payload, ensure_ascii=False, separators=(",", ":"), default=str)
            if isinstance(raw_payload, dict)
            else ""
        )
        parts = [
            f"可选分类：{categories}",
            f"工单标题：{title}".strip(),
            f"工单描述：\n{content}".strip(),
            f"外部原始入参：\n{raw_payload_text}".strip(),
            (
                "请只输出JSON对象，字段尽量包含："
                "title, category, posNo, scoNo, logDate。"
                "其中 posNo/scoNo 必须是纯数字，logDate 输出 YYYY-MM-DD。"
            ),
        ]
        return "\n\n".join([part for part in parts if str(part or "").strip()])

    @classmethod
    def _normalize_ticket_category(cls, raw_category: str) -> str:
        """
        将模型返回的分类值归一化为标准分类名称。
        :param raw_category: 模型返回分类文本
        :return: 标准分类，无法识别时返回空字符串
        """
        category_text = str(raw_category or "").strip()
        if not category_text:
            return ""
        lowered = category_text.lower()
        if lowered in cls.TICKET_CATEGORY_ALIASES:
            return cls.TICKET_CATEGORY_ALIASES[lowered]
        if category_text in cls.TICKET_CATEGORY_CANDIDATES:
            return category_text
        for candidate in cls.TICKET_CATEGORY_CANDIDATES:
            if candidate.lower() in lowered or lowered in candidate.lower():
                return candidate
        for alias, target in cls.TICKET_CATEGORY_ALIASES.items():
            if alias and alias in lowered:
                return target
        return ""

    @staticmethod
    def _normalize_pos_or_sco_no(value: Any) -> int | None:
        """
        将 POS/SCO 值归一化为整数编号。
        :param value: 原始值
        :return: 纯数字编号，无法解析返回 None
        """
        if value in (None, "", []):
            return None
        if isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            number = int(value)
            return number if number > 0 else None
        text = str(value).strip()
        if not text:
            return None
        matched = re.search(r"\d{1,10}", text)
        if not matched:
            return None
        try:
            number = int(matched.group(0))
        except Exception:
            return None
        return number if number > 0 else None

    @classmethod
    def _normalize_log_date_text(cls, value: Any, default_year: int | None = None) -> str:
        """
        将 AI 返回的日期归一化为 YYYY-MM-DD，缺少年份时补当前年份。
        :param value: 原始日期文本或日期对象
        :param default_year: 缺少年份时使用的年份
        :return: 归一化日期文本，无法解析返回空字符串
        """
        if value in (None, "", []):
            return ""
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d")
        if isinstance(value, date):
            return value.strftime("%Y-%m-%d")
        default_year = int(default_year or datetime.now().year)
        text = str(value).strip()
        if not text:
            return ""

        normalized_text = (
            text.replace("年", "-")
            .replace("月", "-")
            .replace("日", "")
            .replace(".", "-")
            .replace("/", "-")
        )
        year_match = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", normalized_text)
        if year_match:
            try:
                parsed = datetime(
                    int(year_match.group(1)),
                    int(year_match.group(2)),
                    int(year_match.group(3)),
                )
                return parsed.strftime("%Y-%m-%d")
            except Exception:
                return ""

        month_day_match = re.search(r"(\d{1,2})-(\d{1,2})", normalized_text)
        if month_day_match:
            try:
                parsed = datetime(
                    default_year,
                    int(month_day_match.group(1)),
                    int(month_day_match.group(2)),
                )
                return parsed.strftime("%Y-%m-%d")
            except Exception:
                return ""
        return ""

    @classmethod
    def _resolve_task_settings(cls, db: Session, provider_config_key: str, prompt_config_key: str) -> tuple[str, str]:
        """
        解析轻量 AI 任务使用的 Provider 和提示词编码。
        :param db: 数据库会话
        :return: (provider_code, prompt_code)
        """
        from module_admin.entity.do.config_do import SysConfig

        provider_row = db.query(SysConfig).filter(SysConfig.config_key == provider_config_key).first()
        prompt_row = db.query(SysConfig).filter(SysConfig.config_key == prompt_config_key).first()
        provider_code = str(provider_row.config_value or "").strip() if provider_row else ""
        prompt_code = str(prompt_row.config_value or "").strip() if prompt_row else ""
        return provider_code, prompt_code

    @staticmethod
    def _json_safe_value(value: Any) -> Any:
        """
        将任意值归一化为可写入 JSON 的内容。
        :param value: 原始值
        :return: JSON 安全值
        """
        if isinstance(value, dict):
            return {key: TicketLightAiService._json_safe_value(item) for key, item in value.items()}
        if isinstance(value, list):
            return [TicketLightAiService._json_safe_value(item) for item in value]
        if isinstance(value, tuple):
            return [TicketLightAiService._json_safe_value(item) for item in value]
        if hasattr(value, "model_dump"):
            try:
                return TicketLightAiService._json_safe_value(value.model_dump(by_alias=False, exclude_none=False))
            except Exception:
                return str(value)
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        return str(value)

    @classmethod
    def _build_knowledge_context(cls, ticket, timeline: dict[str, Any]) -> str:
        """
        构建工单知识提炼上下文。
        :param ticket: 工单数据库对象
        :param timeline: 工单时间线数据
        :return: 上下文文本
        """
        rca = timeline.get("rca")
        messages = timeline.get("messages") or []
        events = timeline.get("events") or []
        ai_payload = ticket.ai_analysis if isinstance(ticket.ai_analysis, dict) else {}
        origin_description = (
            str(ticket.extra_data.get("origin_description") or "").strip()
            if isinstance(ticket.extra_data, dict)
            else ""
        )
        description = origin_description or str(getattr(ticket, "description", "") or "").strip()
        current_root_cause = (
            getattr(ticket, "root_cause", None)
            or getattr(rca, "root_cause_detail", None)
            or ai_payload.get("root_cause")
            or "-"
        )
        current_solution = (
            getattr(ticket, "solution", None)
            or getattr(rca, "fix_solution", None)
            or ai_payload.get("fix_suggestion")
            or "-"
        )
        verify_method = getattr(rca, "verify_method", None) or "-"
        prevention_solution = getattr(rca, "prevention_solution", None) or "-"
        investigation_lines = [
            f"- {item.create_time:%Y-%m-%d %H:%M:%S} {item.event_type}: {item.content or ''}"
            for item in events[-20:]
        ]
        message_lines = [
            f"- {item.create_time:%Y-%m-%d %H:%M:%S} [{item.role}/{item.message_type}] {item.content}"
            for item in messages[-20:]
        ]
        sections = [
            f"工单编号：{getattr(ticket, 'ticket_no', '') or ''}",
            f"工单标题：{getattr(ticket, 'title', '') or ''}",
            f"版本号：{getattr(ticket, 'version_key', '') or ''}",
            f"项目：{getattr(ticket, 'project_name', '') or ''}",
            f"模块：{getattr(ticket, 'module_name', '') or ''}",
            f"分类：{getattr(ticket, 'category_name', '') or ''}",
            f"原始描述：\n{description or '-'}",
            f"当前根因：\n{current_root_cause}",
            f"当前解决方案：\n{current_solution}",
            f"验证与预防：\n{verify_method}\n{prevention_solution}",
            f"AI分析摘要：\n{ai_payload.get('analysis_summary') or '-'}",
            f"排查过程：\n{cls._join_text_lines(investigation_lines, empty='-')}",
            f"协同消息：\n{cls._join_text_lines(message_lines, empty='-')}",
        ]
        return "\n\n".join(section for section in sections if str(section or "").strip())

    @staticmethod
    def _normalize_tags(tags: Any) -> list[str]:
        """
        将 AI 返回的标签归一化为字符串数组。
        :param tags: 原始标签值
        :return: 标签数组
        """
        if isinstance(tags, str):
            tags = re.split(r"[，,;；\s]+", tags)
        if not isinstance(tags, list):
            return []
        normalized: list[str] = []
        for item in tags:
            tag = str(item or "").strip()
            if tag and tag not in normalized:
                normalized.append(tag)
        return normalized

    @staticmethod
    def _join_text_lines(lines: list[str], *, empty: str = "-") -> str:
        """
        合并多行文本。
        :param lines: 文本列表
        :param empty: 为空时的占位文本
        :return: 合并后的文本
        """
        filtered_lines = [str(item or "").strip() for item in lines if str(item or "").strip()]
        if not filtered_lines:
            return empty
        return "\n".join(filtered_lines)

    @classmethod
    def _extract_json_object(cls, response_text: str) -> dict[str, Any]:
        """
        从模型输出中提取 JSON 对象。
        :param response_text: 模型原始输出
        :return: 解析后的字典
        """
        raw_text = str(response_text or "").strip()
        if not raw_text:
            return {}
        match = cls.JSON_BLOCK_PATTERN.search(raw_text)
        if match:
            raw_text = match.group(1).strip()
        first_brace = raw_text.find("{")
        last_brace = raw_text.rfind("}")
        if first_brace >= 0 and last_brace >= first_brace:
            raw_text = raw_text[first_brace : last_brace + 1]
        try:
            parsed = json.loads(raw_text)
        except Exception:
            return {}
        if not isinstance(parsed, dict):
            return {}
        return parsed

    @staticmethod
    def _normalize_knowledge_case_data(raw_data: Any) -> dict[str, Any]:
        """
        归一化知识提炼结果。
        :param raw_data: 模型返回结果
        :return: 归一化后的字典
        """
        data = raw_data if isinstance(raw_data, dict) else {}
        if not data and isinstance(raw_data, list) and raw_data:
            first_item = raw_data[0] if isinstance(raw_data[0], dict) else {}
            data = first_item
        candidate = data.get("data") if isinstance(data.get("data"), dict) else data
        normalized = {
            "symptom": str(candidate.get("symptom") or candidate.get("analysis_summary") or "").strip(),
            "root_cause": str(candidate.get("root_cause") or "").strip(),
            "solution": str(candidate.get("solution") or candidate.get("fix_solution") or "").strip(),
            "prevention": str(candidate.get("prevention") or candidate.get("prevention_solution") or "").strip(),
            "summary": str(candidate.get("summary") or "").strip(),
            "title_suffix": str(candidate.get("title_suffix") or "").strip(),
            "tags": TicketLightAiService._normalize_tags(candidate.get("tags")),
        }
        return {key: value for key, value in normalized.items() if value not in (None, "", [])}

    @classmethod
    def _build_execution_payload(
        cls,
        *,
        task_type: str,
        task_name: str,
        source_type: str | None = None,
        source_id: int | None = None,
        source_ref: str | None = None,
        provider_code: str | None = None,
        prompt_code: str | None = None,
        model_name: str | None = None,
        base_url: str | None = None,
        request_payload: Any = None,
        response_payload: Any = None,
        response_text: str | None = None,
        token_usage: dict[str, Any] | None = None,
        status: str = "pending",
        error_message: str | None = None,
        created_by_name: str | None = None,
    ) -> dict[str, Any]:
        """
        构建审计记录载荷。
        :param task_type: 任务类型编码
        :param task_name: 任务名称
        :param source_type: 来源类型
        :param source_id: 来源ID
        :param source_ref: 来源引用
        :param provider_code: Provider编码
        :param prompt_code: 提示词编码
        :param model_name: 模型名称
        :param base_url: 调用地址
        :param request_payload: 请求载荷
        :param response_payload: 响应载荷
        :param response_text: 原始响应文本
        :param token_usage: Token用量
        :param status: 执行状态
        :param error_message: 错误信息
        :param created_by_name: 创建人名称
        :return: 审计记录数据
        """
        return {
            "task_type": task_type,
            "task_name": task_name,
            "source_type": source_type,
            "source_id": source_id,
            "source_ref": source_ref,
            "provider_code": provider_code,
            "prompt_code": prompt_code,
            "model_name": model_name,
            "base_url": base_url,
            "status": status,
            "request_payload": cls._json_safe_value(request_payload) if request_payload is not None else None,
            "response_payload": cls._json_safe_value(response_payload) if response_payload is not None else None,
            "response_text": response_text,
            "token_usage": cls._json_safe_value(token_usage) if token_usage is not None else None,
            "error_message": error_message,
            "created_by_name": created_by_name or "system",
        }

    @classmethod
    def generate_ticket_knowledge_case(
        cls,
        db: Session,
        *,
        ticket,
        timeline: dict[str, Any],
        current_user_name: str | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """
        基于工单上下文生成知识库案例结构化内容。
        :param db: 数据库会话
        :param ticket: 工单数据库对象
        :param timeline: 工单时间线数据
        :param current_user_name: 当前用户名称
        :return: (结构化结果, 元信息)
        """
        provider_code, prompt_code = cls._resolve_task_settings(
            db, "ticket.ai.knowledge.provider.code", "ticket.ai.knowledge.prompt.code"
        )
        context_text = cls._build_knowledge_context(ticket, timeline)
        extra_data = getattr(ticket, "extra_data", None)
        origin_description = (
            str(extra_data.get("origin_description") or "").strip() if isinstance(extra_data, dict) else ""
        )
        request_payload = {
            "ticketNo": getattr(ticket, "ticket_no", None),
            "title": getattr(ticket, "title", None),
            "versionKey": getattr(ticket, "version_key", None),
            "contextText": context_text,
            "originDescription": origin_description,
        }
        if not provider_code or not prompt_code:
            execution_id = cls._write_execution_record(
                execution_data=cls._build_execution_payload(
                    task_type="ticket_knowledge_extract",
                    task_name="工单知识库提炼",
                    source_type="ticket",
                    source_id=getattr(ticket, "ticket_id", None),
                    source_ref=getattr(ticket, "ticket_no", None),
                    status="skipped",
                    error_message="未配置知识提炼Provider或提示词",
                    request_payload=request_payload,
                    created_by_name=current_user_name,
                ),
            )
            cls._finish_execution_record(
                db,
                execution_id,
                status="skipped",
                error_message="未配置知识提炼Provider或提示词",
            )
            return {}, {"provider_code": provider_code, "prompt_code": prompt_code, "status": "skipped"}

        provider = AiProviderDao.get_ai_provider_by_code(db, provider_code)
        if not provider or not bool(getattr(provider, "enabled", True)):
            execution_id = cls._write_execution_record(
                execution_data=cls._build_execution_payload(
                    task_type="ticket_knowledge_extract",
                    task_name="工单知识库提炼",
                    source_type="ticket",
                    source_id=getattr(ticket, "ticket_id", None),
                    source_ref=getattr(ticket, "ticket_no", None),
                    provider_code=provider_code,
                    prompt_code=prompt_code,
                    status="skipped",
                    error_message="Provider不存在或已停用",
                    request_payload=request_payload,
                    created_by_name=current_user_name,
                ),
            )
            cls._finish_execution_record(db, execution_id, status="skipped", error_message="Provider不存在或已停用")
            return {}, {"provider_code": provider_code, "prompt_code": prompt_code, "status": "skipped"}

        prompt_templates = AiPromptTemplateService.get_prompt_template_texts_by_codes(db, [prompt_code])
        if not prompt_templates:
            execution_id = cls._write_execution_record(
                execution_data=cls._build_execution_payload(
                    task_type="ticket_knowledge_extract",
                    task_name="工单知识库提炼",
                    source_type="ticket",
                    source_id=getattr(ticket, "ticket_id", None),
                    source_ref=getattr(ticket, "ticket_no", None),
                    provider_code=provider_code,
                    prompt_code=prompt_code,
                    model_name=str(getattr(provider, "model_name", "") or "").strip() or None,
                    base_url=str(getattr(provider, "base_url", "") or "").strip() or None,
                    status="skipped",
                    error_message="未找到提示词模板",
                    request_payload=request_payload,
                    created_by_name=current_user_name,
                ),
            )
            cls._finish_execution_record(db, execution_id, status="skipped", error_message="未找到提示词模板")
            return {}, {"provider_code": provider_code, "prompt_code": prompt_code, "status": "skipped"}

        prompt_template = prompt_templates[0]
        system_prompt = AiPromptTemplateService.render_prompt_text(
            prompt_template["promptContent"],
            {"content": context_text},
        )
        user_prompt = "请严格只输出JSON对象，不要输出Markdown、代码块或额外解释。"
        execution_id = cls._write_execution_record(
            execution_data=cls._build_execution_payload(
                task_type="ticket_knowledge_extract",
                task_name="工单知识库提炼",
                source_type="ticket",
                source_id=getattr(ticket, "ticket_id", None),
                source_ref=getattr(ticket, "ticket_no", None),
                provider_code=provider_code,
                prompt_code=prompt_code,
                model_name=str(getattr(provider, "model_name", "") or "").strip() or None,
                base_url=str(getattr(provider, "base_url", "") or "").strip() or None,
                request_payload={**request_payload, "systemPrompt": system_prompt, "userPrompt": user_prompt},
                status="running",
                created_by_name=current_user_name,
            ),
        )
        try:
            raw_text = cls._call_model_api(
                provider=provider,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.2,
            )
            parsed_data = cls._normalize_knowledge_case_data(cls._extract_json_object(raw_text))
            cls._finish_execution_record(
                db,
                execution_id,
                status="success",
                response_text=raw_text,
                response_payload={"rawText": raw_text, "parsed": parsed_data},
            )
            return parsed_data, {
                "provider_code": provider_code,
                "prompt_code": prompt_code,
                "status": "success",
                "raw_text": raw_text,
                "parsed": parsed_data,
            }
        except Exception as exc:
            logger.warning("工单知识库提炼失败，已回退规则提炼: %s", exc)
            cls._finish_execution_record(db, execution_id, status="failed", error_message=str(exc))
            return {}, {
                "provider_code": provider_code,
                "prompt_code": prompt_code,
                "status": "failed",
                "error": str(exc),
            }

    @classmethod
    def _write_execution_record(
        cls,
        *,
        execution_data: dict[str, Any],
    ) -> int | None:
        """
        新增轻量 AI 审计记录。
        :param db: 数据库会话
        :param execution_data: 审计数据
        :return: 审计ID，失败返回None
        """
        with SessionLocal() as audit_db:
            result = AiTaskExecutionService.add_ai_task_execution_services(audit_db, execution_data)
            if not result.is_success or not result.result:
                return None
            return getattr(result.result, "execution_id", None)

    @classmethod
    def _finish_execution_record(
        cls,
        db: Session,
        execution_id: int | None,
        *,
        status: str,
        response_payload: Any = None,
        response_text: str | None = None,
        token_usage: dict[str, Any] | None = None,
        error_message: str | None = None,
    ) -> None:
        """
        更新轻量 AI 审计记录。
        :param db: 数据库会话
        :param execution_id: 审计ID
        :param status: 执行状态
        :param response_payload: 响应载荷
        :param response_text: 原始响应文本
        :param token_usage: Token用量
        :param error_message: 错误信息
        :return: 无
        """
        if not execution_id:
            return
        try:
            with SessionLocal() as audit_db:
                AiTaskExecutionService.update_ai_task_execution_services(
                    audit_db,
                    execution_id,
                    {
                        "status": status,
                        "response_payload": (
                            cls._json_safe_value(response_payload) if response_payload is not None else None
                        ),
                        "response_text": response_text,
                        "token_usage": cls._json_safe_value(token_usage) if token_usage is not None else None,
                        "error_message": error_message,
                    },
                )
        except Exception as exc:
            logger.warning("轻量AI审计记录[%s]更新失败: %s", execution_id, exc)

    @classmethod
    def _resolve_provider_headers(cls, provider) -> dict[str, str]:
        """
        构建 Provider 调用请求头。
        :param provider: Provider数据库对象
        :return: 请求头
        """
        headers = {"Content-Type": "application/json"}
        try:
            api_key = ApiKeyUtil.decrypt_api_key(provider.api_key_cipher_text)
        except Exception as exc:
            raise ValueError(f"Provider密钥解密失败: {exc}") from exc
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return headers

    @classmethod
    def _resolve_provider_url(cls, provider) -> str:
        """
        解析 Provider 的调用地址。
        :param provider: Provider数据库对象
        :return: 接口地址
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
        从 OpenAI 兼容响应中提取文本内容。
        :param response_data: 响应JSON
        :return: 文本内容
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
                content_parts = []
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
    def _call_model_api(
        cls,
        *,
        provider,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        timeout_sec: int | None = None,
    ) -> str:
        """
        调用 OpenAI 兼容的聊天接口。
        :param provider: Provider数据库对象
        :param system_prompt: 系统提示词
        :param user_prompt: 用户提示词
        :param temperature: 温度参数
        :param timeout_sec: 超时时间
        :return: 模型回复文本
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
        with httpx.Client(timeout=timeout_sec or cls.DEFAULT_TIMEOUT_SEC) as client:
            response = client.post(url, json=payload, headers=cls._resolve_provider_headers(provider))
            response.raise_for_status()
            response_data = response.json()
        content = cls._extract_response_text(response_data)
        if not str(content or "").strip():
            raise ValueError("AI接口未返回可解析的内容")
        return str(content).strip()

    @classmethod
    def extract_ticket_sync_fields(
        cls,
        db: Session,
        *,
        title: str,
        description: str,
        raw_payload: dict[str, Any] | None = None,
        source_type: str = "ticket",
        source_id: int | None = None,
        source_ref: str | None = None,
        current_user_name: str | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """
        统一提取工单同步所需信息（标题、分类、POS/SCO、日志日期）。
        :param db: 数据库会话
        :param title: 工单标题
        :param description: 工单描述
        :param raw_payload: 外部原始载荷
        :param source_type: 来源类型
        :param source_id: 来源ID
        :param source_ref: 来源引用
        :param current_user_name: 当前用户名称
        :return: (提取结果, 元信息)
        """
        title_text = str(title or "").strip()
        content = str(description or "").strip()
        request_payload = {
            "title": title_text,
            "description": content,
            "rawPayload": raw_payload if isinstance(raw_payload, dict) else {},
            "categories": list(cls.TICKET_CATEGORY_CANDIDATES),
        }
        empty_result = {
            "title": "",
            "categoryName": "",
            "posNo": None,
            "scoNo": None,
            "logDate": "",
        }
        if not title_text and not content and not isinstance(raw_payload, dict):
            return empty_result, {"provider_code": "", "prompt_code": "", "skipped": True}
        if not cls.is_log_extract_enabled(db):
            return empty_result, {"provider_code": "", "prompt_code": "", "skipped": True}

        provider_code, prompt_code = cls._resolve_task_settings(
            db, cls.CONFIG_LOG_EXTRACT_PROVIDER, cls.CONFIG_LOG_EXTRACT_PROMPT
        )
        if not provider_code or not prompt_code:
            execution_id = cls._write_execution_record(
                execution_data=cls._build_execution_payload(
                    task_type="ticket_sync_extract",
                    task_name="工单同步统一提取",
                    source_type=source_type,
                    source_id=source_id,
                    source_ref=source_ref,
                    status="skipped",
                    error_message="未配置日志参数提取Provider或提示词",
                    request_payload=request_payload,
                    created_by_name=current_user_name,
                ),
            )
            cls._finish_execution_record(db, execution_id, status="skipped", error_message="未配置日志参数提取Provider或提示词")
            return empty_result, {"provider_code": provider_code, "prompt_code": prompt_code, "skipped": True}

        provider = AiProviderDao.get_ai_provider_by_code(db, provider_code)
        if not provider or not bool(getattr(provider, "enabled", True)):
            execution_id = cls._write_execution_record(
                execution_data=cls._build_execution_payload(
                    task_type="ticket_sync_extract",
                    task_name="工单同步统一提取",
                    source_type=source_type,
                    source_id=source_id,
                    source_ref=source_ref,
                    provider_code=provider_code,
                    prompt_code=prompt_code,
                    status="skipped",
                    error_message="Provider不存在或已停用",
                    request_payload=request_payload,
                    created_by_name=current_user_name,
                ),
            )
            cls._finish_execution_record(db, execution_id, status="skipped", error_message="Provider不存在或已停用")
            return empty_result, {"provider_code": provider_code, "prompt_code": prompt_code, "skipped": True}

        prompt_templates = AiPromptTemplateService.get_prompt_template_texts_by_codes(db, [prompt_code])
        if not prompt_templates:
            execution_id = cls._write_execution_record(
                execution_data=cls._build_execution_payload(
                    task_type="ticket_sync_extract",
                    task_name="工单同步统一提取",
                    source_type=source_type,
                    source_id=source_id,
                    source_ref=source_ref,
                    provider_code=provider_code,
                    prompt_code=prompt_code,
                    model_name=str(getattr(provider, "model_name", "") or "").strip() or None,
                    base_url=str(getattr(provider, "base_url", "") or "").strip() or None,
                    status="skipped",
                    error_message="未找到提示词模板",
                    request_payload=request_payload,
                    created_by_name=current_user_name,
                ),
            )
            cls._finish_execution_record(db, execution_id, status="skipped", error_message="未找到提示词模板")
            return empty_result, {"provider_code": provider_code, "prompt_code": prompt_code, "skipped": True}

        prompt_template = prompt_templates[0]
        system_prompt = AiPromptTemplateService.render_prompt_text(
            prompt_template["promptContent"],
            {
                "title": title_text,
                "content": content,
                "description": content,
                "raw_payload": (
                    json.dumps(raw_payload, ensure_ascii=False, default=str) if isinstance(raw_payload, dict) else ""
                ),
                "categories": "、".join(cls.TICKET_CATEGORY_CANDIDATES),
            },
        )
        user_prompt = cls._build_sync_extract_prompt(title_text, content, raw_payload)
        execution_id = cls._write_execution_record(
            execution_data=cls._build_execution_payload(
                task_type="ticket_sync_extract",
                task_name="工单同步统一提取",
                source_type=source_type,
                source_id=source_id,
                source_ref=source_ref,
                provider_code=provider_code,
                prompt_code=prompt_code,
                model_name=str(getattr(provider, "model_name", "") or "").strip() or None,
                base_url=str(getattr(provider, "base_url", "") or "").strip() or None,
                request_payload={
                    **request_payload,
                    "system_prompt": system_prompt,
                    "user_prompt": user_prompt,
                },
                status="running",
                created_by_name=current_user_name,
            ),
        )
        try:
            response_text = cls._call_model_api(
                provider=provider,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
            parsed_payload = cls._extract_json_object(response_text)
            title_candidate = str(
                parsed_payload.get("title")
                or parsed_payload.get("summaryTitle")
                or parsed_payload.get("ticketTitle")
                or ""
            ).strip()
            category_candidate = str(
                parsed_payload.get("category")
                or parsed_payload.get("categoryName")
                or parsed_payload.get("classification")
                or ""
            ).strip()
            pos_no = cls._normalize_pos_or_sco_no(
                parsed_payload.get("posNo")
                or parsed_payload.get("pos_no")
                or parsed_payload.get("pos")
                or parsed_payload.get("posId")
            )
            sco_no = cls._normalize_pos_or_sco_no(
                parsed_payload.get("scoNo")
                or parsed_payload.get("sco_no")
                or parsed_payload.get("sco")
                or parsed_payload.get("scoId")
            )
            log_date = cls._normalize_log_date_text(
                parsed_payload.get("logDate")
                or parsed_payload.get("log_date")
                or parsed_payload.get("date")
                or parsed_payload.get("modifyTime")
                or parsed_payload.get("modify_time")
            )
            normalized_category = cls._normalize_ticket_category(category_candidate)
            extracted = {
                "title": title_candidate,
                "categoryName": normalized_category,
                "posNo": pos_no,
                "scoNo": sco_no,
                "logDate": log_date,
            }
            cls._finish_execution_record(
                db,
                execution_id,
                status="success",
                response_text=response_text,
                response_payload={
                    "rawText": response_text,
                    "parsed": parsed_payload,
                    "normalized": extracted,
                },
            )
            return extracted, {
                "provider_code": provider_code,
                "prompt_code": prompt_code,
                "raw_payload": parsed_payload,
                "raw_text": response_text,
                "result": extracted,
            }
        except Exception as exc:
            cls._finish_execution_record(db, execution_id, status="failed", error_message=str(exc))
            logger.warning("工单同步统一提取失败: %s", exc)
            return empty_result, {
                "provider_code": provider_code,
                "prompt_code": prompt_code,
                "error": str(exc),
            }

    @classmethod
    def summarize_ticket_title(
        cls,
        db: Session,
        *,
        description: str,
        source_type: str = "ticket",
        source_id: int | None = None,
        source_ref: str | None = None,
        current_user_name: str | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """
        根据工单描述生成标题。
        :param db: 数据库会话
        :param description: 工单描述
        :param source_type: 来源类型
        :param source_id: 来源ID
        :param source_ref: 来源引用
        :param current_user_name: 当前用户名称
        :return: (标题, 元信息)
        """
        content = str(description or "").strip()
        if not content:
            return "", {"provider_code": "", "prompt_code": "", "summary_title": "", "skipped": True}
        if not cls.is_title_summary_enabled(db):
            logger.info(
                f"工单标题总结跳过: 总开关关闭, source_type={source_type}, "
                f"source_id={source_id}, source_ref={source_ref}"
            )
            return "", {"provider_code": "", "prompt_code": "", "summary_title": "", "skipped": True}

        provider_code, prompt_code = cls._resolve_task_settings(
            db, cls.CONFIG_TITLE_SUMMARY_PROVIDER, cls.CONFIG_TITLE_SUMMARY_PROMPT
        )
        if not provider_code or not prompt_code:
            execution_id = cls._write_execution_record(
                execution_data=cls._build_execution_payload(
                    task_type="ticket_title_summary",
                    task_name="工单标题总结",
                    source_type=source_type,
                    source_id=source_id,
                    source_ref=source_ref,
                    status="skipped",
                    error_message="未配置标题总结Provider或提示词",
                    request_payload={"description": content},
                    created_by_name=current_user_name,
                ),
            )
            cls._finish_execution_record(db, execution_id, status="skipped", error_message="未配置标题总结Provider或提示词")
            return "", {"provider_code": provider_code, "prompt_code": prompt_code, "summary_title": "", "skipped": True}

        provider = AiProviderDao.get_ai_provider_by_code(db, provider_code)
        if not provider or not bool(getattr(provider, "enabled", True)):
            execution_id = cls._write_execution_record(
                execution_data=cls._build_execution_payload(
                    task_type="ticket_title_summary",
                    task_name="工单标题总结",
                    source_type=source_type,
                    source_id=source_id,
                    source_ref=source_ref,
                    provider_code=provider_code,
                    prompt_code=prompt_code,
                    status="skipped",
                    error_message="Provider不存在或已停用",
                    request_payload={"description": content},
                    created_by_name=current_user_name,
                ),
            )
            cls._finish_execution_record(db, execution_id, status="skipped", error_message="Provider不存在或已停用")
            return "", {"provider_code": provider_code, "prompt_code": prompt_code, "summary_title": "", "skipped": True}

        prompt_templates = AiPromptTemplateService.get_prompt_template_texts_by_codes(db, [prompt_code])
        if not prompt_templates:
            execution_id = cls._write_execution_record(
                execution_data=cls._build_execution_payload(
                    task_type="ticket_title_summary",
                    task_name="工单标题总结",
                    source_type=source_type,
                    source_id=source_id,
                    source_ref=source_ref,
                    provider_code=provider_code,
                    prompt_code=prompt_code,
                    model_name=str(getattr(provider, "model_name", "") or "").strip() or None,
                    base_url=str(getattr(provider, "base_url", "") or "").strip() or None,
                    status="skipped",
                    error_message="未找到提示词模板",
                    request_payload={"description": content},
                    created_by_name=current_user_name,
                ),
            )
            cls._finish_execution_record(db, execution_id, status="skipped", error_message="未找到提示词模板")
            return "", {"provider_code": provider_code, "prompt_code": prompt_code, "summary_title": "", "skipped": True}

        prompt_template = prompt_templates[0]
        system_prompt = AiPromptTemplateService.render_prompt_text(
            prompt_template["promptContent"],
            {"content": content},
        )
        user_prompt = cls._build_title_summary_prompt(content)
        execution_id = cls._write_execution_record(
            execution_data=cls._build_execution_payload(
                task_type="ticket_title_summary",
                task_name="工单标题总结",
                source_type=source_type,
                source_id=source_id,
                source_ref=source_ref,
                provider_code=provider_code,
                prompt_code=prompt_code,
                model_name=str(getattr(provider, "model_name", "") or "").strip() or None,
                base_url=str(getattr(provider, "base_url", "") or "").strip() or None,
                request_payload={
                    "description": content,
                    "system_prompt": system_prompt,
                    "user_prompt": user_prompt,
                },
                status="running",
                created_by_name=current_user_name,
            ),
        )
        try:
            summary_title = str(
                cls._call_model_api(
                    provider=provider,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                )
                or ""
            ).strip()
            summary_title = summary_title.replace("\r", " ").replace("\n", " ").strip()
            cls._finish_execution_record(
                db,
                execution_id,
                status="success",
                response_text=summary_title,
                response_payload={"summaryTitle": summary_title},
            )
            return summary_title, {
                "provider_code": provider_code,
                "prompt_code": prompt_code,
                "summary_title": summary_title,
            }
        except Exception as exc:
            logger.warning(f"工单标题总结失败，已回退描述截断: {exc}")
            cls._finish_execution_record(db, execution_id, status="failed", error_message=str(exc))
            return "", {
                "provider_code": provider_code,
                "prompt_code": prompt_code,
                "summary_title": "",
                "error": str(exc),
            }

    @classmethod
    def classify_ticket_category(
        cls,
        db: Session,
        *,
        title: str,
        description: str,
        source_type: str = "ticket",
        source_id: int | None = None,
        source_ref: str | None = None,
        current_user_name: str | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """
        轻量AI自动归类工单分类。
        :param db: 数据库会话
        :param title: 工单标题
        :param description: 工单描述
        :param source_type: 来源类型
        :param source_id: 来源ID
        :param source_ref: 来源引用
        :param current_user_name: 当前用户名称
        :return: (分类名称, 元信息)
        """
        title_text = str(title or "").strip()
        content = str(description or "").strip()
        if not title_text and not content:
            return "", {"provider_code": "", "prompt_code": "", "category_name": "", "skipped": True}
        if not cls.is_category_classification_enabled(db):
            logger.info(
                f"工单自动分类跳过: 总开关关闭, source_type={source_type}, "
                f"source_id={source_id}, source_ref={source_ref}"
            )
            return "", {"provider_code": "", "prompt_code": "", "category_name": "", "skipped": True}

        provider_code, prompt_code = cls._resolve_task_settings(
            db, cls.CONFIG_CATEGORY_CLASSIFY_PROVIDER, cls.CONFIG_CATEGORY_CLASSIFY_PROMPT
        )
        request_payload = {
            "title": title_text,
            "description": content,
            "categories": list(cls.TICKET_CATEGORY_CANDIDATES),
        }
        if not provider_code or not prompt_code:
            execution_id = cls._write_execution_record(
                execution_data=cls._build_execution_payload(
                    task_type="ticket_category_classify",
                    task_name="工单自动分类",
                    source_type=source_type,
                    source_id=source_id,
                    source_ref=source_ref,
                    status="skipped",
                    error_message="未配置自动分类Provider或提示词",
                    request_payload=request_payload,
                    created_by_name=current_user_name,
                ),
            )
            cls._finish_execution_record(db, execution_id, status="skipped", error_message="未配置自动分类Provider或提示词")
            return "", {"provider_code": provider_code, "prompt_code": prompt_code, "category_name": "", "skipped": True}

        provider = AiProviderDao.get_ai_provider_by_code(db, provider_code)
        if not provider or not bool(getattr(provider, "enabled", True)):
            execution_id = cls._write_execution_record(
                execution_data=cls._build_execution_payload(
                    task_type="ticket_category_classify",
                    task_name="工单自动分类",
                    source_type=source_type,
                    source_id=source_id,
                    source_ref=source_ref,
                    provider_code=provider_code,
                    prompt_code=prompt_code,
                    status="skipped",
                    error_message="Provider不存在或已停用",
                    request_payload=request_payload,
                    created_by_name=current_user_name,
                ),
            )
            cls._finish_execution_record(db, execution_id, status="skipped", error_message="Provider不存在或已停用")
            return "", {"provider_code": provider_code, "prompt_code": prompt_code, "category_name": "", "skipped": True}

        prompt_templates = AiPromptTemplateService.get_prompt_template_texts_by_codes(db, [prompt_code])
        if not prompt_templates:
            execution_id = cls._write_execution_record(
                execution_data=cls._build_execution_payload(
                    task_type="ticket_category_classify",
                    task_name="工单自动分类",
                    source_type=source_type,
                    source_id=source_id,
                    source_ref=source_ref,
                    provider_code=provider_code,
                    prompt_code=prompt_code,
                    model_name=str(getattr(provider, "model_name", "") or "").strip() or None,
                    base_url=str(getattr(provider, "base_url", "") or "").strip() or None,
                    status="skipped",
                    error_message="未找到提示词模板",
                    request_payload=request_payload,
                    created_by_name=current_user_name,
                ),
            )
            cls._finish_execution_record(db, execution_id, status="skipped", error_message="未找到提示词模板")
            return "", {"provider_code": provider_code, "prompt_code": prompt_code, "category_name": "", "skipped": True}

        prompt_template = prompt_templates[0]
        system_prompt = AiPromptTemplateService.render_prompt_text(
            prompt_template["promptContent"],
            {
                "title": title_text,
                "content": content,
                "categories": "、".join(cls.TICKET_CATEGORY_CANDIDATES),
            },
        )
        user_prompt = cls._build_category_classification_prompt(title_text, content)
        execution_id = cls._write_execution_record(
            execution_data=cls._build_execution_payload(
                task_type="ticket_category_classify",
                task_name="工单自动分类",
                source_type=source_type,
                source_id=source_id,
                source_ref=source_ref,
                provider_code=provider_code,
                prompt_code=prompt_code,
                model_name=str(getattr(provider, "model_name", "") or "").strip() or None,
                base_url=str(getattr(provider, "base_url", "") or "").strip() or None,
                request_payload={
                    **request_payload,
                    "system_prompt": system_prompt,
                    "user_prompt": user_prompt,
                },
                status="running",
                created_by_name=current_user_name,
            ),
        )
        try:
            response_text = str(
                cls._call_model_api(
                    provider=provider,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                )
                or ""
            ).strip()
            parsed_payload = cls._extract_json_object(response_text)
            category_candidate = str(
                parsed_payload.get("category")
                or parsed_payload.get("categoryName")
                or parsed_payload.get("classification")
                or response_text
                or ""
            ).strip()
            normalized_category = cls._normalize_ticket_category(category_candidate)
            cls._finish_execution_record(
                db,
                execution_id,
                status="success",
                response_text=response_text,
                response_payload={
                    "categoryCandidate": category_candidate,
                    "categoryName": normalized_category,
                },
            )
            return normalized_category, {
                "provider_code": provider_code,
                "prompt_code": prompt_code,
                "category_name": normalized_category,
                "raw_category": category_candidate,
            }
        except Exception as exc:
            logger.warning(f"工单自动分类失败: {exc}")
            cls._finish_execution_record(db, execution_id, status="failed", error_message=str(exc))
            return "", {
                "provider_code": provider_code,
                "prompt_code": prompt_code,
                "category_name": "",
                "error": str(exc),
            }

    @classmethod
    def translate_ticket_description(
        cls,
        db: Session,
        *,
        title: str,
        content: str,
        source_type: str = "ticket",
        source_id: int | None = None,
        source_ref: str | None = None,
        current_user_name: str | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """
        翻译工单内容并返回拼接后的描述文本。
        :param db: 数据库会话
        :param title: 工单标题
        :param content: 工单原文
        :param source_type: 来源类型
        :param source_id: 来源ID
        :param source_ref: 来源引用
        :param current_user_name: 当前用户名称
        :return: (翻译后内容, 元信息)
        """
        origin_text = str(content or "").strip()
        if not origin_text:
            logger.info(
                f"工单轻量翻译跳过: 原文为空, source_type={source_type}, source_id={source_id}, source_ref={source_ref}"
            )
            return "", {}
        if not cls.is_translation_enabled(db):
            logger.info(
                f"工单轻量翻译跳过: 总开关关闭, source_type={source_type}, "
                f"source_id={source_id}, source_ref={source_ref}"
            )
            return origin_text, {"provider_code": "", "prompt_code": "", "translated_text": "", "skipped": True}
        provider_code, prompt_code = cls._resolve_task_settings(db, cls.CONFIG_TRANSLATE_PROVIDER, cls.CONFIG_TRANSLATE_PROMPT)
        if not provider_code or not prompt_code:
            logger.info(
                f"工单轻量翻译跳过: provider/prompt 未配置, provider={provider_code or '-'}, "
                f"prompt={prompt_code or '-'}, source_ref={source_ref}"
            )
            execution_id = cls._write_execution_record(
                execution_data=cls._build_execution_payload(
                    task_type="ticket_translate",
                    task_name="工单轻量翻译",
                    source_type=source_type,
                    source_id=source_id,
                    source_ref=source_ref,
                    status="skipped",
                    error_message="未配置翻译Provider或提示词",
                    request_payload={"title": title, "content": origin_text},
                    created_by_name=current_user_name,
                ),
            )
            cls._finish_execution_record(db, execution_id, status="skipped", error_message="未配置翻译Provider或提示词")
            return origin_text, {"provider_code": provider_code, "prompt_code": prompt_code, "translated_text": ""}
        provider = AiProviderDao.get_ai_provider_by_code(db, provider_code)
        if not provider or not bool(getattr(provider, "enabled", True)):
            logger.warning(f"工单翻译跳过：Provider{provider_code}不存在或已停用")
            execution_id = cls._write_execution_record(
                execution_data=cls._build_execution_payload(
                    task_type="ticket_translate",
                    task_name="工单轻量翻译",
                    source_type=source_type,
                    source_id=source_id,
                    source_ref=source_ref,
                    provider_code=provider_code,
                    prompt_code=prompt_code,
                    status="skipped",
                    error_message="Provider不存在或已停用",
                    request_payload={"title": title, "content": origin_text},
                    created_by_name=current_user_name,
                ),
            )
            cls._finish_execution_record(db, execution_id, status="skipped", error_message="Provider不存在或已停用")
            return origin_text, {"provider_code": provider_code, "prompt_code": prompt_code, "translated_text": ""}

        prompt_templates = AiPromptTemplateService.get_prompt_template_texts_by_codes(db, [prompt_code])
        if not prompt_templates:
            logger.warning(f"工单翻译跳过：未找到提示词模板{prompt_code}")
            execution_id = cls._write_execution_record(
                execution_data=cls._build_execution_payload(
                    task_type="ticket_translate",
                    task_name="工单轻量翻译",
                    source_type=source_type,
                    source_id=source_id,
                    source_ref=source_ref,
                    provider_code=provider_code,
                    prompt_code=prompt_code,
                    model_name=str(getattr(provider, "model_name", "") or "").strip() or None,
                    base_url=str(getattr(provider, "base_url", "") or "").strip() or None,
                    status="skipped",
                    error_message="未找到提示词模板",
                    request_payload={"title": title, "content": origin_text},
                    created_by_name=current_user_name,
                ),
            )
            cls._finish_execution_record(db, execution_id, status="skipped", error_message="未找到提示词模板")
            return origin_text, {"provider_code": provider_code, "prompt_code": prompt_code, "translated_text": ""}
        prompt_template = prompt_templates[0]
        system_prompt = AiPromptTemplateService.render_prompt_text(
            prompt_template["promptContent"],
            {"content": origin_text},
        )
        user_prompt = cls._build_translation_prompt(title, origin_text)
        execution_id = cls._write_execution_record(
            execution_data=cls._build_execution_payload(
                task_type="ticket_translate",
                task_name="工单轻量翻译",
                source_type=source_type,
                source_id=source_id,
                source_ref=source_ref,
                provider_code=provider_code,
                prompt_code=prompt_code,
                model_name=str(getattr(provider, "model_name", "") or "").strip() or None,
                base_url=str(getattr(provider, "base_url", "") or "").strip() or None,
                request_payload={
                    "title": title,
                    "content": origin_text,
                    "system_prompt": system_prompt,
                    "user_prompt": user_prompt,
                },
                status="running",
                created_by_name=current_user_name,
            ),
        )
        try:
            translated_text = cls._call_model_api(
                provider=provider,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
            cls._finish_execution_record(
                db,
                execution_id,
                status="success",
                response_text=translated_text,
                response_payload={"translatedText": translated_text},
            )
        except Exception as exc:
            logger.warning(f"工单翻译失败，已回退原文: {exc}")
            cls._finish_execution_record(db, execution_id, status="failed", error_message=str(exc))
            return origin_text, {
                "provider_code": provider_code,
                "prompt_code": prompt_code,
                "translated_text": "",
                "error": str(exc),
            }

        combined_text = "\n\n".join(
            [
                origin_text,
                "【AI翻译】",
                translated_text,
            ]
        )
        return combined_text, {
            "provider_code": provider_code,
            "prompt_code": prompt_code,
            "translated_text": translated_text,
        }
