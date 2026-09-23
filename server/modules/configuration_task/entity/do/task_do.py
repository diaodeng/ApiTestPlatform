"""配置任务、任务版本 ORM 实体。"""

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from config.database import Base
from utils.snowflake import snowIdWorker


class ConfigurationTask(Base):
    """配置任务定义：长期可编辑的任务身份、默认执行参数和当前发布版本指针。"""

    __tablename__ = "configuration_task"
    __table_args__ = (Index("idx_ct_task_status", "status", "task_id"),)

    task_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        nullable=False,
        unique=True,
        default=snowIdWorker.get_id,
        comment="任务ID，Snowflake BIGINT",
    )
    task_name: Mapped[str] = mapped_column(String(128), nullable=False, comment="任务名称")
    description: Mapped[str] = mapped_column(String(500), nullable=False, default="", comment="任务描述")
    agent_code: Mapped[str] = mapped_column(String(128), nullable=False, comment="默认执行Agent编码")
    variables_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}", comment="业务变量JSON")
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="ACTIVE", comment="任务状态：ACTIVE/DISABLED"
    )
    current_version_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, default=None, comment="当前发布版本ID"
    )
    current_version_no: Mapped[int | None] = mapped_column(
        Integer, nullable=True, default=None, comment="当前发布版本号"
    )
    create_by: Mapped[str] = mapped_column(String(64), nullable=False, default="", comment="创建者")
    create_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, comment="创建时间")
    update_by: Mapped[str] = mapped_column(String(64), nullable=False, default="", comment="更新者")
    update_time: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.now,
        onupdate=datetime.now,
        comment="更新时间",
    )
    remark: Mapped[str] = mapped_column(Text, nullable=False, default="", comment="备注")


class ConfigurationTaskVersion(Base):
    """任务版本快照：发布后不可变，冻结步骤、变量和输入资源绑定。"""

    __tablename__ = "configuration_task_version"
    __table_args__ = (
        UniqueConstraint("task_id", "version_no", name="uk_ct_version_task_no"),
        Index("idx_ct_version_task_status", "task_id", "status"),
    )

    version_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        nullable=False,
        unique=True,
        default=snowIdWorker.get_id,
        comment="版本ID，Snowflake BIGINT",
    )
    task_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="任务ID")
    version_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1, comment="版本号，从1递增")
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="DRAFT",
        comment="版本状态：DRAFT/PUBLISHED/DEPRECATED",
    )
    start_url: Mapped[str] = mapped_column(String(512), nullable=False, default="", comment="起始URL")
    browser_name: Mapped[str] = mapped_column(String(32), nullable=False, default="chromium", comment="浏览器名称")
    headless: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="是否无头模式")
    credential_binding_id: Mapped[str] = mapped_column(String(64), nullable=False, default="", comment="凭证绑定ID")
    variables_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}", comment="版本冻结变量JSON")
    steps_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]", comment="Web步骤列表JSON")
    input_bindings_json: Mapped[str] = mapped_column(
        Text, nullable=False, default="{}", comment="fileKey到资源ID绑定JSON"
    )
    publish_by: Mapped[str] = mapped_column(String(64), nullable=False, default="", comment="发布人")
    publish_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None, comment="发布时间")
    create_by: Mapped[str] = mapped_column(String(64), nullable=False, default="", comment="创建者")
    create_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, comment="创建时间")
    update_by: Mapped[str] = mapped_column(String(64), nullable=False, default="", comment="更新者")
    update_time: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.now,
        onupdate=datetime.now,
        comment="更新时间",
    )


class ConfigurationTaskCredentialMapping(Base):
    """任务级"系统标识 → 凭证绑定"映射。

    独立于版本快照的环境配置：阶段/阶段模板通过 system_key 声明目标系统，
    凭证绑定在任务级统一维护，发布后仍可修改。
    """

    __tablename__ = "configuration_task_credential_mapping"
    __table_args__ = (
        UniqueConstraint("task_id", "system_key", name="uk_ct_cred_map_task_key"),
        Index("idx_ct_cred_map_task", "task_id"),
    )

    mapping_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        nullable=False,
        unique=True,
        default=snowIdWorker.get_id,
        comment="映射ID，Snowflake BIGINT",
    )
    task_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="任务ID")
    system_key: Mapped[str] = mapped_column(String(64), nullable=False, comment="系统标识，任务内唯一")
    credential_binding_id: Mapped[str] = mapped_column(
        String(64), nullable=False, default="", comment="统一凭证绑定ID，空表示未绑定"
    )
    remark: Mapped[str] = mapped_column(String(255), nullable=False, default="", comment="说明")
    create_by: Mapped[str] = mapped_column(String(64), nullable=False, default="", comment="创建者")
    create_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, comment="创建时间")
    update_by: Mapped[str] = mapped_column(String(64), nullable=False, default="", comment="更新者")
    update_time: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.now,
        onupdate=datetime.now,
        comment="更新时间",
    )
