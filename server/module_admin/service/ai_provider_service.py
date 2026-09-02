import json
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from module_admin.dao.ai_provider_dao import AiProviderDao
from module_admin.dao.user_dao import UserDao
from module_admin.entity.vo.ai_provider_vo import (
    AiProviderDetailModel,
    AiProviderOptionModel,
    AiProviderPageQueryModel,
    CreateAiProviderModel,
    UpdateAiProviderModel,
)
from module_admin.entity.vo.common_vo import CrudResponseModel
from module_admin.service.ai_provider_capability_service import AiProviderCapabilityService
from utils.api_key_util import ApiKeyUtil
from utils.log_util import logger
from utils.page_util import PageResponseModel
from utils.pwd_util import PwdUtil


class AiProviderService:
    """
    AI Provider 管理模块服务层。
    """

    @classmethod
    def _normalize_dict_config(cls, config: Any, field_name: str) -> dict[str, Any] | None:
        """
        归一化扩展配置。
        :param config: 原始配置
        :param field_name: 配置字段名称
        :return: 归一化后的字典或None
        """
        if config in (None, ""):
            return None
        if isinstance(config, dict):
            return config
        if isinstance(config, str):
            raw_text = config.strip()
            if not raw_text:
                return None
            parsed = json.loads(raw_text)
            if not isinstance(parsed, dict):
                raise ValueError(f"{field_name}必须是JSON对象")
            return parsed
        raise ValueError(f"{field_name}格式不正确")

    @classmethod
    def build_ai_provider_model(cls, ai_provider_info) -> AiProviderDetailModel:
        """
        将数据库对象转换为返回模型。
        :param ai_provider_info: AI Provider数据库对象
        :return: 返回模型
        """
        model = AiProviderDetailModel.model_validate(ai_provider_info)
        model.has_secret = bool(getattr(ai_provider_info, "api_key_cipher_text", ""))
        model.has_observability_secret = bool(getattr(ai_provider_info, "observability_api_key_cipher_text", ""))
        return model

    @classmethod
    def _validate_observability(cls, page_object, *, has_stored_secret: bool) -> dict[str, Any]:
        """
        校验并归一化可观测上报配置。
        :param page_object: Provider请求模型
        :param has_stored_secret: 数据库中是否已保存可观测密钥
        :return: 可观测字段的持久化字典（不含密钥）
        :raise ValueError: 配置不完整时抛出
        """
        enabled = bool(getattr(page_object, "observability_enabled", False))
        endpoint = str(getattr(page_object, "observability_endpoint", "") or "").strip()
        auth_type = str(getattr(page_object, "observability_auth_type", "") or "bearer").strip().lower()
        service_name = str(getattr(page_object, "observability_service_name", "") or "").strip()
        api_key = str(getattr(page_object, "observability_api_key", "") or "").strip()
        if not enabled:
            # 关闭总开关时保留端点等配置不清空（隐藏字段不清空规范），仅停用开关；
            # 密钥始终由 _build_observability_secret_data 决定是否更新，关闭时不主动清除。
            return {
                "observability_enabled": False,
                "observability_endpoint": endpoint or None,
                "observability_auth_type": auth_type,
                "observability_service_name": service_name or None,
                "observability_cli_enabled": False,
            }
        cli_enabled = bool(getattr(page_object, "observability_cli_enabled", False))
        if not endpoint:
            raise ValueError("启用可观测上报时必须填写OTLP端点")
        if auth_type not in ("bearer", "basic"):
            raise ValueError("可观测鉴权类型仅支持 bearer/basic")
        if not api_key and not has_stored_secret:
            raise ValueError("启用可观测上报时必须填写鉴权密钥")
        return {
            "observability_enabled": True,
            "observability_endpoint": endpoint,
            "observability_auth_type": auth_type,
            "observability_service_name": service_name or None,
            "observability_cli_enabled": cli_enabled,
        }

    @classmethod
    def _build_observability_secret_data(cls, page_object) -> dict[str, Any]:
        """
        根据提交的明文密钥生成可观测密钥持久化字段。
        :param page_object: Provider请求模型
        :return: 密钥前缀与密文字段字典；未提交密钥时返回空字典表示保持原值
        """
        api_key = str(getattr(page_object, "observability_api_key", "") or "").strip()
        if not api_key:
            return {}
        return {
            "observability_api_key_prefix": ApiKeyUtil.mask_api_key(api_key),
            "observability_api_key_cipher_text": ApiKeyUtil.encrypt_api_key(api_key),
        }

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
        rows = [
            cls.build_ai_provider_model(ai_provider).model_dump(by_alias=True)
            for ai_provider in query_result["rows"]
        ]
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
    def get_ai_provider_options_services(
        cls,
        query_db: Session,
        usage: str | None = None,
        executor: str | None = None,
    ) -> list[AiProviderOptionModel]:
        """
        获取 AI Provider 下拉选项。
        :param query_db: orm对象
        :param usage: 可选业务用途过滤
        :param executor: 可选执行器过滤
        :return: Provider选项列表
        """
        providers = AiProviderDao.get_ai_provider_options(query_db, enabled_only=True)
        options = []
        for provider in providers:
            if not AiProviderCapabilityService.is_provider_eligible(provider, usage, executor):
                continue
            # 工单 AI 分析场景未指定具体执行器时，按“分析执行器集合”过滤，
            # 使仅支持 claude_code 而未配置 codex 的 Provider 也能出现在下拉候选中。
            if (
                usage == "ticket_analysis_worker"
                and not executor
                and not AiProviderCapabilityService.resolve_analysis_executor_options(provider)
            ):
                continue
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
        platform_code = str(page_object.platform_code or "").strip()
        api_protocol = str(page_object.api_protocol or "").strip()
        default_model = str(page_object.default_model or "").strip()
        api_key = str(page_object.api_key or "").strip()
        if not provider_code:
            return CrudResponseModel(is_success=False, message="Provider编码不能为空")
        if not provider_name:
            return CrudResponseModel(is_success=False, message="Provider名称不能为空")
        if not platform_code or not api_protocol:
            return CrudResponseModel(is_success=False, message="Provider平台和API协议不能为空")
        if not default_model:
            return CrudResponseModel(is_success=False, message="默认模型名称不能为空")
        if not api_key:
            return CrudResponseModel(is_success=False, message="Provider密钥不能为空")
        try:
            supported_usages, supported_executors = AiProviderCapabilityService.validate_provider_contract(
                platform_code=platform_code,
                api_protocol=api_protocol,
                supported_usages=page_object.supported_usages,
                supported_executors=page_object.supported_executors,
            )
        except ValueError as exc:
            return CrudResponseModel(is_success=False, message=str(exc))
        if AiProviderDao.get_ai_provider_by_code(query_db, provider_code):
            return CrudResponseModel(is_success=False, message="Provider编码已存在")
        try:
            observability_data = cls._validate_observability(page_object, has_stored_secret=False)
        except ValueError as exc:
            return CrudResponseModel(is_success=False, message=str(exc))
        now = datetime.now()
        try:
            db_ai_provider = AiProviderDao.add_ai_provider_dao(
                query_db,
                {
                    "provider_code": provider_code,
                    "provider_name": provider_name,
                    "platform_code": platform_code,
                    "api_protocol": api_protocol,
                    "supported_usages": supported_usages,
                    "supported_executors": supported_executors,
                    "preferred_executor": str(page_object.preferred_executor or "").strip() or None,
                    "preferred_agent_code": str(page_object.preferred_agent_code or "").strip() or None,
                    "default_model": default_model,
                    "provider_level": int(page_object.provider_level or 0),
                    "base_url": str(page_object.base_url or "").strip() or None,
                    "api_key_prefix": ApiKeyUtil.mask_api_key(api_key),
                    "api_key_cipher_text": ApiKeyUtil.encrypt_api_key(api_key),
                    "enabled": bool(page_object.enabled),
                    "connection_config": cls._normalize_dict_config(page_object.connection_config, "connectionConfig"),
                    "worker_env": cls._normalize_dict_config(page_object.worker_env, "workerEnv"),
                    **observability_data,
                    **cls._build_observability_secret_data(page_object),
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
        platform_code = str(page_object.platform_code or "").strip()
        api_protocol = str(page_object.api_protocol or "").strip()
        default_model = str(page_object.default_model or "").strip()
        if not provider_name:
            return CrudResponseModel(is_success=False, message="Provider名称不能为空")
        if not platform_code or not api_protocol:
            return CrudResponseModel(is_success=False, message="Provider平台和API协议不能为空")
        if not default_model:
            return CrudResponseModel(is_success=False, message="默认模型名称不能为空")
        try:
            supported_usages, supported_executors = AiProviderCapabilityService.validate_provider_contract(
                platform_code=platform_code,
                api_protocol=api_protocol,
                supported_usages=page_object.supported_usages,
                supported_executors=page_object.supported_executors,
            )
        except ValueError as exc:
            return CrudResponseModel(is_success=False, message=str(exc))
        try:
            observability_data = cls._validate_observability(
                page_object,
                has_stored_secret=bool(provider_info.observability_api_key_cipher_text),
            )
        except ValueError as exc:
            return CrudResponseModel(is_success=False, message=str(exc))

        update_data: dict[str, Any] = {
            "provider_name": provider_name,
            "platform_code": platform_code,
            "api_protocol": api_protocol,
            "supported_usages": supported_usages,
            "supported_executors": supported_executors,
            "preferred_executor": str(page_object.preferred_executor or "").strip() or None,
            "preferred_agent_code": str(page_object.preferred_agent_code or "").strip() or None,
            "default_model": default_model,
            "provider_level": int(page_object.provider_level or 0),
            "base_url": str(page_object.base_url or "").strip() or None,
            "enabled": bool(page_object.enabled),
            "connection_config": cls._normalize_dict_config(page_object.connection_config, "connectionConfig"),
            "worker_env": cls._normalize_dict_config(page_object.worker_env, "workerEnv"),
            **observability_data,
            **cls._build_observability_secret_data(page_object),
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
    def view_ai_provider_secret_services(
        cls,
        query_db: Session,
        current_user,
        provider_id: int,
        password: str,
    ) -> CrudResponseModel:
        """
        校验当前登录用户密码后返回指定Provider密钥明文。
        :param query_db: 数据库会话
        :param current_user: 当前登录用户
        :param provider_id: Provider主键
        :param password: 当前用户密码
        :return: 查看结果，成功时携带密钥明文
        """
        provider = AiProviderDao.get_ai_provider_by_id(query_db, provider_id)
        if not provider:
            logger.warning(f"查看Provider密钥被拒绝: provider_id={provider_id}, 原因=Provider不存在")
            return CrudResponseModel(is_success=False, message="Provider不存在")
        user_info = UserDao.get_user_by_id(query_db, current_user.user.user_id).get("user_basic_info")
        if not user_info or not PwdUtil.verify_password(password, user_info.password):
            logger.warning(
                f"查看Provider密钥被拒绝: provider_id={provider_id}, "
                f"user_id={current_user.user.user_id}, 原因=当前账号密码校验失败"
            )
            return CrudResponseModel(is_success=False, message="当前账号密码不正确")
        try:
            secret = ApiKeyUtil.decrypt_api_key(provider.api_key_cipher_text)
        except Exception as exc:
            logger.error(f"查看Provider密钥失败: provider_id={provider_id}, 原因=密钥解密异常: {exc}")
            return CrudResponseModel(is_success=False, message="Provider密钥解密失败")
        logger.info(
            f"查看Provider密钥成功: provider_id={provider_id}, "
            f"user_id={current_user.user.user_id}, user_name={current_user.user.user_name}"
        )
        return CrudResponseModel(
            is_success=True,
            message="查看成功",
            result={"providerId": provider_id, "apiKey": secret},
        )

    @classmethod
    def delete_ai_provider_services(
        cls,
        query_db: Session,
        provider_id: int,
        current_user_name: str,
    ) -> CrudResponseModel:
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
