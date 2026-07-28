from types import SimpleNamespace

from sqlalchemy.orm import Session

from module_admin.dao.ai_provider_dao import AiProviderDao
from module_admin.service.ai_provider_protocol_service import AiProviderProtocolService
from utils.log_util import logger


class AiProviderConnectionService:
    """
    AI Provider 表单草稿连接服务。

    该服务只使用弹窗当前填写的地址、协议、模型和扩展配置进行模型发现或连通性测试；
    已保存 Provider 未重新填写密钥时，仅在服务端读取同一 Provider 的密文密钥，不回传也不写库。
    """

    @classmethod
    def build_draft_provider(cls, db: Session, provider_draft) -> tuple[SimpleNamespace, str | None]:
        """
        构建用于上游请求的临时 Provider 对象。
        :param db: 数据库会话
        :param provider_draft: 当前页面提交的 Provider 草稿
        :return: (临时 Provider对象, 当前页面新填写的密钥或None)
        """
        input_api_key = str(getattr(provider_draft, "api_key", "") or "").strip() or None
        api_key_cipher_text = ""
        provider_id = getattr(provider_draft, "provider_id", None)
        if not input_api_key:
            if not provider_id:
                raise ValueError("新增Provider测试连接或更新模型时必须填写密钥")
            saved_provider = AiProviderDao.get_ai_provider_by_id(db, provider_id)
            if not saved_provider:
                raise ValueError("Provider不存在，无法使用已保存密钥")
            api_key_cipher_text = str(getattr(saved_provider, "api_key_cipher_text", "") or "")
            if not api_key_cipher_text:
                raise ValueError("Provider未配置已保存密钥，请在页面填写密钥后重试")
        return (
            SimpleNamespace(
                provider_id=provider_id,
                platform_code=str(getattr(provider_draft, "platform_code", "") or "").strip(),
                api_protocol=str(getattr(provider_draft, "api_protocol", "") or "").strip(),
                base_url=str(getattr(provider_draft, "base_url", "") or "").strip(),
                default_model=str(getattr(provider_draft, "default_model", "") or "").strip(),
                connection_config=getattr(provider_draft, "connection_config", None),
                api_key_cipher_text=api_key_cipher_text,
            ),
            input_api_key,
        )

    @classmethod
    def preview_models(cls, db: Session, provider_draft) -> list[dict[str, str]]:
        """
        使用当前表单草稿拉取上游模型目录，不写入数据库。
        :param db: 数据库会话
        :param provider_draft: 当前页面提交的 Provider 草稿
        :return: 上游模型目录
        """
        try:
            provider, input_api_key = cls.build_draft_provider(db, provider_draft)
            models = AiProviderProtocolService.discover_models(provider, api_key=input_api_key)
            logger.info(
                f"AI Provider模型目录探测成功: provider_id={provider.provider_id or '-'}, "
                f"protocol={provider.api_protocol}, model_count={len(models)}"
            )
            return models
        except Exception as exc:
            logger.warning(
                f"AI Provider模型目录探测失败: provider_id={getattr(provider_draft, 'provider_id', None) or '-'}, "
                f"protocol={getattr(provider_draft, 'api_protocol', '') or '-'}, 原因={exc}"
            )
            raise

    @classmethod
    def test_connection(cls, db: Session, provider_draft) -> dict[str, str]:
        """
        使用当前表单草稿向默认模型发送最小文本请求，验证地址、密钥、协议和模型是否有效。
        :param db: 数据库会话
        :param provider_draft: 当前页面提交的 Provider 草稿
        :return: 测试结果摘要，不包含密钥
        """
        try:
            provider, input_api_key = cls.build_draft_provider(db, provider_draft)
            if not provider.default_model:
                raise ValueError("测试连接前必须填写默认模型")
            response_text = AiProviderProtocolService.generate_text(
                provider=provider,
                system_prompt="你是连通性测试助手。",
                user_prompt="请仅回复 OK。",
                temperature=0,
                timeout_sec=30,
                api_key=input_api_key,
            )
            logger.info(
                f"AI Provider模型测试成功: provider_id={provider.provider_id or '-'}, "
                f"protocol={provider.api_protocol}, model={provider.default_model}"
            )
            return {"message": "连接和模型调用成功", "response": response_text[:1000]}
        except Exception as exc:
            logger.warning(
                f"AI Provider模型测试失败: provider_id={getattr(provider_draft, 'provider_id', None) or '-'}, "
                f"protocol={getattr(provider_draft, 'api_protocol', '') or '-'}, "
                f"model={getattr(provider_draft, 'default_model', '') or '-'}, 原因={exc}"
            )
            raise
