from sqlalchemy.orm import Session

from module_admin.entity.do.user_config_do import SysUserConfig


class UserConfigDao:
    """
    用户配置数据访问层。
    """

    @classmethod
    def get_user_config(cls, db: Session, user_id: int, config_type: str, config_key: str) -> SysUserConfig | None:
        """
        获取指定用户的单个配置。
        :param db: 数据库会话
        :param user_id: 用户ID
        :param config_type: 配置类型
        :param config_key: 配置键名
        :return: 用户配置记录，不存在返回None
        """
        return (
            db.query(SysUserConfig)
            .filter(
                SysUserConfig.user_id == user_id,
                SysUserConfig.config_type == config_type,
                SysUserConfig.config_key == config_key,
            )
            .first()
        )

    @classmethod
    def list_user_configs(cls, db: Session, user_id: int, config_type: str | None = None) -> list[SysUserConfig]:
        """
        获取指定用户的配置列表。
        :param db: 数据库会话
        :param user_id: 用户ID
        :param config_type: 可选配置类型
        :return: 用户配置列表
        """
        query = db.query(SysUserConfig).filter(SysUserConfig.user_id == user_id)
        if config_type:
            query = query.filter(SysUserConfig.config_type == config_type)
        return query.order_by(SysUserConfig.config_type.asc(), SysUserConfig.config_key.asc()).all()

    @classmethod
    def add_user_config(cls, db: Session, config: SysUserConfig) -> SysUserConfig:
        """
        新增用户配置。
        :param db: 数据库会话
        :param config: 用户配置实体
        :return: 新增后的用户配置实体
        """
        db.add(config)
        db.flush()
        return config
