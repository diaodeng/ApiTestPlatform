from datetime import datetime

from sqlalchemy import JSON, BigInteger, Boolean, Column, DateTime, ForeignKey, Integer, String, Text

from config.database import Base


class AuthCredential(Base):
    """凭证聚合根，密文快照是平台内凭证内容的唯一事实源。"""

    __tablename__ = "auth_credential"

    credential_id = Column(BigInteger, primary_key=True, autoincrement=True, comment="凭证主键")
    credential_name = Column(String(128, collation="utf8_general_ci"), nullable=False, comment="凭证名称")
    credential_type = Column(String(32, collation="utf8_general_ci"), nullable=False, comment="凭证类型")
    auth_mode = Column(String(32, collation="utf8_general_ci"), nullable=False, default="manual", comment="认证或刷新方式")
    enabled = Column(Boolean, nullable=False, default=True, comment="是否启用")
    auto_refresh_enabled = Column(Boolean, nullable=False, default=False, comment="是否自动刷新")
    refresh_interval_sec = Column(Integer, nullable=False, default=0, comment="自动刷新最小间隔秒数")
    sharing_mode = Column(String(32, collation="utf8_general_ci"), nullable=False, default="shared_read", comment="并发使用策略")
    secret_cipher_text = Column(Text, nullable=False, default="", comment="凭证内容密文JSON")
    secret_mask = Column(String(255, collation="utf8_general_ci"), nullable=False, default="", comment="凭证内容脱敏摘要")
    revision = Column(Integer, nullable=False, default=1, comment="乐观锁版本")
    expire_time = Column(DateTime, nullable=True, comment="凭证到期时间")
    last_refresh_time = Column(DateTime, nullable=True, comment="最近成功刷新时间")
    last_refresh_status = Column(String(32, collation="utf8_general_ci"), nullable=False, default="never", comment="最近刷新状态")
    last_refresh_message = Column(String(500, collation="utf8_general_ci"), nullable=False, default="", comment="最近刷新结果")
    create_by = Column(String(64, collation="utf8_general_ci"), default="", comment="创建者")
    create_time = Column(DateTime, default=datetime.now, comment="创建时间")
    update_by = Column(String(64, collation="utf8_general_ci"), default="", comment="更新者")
    update_time = Column(DateTime, default=datetime.now, comment="更新时间")
    remark = Column(String(500, collation="utf8_general_ci"), nullable=True, comment="备注")
    del_flag = Column(String(1, collation="utf8_general_ci"), default="0", comment="删除标志")


class AuthCredentialAuthConfig(Base):
    """凭证的登录、刷新与 OTP 配置；敏感字段仍保存在凭证密文中。"""

    __tablename__ = "auth_credential_auth_config"

    auth_config_id = Column(BigInteger, primary_key=True, autoincrement=True, comment="认证配置主键")
    credential_id = Column(BigInteger, ForeignKey("auth_credential.credential_id", ondelete="CASCADE"), nullable=False, unique=True, comment="凭证主键")
    login_url = Column(String(1000, collation="utf8_general_ci"), nullable=False, default="", comment="HTTP登录地址")
    refresh_url = Column(String(1000, collation="utf8_general_ci"), nullable=False, default="", comment="HTTP刷新地址")
    request_method = Column(String(16, collation="utf8_general_ci"), nullable=False, default="POST", comment="请求方法")
    request_template = Column(JSON, nullable=True, comment="登录或刷新请求模板")
    response_mapping = Column(JSON, nullable=True, comment="响应字段映射")
    login_method = Column(String(16, collation="utf8_general_ci"), nullable=False, default="POST", comment="登录请求方法")
    refresh_method = Column(String(16, collation="utf8_general_ci"), nullable=False, default="POST", comment="刷新请求方法")
    login_request_template = Column(JSON, nullable=True, comment="登录请求模板")
    login_response_mapping = Column(JSON, nullable=True, comment="登录响应映射")
    refresh_request_template = Column(JSON, nullable=True, comment="刷新请求模板")
    refresh_response_mapping = Column(JSON, nullable=True, comment="刷新响应映射")
    browser_start_url = Column(String(1000, collation="utf8_general_ci"), nullable=False, default="", comment="浏览器登录起始地址")
    otp_type = Column(String(32, collation="utf8_general_ci"), nullable=False, default="none", comment="OTP类型")
    target_host_patterns = Column(JSON, nullable=True, comment="允许投影的目标域名模式")
    update_time = Column(DateTime, default=datetime.now, comment="更新时间")


