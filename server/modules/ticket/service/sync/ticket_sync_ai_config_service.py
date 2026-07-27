"""
工单同步轻量 AI 配置服务：统一解析同步配置中的 AI 任务开关、Provider 和提示词。
"""

from copy import deepcopy
from typing import Any

from sqlalchemy.orm import Session

from module_admin.entity.do.config_do import SysConfig
from modules.ticket.util.sync_util import SyncUtil


class TicketSyncAiConfigService:
    """工单同步轻量 AI 配置解析服务。"""

    CONFIG_KEY = "ticket.sync.automation"
    SECTION_DEFAULTS: dict[str, dict[str, Any]] = {
        "translateConfig": {
            "enabled": False,
            "providerCode": "",
            "promptCode": "ticket_translate_default",
            "translateOnExternalSync": True,
            "translateOnRemotePull": True,
            "translateOnBitablePull": True,
            "translateOnManualCreate": False,
        },
        "titleSummaryConfig": {
            "enabled": False,
            "providerCode": "",
            "promptCode": "ticket_title_summary_default",
        },
        "aiClassification": {
            "enabled": False,
            "providerCode": "",
            "promptCode": "ticket_stat_classify_default",
        },
        "aiSyncExtract": {
            "externalPushEnabled": False,
            "remotePullEnabled": False,
            "bitablePullEnabled": False,
            "manualCreateEnabled": False,
            "providerCode": "",
            "promptCode": "ticket_sync_extract_default",
            "extractFields": ["storeName", "posNo", "scoNo", "logDate", "versionKey"],
        },
        "knowledgeConfig": {
            "enabled": False,
            "providerCode": "",
            "promptCode": "ticket_knowledge_extract_default",
        },
    }
    BOOLEAN_FIELDS = {
        "enabled",
        "translateOnExternalSync",
        "translateOnRemotePull",
        "translateOnBitablePull",
        "translateOnManualCreate",
        "externalPushEnabled",
        "remotePullEnabled",
        "bitablePullEnabled",
        "manualCreateEnabled",
    }

    @classmethod
    def default_section(cls, section_name: str) -> dict[str, Any]:
        """
        获取轻量 AI 配置段默认值。

        :param section_name: 配置段名称。
        :return: 独立的默认配置字典。
        """
        return deepcopy(cls.SECTION_DEFAULTS.get(section_name) or {})

    @classmethod
    def normalize_section(cls, section_name: str, value: Any) -> dict[str, Any]:
        """
        归一化指定轻量 AI 配置段。

        :param section_name: 配置段名称。
        :param value: 待归一化的原始配置。
        :return: 合并默认值并清洗后的配置。
        """
        defaults = cls.default_section(section_name)
        source = value if isinstance(value, dict) else {}
        normalized = {**defaults, **source}
        for field_name in cls.BOOLEAN_FIELDS.intersection(normalized):
            normalized[field_name] = SyncUtil.to_bool(normalized.get(field_name), bool(defaults.get(field_name)))
        normalized["providerCode"] = str(normalized.get("providerCode") or "").strip()
        normalized["promptCode"] = str(
            normalized.get("promptCode") or defaults.get("promptCode") or ""
        ).strip()
        if "extractFields" in defaults:
            extract_fields = normalized.get("extractFields")
            normalized["extractFields"] = (
                list(dict.fromkeys(str(item or "").strip() for item in extract_fields if str(item or "").strip()))
                if isinstance(extract_fields, list)
                else list(defaults["extractFields"])
            )
        return normalized

    @classmethod
    def load_section(cls, db: Session, section_name: str) -> dict[str, Any]:
        """
        从工单同步配置读取指定轻量 AI 配置段。

        :param db: 数据库会话。
        :param section_name: 配置段名称。
        :return: 归一化后的配置段；配置不存在时返回默认值。
        """
        row = db.query(SysConfig).filter(SysConfig.config_key == cls.CONFIG_KEY).first()
        config = SyncUtil.json_loads(getattr(row, "config_value", None), {})
        section = config.get(section_name) if isinstance(config, dict) else None
        return cls.normalize_section(section_name, section)

    @classmethod
    def is_enabled(cls, db: Session, section_name: str) -> bool:
        """
        判断指定轻量 AI 任务总开关是否启用。

        :param db: 数据库会话。
        :param section_name: 配置段名称。
        :return: 是否启用。
        """
        return bool(cls.load_section(db, section_name).get("enabled"))

    @classmethod
    def resolve_task_settings(cls, db: Session, section_name: str) -> tuple[str, str]:
        """
        解析指定轻量 AI 任务使用的 Provider 和提示词编码。

        :param db: 数据库会话。
        :param section_name: 配置段名称。
        :return: Provider 编码和提示词编码。
        """
        section = cls.load_section(db, section_name)
        return str(section.get("providerCode") or "").strip(), str(section.get("promptCode") or "").strip()

    @classmethod
    def is_sync_extract_enabled_for_scene(cls, db: Session, sync_scene: str) -> bool:
        """
        判断指定同步场景是否启用 AI 参数提取。

        :param db: 数据库会话。
        :param sync_scene: 同步场景编码。
        :return: 是否启用该场景的参数提取。
        """
        scene_field_map = {
            "external_sync": "externalPushEnabled",
            "remote_pull": "remotePullEnabled",
            "bitable_pull": "bitablePullEnabled",
            "manual_create": "manualCreateEnabled",
        }
        field_name = scene_field_map.get(str(sync_scene or "").strip())
        if not field_name:
            return False
        return bool(cls.load_section(db, "aiSyncExtract").get(field_name))
