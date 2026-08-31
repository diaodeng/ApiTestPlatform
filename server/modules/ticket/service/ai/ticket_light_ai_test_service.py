"""
工单轻量 AI 手动测试服务。

供测试工作台对信息提取、分类统计、翻译、标题总结和知识提炼做试运行：
- 复用生产链路的提示词渲染与结果归一化逻辑，保证测试结论对生产行为有参考性；
- 不读取生产场景开关、不读写提取缓存、不回写工单业务字段；
- 审计记录 task_type 统一追加 `_test` 后缀，与生产调用区分。
"""
import json
import time
from typing import Any

from sqlalchemy.orm import Session

from config.database import SessionLocal
from module_admin.dao.ai_provider_dao import AiProviderDao
from module_admin.service.ai_prompt_template_service import AiPromptTemplateService
from module_admin.service.ai_provider_capability_service import AiProviderCapabilityService
from module_admin.service.ai_provider_model_catalog_service import AiProviderModelCatalogService
from module_admin.service.ai_provider_protocol_service import AiProviderProtocolService
from module_admin.service.ai_provider_service import AiProviderService
from module_admin.service.ai_task_execution_service import AiTaskExecutionService
from modules.ticket.dao.ticket_dao import TicketDao
from modules.ticket.entity.do.ticket_do import Ticket
from modules.ticket.entity.vo.ticket_ai_test_vo import TicketAiTestRunModel
from modules.ticket.service.ai.ticket_auto_classification_service import TicketAutoClassificationService
from modules.ticket.service.ai.ticket_light_ai_service import TicketLightAiService
from modules.ticket.service.sync.ticket_sync_config_service import TicketSyncConfigService
from utils.log_util import logger

# 测试工作台支持的任务类型定义（value/label/说明）。
TASK_TYPES: list[dict[str, str]] = [
    {
        "value": "sync_extract",
        "label": "信息提取",
        "description": "从标题、描述和原始入参提取分类、门店、POS/SCO、日期和版本号",
    },
    {
        "value": "classification",
        "label": "分类统计",
        "description": "输出问题性质、工单类型、细分问题等结构化分类字段",
    },
    {
        "value": "translate",
        "label": "翻译",
        "description": "将工单标题和描述翻译为中文",
    },
    {
        "value": "title_summary",
        "label": "标题总结",
        "description": "根据工单描述生成简洁标题",
    },
    {
        "value": "knowledge",
        "label": "知识提炼",
        "description": "基于工单上下文提炼知识库案例结构化内容",
    },
]

# 每类任务默认使用的提示词模板编码。
TASK_DEFAULT_PROMPT_CODES: dict[str, str] = {
    "sync_extract": "ticket_sync_extract_default",
    "classification": "ticket_stat_classify_default",
    "translate": "ticket_translate_default",
    "title_summary": "ticket_title_summary_default",
    "knowledge": "ticket_knowledge_extract_default",
}

# 测试审计记录使用的任务类型（生产类型 + _test 后缀）。
TEST_TASK_TYPE_SUFFIX = "_test"


