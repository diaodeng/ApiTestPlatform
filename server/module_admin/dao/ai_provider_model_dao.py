from datetime import datetime

from sqlalchemy.orm import Session

from module_admin.entity.do.ai_provider_do import SysAiProviderModel


class AiProviderModelDao:
    """AI Provider模型目录数据访问层。"""

    @classmethod
    def list_provider_models(cls, db: Session, provider_id: int) -> list[SysAiProviderModel]:
        """
        查询Provider已缓存且启用的模型目录。
        :param db: 数据库会话
        :param provider_id: Provider主键
        :return: 模型目录列表
        """
        return (
            db.query(SysAiProviderModel)
            .filter(SysAiProviderModel.provider_id == provider_id, SysAiProviderModel.enabled.is_(True))
            .order_by(SysAiProviderModel.model_id.asc())
            .all()
        )

    @classmethod
    def list_provider_models_all(cls, db: Session, provider_id: int) -> list[SysAiProviderModel]:
        """
        查询Provider所有模型目录（含已禁用），用于管理页面展示。
        :param db: 数据库会话
        :param provider_id: Provider主键
        :return: 模型目录全部列表
        """
        return (
            db.query(SysAiProviderModel)
            .filter(SysAiProviderModel.provider_id == provider_id)
            .order_by(SysAiProviderModel.model_id.asc())
            .all()
        )

    @classmethod
    def list_enabled_models_by_provider_code(cls, db: Session, provider_code: str) -> list[SysAiProviderModel]:
        """
        按Provider编码查询已启用的模型目录，供使用方页面选择模型。
        :param db: 数据库会话
        :param provider_code: Provider编码
        :return: 已启用模型目录列表
        """
        from module_admin.entity.do.ai_provider_do import SysAiProvider

        provider = (
            db.query(SysAiProvider)
            .filter(SysAiProvider.provider_code == provider_code, SysAiProvider.enabled.is_(True))
            .first()
        )
        if not provider:
            return []
        return cls.list_provider_models(db, provider.provider_id)

    @classmethod
    def get_provider_model_by_id(cls, db: Session, provider_id: int, model_id: str) -> SysAiProviderModel | None:
        """
        查询指定Provider的单个模型目录项。
        :param db: 数据库会话
        :param provider_id: Provider主键
        :param model_id: 模型标识
        :return: 模型目录项，不存在返回None
        """
        return (
            db.query(SysAiProviderModel)
            .filter(
                SysAiProviderModel.provider_id == provider_id,
                SysAiProviderModel.model_id == model_id,
            )
            .first()
        )

    @classmethod
    def add_provider_model(
        cls, db: Session, provider_id: int, model_id: str, display_name: str = ""
    ) -> SysAiProviderModel:
        """
        手动添加模型目录项。
        :param db: 数据库会话
        :param provider_id: Provider主键
        :param model_id: 模型标识
        :param display_name: 展示名称
        :return: 新增的模型目录项
        """
        now = datetime.now()
        model = SysAiProviderModel(
            provider_id=provider_id,
            model_id=model_id,
            display_name=display_name or model_id,
            source="manual",
            enabled=True,
            discovered_at=now,
            create_time=now,
            update_time=now,
        )
        db.add(model)
        return model

    @classmethod
    def toggle_provider_model(cls, db: Session, provider_id: int, model_id: str, enabled: bool) -> bool:
        """
        启用/禁用模型目录项。
        :param db: 数据库会话
        :param provider_id: Provider主键
        :param model_id: 模型标识
        :param enabled: 是否启用
        :return: 是否找到并更新
        """
        row = cls.get_provider_model_by_id(db, provider_id, model_id)
        if not row:
            return False
        row.enabled = enabled
        row.update_time = datetime.now()
        return True

    @classmethod
    def delete_provider_model(cls, db: Session, provider_id: int, model_id: str) -> bool:
        """
        删除模型目录项（仅允许删除人工添加的）。
        :param db: 数据库会话
        :param provider_id: Provider主键
        :param model_id: 模型标识
        :return: 是否找到并删除
        """
        row = cls.get_provider_model_by_id(db, provider_id, model_id)
        if not row:
            return False
        if row.source != "manual":
            return False
        db.delete(row)
        return True

    @classmethod
    def replace_remote_models(cls, db: Session, provider_id: int, models: list[dict[str, str]]) -> None:
        """
        用本次远端发现结果更新Provider模型目录，保留人工模型项。
        :param db: 数据库会话
        :param provider_id: Provider主键
        :param models: 标准化后的远端模型列表
        :return: 无返回
        """
        now = datetime.now()
        existing = {
            item.model_id: item
            for item in db.query(SysAiProviderModel)
            .filter(SysAiProviderModel.provider_id == provider_id, SysAiProviderModel.source == "remote")
            .all()
        }
        found_ids = set()
        for model in models:
            model_id = str(model.get("model_id") or "").strip()
            if not model_id:
                continue
            found_ids.add(model_id)
            row = existing.get(model_id)
            if row:
                row.display_name = str(model.get("display_name") or model_id).strip()
                row.enabled = True
                row.discovered_at = now
                row.last_seen_at = now
                row.update_time = now
                continue
            db.add(
                SysAiProviderModel(
                    provider_id=provider_id,
                    model_id=model_id,
                    display_name=str(model.get("display_name") or model_id).strip(),
                    source="remote",
                    enabled=True,
                    discovered_at=now,
                    last_seen_at=now,
                    create_time=now,
                    update_time=now,
                )
            )
        for model_id, row in existing.items():
            if model_id not in found_ids:
                row.enabled = False
                row.update_time = now
