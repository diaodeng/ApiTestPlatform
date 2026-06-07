from __future__ import annotations

import json
import re
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

    @classmethod
    def is_translation_enabled(cls, db: Session) -> bool:
        """
        读取工单轻量翻译总开关。
        :param db: 数据库会话
        :return: 是否启用翻译
        """
        config_row = db.query(SysConfig).filter(SysConfig.config_key == "ticket.ai.translate.enabled").first()
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
        origin_description = str(ticket.extra_data.get("origin_description") or "").strip() if isinstance(ticket.extra_data, dict) else ""
        description = origin_description or str(getattr(ticket, "description", "") or "").strip()
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
            f"当前根因：\n{getattr(ticket, 'root_cause', None) or getattr(rca, 'root_cause_detail', None) or ai_payload.get('root_cause') or '-'}",
            f"当前解决方案：\n{getattr(ticket, 'solution', None) or getattr(rca, 'fix_solution', None) or ai_payload.get('fix_suggestion') or '-'}",
            f"验证与预防：\n{getattr(rca, 'verify_method', None) or '-'}\n{getattr(rca, 'prevention_solution', None) or '-'}",
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
        origin_description = str(extra_data.get("origin_description") or "").strip() if isinstance(extra_data, dict) else ""
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
            cls._finish_execution_record(db, execution_id, status="skipped", error_message="未配置知识提炼Provider或提示词")
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
            return {}, {"provider_code": provider_code, "prompt_code": prompt_code, "status": "failed", "error": str(exc)}

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
                        "response_payload": cls._json_safe_value(response_payload) if response_payload is not None else None,
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
            return "", {}
        if not cls.is_translation_enabled(db):
            return origin_text, {"provider_code": "", "prompt_code": "", "translated_text": "", "skipped": True}
        provider_code, prompt_code = cls._resolve_task_settings(
            db, "ticket.ai.translate.provider.code", "ticket.ai.translate.prompt.code"
        )
        if not provider_code or not prompt_code:
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
            logger.warning("工单翻译跳过：Provider[%s]不存在或已停用", provider_code)
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
            logger.warning("工单翻译跳过：未找到提示词模板[%s]", prompt_code)
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
        system_prompt = AiPromptTemplateService.render_prompt_text(prompt_template["promptContent"], {"content": origin_text})
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
            logger.warning("工单翻译失败，已回退原文: %s", exc)
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
