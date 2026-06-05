from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, JSON, String, Text, UniqueConstraint

from config.database import Base


class SysAiProvider(Base):
    """
    AI Provider 配置表，保存不同供应商的 Agent、密钥、模型与等级配置。
    """

    __tablename__ = "sys_ai_provider"
    __table_args__ = (UniqueConstraint("provider_code", name="uq_sys_ai_provider_provider_code"),)

    provider_id = Column(Integer, primary_key=True, autoincrement=True, comment="Provider主键")
    provider_code = Column(String(64, collation="utf8_general_ci"), nullable=False, comment="Provider编码")
    provider_name = Column(String(128, collation="utf8_general_ci"), nullable=False, comment="Provider名称")
    provider_type = Column(String(64, collation="utf8_general_ci"), nullable=False, comment="Provider类型")
    agent_code = Column(String(64, collation="utf8_general_ci"), nullable=True, default="", comment="绑定Agent编码")
    model_name = Column(String(128, collation="utf8_general_ci"), nullable=False, default="", comment="默认模型名称")
    provider_level = Column(Integer, nullable=False, default=0, comment="Provider等级")
    base_url = Column(String(500, collation="utf8_general_ci"), nullable=True, default="", comment="API基础地址")
    api_key_prefix = Column(String(128, collation="utf8_general_ci"), nullable=True, default="", comment="密钥掩码前缀")
    api_key_cipher_text = Column(Text, nullable=False, comment="密钥密文")
    enabled = Column(Boolean, nullable=False, default=True, comment="是否启用")
    extra_config = Column(JSON, nullable=True, comment="扩展配置")
    create_by = Column(String(64, collation="utf8_general_ci"), default="", comment="创建者")
    create_time = Column(DateTime, comment="创建时间", default=datetime.now)
    update_by = Column(String(64, collation="utf8_general_ci"), default="", comment="更新者")
    update_time = Column(DateTime, comment="更新时间", default=datetime.now)
    remark = Column(String(500, collation="utf8_general_ci"), comment="备注")
    del_flag = Column(String(1, collation="utf8_general_ci"), default="0", comment="删除标志（0代表存在 2代表删除）")
