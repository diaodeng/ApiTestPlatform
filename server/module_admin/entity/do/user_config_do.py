from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, UniqueConstraint

from config.database import Base
from config.sqlalchemy_types import long_text_type


class SysUserConfig(Base):
    """
    用户配置表，用于保存按用户隔离的页面偏好和功能配置。
    """

    __tablename__ = "sys_user_config"
    __table_args__ = (
        UniqueConstraint("user_id", "config_type", "config_key", name="uk_sys_user_config_user_type_key"),
    )

    config_id = Column(Integer, primary_key=True, autoincrement=True, comment="配置主键")
    user_id = Column(Integer, nullable=False, comment="用户ID")
    config_type = Column(String(64), nullable=False, default="", comment="配置类型")
    config_key = Column(String(128), nullable=False, default="", comment="配置键名")
    config_value = Column(long_text_type(), nullable=True, default="", comment="配置JSON值")
    create_by = Column(String(64), nullable=True, default="", comment="创建者")
    create_time = Column(DateTime, nullable=True, default=datetime.now, comment="创建时间")
    update_by = Column(String(64), nullable=True, default="", comment="更新者")
    update_time = Column(DateTime, nullable=True, default=datetime.now, comment="更新时间")
    remark = Column(String(500), nullable=True, default="", comment="备注")
