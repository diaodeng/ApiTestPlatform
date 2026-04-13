import copy
import json
from typing import Any

from loguru import logger
from sqlalchemy.orm import Session

from module_admin.dao.config_dao import ConfigDao
from module_admin.entity.vo.config_vo import ConfigModel


class AgentBootstrapService:
    POS_CONFIG_KEY = "agent_pos_config"
    CLIENT_CONFIG_KEY = "agent_client_config"
    PLAYWRIGHT_DOWNLOAD_HOST_CONFIG_KEY = "agent_playwright_download_host"
    DEFAULT_PLAYWRIGHT_DOWNLOAD_HOST = "https://npmmirror.com/mirrors/playwright"

    @classmethod
    def get_config_services(cls, query_db: Session, config_key: str) -> dict[str, Any]:
        """
        读取并返回客户端启动配置。

        :param query_db: 数据库会话，用于读取系统配置。
        :param config_key: 系统配置键名（如 agent_client_config）。
        :return: 包含配置内容和更新时间的字典。
        """
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
        payload = cls._apply_agent_client_defaults(query_db, normalized_key, payload)

        updated_at = getattr(config, "update_time", None) or getattr(config, "create_time", None)
        return {
            "configKey": normalized_key,
            "updatedAt": updated_at,
            "config": payload,
        }

    @classmethod
    def get_pos_config_services(cls, query_db: Session) -> dict[str, Any]:
        """
        读取 POS 启动配置。

        :param query_db: 数据库会话，用于读取系统配置。
        :return: POS 启动配置字典。
        """
        return cls.get_config_services(query_db, cls.POS_CONFIG_KEY)

    @classmethod
    def _apply_agent_client_defaults(
        cls, query_db: Session, config_key: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """
        为 Agent 客户端配置补充默认值。

        :param query_db: 数据库会话，用于读取默认下载源配置。
        :param config_key: 当前请求的配置键名。
        :param payload: 原始配置 JSON。
        :return: 合并默认值后的配置 JSON。
        """
        if config_key != cls.CLIENT_CONFIG_KEY:
            return payload

        resolved_payload = copy.deepcopy(payload)
        browser_payload = resolved_payload.get("browser")
        if not isinstance(browser_payload, dict):
            browser_payload = {}

        download_host = str(browser_payload.get("playwright_download_host") or "").strip()
        if not download_host:
            browser_payload["playwright_download_host"] = cls._get_playwright_download_host(query_db)

        resolved_payload["browser"] = browser_payload
        return resolved_payload

    @classmethod
    def _get_playwright_download_host(cls, query_db: Session) -> str:
        """
        获取 Playwright 浏览器下载源地址。

        :param query_db: 数据库会话，用于读取系统配置键 agent_playwright_download_host。
        :return: 下载源地址；若系统配置未设置则返回内置默认值。
        """
        config = ConfigDao.get_config_detail_by_info(
            query_db,
            ConfigModel(config_key=cls.PLAYWRIGHT_DOWNLOAD_HOST_CONFIG_KEY),
        )
        download_host = str(getattr(config, "config_value", "") or "").strip() if config else ""
        return download_host or cls.DEFAULT_PLAYWRIGHT_DOWNLOAD_HOST
