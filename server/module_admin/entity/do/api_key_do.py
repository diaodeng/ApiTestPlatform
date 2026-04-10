from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text, UniqueConstraint

from config.database import Base


class SysApiKey(Base):
    """
    API Key信息表
    """

    __tablename__ = "sys_api_key"
    __table_args__ = (UniqueConstraint("key_code", name="uq_sys_api_key_key_code"),)

    api_key_id = Column(Integer, primary_key=True, autoincrement=True, comment="API Key主键")
    user_id = Column(Integer, nullable=False, index=True, comment="所属用户ID")
    key_name = Column(String(64, collation="utf8_general_ci"), nullable=False, comment="API Key名称")
    key_code = Column(String(32, collation="utf8_general_ci"), nullable=False, comment="API Key公开标识")
    key_prefix = Column(String(64, collation="utf8_general_ci"), nullable=False, comment="API Key展示前缀")
    key_hash = Column(String(128, collation="utf8_general_ci"), nullable=False, comment="API Key摘要")
    key_cipher_text = Column(Text, nullable=False, comment="API Key密文")
    permission_codes = Column(Text, nullable=False, comment="API Key权限JSON")
    expire_time = Column(DateTime, comment="失效时间")
    never_expire = Column(String(1, collation="utf8_general_ci"), default="0", comment="是否永不过期（0否 1是）")
    status = Column(String(1, collation="utf8_general_ci"), default="0", comment="状态（0正常 1已手动过期）")
    last_used_ip = Column(String(128, collation="utf8_general_ci"), default="", comment="最后使用IP")
    last_used_time = Column(DateTime, comment="最后使用时间")
    create_by = Column(String(64, collation="utf8_general_ci"), default="", comment="创建者")
    create_time = Column(DateTime, comment="创建时间", default=datetime.now)
    update_by = Column(String(64, collation="utf8_general_ci"), default="", comment="更新者")
    update_time = Column(DateTime, comment="更新时间", default=datetime.now)
    remark = Column(String(500, collation="utf8_general_ci"), comment="备注")
    del_flag = Column(String(1, collation="utf8_general_ci"), default="0", comment="删除标志（0代表存在 2代表删除）")
