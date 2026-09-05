from datetime import datetime

from sqlalchemy import BigInteger, Boolean, Column, DateTime, Integer, String

from config.database import Base

# 主键跨库兼容：MySQL 保持 BIGINT 自增；SQLite 中 BIGINT 主键不能成为 rowid
# 别名导致自增失败，因此 sqlite 方言降级为 INTEGER。
ProfilePKBigInteger = BigInteger().with_variant(Integer(), "sqlite")


class MetricsCollectorProfile(Base):
    """资源采集服务配置，每行代表一个独立的指标推送通道（采集服务实例）。

    一个 profile 决定采集线程往哪里推（push_url）、以什么身份推（认证与标签）、
    以什么节奏推（interval/batch/timeout）以及推哪些指标（extended_enabled）。
    采集线程运行期轮询本表实现配置热生效，不再从环境配置读取。
    """

    __tablename__ = "metrics_collector_profile"

    profile_id = Column(ProfilePKBigInteger, primary_key=True, autoincrement=True, comment="采集服务主键")
    profile_name = Column(String(64, collation="utf8_general_ci"), nullable=False, comment="采集服务名称")
    enabled = Column(Boolean, nullable=False, default=False, comment="是否启用采集推送")
    push_url = Column(String(255, collation="utf8_general_ci"), nullable=False, default="", comment="Prometheus文本协议推送地址")
    auth_user = Column(String(64, collation="utf8_general_ci"), nullable=False, default="", comment="推送认证用户")
    auth_password_cipher = Column(String(500, collation="utf8_general_ci"), nullable=False, default="", comment="推送认证密码密文")
    job_label = Column(String(64, collation="utf8_general_ci"), nullable=False, default="QTR", comment="指标job标签")
    instance_label = Column(String(64, collation="utf8_general_ci"), nullable=False, default="TEST_ENV", comment="指标instance标签")
    machine_label = Column(String(64, collation="utf8_general_ci"), nullable=False, default="", comment="指标machine标签")
    interval_seconds = Column(Integer, nullable=False, default=5, comment="推送间隔秒数")
    batch_size = Column(Integer, nullable=False, default=100, comment="单批最大样本条数")
    timeout_seconds = Column(Integer, nullable=False, default=10, comment="推送请求超时秒数")
    extended_enabled = Column(Boolean, nullable=False, default=False, comment="是否发送进程/cgroup/任务扩展指标")
    revision = Column(Integer, nullable=False, default=1, comment="配置版本号，热生效比对用")
    last_push_time = Column(DateTime, nullable=True, comment="最近一次推送尝试时间")
    last_push_status = Column(String(32, collation="utf8_general_ci"), nullable=False, default="never", comment="最近推送状态：never/success/failed")
    last_push_message = Column(String(500, collation="utf8_general_ci"), nullable=False, default="", comment="最近推送结果说明")
    push_failure_count = Column(Integer, nullable=False, default=0, comment="累计推送失败次数")
    create_by = Column(String(64, collation="utf8_general_ci"), default="", comment="创建者")
    create_time = Column(DateTime, default=datetime.now, comment="创建时间")
    update_by = Column(String(64, collation="utf8_general_ci"), default="", comment="更新者")
    update_time = Column(DateTime, default=datetime.now, comment="更新时间")
    remark = Column(String(500, collation="utf8_general_ci"), nullable=True, comment="备注")