class TicketLightAiTestService:
    """工单轻量 AI 手动测试编排服务。"""

    @classmethod
    def get_test_options(cls, db: Session) -> dict[str, Any]:
        """
        获取测试工作台选项：任务类型、Provider、模型目录和提示词模板。
        :param db: 数据库会话
        :return: 选项字典
        """
        provider_options = AiProviderService.get_ai_provider_options_services(
            db,
            usage="ticket_light_text",
            executor="direct_http",
        )
        providers: list[dict[str, Any]] = []
        provider_models: dict[str, list[dict[str, str]]] = {}
        for option in provider_options:
            provider_code = str(getattr(option, "provider_code", "") or "").strip()
            if not provider_code:
                continue
            providers.append(
                {
                    "providerCode": provider_code,
                    "providerName": str(getattr(option, "provider_name", "") or "").strip(),
                    "defaultModel": str(getattr(option, "default_model", "") or "").strip(),
                }
            )
            model_options = AiProviderModelCatalogService.list_model_options_by_provider_code(db, provider_code)
            provider_models[provider_code] = [
                {
                    "modelId": str(getattr(item, "model_id", "") or ""),
                    "displayName": str(getattr(item, "display_name", "") or ""),
                }
                for item in model_options
            ]
        prompt_templates = AiPromptTemplateService.get_prompt_template_options_services(db, enabled_only=True)
        default_codes = set(TASK_DEFAULT_PROMPT_CODES.values())
        templates: list[dict[str, Any]] = []
        for item in prompt_templates:
            template_code = str(getattr(item, "template_code", "") or "").strip()
            if not template_code:
                continue
            task_types = [task["value"] for task, code in TASK_DEFAULT_PROMPT_CODES.items() if code == template_code]
            templates.append(
                {
                    "templateCode": template_code,
                    "templateName": str(getattr(item, "template_name", "") or "").strip(),
                    "isDefault": template_code in default_codes,
                    "taskTypes": task_types,
                }
            )
        return {
            "taskTypes": TASK_TYPES,
            "providers": providers,
            "providerModels": provider_models,
            "promptTemplates": templates,
        }

    @classmethod
    def search_tickets(cls, db: Session, keyword: str, limit: int = 20) -> list[dict[str, Any]]:
        """
        按工单号或标题关键字搜索工单，供测试工作台选择。
        :param db: 数据库会话
        :param keyword: 搜索关键字
        :param limit: 返回数量上限
        :return: 工单摘要列表
        """
        normalized_keyword = str(keyword or "").strip()
        if not normalized_keyword:
            return []
        rows = TicketDao.search_tickets_by_keyword(db, normalized_keyword, limit=min(max(limit, 1), 50))
        return [
            {
                "ticketId": str(row.ticket_id),
                "ticketNo": row.ticket_no,
                "title": str(row.title or ""),
                "moduleName": str(row.module_name or ""),
                "createTime": row.create_time.strftime("%Y-%m-%d %H:%M:%S") if row.create_time else "",
            }
            for row in rows
        ]

    @classmethod
    def get_prompt_template_content(cls, db: Session, template_code: str) -> dict[str, Any]:
        """
        获取提示词模板内容，供前端选择模板后回填编辑区。
        :param db: 数据库会话
        :param template_code: 模板编码
        :return: (模板编码, 模板名称, 提示词内容)
        """
        normalized_code = str(template_code or "").strip()
        if not normalized_code:
            raise ValueError("模板编码不能为空")
        templates = AiPromptTemplateService.get_prompt_template_texts_by_codes(db, [normalized_code])
        if not templates:
            raise ValueError(f"提示词模板不存在或已停用: {normalized_code}")
        template = templates[0]
        return {
            "templateCode": template.get("templateCode"),
            "templateName": template.get("templateName"),
            "promptContent": str(template.get("promptContent") or ""),
        }

    @classmethod
    def get_ticket_test_context(cls, db: Session, ticket_no: str) -> dict[str, Any]:
        """
        获取工单测试上下文（标题、描述、原始入参和当前字段），供前端回填与展示。
        :param db: 数据库会话
        :param ticket_no: 工单编号
        :return: 测试上下文字典
        """
        ticket = cls._require_ticket(db, ticket_no)
        raw_payload = ticket.extra_data.get("raw_payload") if isinstance(ticket.extra_data, dict) else None
        return {
            "ticketId": str(ticket.ticket_id),
            "ticketNo": ticket.ticket_no,
            "title": str(ticket.title or ""),
            "description": str(ticket.description or ""),
            "originDescription": cls._read_origin_description(ticket),
            "rawPayload": raw_payload if isinstance(raw_payload, dict) else None,
            "currentFields": TicketAutoClassificationService.build_ticket_stat_current_fields(ticket),
        }

    @staticmethod
    def _read_origin_description(ticket: Ticket) -> str:
        """
        读取工单扩展字段中的翻译前原始描述。
        :param ticket: 工单对象
        :return: 原始描述文本
        """
        extra_data = ticket.extra_data if isinstance(ticket.extra_data, dict) else {}
        return str(extra_data.get("origin_description") or "").strip()

    @classmethod
    def run_test(cls, db: Session, run_object: TicketAiTestRunModel, current_user_name: str) -> dict[str, Any]:
        """
        执行一次轻量 AI 测试。
        :param db: 数据库会话
        :param run_object: 测试请求
        :param current_user_name: 当前用户名
        :return: 测试结果字典
        """
        ticket = cls._require_ticket(db, run_object.ticket_no)
        provider = cls._resolve_provider(db, run_object.provider_code)
        prompt_code = str(run_object.prompt_code or "").strip() or TASK_DEFAULT_PROMPT_CODES.get(
            run_object.task_type, ""
        )
        prompt_content = cls._resolve_prompt_content(db, prompt_code, run_object.prompt_override)
        dispatchers = {
            "sync_extract": cls._run_sync_extract_test,
            "classification": cls._run_classification_test,
            "translate": cls._run_translate_test,
            "title_summary": cls._run_title_summary_test,
            "knowledge": cls._run_knowledge_test,
        }
        dispatcher = dispatchers.get(run_object.task_type)
        if not dispatcher:
            raise ValueError(f"不支持的任务类型: {run_object.task_type}")
        started_ms = time.monotonic() * 1000
        result = dispatcher(
            db,
            ticket=ticket,
            provider=provider,
            run_object=run_object,
            prompt_content=prompt_content,
            current_user_name=current_user_name,
        )
        result["elapsedMs"] = int(time.monotonic() * 1000 - started_ms)
        return result

    @classmethod
    def _require_ticket(cls, db: Session, ticket_no: str) -> Ticket:
        """
        按工单号查询工单，不存在时抛出异常。
        :param db: 数据库会话
        :param ticket_no: 工单编号
        :return: 工单对象
        """
        normalized_no = str(ticket_no or "").strip()
        if not normalized_no:
            raise ValueError("工单编号不能为空")
        ticket = TicketDao.get_ticket_by_no(db, normalized_no)
        if not ticket:
            raise ValueError(f"工单不存在: {normalized_no}")
        return ticket

    @classmethod
    def _resolve_provider(cls, db: Session, provider_code: str):
        """
        校验并返回启用的 Provider 对象。
        :param db: 数据库会话
        :param provider_code: Provider 编码
        :return: Provider 数据库对象
        """
        normalized_code = str(provider_code or "").strip()
        provider = AiProviderDao.get_ai_provider_by_code(db, normalized_code)
        if not provider or not bool(getattr(provider, "enabled", True)):
            raise ValueError(f"Provider不存在或已停用: {normalized_code}")
        return provider

    @classmethod
    def _resolve_prompt_content(cls, db: Session, prompt_code: str, prompt_override: str) -> dict[str, Any]:
        """
        解析提示词内容：有临时编辑内容时使用编辑值，否则使用模板原文。
        :param db: 数据库会话
        :param prompt_code: 提示词模板编码
        :param prompt_override: 临时编辑内容
        :return: (提示词文本, 来源标记, 编码)
        """
        override_text = str(prompt_override or "").strip()
        if override_text:
            return {"content": override_text, "source": "override", "code": str(prompt_code or "").strip()}
        normalized_code = str(prompt_code or "").strip()
        if not normalized_code:
            raise ValueError("未指定提示词模板编码")
        templates = AiPromptTemplateService.get_prompt_template_texts_by_codes(db, [normalized_code])
        if not templates:
            raise ValueError(f"提示词模板不存在或已停用: {normalized_code}")
        return {"content": str(templates[0].get("promptContent") or ""), "source": "template", "code": normalized_code}

    @classmethod
    def _call_model(
        cls,
        *,
        provider,
        system_prompt: str,
        user_prompt: str,
        model_name: str,
        task_type: str,
        task_name: str,
        source_ref: str,
        request_payload: dict[str, Any],
        current_user_name: str,
    ) -> tuple[str, dict[str, Any], int | None]:
        """
        调用模型并写入测试审计记录。
        :param provider: Provider 对象
        :param system_prompt: 系统提示词
        :param user_prompt: 用户提示词
        :param model_name: 模型名称
        :param task_type: 任务类型编码（自动追加 _test）
        :param task_name: 任务名称
        :param source_ref: 工单编号
        :param request_payload: 审计请求载荷
        :param current_user_name: 当前用户名
        :return: (模型输出, 错误信息, Token 用量)
        """
        execution_id = cls._write_test_execution_record(
            task_type=f"{task_type}{TEST_TASK_TYPE_SUFFIX}",
            task_name=task_name,
            source_ref=source_ref,
            provider=provider,
            model_name=model_name,
            request_payload={**request_payload, "systemPrompt": system_prompt, "userPrompt": user_prompt},
            current_user_name=current_user_name,
        )
        try:
            AiProviderCapabilityService.require_provider_eligibility(
                provider,
                usage="ticket_light_text",
                executor="direct_http",
            )
            generation = AiProviderProtocolService.generate_text_with_usage(
                provider=provider,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.2,
                model_name=model_name if model_name else None,
            )
            content = str(generation.text or "").strip()
            if not content:
                raise ValueError("AI接口未返回可解析的内容")
            if execution_id:
                cls._finish_test_execution_record(
                    execution_id,
                    status="success",
                    response_text=content,
                    token_usage=generation.token_usage,
                )
            return content, "", generation.token_usage
        except Exception as exc:
            if execution_id:
                cls._finish_test_execution_record(execution_id, status="failed", error_message=str(exc))
            return "", str(exc), None

    @classmethod
    def _write_test_execution_record(
        cls,
        *,
        task_type: str,
        task_name: str,
        source_ref: str,
        provider,
        model_name: str,
        request_payload: dict[str, Any],
        current_user_name: str,
    ) -> int | None:
        """
        写入测试审计记录，失败不影响测试执行。
        :param task_type: 任务类型
        :param task_name: 任务名称
        :param source_ref: 工单编号
        :param provider: Provider 对象
        :param model_name: 模型名称
        :param request_payload: 请求载荷
        :param current_user_name: 当前用户名
        :return: 审计ID
        """
        try:
            with SessionLocal() as audit_db:
                result = AiTaskExecutionService.add_ai_task_execution_services(
                    audit_db,
                    TicketLightAiService._build_execution_payload(
                        task_type=task_type,
                        task_name=task_name,
                        source_type="ai_test",
                        source_ref=source_ref,
                        provider_code=str(getattr(provider, "provider_code", "") or ""),
                        prompt_code="",
                        model_name=model_name,
                        base_url=str(getattr(provider, "base_url", "") or ""),
                        request_payload=TicketLightAiService._json_safe_value(request_payload),
                        status="running",
                        created_by_name=current_user_name,
                    ),
                )
                if result.is_success and result.result:
                    return getattr(result.result, "execution_id", None)
        except Exception as exc:
            logger.warning(f"轻量AI测试审计记录写入失败: task_type={task_type}, error={exc}")
        return None

    @classmethod
    def _finish_test_execution_record(
        cls,
        execution_id: int,
        *,
        status: str,
        response_text: str | None = None,
        token_usage: dict[str, Any] | None = None,
        error_message: str | None = None,
    ) -> None:
        """
        更新测试审计记录终态。
        :param execution_id: 审计ID
        :param status: 终态状态
        :param response_text: 原始输出
        :param token_usage: Token 用量
        :param error_message: 错误信息
        :return: 无
        """
        try:
            with SessionLocal() as audit_db:
                AiTaskExecutionService.update_ai_task_execution_services(
                    audit_db,
                    execution_id,
                    {
                        "status": status,
                        "response_text": response_text,
                        "token_usage": TicketLightAiService._json_safe_value(token_usage) if token_usage else None,
                        "error_message": error_message,
                    },
                )
        except Exception as exc:
            logger.warning(f"轻量AI测试审计记录[{execution_id}]更新失败: {exc}")

    @classmethod
    def _run_sync_extract_test(
        cls,
        db: Session,
        *,
        ticket: Ticket,
        provider,
        run_object: TicketAiTestRunModel,
        prompt_content: dict[str, Any],
        current_user_name: str,
    ) -> dict[str, Any]:
        """
        执行信息提取测试：模型输出后复用生产归一化（含机台校验告警），不读缓存不回写。
        """
        title_text = str(ticket.title or "").strip()
        content = str(ticket.description or "").strip()
        raw_payload = None
        if isinstance(ticket.extra_data, dict):
            candidate = ticket.extra_data.get("raw_payload")
            raw_payload = candidate if isinstance(candidate, dict) else None
        if run_object.use_ticket_description_only:
            raw_payload = None
        categories = "、".join(TicketLightAiService.TICKET_CATEGORY_CANDIDATES)
        raw_payload_text = (
            json.dumps(raw_payload, ensure_ascii=False, default=str) if isinstance(raw_payload, dict) else ""
        )
        system_prompt = AiPromptTemplateService.render_prompt_text(
            prompt_content["content"],
            {
                "title": title_text,
                "content": content,
                "description": content,
                "raw_payload": raw_payload_text,
                "categories": categories,
            },
        )
        user_prompt = TicketLightAiService._build_sync_extract_prompt(title_text, content, raw_payload)
        raw_text, error_message, token_usage = cls._call_model(
            provider=provider,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model_name=str(run_object.model_name or "").strip(),
            task_type="ticket_sync_extract",
            task_name="工单同步统一提取测试",
            source_ref=ticket.ticket_no,
            request_payload={
                "title": title_text,
                "description": content,
                "rawPayloadIncluded": bool(raw_payload),
                "promptCode": prompt_content["code"],
                "promptSource": prompt_content["source"],
            },
            current_user_name=current_user_name,
        )
        result: dict[str, Any] = {
            "taskType": run_object.task_type,
            "success": not error_message,
            "providerCode": str(getattr(provider, "provider_code", "") or ""),
            "modelName": str(run_object.model_name or "").strip()
            or str(getattr(provider, "default_model", "") or "").strip(),
            "promptCode": prompt_content["code"],
            "promptSource": prompt_content["source"],
            "systemPrompt": system_prompt,
            "userPrompt": user_prompt,
            "rawText": raw_text,
            "parsed": {},
            "normalized": {},
            "machineNumberWarnings": [],
            "warnings": [],
            "resultText": "",
            "tokenUsage": token_usage or {},
            "errorMessage": error_message,
        }
        if error_message:
            return result
        parsed_payload = TicketLightAiService._extract_json_object(raw_text)
        result["parsed"] = parsed_payload
        pos_no, sco_no, machine_warnings = TicketLightAiService._normalize_sync_extract_machine_numbers(
            parsed_payload,
            title_text,
            content,
            raw_payload,
        )
        log_date = TicketLightAiService._normalize_log_date_text(
            parsed_payload.get("logDate")
            or parsed_payload.get("log_date")
            or parsed_payload.get("date")
            or parsed_payload.get("modifyTime")
            or parsed_payload.get("modify_time")
        )
        category_candidate = str(
            parsed_payload.get("category") or parsed_payload.get("categoryName") or ""
        ).strip()
        result["normalized"] = {
            "title": str(parsed_payload.get("title") or "").strip(),
            "categoryName": TicketLightAiService._normalize_ticket_category(category_candidate),
            "store": str(
                parsed_payload.get("storeName")
                or parsed_payload.get("store")
                or parsed_payload.get("store_name")
                or ""
            ).strip(),
            "posNo": pos_no,
            "scoNo": sco_no,
            "logDate": log_date,
            "versionKey": str(
                parsed_payload.get("versionKey")
                or parsed_payload.get("version_key")
                or parsed_payload.get("version")
                or ""
            ).strip(),
        }
        result["machineNumberWarnings"] = machine_warnings
        return result

    @classmethod
    def _run_classification_test(
        cls,
        db: Session,
        *,
        ticket: Ticket,
        provider,
        run_object: TicketAiTestRunModel,
        prompt_content: dict[str, Any],
        current_user_name: str,
    ) -> dict[str, Any]:
        """
        执行分类统计测试：候选枚举和当前字段取自同步配置与工单现状。
        """
        title_text = str(ticket.title or "").strip()
        content = str(ticket.description or "").strip()
        comments = TicketAutoClassificationService.build_ticket_comment_context(db, ticket_id=ticket.ticket_id)
        current_fields = TicketAutoClassificationService.build_ticket_stat_current_fields(ticket)
        config = TicketSyncConfigService.load_sync_config(db)
        stat_options = config.get("statClassification") if isinstance(config.get("statClassification"), dict) else {}
        if isinstance(stat_options.get("problemPatterns"), list):
            stat_options = dict(stat_options)
            stat_options["problemPatterns"] = [
                item
                for item in stat_options["problemPatterns"]
                if not isinstance(item, dict) or item.get("enabled") is not False
            ]
        system_prompt = AiPromptTemplateService.render_prompt_text(
            prompt_content["content"],
            {
                "title": title_text,
                "content": content,
                "current_fields": json.dumps(current_fields, ensure_ascii=False, default=str),
                "stat_options": json.dumps(stat_options, ensure_ascii=False, default=str),
            },
        )
        user_prompt = TicketLightAiService._build_structured_classification_prompt(
            title=title_text,
            content=content,
            comments=comments,
            current_fields=current_fields,
            stat_options=stat_options,
        )
        raw_text, error_message, token_usage = cls._call_model(
            provider=provider,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model_name=str(run_object.model_name or "").strip(),
            task_type="ticket_stat_classify",
            task_name="工单分类统计测试",
            source_ref=ticket.ticket_no,
            request_payload={
                "title": title_text,
                "commentCount": len(comments),
                "promptCode": prompt_content["code"],
                "promptSource": prompt_content["source"],
            },
            current_user_name=current_user_name,
        )
        result: dict[str, Any] = {
            "taskType": run_object.task_type,
            "success": not error_message,
            "providerCode": str(getattr(provider, "provider_code", "") or ""),
            "modelName": str(run_object.model_name or "").strip()
            or str(getattr(provider, "default_model", "") or "").strip(),
            "promptCode": prompt_content["code"],
            "promptSource": prompt_content["source"],
            "systemPrompt": system_prompt,
            "userPrompt": user_prompt,
            "rawText": raw_text,
            "parsed": {},
            "normalized": {},
            "machineNumberWarnings": [],
            "warnings": [],
            "resultText": "",
            "tokenUsage": token_usage or {},
            "errorMessage": error_message,
        }
        if error_message:
            return result
        parsed_payload = TicketLightAiService._extract_json_object(raw_text)
        result["parsed"] = parsed_payload
        normalized = TicketLightAiService._normalize_structured_classification_result(
            parsed_payload,
            response_text=raw_text,
            stat_options=stat_options,
        )
        result["normalized"] = normalized
        return result

    @classmethod
    def _run_translate_test(
        cls,
        db: Session,
        *,
        ticket: Ticket,
        provider,
        run_object: TicketAiTestRunModel,
        prompt_content: dict[str, Any],
        current_user_name: str,
    ) -> dict[str, Any]:
        """执行翻译测试，返回翻译后文本。"""
        title_text = str(ticket.title or "").strip()
        origin_text = str(ticket.description or "").strip()
        system_prompt = AiPromptTemplateService.render_prompt_text(
            prompt_content["content"],
            {"content": origin_text},
        )
        user_prompt = TicketLightAiService._build_translation_prompt(title_text, origin_text)
        raw_text, error_message, token_usage = cls._call_model(
            provider=provider,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model_name=str(run_object.model_name or "").strip(),
            task_type="ticket_translate",
            task_name="工单轻量翻译测试",
            source_ref=ticket.ticket_no,
            request_payload={
                "title": title_text,
                "promptCode": prompt_content["code"],
                "promptSource": prompt_content["source"],
            },
            current_user_name=current_user_name,
        )
        return {
            "taskType": run_object.task_type,
            "success": not error_message,
            "providerCode": str(getattr(provider, "provider_code", "") or ""),
            "modelName": str(run_object.model_name or "").strip()
            or str(getattr(provider, "default_model", "") or "").strip(),
            "promptCode": prompt_content["code"],
            "promptSource": prompt_content["source"],
            "systemPrompt": system_prompt,
            "userPrompt": user_prompt,
            "rawText": raw_text,
            "parsed": {},
            "normalized": {},
            "machineNumberWarnings": [],
            "warnings": [],
            "resultText": raw_text,
            "tokenUsage": token_usage or {},
            "errorMessage": error_message,
        }

    @classmethod
    def _run_title_summary_test(
        cls,
        db: Session,
        *,
        ticket: Ticket,
        provider,
        run_object: TicketAiTestRunModel,
        prompt_content: dict[str, Any],
        current_user_name: str,
    ) -> dict[str, Any]:
        """执行标题总结测试，返回生成的标题文本。"""
        content = str(ticket.description or "").strip()
        system_prompt = AiPromptTemplateService.render_prompt_text(
            prompt_content["content"],
            {"content": content},
        )
        user_prompt = TicketLightAiService._build_title_summary_prompt(content)
        raw_text, error_message, token_usage = cls._call_model(
            provider=provider,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model_name=str(run_object.model_name or "").strip(),
            task_type="ticket_title_summary",
            task_name="工单标题总结测试",
            source_ref=ticket.ticket_no,
            request_payload={
                "promptCode": prompt_content["code"],
                "promptSource": prompt_content["source"],
            },
            current_user_name=current_user_name,
        )
        summary_title = raw_text.replace("\r", " ").replace("\n", " ").strip()
        return {
            "taskType": run_object.task_type,
            "success": not error_message,
            "providerCode": str(getattr(provider, "provider_code", "") or ""),
            "modelName": str(run_object.model_name or "").strip()
            or str(getattr(provider, "default_model", "") or "").strip(),
            "promptCode": prompt_content["code"],
            "promptSource": prompt_content["source"],
            "systemPrompt": system_prompt,
            "userPrompt": user_prompt,
            "rawText": raw_text,
            "parsed": {},
            "normalized": {},
            "machineNumberWarnings": [],
            "warnings": [],
            "resultText": summary_title,
            "tokenUsage": token_usage or {},
            "errorMessage": error_message,
        }

    @classmethod
    def _run_knowledge_test(
        cls,
        db: Session,
        *,
        ticket: Ticket,
        provider,
        run_object: TicketAiTestRunModel,
        prompt_content: dict[str, Any],
        current_user_name: str,
    ) -> dict[str, Any]:
        """执行知识提炼测试：上下文按生产口径从工单时间线构建。"""
        from modules.ticket.service.core.ticket_service import TicketService

        timeline = TicketService.get_timeline_services(db, ticket.ticket_id) or {}
        context_text = TicketLightAiService._build_knowledge_context(ticket, timeline)
        system_prompt = AiPromptTemplateService.render_prompt_text(
            prompt_content["content"],
            {"content": context_text},
        )
        user_prompt = "请严格只输出JSON对象，不要输出Markdown、代码块或额外解释。"
        raw_text, error_message, token_usage = cls._call_model(
            provider=provider,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model_name=str(run_object.model_name or "").strip(),
            task_type="ticket_knowledge_extract",
            task_name="工单知识库提炼测试",
            source_ref=ticket.ticket_no,
            request_payload={
                "promptCode": prompt_content["code"],
                "promptSource": prompt_content["source"],
            },
            current_user_name=current_user_name,
        )
        result: dict[str, Any] = {
            "taskType": run_object.task_type,
            "success": not error_message,
            "providerCode": str(getattr(provider, "provider_code", "") or ""),
            "modelName": str(run_object.model_name or "").strip()
            or str(getattr(provider, "default_model", "") or "").strip(),
            "promptCode": prompt_content["code"],
            "promptSource": prompt_content["source"],
            "systemPrompt": system_prompt,
            "userPrompt": user_prompt,
            "rawText": raw_text,
            "parsed": {},
            "normalized": {},
            "machineNumberWarnings": [],
            "warnings": [],
            "resultText": "",
            "tokenUsage": token_usage or {},
            "errorMessage": error_message,
        }
        if error_message:
            return result
        parsed_payload = TicketLightAiService._extract_json_object(raw_text)
        result["parsed"] = parsed_payload
        result["normalized"] = TicketLightAiService._normalize_knowledge_case_data(parsed_payload)
        return result
