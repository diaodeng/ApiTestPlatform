import json
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from module_admin.dao.ai_provider_dao import AiProviderDao
from module_admin.entity.vo.ai_provider_vo import (
    AiProviderDetailModel,
    AiProviderOptionModel,
    AiProviderPageQueryModel,
    CreateAiProviderModel,
    UpdateAiProviderModel,
)
from module_admin.entity.vo.common_vo import CrudResponseModel
from utils.api_key_util import ApiKeyUtil
from utils.page_util import PageResponseModel


class AiProviderService:
    """
    AI Provider 管理模块服务层。
    """

    PROVIDER_TYPE_LABELS = {
        "openai": "OpenAI",
        "llm": "LLM",
        "azure_openai": "Azure OpenAI",
        "ollama": "Ollama",
        "custom": "Custom",
    }

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
    def build_ai_provider_model(cls, ai_provider_info) -> AiProviderDetailModel:
        """
        将数据库对象转换为返回模型。
        :param ai_provider_info: AI Provider数据库对象
        :return: 返回模型
        """
        model = AiProviderDetailModel.model_validate(ai_provider_info)
        model.has_secret = bool(getattr(ai_provider_info, "api_key_cipher_text", ""))
        return model

    @classmethod
    def get_ai_provider_list_services(
        cls,
        query_db: Session,
        query_object: AiProviderPageQueryModel,
    ) -> PageResponseModel:
        """
        获取 AI Provider 分页列表。
        :param query_db: orm对象
        :param query_object: 查询对象
        :return: 分页响应对象
        """
        query_result = AiProviderDao.get_ai_provider_list(query_db, query_object)
        rows = [cls.build_ai_provider_model(ai_provider).model_dump(by_alias=True) for ai_provider in query_result["rows"]]
        return PageResponseModel(
            rows=rows,
            page_num=query_result["page_num"],
            page_size=query_result["page_size"],
            total=query_result["total"],
            has_next=query_result["has_next"],
        )

    @classmethod
    def get_ai_provider_detail_services(cls, query_db: Session, provider_id: int) -> AiProviderDetailModel | None:
        """
        获取 AI Provider 详情。
        :param query_db: orm对象
        :param provider_id: Provider主键
        :return: 详情模型，不存在时返回None
        """
        provider_info = AiProviderDao.get_ai_provider_by_id(query_db, provider_id)
        if not provider_info:
            return None
        return cls.build_ai_provider_model(provider_info)

    @classmethod
    def get_ai_provider_options_services(cls, query_db: Session) -> list[AiProviderOptionModel]:
        """
        获取 AI Provider 下拉选项。
        :param query_db: orm对象
        :return: Provider选项列表
        """
        providers = AiProviderDao.get_ai_provider_options(query_db, enabled_only=True)
        options = []
        for provider in providers:
            option = AiProviderOptionModel.model_validate(provider)
            options.append(option)
        return options

    @classmethod
    def add_ai_provider_services(
        cls,
        query_db: Session,
        page_object: CreateAiProviderModel,
        current_user_name: str,
    ) -> CrudResponseModel:
        """
        新增 AI Provider。
        :param query_db: orm对象
        :param page_object: 新增请求对象
        :param current_user_name: 当前登录用户名
        :return: 新增结果
        """
        provider_code = str(page_object.provider_code or "").strip()
        provider_name = str(page_object.provider_name or "").strip()
        provider_type = str(page_object.provider_type or "").strip()
        model_name = str(page_object.model_name or "").strip()
        api_key = str(page_object.api_key or "").strip()
        if not provider_code:
            return CrudResponseModel(is_success=False, message="Provider编码不能为空")
        if not provider_name:
            return CrudResponseModel(is_success=False, message="Provider名称不能为空")
        if not provider_type:
            return CrudResponseModel(is_success=False, message="Provider类型不能为空")
        if not model_name:
            return CrudResponseModel(is_success=False, message="默认模型名称不能为空")
        if not api_key:
            return CrudResponseModel(is_success=False, message="Provider密钥不能为空")
        if AiProviderDao.get_ai_provider_by_code(query_db, provider_code):
            return CrudResponseModel(is_success=False, message="Provider编码已存在")
        now = datetime.now()
        try:
            db_ai_provider = AiProviderDao.add_ai_provider_dao(
                query_db,
                {
                    "provider_code": provider_code,
                    "provider_name": provider_name,
                    "provider_type": provider_type,
                    "agent_code": str(page_object.agent_code or "").strip() or None,
                    "model_name": model_name,
                    "provider_level": int(page_object.provider_level or 0),
                    "base_url": str(page_object.base_url or "").strip() or None,
                    "api_key_prefix": ApiKeyUtil.mask_api_key(api_key),
                    "api_key_cipher_text": ApiKeyUtil.encrypt_api_key(api_key),
                    "enabled": bool(page_object.enabled),
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
                result=cls.build_ai_provider_model(db_ai_provider),
            )
        except Exception as exc:
            query_db.rollback()
            raise exc

    @classmethod
    def update_ai_provider_services(
        cls,
        query_db: Session,
        page_object: UpdateAiProviderModel,
        current_user_name: str,
    ) -> CrudResponseModel:
        """
        编辑 AI Provider。
        :param query_db: orm对象
        :param page_object: 编辑请求对象
        :param current_user_name: 当前登录用户名
        :return: 编辑结果
        """
        provider_info = AiProviderDao.get_ai_provider_by_id(query_db, page_object.provider_id)
        if not provider_info:
            return CrudResponseModel(is_success=False, message="Provider不存在")

        provider_name = str(page_object.provider_name or "").strip()
        provider_type = str(page_object.provider_type or "").strip()
        model_name = str(page_object.model_name or "").strip()
        if not provider_name:
            return CrudResponseModel(is_success=False, message="Provider名称不能为空")
        if not provider_type:
            return CrudResponseModel(is_success=False, message="Provider类型不能为空")
        if not model_name:
            return CrudResponseModel(is_success=False, message="默认模型名称不能为空")

        update_data: dict[str, Any] = {
            "provider_name": provider_name,
            "provider_type": provider_type,
            "agent_code": str(page_object.agent_code or "").strip() or None,
            "model_name": model_name,
            "provider_level": int(page_object.provider_level or 0),
            "base_url": str(page_object.base_url or "").strip() or None,
            "enabled": bool(page_object.enabled),
            "extra_config": cls._normalize_extra_config(page_object.extra_config),
            "update_by": current_user_name,
            "update_time": datetime.now(),
            "remark": page_object.remark,
        }
        api_key = str(page_object.api_key or "").strip()
        if api_key:
            update_data["api_key_prefix"] = ApiKeyUtil.mask_api_key(api_key)
            update_data["api_key_cipher_text"] = ApiKeyUtil.encrypt_api_key(api_key)

        try:
            AiProviderDao.edit_ai_provider_dao(query_db, page_object.provider_id, update_data)
            query_db.commit()
            updated_provider = AiProviderDao.get_ai_provider_by_id(query_db, page_object.provider_id)
            return CrudResponseModel(
                is_success=True,
                message="修改成功",
                result=cls.build_ai_provider_model(updated_provider) if updated_provider else None,
            )
        except Exception as exc:
            query_db.rollback()
            raise exc

    @classmethod
    def delete_ai_provider_services(cls, query_db: Session, provider_id: int, current_user_name: str) -> CrudResponseModel:
        """
        删除 AI Provider。
        :param query_db: orm对象
        :param provider_id: Provider主键
        :param current_user_name: 当前登录用户名
        :return: 删除结果
        """
        provider_info = AiProviderDao.get_ai_provider_by_id(query_db, provider_id)
        if not provider_info:
            return CrudResponseModel(is_success=False, message="Provider不存在")
        try:
            AiProviderDao.delete_ai_provider_dao(
                query_db,
                provider_id,
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
