import json
from typing import Any

from loguru import logger
from sqlalchemy.orm import Session

from module_admin.dao.config_dao import ConfigDao
from module_admin.entity.vo.config_vo import ConfigModel


class AgentBootstrapService:
    POS_CONFIG_KEY = "agent_pos_config"

    @classmethod
    def get_config_services(cls, query_db: Session, config_key: str) -> dict[str, Any]:
        normalized_key = (config_key or "").strip()
        if not normalized_key:
            raise ValueError("配置键不能为空")

        config = ConfigDao.get_config_detail_by_info(
            query_db,
            ConfigModel(config_key=normalized_key),
        )
        if not config or not getattr(config, "config_value", None):
            raise ValueError(f"未配置启动配置，请先维护参数键 {normalized_key}")

        raw_value = getattr(config, "config_value", None)
        try:
            payload = json.loads(raw_value)
        except Exception as exc:
            logger.info(raw_value)
            raise ValueError(f"参数键 {normalized_key} 的值不是有效 JSON") from exc

        if not isinstance(payload, dict):
            raise ValueError(f"参数键 {normalized_key} 的值必须是 JSON 对象")

        updated_at = getattr(config, "update_time", None) or getattr(config, "create_time", None)
        return {
            "configKey": normalized_key,
            "updatedAt": updated_at,
            "config": payload,
        }

    @classmethod
    def get_pos_config_services(cls, query_db: Session) -> dict[str, Any]:
        return cls.get_config_services(query_db, cls.POS_CONFIG_KEY)
