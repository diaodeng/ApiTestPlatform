import json
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from module_admin.dao.user_config_dao import UserConfigDao
from module_admin.entity.do.user_config_do import SysUserConfig
from module_admin.entity.vo.user_config_vo import UserConfigModel


class UserConfigService:
    """
    用户配置服务层，统一管理按用户隔离的少量杂项配置。
    """

    @classmethod
    def _normalize_text(cls, value: str | None, max_length: int) -> str:
        """
        清理配置类型、键名和备注文本。
        :param value: 原始文本
        :param max_length: 最大长度
        :return: 清理后的文本
        """
        return str(value or "").strip()[:max_length]

    @classmethod
    def _dump_config_value(cls, value: Any) -> str:
        """
        序列化配置值。
        :param value: Python配置值
        :return: JSON字符串
        """
        return json.dumps(value, ensure_ascii=False, default=str)

    @classmethod
    def _load_config_value(cls, raw_value: str | None) -> Any:
        """
        解析配置值。
        :param raw_value: 数据库存储的JSON字符串
        :return: Python配置值
        """
        if raw_value is None or raw_value == "":
            return None
        try:
            return json.loads(raw_value)
        except Exception:
            return raw_value

    @classmethod
    def _to_model(cls, config: SysUserConfig) -> UserConfigModel:
        """
        将数据库实体转换为接口模型。
        :param config: 用户配置实体
        :return: 用户配置接口模型
        """
        return UserConfigModel(
            configId=config.config_id,
            userId=config.user_id,
            configType=config.config_type,
            configKey=config.config_key,
            configValue=cls._load_config_value(config.config_value),
            remark=config.remark,
            createBy=config.create_by,
            createTime=config.create_time,
            updateBy=config.update_by,
            updateTime=config.update_time,
        )

    @classmethod
    def get_current_user_config_services(
        cls,
        query_db: Session,
        user_id: int,
        config_type: str,
        config_key: str,
    ) -> UserConfigModel | None:
        """
        查询当前用户的指定配置。
        :param query_db: 数据库会话
        :param user_id: 当前用户ID
        :param config_type: 配置类型
        :param config_key: 配置键名
        :return: 用户配置模型，不存在返回None
        """
        safe_type = cls._normalize_text(config_type, 64)
        safe_key = cls._normalize_text(config_key, 128)
        if not safe_type or not safe_key:
            return None
        config = UserConfigDao.get_user_config(query_db, user_id, safe_type, safe_key)
        return cls._to_model(config) if config else None

    @classmethod
    def list_current_user_config_services(
        cls,
        query_db: Session,
        user_id: int,
        config_type: str | None = None,
    ) -> list[UserConfigModel]:
        """
        查询当前用户的配置列表。
        :param query_db: 数据库会话
        :param user_id: 当前用户ID
        :param config_type: 可选配置类型
        :return: 用户配置模型列表
        """
        safe_type = cls._normalize_text(config_type, 64) if config_type else None
        return [cls._to_model(item) for item in UserConfigDao.list_user_configs(query_db, user_id, safe_type)]

    @classmethod
    def save_current_user_config_services(
        cls,
        query_db: Session,
        user_id: int,
        user_name: str,
        config_model: UserConfigModel,
    ) -> UserConfigModel:
        """
        新增或更新当前用户的配置。
        :param query_db: 数据库会话
        :param user_id: 当前用户ID
        :param user_name: 当前用户名
        :param config_model: 配置保存模型
        :return: 保存后的用户配置模型
        """
        safe_type = cls._normalize_text(config_model.config_type, 64)
        safe_key = cls._normalize_text(config_model.config_key, 128)
        if not safe_type or not safe_key:
            raise ValueError("配置类型和配置键名不能为空")

        now = datetime.now()
        existing = UserConfigDao.get_user_config(query_db, user_id, safe_type, safe_key)
        if existing:
            existing.config_value = cls._dump_config_value(config_model.config_value)
            existing.remark = cls._normalize_text(config_model.remark, 500)
            existing.update_by = user_name
            existing.update_time = now
            query_db.flush()
            return cls._to_model(existing)

        config = SysUserConfig(
            user_id=user_id,
            config_type=safe_type,
            config_key=safe_key,
            config_value=cls._dump_config_value(config_model.config_value),
            remark=cls._normalize_text(config_model.remark, 500),
            create_by=user_name,
            create_time=now,
            update_by=user_name,
            update_time=now,
        )
        return cls._to_model(UserConfigDao.add_user_config(query_db, config))
