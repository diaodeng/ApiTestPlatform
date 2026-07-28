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
