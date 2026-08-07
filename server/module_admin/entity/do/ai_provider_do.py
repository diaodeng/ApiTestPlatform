from datetime import datetime

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint

from config.database import Base


class SysAiProvider(Base):
    """
    AI Provider 配置表，保存平台、调用协议、业务用途、执行器兼容性和连接凭据。
    """

    __tablename__ = "sys_ai_provider"
    __table_args__ = (UniqueConstraint("provider_code", name="uq_sys_ai_provider_provider_code"),)

    provider_id = Column(Integer, primary_key=True, autoincrement=True, comment="Provider主键")
    provider_code = Column(String(64, collation="utf8_general_ci"), nullable=False, comment="Provider编码")
    provider_name = Column(String(128, collation="utf8_general_ci"), nullable=False, comment="Provider名称")
    platform_code = Column(String(64, collation="utf8_general_ci"), nullable=False, comment="平台编码")
    api_protocol = Column(String(64, collation="utf8_general_ci"), nullable=False, comment="API调用协议")
    supported_usages = Column(JSON, nullable=False, comment="允许的业务用途")
    supported_executors = Column(JSON, nullable=False, comment="兼容的执行器")
    preferred_agent_code = Column(
        String(64, collation="utf8_general_ci"),
        nullable=True,
        default="",
        comment="首选Agent编码",
    )
    default_model = Column(String(128, collation="utf8_general_ci"), nullable=False, default="", comment="默认模型名称")
    provider_level = Column(Integer, nullable=False, default=0, comment="Provider等级")
    base_url = Column(String(500, collation="utf8_general_ci"), nullable=True, default="", comment="API基础地址")
    api_key_prefix = Column(String(128, collation="utf8_general_ci"), nullable=True, default="", comment="密钥掩码前缀")
    api_key_cipher_text = Column(Text, nullable=False, comment="密钥密文")
    enabled = Column(Boolean, nullable=False, default=True, comment="是否启用")
    connection_config = Column(JSON, nullable=True, comment="协议连接扩展配置")
    worker_env = Column(JSON, nullable=True, comment="Worker环境变量覆盖配置")
    create_by = Column(String(64, collation="utf8_general_ci"), default="", comment="创建者")
    create_time = Column(DateTime, comment="创建时间", default=datetime.now)
    update_by = Column(String(64, collation="utf8_general_ci"), default="", comment="更新者")
    update_time = Column(DateTime, comment="更新时间", default=datetime.now)
    remark = Column(String(500, collation="utf8_general_ci"), comment="备注")
    del_flag = Column(String(1, collation="utf8_general_ci"), default="0", comment="删除标志（0代表存在 2代表删除）")


class SysAiProviderModel(Base):
    """
    AI Provider 模型目录表，缓存远端发现或人工维护的模型候选。
    """

    __tablename__ = "sys_ai_provider_model"
    __table_args__ = (UniqueConstraint("provider_id", "model_id", name="uq_sys_ai_provider_model_provider_model"),)

    provider_model_id = Column(Integer, primary_key=True, autoincrement=True, comment="模型目录主键")
    provider_id = Column(
        Integer,
        ForeignKey("sys_ai_provider.provider_id", ondelete="CASCADE"),
        nullable=False,
        comment="Provider主键",
    )
    model_id = Column(String(255, collation="utf8_general_ci"), nullable=False, comment="上游模型标识")
    display_name = Column(String(255, collation="utf8_general_ci"), nullable=False, default="", comment="模型展示名称")
    source = Column(String(32, collation="utf8_general_ci"), nullable=False, comment="目录来源")
    enabled = Column(Boolean, nullable=False, default=True, comment="是否可选")
    capability_overrides = Column(JSON, nullable=True, comment="模型级能力覆盖")
    discovered_at = Column(DateTime, nullable=True, comment="最近发现时间")
    last_seen_at = Column(DateTime, nullable=True, comment="最近一次出现在远端目录的时间")
    create_time = Column(DateTime, comment="创建时间", default=datetime.now)
    update_time = Column(DateTime, comment="更新时间", default=datetime.now)
