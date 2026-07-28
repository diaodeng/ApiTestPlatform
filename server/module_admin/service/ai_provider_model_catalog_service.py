from __future__ import annotations

from sqlalchemy.orm import Session

from module_admin.dao.ai_provider_dao import AiProviderDao
from module_admin.dao.ai_provider_model_dao import AiProviderModelDao
from module_admin.entity.vo.ai_provider_vo import AiProviderModelCatalogItemModel


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
