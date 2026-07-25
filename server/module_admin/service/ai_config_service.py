from datetime import datetime
from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from module_admin.dao.ai_prompt_template_dao import AiPromptTemplateDao
from module_admin.dao.ai_provider_dao import AiProviderDao
from module_admin.dao.config_dao import ConfigDao
from module_admin.entity.do.config_do import SysConfig
from module_admin.entity.vo.ai_config_vo import AiConfigSummaryItemModel, AiConfigSummaryModel, AiConfigUpdateModel
from module_admin.entity.vo.ai_prompt_template_vo import AiPromptTemplateOptionModel
from module_admin.entity.vo.ai_provider_vo import AiProviderOptionModel
from module_admin.entity.vo.common_vo import CrudResponseModel
from modules.ticket.service.ai.ticket_ai_analysis_service import TicketAiAnalysisService


class AiConfigService:
    """
    AI 聚合配置服务层。
    """

    CONFIG_DEFS: tuple[dict[str, Any], ...] = (
        {
            "field_name": "translate_enabled",
            "config_key": "ticket.ai.translate.enabled",
            "config_name": "工单AI翻译开关",
            "default_value": "false",
            "remark": "控制工单创建、编辑和外部同步后是否自动执行轻量翻译",
            "section": "light_translate",
        },
        {
            "field_name": "translate_provider_code",
            "config_key": "ticket.ai.translate.provider.code",
            "config_name": "工单AI翻译Provider编码",
            "default_value": "",
            "remark": "工单创建或编辑后执行轻量翻译时使用的AI Provider编码",
            "section": "light_translate",
        },
        {
            "field_name": "translate_prompt_code",
            "config_key": "ticket.ai.translate.prompt.code",
            "config_name": "工单AI翻译提示词编码",
            "default_value": "ticket_translate_default",
            "remark": "工单创建或编辑后执行轻量翻译时使用的提示词模板编码",
            "section": "light_translate",
        },
        {
            "field_name": "title_summary_enabled",
            "config_key": "ticket.ai.title.summary.enabled",
            "config_name": "工单标题总结开关",
            "default_value": "false",
            "remark": "控制外部工单未传标题时是否自动调用轻量AI总结标题",
            "section": "light_translate",
        },
        {
            "field_name": "title_summary_provider_code",
            "config_key": "ticket.ai.title.summary.provider.code",
            "config_name": "工单标题总结Provider编码",
            "default_value": "",
            "remark": "外部工单标题总结时使用的AI Provider编码",
            "section": "light_translate",
        },
        {
            "field_name": "title_summary_prompt_code",
            "config_key": "ticket.ai.title.summary.prompt.code",
            "config_name": "工单标题总结提示词编码",
            "default_value": "ticket_title_summary_default",
            "remark": "外部工单标题总结时使用的提示词模板编码",
            "section": "light_translate",
        },
        {
            "field_name": "category_classify_enabled",
            "config_key": "ticket.ai.category.classify.enabled",
            "config_name": "工单自动分类开关",
            "default_value": "false",
            "remark": "控制工单同步后是否自动执行轻量AI分类",
            "section": "light_translate",
        },
        {
            "field_name": "category_classify_provider_code",
            "config_key": "ticket.ai.category.classify.provider.code",
            "config_name": "工单自动分类Provider编码",
            "default_value": "",
            "remark": "工单自动分类时使用的AI Provider编码",
            "section": "light_translate",
        },
        {
            "field_name": "category_classify_prompt_code",
            "config_key": "ticket.ai.category.classify.prompt.code",
            "config_name": "工单自动分类提示词编码",
            "default_value": "ticket_stat_classify_default",
            "remark": "工单分类统计时使用的提示词模板编码",
            "section": "light_translate",
        },
        {
            "field_name": "log_extract_enabled",
            "config_key": "ticket.ai.log_extract.enabled",
            "config_name": "工单日志参数提取开关",
            "default_value": "false",
            "remark": "控制外部工单同步后是否调用轻量AI提取POS/SCO与日志日期，并复用同次结果做标题/分类理解",
            "section": "light_translate",
        },
        {
            "field_name": "log_extract_provider_code",
            "config_key": "ticket.ai.log_extract.provider.code",
            "config_name": "工单日志参数提取Provider编码",
            "default_value": "",
            "remark": "工单日志参数提取时使用的AI Provider编码",
            "section": "light_translate",
        },
        {
            "field_name": "log_extract_prompt_code",
            "config_key": "ticket.ai.log_extract.prompt.code",
            "config_name": "工单日志参数提取提示词编码",
            "default_value": "ticket_sync_extract_default",
            "remark": "工单日志参数提取时使用的提示词模板编码",
            "section": "light_translate",
        },
        {
            "field_name": "knowledge_provider_code",
            "config_key": "ticket.ai.knowledge.provider.code",
            "config_name": "工单知识提炼Provider编码",
            "default_value": "",
            "remark": "工单关闭后自动提炼知识库案例时使用的AI Provider编码",
            "section": "knowledge_extract",
        },
        {
            "field_name": "knowledge_prompt_code",
            "config_key": "ticket.ai.knowledge.prompt.code",
            "config_name": "工单知识提炼提示词编码",
            "default_value": "ticket_knowledge_extract_default",
            "remark": "工单关闭后自动提炼知识库案例时使用的提示词模板编码",
            "section": "knowledge_extract",
        },
        {
            "field_name": "analysis_worker_command",
            "config_key": TicketAiAnalysisService.CONFIG_WORKER_COMMAND,
            "config_name": "工单AI分析Worker命令",
            "default_value": TicketAiAnalysisService.DEFAULT_WORKER_COMMAND,
            "remark": "AI分析Worker执行命令",
            "section": "analysis_worker",
        },
        {
            "field_name": "analysis_worker_model",
            "config_key": TicketAiAnalysisService.CONFIG_WORKER_MODEL,
            "config_name": "工单AI分析Worker模型",
            "default_value": TicketAiAnalysisService.DEFAULT_WORKER_MODEL,
            "remark": "AI分析Worker默认模型",
            "section": "analysis_worker",
        },
        {
            "field_name": "analysis_worker_sandbox",
            "config_key": TicketAiAnalysisService.CONFIG_WORKER_SANDBOX,
            "config_name": "工单AI分析Worker沙箱",
            "default_value": TicketAiAnalysisService.DEFAULT_WORKER_SANDBOX,
            "remark": "AI分析Worker沙箱模式",
            "section": "analysis_worker",
        },
        {
            "field_name": "analysis_worker_timeout_sec",
            "config_key": TicketAiAnalysisService.CONFIG_WORKER_TIMEOUT,
            "config_name": "工单AI分析Worker超时秒数",
            "default_value": str(TicketAiAnalysisService.DEFAULT_WORKER_TIMEOUT),
            "remark": "AI分析Worker最大执行时长",
            "section": "analysis_worker",
        },
        {
            "field_name": "analysis_workspace_root",
            "config_key": TicketAiAnalysisService.CONFIG_WORKSPACE_ROOT,
            "config_name": "工单AI分析工作区根目录",
            "default_value": str(TicketAiAnalysisService.DEFAULT_WORKSPACE_ROOT),
            "remark": "AI分析任务工作区根目录",
            "section": "analysis_worker",
        },
        {
            "field_name": "analysis_agent_code",
            "config_key": TicketAiAnalysisService.CONFIG_AGENT_CODE,
            "config_name": "工单AI分析Agent编码",
            "default_value": TicketAiAnalysisService.DEFAULT_AGENT_CODE,
            "remark": "AI分析任务优先投递的Agent编码，留空则自动选择在线Agent",
            "section": "analysis_worker",
        },
        {
            "field_name": "analysis_log_mode",
            "config_key": TicketAiAnalysisService.CONFIG_LOG_ANALYSIS_MODE,
            "config_name": "工单AI日志分析模式",
            "default_value": TicketAiAnalysisService.DEFAULT_LOG_ANALYSIS_MODE,
            "remark": "AI分析日志处理模式：digest摘要、full_directory完整目录、hybrid摘要加完整目录",
            "section": "analysis_worker",
        },
        {
            "field_name": "analysis_log_window_missing_strategy",
            "config_key": TicketAiAnalysisService.CONFIG_LOG_WINDOW_MISSING_STRATEGY,
            "config_name": "工单AI时间窗口缺失策略",
            "default_value": TicketAiAnalysisService.DEFAULT_LOG_WINDOW_MISSING_STRATEGY,
            "remark": "时间窗口模式下数据库无截取正文时的处理策略：server_extract服务端截取、agent_extract由Agent截取",
            "section": "analysis_worker",
        },
    )

    QUICK_LINKS: tuple[dict[str, str], ...] = (
        {
            "label": "AI Provider 管理",
            "path": "/system/aiprovider",
            "description": "维护多个 Provider、密钥、模型和等级。",
        },
        {
            "label": "AI 提示词管理",
            "path": "/system/aiprompt",
            "description": "维护翻译、知识提炼和分析追加模板。",
        },
        {
            "label": "AI 执行审计",
            "path": "/system/aitaskexecution",
            "description": "查看轻量 AI 和知识提炼的执行记录。",
        },
        {
            "label": "AI 仓库映射",
            "path": "/ticket/aiRepoMapping",
            "description": "维护工单版本号与仓库、分支和 Worker 配置的映射。",
        },
    )

    @classmethod
    def _get_config_model(cls, db: Session, config_key: str, default_value: str, config_name: str, remark: str):
        """
        获取单个系统参数的展示模型。
        :param db: orm对象
        :param config_key: 参数键名
        :param default_value: 默认值
        :param config_name: 参数名称
        :param remark: 参数说明
        :return: 配置项模型
        """
        config_info = ConfigDao.get_config_detail_by_key(db, config_key)
        current_value = getattr(config_info, "config_value", None)
        return AiConfigSummaryItemModel(
            field_name=next(item["field_name"] for item in cls.CONFIG_DEFS if item["config_key"] == config_key),
            config_key=config_key,
            config_name=config_name,
            current_value=str(current_value) if current_value is not None else default_value,
            default_value=default_value,
            remark=remark,
        )

    @classmethod
    def _get_config_text(cls, db: Session, config_key: str, default_value: str) -> str:
        """
        获取系统参数文本值。
        :param db: orm对象
        :param config_key: 参数键名
        :param default_value: 默认值
        :return: 参数值
        """
        config_info = ConfigDao.get_config_detail_by_key(db, config_key)
        if not config_info:
            return default_value
        value = getattr(config_info, "config_value", None)
        if value is None:
            return default_value
        return str(value)

    @classmethod
    def _get_config_int(cls, db: Session, config_key: str, default_value: int) -> int:
        """
        获取系统参数整数值。
        :param db: orm对象
        :param config_key: 参数键名
        :param default_value: 默认值
        :return: 整数参数值
        """
        raw_value = cls._get_config_text(db, config_key, "")
        try:
            return int(raw_value)
        except Exception:
            return int(default_value)

    @classmethod
    def _get_config_text_with_blank_default(cls, db: Session, config_key: str, default_value: str) -> str:
        """
        获取系统参数文本值，若值为空字符串则回退默认值。
        :param db: orm对象
        :param config_key: 参数键名
        :param default_value: 默认值
        :return: 参数值
        """
        value = cls._get_config_text(db, config_key, "")
        if str(value or "").strip():
            return str(value)
        return str(default_value)

    @classmethod
    def _normalize_classify_prompt_code(cls, prompt_code: str | None) -> str:
        """
        归一化工单分类提示词编码。
        :param prompt_code: 系统参数或前端提交的提示词编码。
        :return: 可用的分类统计提示词编码。
        """
        normalized = str(prompt_code or "").strip()
        if not normalized or normalized == "ticket_category_classify_default":
            return "ticket_stat_classify_default"
        return normalized

    @classmethod
    def _upsert_config(
        cls,
        db: Session,
        *,
        config_key: str,
        config_name: str,
        config_value: Any,
        remark: str,
        current_user_name: str,
    ):
        """
        新增或更新系统参数。
        :param db: orm对象
        :param config_key: 参数键名
        :param config_name: 参数名称
        :param config_value: 参数值
        :param remark: 备注说明
        :param current_user_name: 当前用户名
        :return: 无
        """
        now = datetime.now()
        config_info = ConfigDao.get_config_detail_by_key(db, config_key)
        value_text = "" if config_value is None else str(config_value)
        if config_info:
            ConfigDao.edit_config_dao(
                db,
                {
                    "config_id": config_info.config_id,
                    "config_name": config_name,
                    "config_key": config_key,
                    "config_value": value_text,
                    "config_type": "Y",
                    "update_by": current_user_name,
                    "update_time": now,
                    "remark": remark,
                },
            )
            return
        db.add(
            SysConfig(
                config_name=config_name,
                config_key=config_key,
                config_value=value_text,
                config_type="Y",
                create_by=current_user_name,
                create_time=now,
                update_by=current_user_name,
                update_time=now,
                remark=remark,
            )
        )

    @classmethod
    def get_ai_config_summary_services(cls, db: Session) -> AiConfigSummaryModel:
        """
        获取 AI 聚合配置页所需数据。
        :param db: orm对象
        :return: 聚合配置数据
        """
        config_rows = [
            cls._get_config_model(
                db,
                item["config_key"],
                item["default_value"],
                item["config_name"],
                item["remark"],
            )
            for item in cls.CONFIG_DEFS
        ]
        provider_options = [
            AiProviderOptionModel.model_validate(provider)
            for provider in AiProviderDao.get_ai_provider_options(db, enabled_only=False)
        ]
        prompt_options = {
            category: [
                AiPromptTemplateOptionModel.model_validate(template)
                for template in AiPromptTemplateDao.get_prompt_template_options(
                    db, enabled_only=False, template_categories=[category]
                )
            ]
            for category in ("translate", "knowledge", "analysis", "common")
        }
        summary = AiConfigSummaryModel(
            translate_enabled=str(cls._get_config_text(db, "ticket.ai.translate.enabled", "false")).lower()
            == "true",
            translate_provider_code=cls._get_config_text(db, "ticket.ai.translate.provider.code", ""),
            translate_prompt_code=cls._get_config_text(
                db, "ticket.ai.translate.prompt.code", "ticket_translate_default"
            ),
            title_summary_enabled=str(cls._get_config_text(db, "ticket.ai.title.summary.enabled", "false")).lower()
            == "true",
            title_summary_provider_code=cls._get_config_text(db, "ticket.ai.title.summary.provider.code", ""),
            title_summary_prompt_code=cls._get_config_text(
                db, "ticket.ai.title.summary.prompt.code", "ticket_title_summary_default"
            ),
            category_classify_enabled=str(
                cls._get_config_text(db, "ticket.ai.category.classify.enabled", "false")
            ).lower()
            == "true",
            category_classify_provider_code=cls._get_config_text(db, "ticket.ai.category.classify.provider.code", ""),
            category_classify_prompt_code=cls._normalize_classify_prompt_code(
                cls._get_config_text_with_blank_default(
                    db, "ticket.ai.category.classify.prompt.code", "ticket_stat_classify_default"
                )
            ),
            log_extract_enabled=str(cls._get_config_text(db, "ticket.ai.log_extract.enabled", "false")).lower()
            == "true",
            log_extract_provider_code=cls._get_config_text(db, "ticket.ai.log_extract.provider.code", ""),
            log_extract_prompt_code=cls._get_config_text_with_blank_default(
                db, "ticket.ai.log_extract.prompt.code", "ticket_sync_extract_default"
            ),
            knowledge_provider_code=cls._get_config_text(db, "ticket.ai.knowledge.provider.code", ""),
            knowledge_prompt_code=cls._get_config_text(
                db, "ticket.ai.knowledge.prompt.code", "ticket_knowledge_extract_default"
            ),
            analysis_worker_command=cls._get_config_text(
                db, TicketAiAnalysisService.CONFIG_WORKER_COMMAND, TicketAiAnalysisService.DEFAULT_WORKER_COMMAND
            ),
            analysis_worker_model=cls._get_config_text(
                db, TicketAiAnalysisService.CONFIG_WORKER_MODEL, TicketAiAnalysisService.DEFAULT_WORKER_MODEL
            ),
            analysis_worker_sandbox=cls._get_config_text(
                db, TicketAiAnalysisService.CONFIG_WORKER_SANDBOX, TicketAiAnalysisService.DEFAULT_WORKER_SANDBOX
            ),
            analysis_worker_timeout_sec=cls._get_config_int(
                db, TicketAiAnalysisService.CONFIG_WORKER_TIMEOUT, TicketAiAnalysisService.DEFAULT_WORKER_TIMEOUT
            ),
            analysis_workspace_root=cls._get_config_text(
                db,
                TicketAiAnalysisService.CONFIG_WORKSPACE_ROOT,
                str(TicketAiAnalysisService.DEFAULT_WORKSPACE_ROOT),
            ),
            analysis_agent_code=cls._get_config_text(
                db, TicketAiAnalysisService.CONFIG_AGENT_CODE, TicketAiAnalysisService.DEFAULT_AGENT_CODE
            ),
            analysis_log_mode=TicketAiAnalysisService._normalize_log_analysis_mode(
                cls._get_config_text(
                    db,
                    TicketAiAnalysisService.CONFIG_LOG_ANALYSIS_MODE,
                    TicketAiAnalysisService.DEFAULT_LOG_ANALYSIS_MODE,
                )
            ),
            analysis_log_window_missing_strategy=TicketAiAnalysisService._normalize_log_window_missing_strategy(
                cls._get_config_text(
                    db,
                    TicketAiAnalysisService.CONFIG_LOG_WINDOW_MISSING_STRATEGY,
                    TicketAiAnalysisService.DEFAULT_LOG_WINDOW_MISSING_STRATEGY,
                )
            ),
            config_rows=config_rows,
            provider_options=provider_options,
            prompt_options=prompt_options,
            quick_links=[dict(item) for item in cls.QUICK_LINKS],
        )
        return summary

    @classmethod
    async def update_ai_config_services(
        cls,
        request: Request,
        query_db: Session,
        page_object: AiConfigUpdateModel,
        current_user_name: str,
    ) -> CrudResponseModel:
        """
        更新 AI 聚合配置。
        :param request: Request对象
        :param query_db: orm对象
        :param page_object: 配置更新对象
        :param current_user_name: 当前用户名
        :return: 更新结果
        """
        edit_data = page_object.model_dump(exclude_unset=True)
        field_to_config = {item["field_name"]: item for item in cls.CONFIG_DEFS}
        try:
            for field_name, value in edit_data.items():
                if field_name not in field_to_config:
                    continue
                config_def = field_to_config[field_name]
                if field_name == "category_classify_prompt_code":
                    value = cls._normalize_classify_prompt_code(value)
                cls._upsert_config(
                    query_db,
                    config_key=config_def["config_key"],
                    config_name=config_def["config_name"],
                    config_value=value,
                    remark=config_def["remark"],
                    current_user_name=current_user_name,
                )
            query_db.commit()
            from module_admin.service.config_service import ConfigService

            await ConfigService.init_cache_sys_config_services(query_db, request.app.state.redis)
            return CrudResponseModel(is_success=True, message="保存成功")
        except Exception as exc:
            query_db.rollback()
            raise exc
