from __future__ import annotations

from sqlalchemy.orm import Session

from module_admin.dao.ai_provider_dao import AiProviderDao
from module_admin.dao.ai_provider_model_dao import AiProviderModelDao
from module_admin.entity.vo.ai_provider_vo import AiProviderModelCatalogItemModel
from module_admin.service.ai_provider_protocol_service import AiProviderProtocolService


class AiProviderModelCatalogService:
    """AI Provider模型目录查询与刷新服务。"""

    @classmethod
    def list_models(cls, db: Session, provider_id: int) -> list[AiProviderModelCatalogItemModel]:
        """
        查询已保存Provider的模型目录缓存。
        :param db: 数据库会话
        :param provider_id: Provider主键
        :return: 模型目录列表
        """
        if not AiProviderDao.get_ai_provider_by_id(db, provider_id):
            raise ValueError("Provider不存在")
        models = AiProviderModelDao.list_provider_models(db, provider_id)
        return [AiProviderModelCatalogItemModel.model_validate(item) for item in models]

    @classmethod
    def refresh_models(cls, db: Session, provider_id: int) -> list[AiProviderModelCatalogItemModel]:
        """
        使用已保存Provider凭据刷新模型目录。
        :param db: 数据库会话
        :param provider_id: Provider主键
        :return: 刷新后的模型目录
        """
        provider = AiProviderDao.get_ai_provider_by_id(db, provider_id)
        if not provider:
            raise ValueError("Provider不存在")
        models = AiProviderProtocolService.discover_models(provider)
        AiProviderModelDao.replace_remote_models(db, provider_id, models)
        db.commit()
        return cls.list_models(db, provider_id)

    @classmethod
    def preview_models(cls, provider_draft) -> list[dict[str, str]]:
        """
        使用未保存Provider草稿探测模型目录，不写入数据库。
        :param provider_draft: 包含地址、密钥和协议的Provider草稿
        :return: 远端模型目录
        """
        return AiProviderProtocolService.discover_models(provider_draft, api_key=provider_draft.api_key)
