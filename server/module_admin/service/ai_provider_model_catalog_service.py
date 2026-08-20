from __future__ import annotations

from sqlalchemy.orm import Session

from module_admin.dao.ai_provider_dao import AiProviderDao
from module_admin.dao.ai_provider_model_dao import AiProviderModelDao
from module_admin.entity.vo.ai_provider_vo import (
    AiProviderModelCatalogItemModel,
    ProviderModelOptionModel,
)
from module_admin.service.ai_provider_protocol_service import AiProviderProtocolService
from utils.log_util import logger


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
    def list_all_models(cls, db: Session, provider_id: int) -> list[AiProviderModelCatalogItemModel]:
        """
        查询Provider所有模型目录（含已禁用），供管理页面使用。
        :param db: 数据库会话
        :param provider_id: Provider主键
        :return: 模型目录全部列表
        """
        if not AiProviderDao.get_ai_provider_by_id(db, provider_id):
            raise ValueError("Provider不存在")
        models = AiProviderModelDao.list_provider_models_all(db, provider_id)
        return [AiProviderModelCatalogItemModel.model_validate(item) for item in models]

    @classmethod
    def list_model_options_by_provider_code(
        cls, db: Session, provider_code: str
    ) -> list[ProviderModelOptionModel]:
        """
        按Provider编码查询已启用模型下拉选项，供使用方页面选择模型。
        :param db: 数据库会话
        :param provider_code: Provider编码
        :return: 模型下拉选项列表
        """
        if not str(provider_code or "").strip():
            return []
        models = AiProviderModelDao.list_enabled_models_by_provider_code(db, provider_code)
        return [ProviderModelOptionModel(model_id=item.model_id, display_name=item.display_name) for item in models]

    @classmethod
    def refresh_and_persist_models(cls, db: Session, provider_id: int) -> list[AiProviderModelCatalogItemModel]:
        """
        从远端API拉取模型列表并持久化到数据库。
        :param db: 数据库会话
        :param provider_id: Provider主键
        :return: 刷新后的模型目录全部列表
        """
        provider = AiProviderDao.get_ai_provider_by_id(db, provider_id)
        if not provider:
            raise ValueError("Provider不存在")
        if not bool(getattr(provider, "enabled", True)):
            raise ValueError("Provider已停用，无法刷新模型目录")
        try:
            remote_models = AiProviderProtocolService.discover_models(provider)
        except Exception as exc:
            logger.warning(f"Provider[{provider_id}]远端模型目录拉取失败: {exc}")
            raise ValueError(f"远端模型目录拉取失败: {exc}") from exc
        if not remote_models:
            raise ValueError("远端未返回任何模型")
        AiProviderModelDao.replace_remote_models(db, provider_id, remote_models)
        db.commit()
        logger.info(f"Provider[{provider_id}]模型目录已刷新，共{len(remote_models)}个远端模型")
        return cls.list_all_models(db, provider_id)

    @classmethod
    def add_manual_model(
        cls, db: Session, provider_id: int, model_id: str, display_name: str = ""
    ) -> AiProviderModelCatalogItemModel:
        """
        手动添加模型目录项。
        :param db: 数据库会话
        :param provider_id: Provider主键
        :param model_id: 模型标识
        :param display_name: 展示名称
        :return: 新增的模型目录项
        """
        if not AiProviderDao.get_ai_provider_by_id(db, provider_id):
            raise ValueError("Provider不存在")
        model_id = str(model_id or "").strip()
        if not model_id:
            raise ValueError("模型标识不能为空")
        existing = AiProviderModelDao.get_provider_model_by_id(db, provider_id, model_id)
        if existing:
            raise ValueError(f"模型[{model_id}]已存在")
        model = AiProviderModelDao.add_provider_model(db, provider_id, model_id, str(display_name or "").strip())
        db.commit()
        return AiProviderModelCatalogItemModel.model_validate(model)

    @classmethod
    def toggle_model(
        cls, db: Session, provider_id: int, model_id: str, enabled: bool
    ) -> AiProviderModelCatalogItemModel:
        """
        启用/禁用模型目录项。
        :param db: 数据库会话
        :param provider_id: Provider主键
        :param model_id: 模型标识
        :param enabled: 是否启用
        :return: 更新后的模型目录项
        """
        if not AiProviderDao.get_ai_provider_by_id(db, provider_id):
            raise ValueError("Provider不存在")
        found = AiProviderModelDao.toggle_provider_model(db, provider_id, model_id, enabled)
        if not found:
            raise ValueError(f"模型[{model_id}]不存在")
        db.commit()
        model = AiProviderModelDao.get_provider_model_by_id(db, provider_id, model_id)
        return AiProviderModelCatalogItemModel.model_validate(model)

    @classmethod
    def delete_manual_model(cls, db: Session, provider_id: int, model_id: str) -> None:
        """
        删除人工添加的模型目录项。
        :param db: 数据库会话
        :param provider_id: Provider主键
        :param model_id: 模型标识
        """
        if not AiProviderDao.get_ai_provider_by_id(db, provider_id):
            raise ValueError("Provider不存在")
        deleted = AiProviderModelDao.delete_provider_model(db, provider_id, model_id)
        if not deleted:
            raise ValueError(f"模型[{model_id}]不存在或不允许删除（仅支持删除人工添加的模型）")
        db.commit()