class AuthCredentialBinding(Base):
    """业务与凭证的显式绑定，决定投影形式和调用并发策略。"""

    __tablename__ = "auth_credential_binding"

    binding_id = Column(BigInteger, primary_key=True, autoincrement=True, comment="绑定主键")
    binding_name = Column(String(128, collation="utf8_general_ci"), nullable=False, comment="绑定名称")
    credential_id = Column(BigInteger, ForeignKey("auth_credential.credential_id", ondelete="CASCADE"), nullable=False, index=True, comment="凭证主键")
    business_type = Column(String(32, collation="utf8_general_ci"), nullable=False, comment="业务类型")
    projection_type = Column(String(32, collation="utf8_general_ci"), nullable=False, comment="投影类型")
    target_url = Column(String(1000, collation="utf8_general_ci"), nullable=False, default="", comment="目标地址")
    target_host_patterns = Column(JSON, nullable=True, comment="绑定域名范围")
    sharing_mode = Column(String(32, collation="utf8_general_ci"), nullable=False, default="shared_read", comment="绑定并发策略")
    writeback_enabled = Column(Boolean, nullable=False, default=False, comment="是否允许客户端回写凭证")
    enabled = Column(Boolean, nullable=False, default=True, comment="是否启用")
    create_by = Column(String(64, collation="utf8_general_ci"), default="", comment="创建者")
    create_time = Column(DateTime, default=datetime.now, comment="创建时间")
    update_by = Column(String(64, collation="utf8_general_ci"), default="", comment="更新者")
    update_time = Column(DateTime, default=datetime.now, comment="更新时间")
    remark = Column(String(500, collation="utf8_general_ci"), nullable=True, comment="备注")
    del_flag = Column(String(1, collation="utf8_general_ci"), default="0", comment="删除标志")


class AuthCredentialOperationLog(Base):
    """凭证解析、刷新、写回和冲突的安全审计日志。"""

    __tablename__ = "auth_credential_operation_log"

    operation_id = Column(BigInteger, primary_key=True, autoincrement=True, comment="操作日志主键")
    credential_id = Column(BigInteger, nullable=False, index=True, comment="凭证主键")
    binding_id = Column(BigInteger, nullable=True, index=True, comment="绑定主键")
    operation_type = Column(String(32, collation="utf8_general_ci"), nullable=False, comment="操作类型")
    status = Column(String(32, collation="utf8_general_ci"), nullable=False, comment="执行状态")
    revision = Column(Integer, nullable=True, comment="关联版本")
    message = Column(String(1000, collation="utf8_general_ci"), nullable=False, default="", comment="结果说明")
    operator = Column(String(64, collation="utf8_general_ci"), nullable=False, default="system", comment="操作者")
    create_time = Column(DateTime, default=datetime.now, comment="创建时间")


class AuthCredentialLease(Base):
    """独占刷新或独占使用时的短期租约。"""

    __tablename__ = "auth_credential_lease"

    lease_id = Column(BigInteger, primary_key=True, autoincrement=True, comment="租约主键")
    credential_id = Column(BigInteger, nullable=False, index=True, comment="凭证主键")
    lease_token = Column(String(64, collation="utf8_general_ci"), nullable=False, unique=True, comment="租约令牌")
    lease_type = Column(String(32, collation="utf8_general_ci"), nullable=False, comment="租约类型")
    holder = Column(String(128, collation="utf8_general_ci"), nullable=False, comment="持有者")
    expires_at = Column(DateTime, nullable=False, comment="到期时间")
    create_time = Column(DateTime, default=datetime.now, comment="创建时间")
