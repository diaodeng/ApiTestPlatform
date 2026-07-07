import json
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from module_admin.dao.ai_prompt_template_dao import AiPromptTemplateDao
from module_admin.entity.do.ai_prompt_template_do import SysAiPromptTemplate
from module_admin.entity.vo.ai_prompt_template_vo import (
    AiPromptTemplateDetailModel,
    AiPromptTemplateOptionModel,
    AiPromptTemplatePageQueryModel,
    CreateAiPromptTemplateModel,
    UpdateAiPromptTemplateModel,
)
from module_admin.entity.vo.common_vo import CrudResponseModel
from utils.page_util import PageResponseModel


class AiPromptTemplateService:
    """
    AI 提示词模板管理服务层。
    """

    DEFAULT_PROMPT_TEMPLATES: tuple[dict[str, Any], ...] = (
        {
            "template_code": "ticket_translate_default",
            "template_name": "工单翻译默认提示词",
            "template_category": "translate",
            "prompt_content": (
                "你是专业的工单翻译助手。请将输入内容翻译为中文，保留版本号、错误码、路径、IP、接口名、SQL、日志行号等关键信息，"
                "不要遗漏技术术语。请输出可直接追加到原文后的翻译结果，不要输出额外解释。\n\n原文：\n{{content}}"
            ),
            "sort": 1,
            "enabled": True,
            "remark": "工单创建时默认翻译模板",
        },
        {
            "template_code": "ticket_title_summary_default",
            "template_name": "工单标题总结默认提示词",
            "template_category": "translate",
            "prompt_content": (
                "你是资深工单助手，请根据工单描述生成一句简洁标题。要求："
                "1) 只输出标题，不要解释；2) 不超过30个中文字符；3) 保留版本号、错误码、模块等关键信息；"
                "4) 不确定的信息不要编造。\n\n工单描述：\n{{content}}"
            ),
            "sort": 2,
            "enabled": True,
            "remark": "外部工单未传标题时用于自动总结标题",
        },
        {
            "template_code": "ticket_knowledge_extract_default",
            "template_name": "工单知识提炼默认提示词",
            "template_category": "knowledge",
            "prompt_content": (
                "你是资深的工单知识库提炼助手。请根据输入的工单信息，提炼出可直接沉淀为知识库案例的结构化结果。"
                "请严格只输出JSON对象，不要输出Markdown、代码块或额外解释。JSON字段要求如下："
                "symptom（问题现象）、root_cause（根因）、solution（解决方案）、prevention（验证与预防）、"
                "summary（50字以内摘要）、title_suffix（适合补充到标题后的短语）、tags（字符串数组）。"
                "如果某个字段没有足够信息，请根据上下文合理归纳，但不要编造不存在的事实。\n\n工单信息：\n{{content}}"
            ),
            "sort": 3,
            "enabled": True,
            "remark": "工单关闭后自动提炼知识库案例使用的默认模板",
        },
        {
            "template_code": "ticket_analysis_append_default",
            "template_name": "工单分析追加默认提示词",
            "template_category": "analysis",
            "prompt_content": (
                "如果本次分析需要补充排查范围、业务背景或输出格式约束，请优先结合当前模板内容，"
                "在不破坏原有输出 schema 的前提下追加到主提示词中。"
            ),
            "sort": 10,
            "enabled": True,
            "remark": "工单分析可选追加模板",
        },
        {
            "template_code": "ticket_stat_classify_default",
            "template_name": "工单分类统计默认提示词",
            "template_category": "common",
            "prompt_content": "",
            "sort": 20,
            "enabled": True,
            "remark": "工单分类统计结构化字段默认模板，启动时会自动补齐内置内容",
        },
        {
            "template_code": "ticket_log_extract_default",
            "template_name": "工单日志参数提取默认提示词",
            "template_category": "common",
            "prompt_content": "",
            "sort": 21,
            "enabled": True,
            "remark": "工单日志参数提取默认提示词占位模板，允许先选中后再补充内容",
        },
        {
            "template_code": "ticket_sync_extract_default",
            "template_name": "工单同步AI提取默认提示词",
            "template_category": "common",
            "prompt_content": "",
            "sort": 22,
            "enabled": True,
            "remark": "工单同步时从工单信息中提取门店/POS/SCO/日期/版本号等字段，启动时会自动补齐内置内容",
        },
    )

    @classmethod
    def _normalize_extra_config(cls, extra_config: Any) -> dict[str, Any] | None:
        """
        归一化扩展配置。
        :param extra_config: 原始扩展配置
        :return: 归一化后的字典或None
        """
        if extra_config in (None, ""):
            return None
        if isinstance(extra_config, dict):
            return extra_config
        if isinstance(extra_config, str):
            raw_text = extra_config.strip()
            if not raw_text:
                return None
            parsed = json.loads(raw_text)
            if not isinstance(parsed, dict):
                raise ValueError("extraConfig 必须是JSON对象")
            return parsed
        raise ValueError("extraConfig 格式不正确")

    @classmethod
    def build_prompt_template_model(cls, prompt_template_info) -> AiPromptTemplateDetailModel:
        """
        将数据库对象转换为返回模型。
        :param prompt_template_info: AI提示词模板数据库对象
        :return: 返回模型
        """
        model = AiPromptTemplateDetailModel.model_validate(prompt_template_info)
        return model

    @classmethod
    def ensure_default_prompt_templates(cls, db: Session) -> None:
        """
        初始化默认提示词模板。
        :param db: 数据库会话
        :return: 无
        """
        from modules.ticket.service.ai.ticket_light_ai_service import TicketLightAiService

        now = datetime.now()
        for item in cls.DEFAULT_PROMPT_TEMPLATES:
            existing = AiPromptTemplateDao.get_prompt_template_by_code(db, item["template_code"])
            if existing:
                if (
                    item["template_code"] == "ticket_stat_classify_default"
                    and not str(getattr(existing, "prompt_content", "") or "").strip()
                ):
                    existing.prompt_content = TicketLightAiService.DEFAULT_STRUCTURED_CLASSIFICATION_PROMPT
                    existing.update_by = "system"
                    existing.update_time = now
                elif (
                    item["template_code"] == "ticket_sync_extract_default"
                    and not str(getattr(existing, "prompt_content", "") or "").strip()
                ):
                    existing.prompt_content = TicketLightAiService.DEFAULT_SYNC_EXTRACT_PROMPT
                    existing.update_by = "system"
                    existing.update_time = now
                continue
            prompt_content = item["prompt_content"]
            if item["template_code"] == "ticket_stat_classify_default":
                prompt_content = TicketLightAiService.DEFAULT_STRUCTURED_CLASSIFICATION_PROMPT
            elif item["template_code"] == "ticket_sync_extract_default":
                prompt_content = TicketLightAiService.DEFAULT_SYNC_EXTRACT_PROMPT
            db.add(
                SysAiPromptTemplate(
                    template_code=item["template_code"],
                    template_name=item["template_name"],
                    template_category=item["template_category"],
                    provider_code=item.get("provider_code") or None,
                    model_name=item.get("model_name") or None,
                    prompt_content=prompt_content,
                    enabled=bool(item.get("enabled", True)),
                    sort=int(item.get("sort") or 0),
                    extra_config=cls._normalize_extra_config(item.get("extra_config")),
                    create_by="system",
                    create_time=now,
                    update_by="system",
                    update_time=now,
                    remark=item.get("remark") or "",
                )
            )
        legacy_template = AiPromptTemplateDao.get_prompt_template_by_code(db, "ticket_category_classify_default")
        if legacy_template:
            legacy_template.del_flag = "2"
            legacy_template.enabled = False
            legacy_template.update_by = "system"
            legacy_template.update_time = now
        db.flush()

    @classmethod
    def get_prompt_template_list_services(
        cls,
        query_db: Session,
        query_object: AiPromptTemplatePageQueryModel,
    ) -> PageResponseModel:
        """
        获取 AI 提示词模板分页列表。
        :param query_db: orm对象
        :param query_object: 查询对象
        :return: 分页响应对象
        """
        query_result = AiPromptTemplateDao.get_prompt_template_list(query_db, query_object)
        rows = [
            cls.build_prompt_template_model(prompt_template).model_dump(by_alias=True)
            for prompt_template in query_result["rows"]
        ]
        return PageResponseModel(
            rows=rows,
            page_num=query_result["page_num"],
            page_size=query_result["page_size"],
            total=query_result["total"],
            has_next=query_result["has_next"],
        )

    @classmethod
    def get_prompt_template_detail_services(
        cls,
        query_db: Session,
        template_id: int,
    ) -> AiPromptTemplateDetailModel | None:
        """
        获取 AI 提示词模板详情。
        :param query_db: orm对象
        :param template_id: 模板主键
        :return: 详情模型，不存在时返回None
        """
        prompt_template_info = AiPromptTemplateDao.get_prompt_template_by_id(query_db, template_id)
        if not prompt_template_info:
            return None
        return cls.build_prompt_template_model(prompt_template_info)

    @classmethod
    def get_prompt_template_options_services(
        cls,
        query_db: Session,
        *,
        template_category: str | None = None,
        enabled_only: bool = True,
    ) -> list[AiPromptTemplateOptionModel]:
        """
        获取 AI 提示词模板下拉选项。
        :param query_db: orm对象
        :param template_category: 模板分类，支持逗号分隔
        :param enabled_only: 是否仅返回启用中的模板
        :return: 模板选项列表
        """
        categories = [item.strip() for item in str(template_category or "").split(",") if item.strip()]
        templates = AiPromptTemplateDao.get_prompt_template_options(
            query_db, enabled_only=enabled_only, template_categories=categories or None
        )
        return [AiPromptTemplateOptionModel.model_validate(item) for item in templates]

    @classmethod
    def get_prompt_template_texts_by_codes(
        cls, query_db: Session, template_codes: list[str] | None
    ) -> list[dict[str, Any]]:
        """
        按模板编码批量获取提示词内容，保持输入顺序并去重。
        :param query_db: orm对象
        :param template_codes: 模板编码列表
        :return: 模板内容列表
        """
        normalized_codes: list[str] = []
        for item in template_codes or []:
            template_code = str(item or "").strip()
            if template_code and template_code not in normalized_codes:
                normalized_codes.append(template_code)
        if not normalized_codes:
            return []
        templates = []
        for template_code in normalized_codes:
            template = AiPromptTemplateDao.get_prompt_template_by_code(query_db, template_code)
            if not template or not bool(getattr(template, "enabled", True)):
                continue
            templates.append(
                {
                    "templateCode": template.template_code,
                    "templateName": template.template_name,
                    "templateCategory": template.template_category,
                    "providerCode": template.provider_code,
                    "modelName": template.model_name,
                    "promptContent": template.prompt_content,
                }
            )
        return templates

    @classmethod
    def render_prompt_text(cls, prompt_content: str, variables: dict[str, Any] | None = None) -> str:
        """
        渲染提示词变量。
        :param prompt_content: 模板内容
        :param variables: 变量映射
        :return: 渲染后的文本
        """
        rendered = str(prompt_content or "")
        for key, value in (variables or {}).items():
            rendered = rendered.replace(f"{{{{{key}}}}}", str(value if value is not None else ""))
            rendered = rendered.replace(f"{{{key}}}", str(value if value is not None else ""))
        return rendered

    @classmethod
    def add_prompt_template_services(
        cls,
        query_db: Session,
        page_object: CreateAiPromptTemplateModel,
        current_user_name: str,
    ) -> CrudResponseModel:
        """
        新增 AI 提示词模板。
        :param query_db: orm对象
        :param page_object: 新增请求对象
        :param current_user_name: 当前登录用户名
        :return: 新增结果
        """
        template_code = str(page_object.template_code or "").strip()
        template_name = str(page_object.template_name or "").strip()
        template_category = str(page_object.template_category or "").strip()
        prompt_content = str(page_object.prompt_content or "").strip()
        if not template_code:
            return CrudResponseModel(is_success=False, message="模板编码不能为空")
        if not template_name:
            return CrudResponseModel(is_success=False, message="模板名称不能为空")
        if not template_category:
            return CrudResponseModel(is_success=False, message="模板分类不能为空")
        if not prompt_content:
            return CrudResponseModel(is_success=False, message="提示词内容不能为空")
        if AiPromptTemplateDao.get_prompt_template_by_code(query_db, template_code):
            return CrudResponseModel(is_success=False, message="模板编码已存在")
        now = datetime.now()
        try:
            db_prompt_template = AiPromptTemplateDao.add_prompt_template_dao(
                query_db,
                {
                    "template_code": template_code,
                    "template_name": template_name,
                    "template_category": template_category,
                    "provider_code": str(page_object.provider_code or "").strip() or None,
                    "model_name": str(page_object.model_name or "").strip() or None,
                    "prompt_content": prompt_content,
                    "enabled": bool(page_object.enabled),
                    "sort": int(page_object.sort or 0),
                    "extra_config": cls._normalize_extra_config(page_object.extra_config),
                    "create_by": current_user_name,
                    "create_time": now,
                    "update_by": current_user_name,
                    "update_time": now,
                    "remark": page_object.remark,
                },
            )
            query_db.commit()
            return CrudResponseModel(
                is_success=True,
                message="新增成功",
                result=cls.build_prompt_template_model(db_prompt_template),
            )
        except Exception as exc:
            query_db.rollback()
            raise exc

    @classmethod
    def update_prompt_template_services(
        cls,
        query_db: Session,
        page_object: UpdateAiPromptTemplateModel,
        current_user_name: str,
    ) -> CrudResponseModel:
        """
        编辑 AI 提示词模板。
        :param query_db: orm对象
        :param page_object: 编辑请求对象
        :param current_user_name: 当前登录用户名
        :return: 编辑结果
        """
        template_info = AiPromptTemplateDao.get_prompt_template_by_id(query_db, page_object.template_id)
        if not template_info:
            return CrudResponseModel(is_success=False, message="模板不存在")

        template_name = str(page_object.template_name or "").strip()
        template_category = str(page_object.template_category or "").strip()
        prompt_content = str(page_object.prompt_content or "").strip()
        if not template_name:
            return CrudResponseModel(is_success=False, message="模板名称不能为空")
        if not template_category:
            return CrudResponseModel(is_success=False, message="模板分类不能为空")
        if not prompt_content:
            return CrudResponseModel(is_success=False, message="提示词内容不能为空")

        update_data = {
            "template_name": template_name,
            "template_category": template_category,
            "provider_code": str(page_object.provider_code or "").strip() or None,
            "model_name": str(page_object.model_name or "").strip() or None,
            "prompt_content": prompt_content,
            "enabled": bool(page_object.enabled),
            "sort": int(page_object.sort or 0),
            "extra_config": cls._normalize_extra_config(page_object.extra_config),
            "update_by": current_user_name,
            "update_time": datetime.now(),
            "remark": page_object.remark,
        }

        try:
            AiPromptTemplateDao.edit_prompt_template_dao(query_db, page_object.template_id, update_data)
            query_db.commit()
            updated_template = AiPromptTemplateDao.get_prompt_template_by_id(query_db, page_object.template_id)
            return CrudResponseModel(
                is_success=True,
                message="修改成功",
                result=cls.build_prompt_template_model(updated_template) if updated_template else None,
            )
        except Exception as exc:
            query_db.rollback()
            raise exc

    @classmethod
    def delete_prompt_template_services(
        cls, query_db: Session, template_id: int, current_user_name: str
    ) -> CrudResponseModel:
        """
        删除 AI 提示词模板。
        :param query_db: orm对象
        :param template_id: 模板主键
        :param current_user_name: 当前登录用户名
        :return: 删除结果
        """
        template_info = AiPromptTemplateDao.get_prompt_template_by_id(query_db, template_id)
        if not template_info:
            return CrudResponseModel(is_success=False, message="模板不存在")
        try:
            AiPromptTemplateDao.delete_prompt_template_dao(
                query_db,
                template_id,
                {
                    "update_by": current_user_name,
                    "update_time": datetime.now(),
                },
            )
            query_db.commit()
            return CrudResponseModel(is_success=True, message="删除成功")
        except Exception as exc:
            query_db.rollback()
            raise exc
