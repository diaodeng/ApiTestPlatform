from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import JSON, BigInteger, Boolean, Date, DateTime, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from config.database import Base
from config.sqlalchemy_types import long_text_type
from utils.snowflake import snowIdWorker


class TicketLogPullRecord(Base):
    """
    工单日志拉取记录表，保存外部日志申请、轮询下载、存储和解析结果。
    """

    __tablename__ = "ticket_log_pull_record"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, nullable=False, unique=True, default=snowIdWorker.get_id, comment="记录ID"
    )
    ticket_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True, comment="工单ID")
    vendor_id: Mapped[int] = mapped_column(Integer, nullable=False, comment="商户vendorId")
    store_id: Mapped[int] = mapped_column(Integer, nullable=False, comment="门店storeId")
    pos_no: Mapped[int] = mapped_column(Integer, nullable=False, comment="POS编号")
    command_type: Mapped[int] = mapped_column(Integer, nullable=False, default=1, comment="命令类型")
    command_data_type: Mapped[int] = mapped_column(Integer, nullable=False, default=1, comment="命令数据类型")
    command_content: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="提交给外部接口的命令内容")
    log_begin_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="日志筛选开始时间")
    log_end_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="日志筛选结束时间")
    storage_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="local", comment="存储模式")
    storage_path: Mapped[str | None] = mapped_column(String(1000), nullable=True, comment="最终归档文件地址")
    download_file_name: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="下载文件名")
    download_file_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="下载文件大小")
    external_command_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="外部命令ID")
    external_serial_number: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="外部流水号")
    external_command_status: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="外部命令状态")
    external_command_status_desc: Mapped[str | None] = mapped_column(
        String(100), nullable=True, comment="外部命令状态描述"
    )
    command_result_url: Mapped[str | None] = mapped_column(String(1000), nullable=True, comment="外部返回压缩包地址")
    source_created_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="外部命令创建时间")
    last_polled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="最近轮询时间")
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="处理完成时间")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="created", comment="内部处理状态")
    status_desc: Mapped[str] = mapped_column(String(100), nullable=False, default="待提交", comment="内部状态说明")
    is_error: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="是否异常/失败")
    error_message: Mapped[str | None] = mapped_column(long_text_type(), nullable=True, comment="异常信息")
    exception_detail: Mapped[str | None] = mapped_column(long_text_type(), nullable=True, comment="异常堆栈或详细错误")
    archive_entry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="压缩包文件数")
    matched_entry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="命中的日志条目数")
    content_char_count: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, comment="日志文本字符数")
    content_truncated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="日志内容是否截断")
    compressed_content: Mapped[str | None] = mapped_column(
        long_text_type(), nullable=True, comment="gzip+base64日志内容"
    )
    compressed_content_encoding: Mapped[str | None] = mapped_column(
        String(50), nullable=True, default="gzip+base64", comment="压缩内容编码方式"
    )
    content_summary: Mapped[str | None] = mapped_column(long_text_type(), nullable=True, comment="日志内容摘要")
    create_by: Mapped[str | None] = mapped_column(String(100), nullable=True, default="", comment="创建者")
    update_by: Mapped[str | None] = mapped_column(String(100), nullable=True, default="", comment="更新者")
    create_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, comment="创建时间")
    update_time: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now, onupdate=datetime.now, comment="更新时间"
    )


class TicketLogPullStoreConfig(Base):
    """
    工单日志拉取门店配置表，保存外部门店基础信息与检索字段。
    """

    __tablename__ = "ticket_log_pull_store_config"
    __table_args__ = (
        Index("idx_ticket_log_pull_store_config_vender_no", "vender_no"),
        Index("idx_ticket_log_pull_store_config_org_no", "org_no"),
        Index("idx_ticket_log_pull_store_config_sap_org_no", "sap_org_no"),
        Index("idx_ticket_log_pull_store_config_group_no", "group_no"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, nullable=False, unique=True, default=snowIdWorker.get_id, comment="配置ID"
    )
    group_no: Mapped[str] = mapped_column(String(30), nullable=False, default="", comment="集团编号")
    vender_no: Mapped[str] = mapped_column(String(30), nullable=False, default="", comment="商户编号")
    region_no: Mapped[str] = mapped_column(String(30), nullable=False, default="", comment="区域编号")
    org_no: Mapped[str | None] = mapped_column(String(30), nullable=True, comment="机构编号")
    org_name: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="机构名称")
    sap_org_no: Mapped[str | None] = mapped_column(String(30), nullable=True, comment="SAP机构编号")
    platform_no: Mapped[str] = mapped_column(String(10), nullable=False, default="", comment="会员渠道编号")
    parent_org_no: Mapped[str | None] = mapped_column(String(30), nullable=True, comment="上级机构编号")
    perm_node_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="权限树节点ID")
    org_type: Mapped[int] = mapped_column(Integer, nullable=False, default=1, comment="机构类型")
    company_no: Mapped[str] = mapped_column(String(20), nullable=False, default="", comment="所属公司代码")
    city_no: Mapped[str] = mapped_column(String(10), nullable=False, default="", comment="城市编号")
    biz_type_no: Mapped[str] = mapped_column(String(10), nullable=False, default="1", comment="业态编号")
    status: Mapped[int] = mapped_column(Integer, nullable=False, default=1, comment="状态")
    created: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, comment="创建时间")
    modifid: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, comment="修改时间")
    open_date: Mapped[date] = mapped_column(Date, nullable=False, default=date(1900, 1, 1), comment="开业日期")
    language_desc: Mapped[str | None] = mapped_column(String(50), nullable=True, default="zh_HK", comment="默认语言")


class TicketLogPullProjectVendorMap(Base):
    """
    工单日志拉取项目商家映射表，用于自动回填当前系统项目对应的商户编号。
    """

    __tablename__ = "ticket_log_pull_project_vendor_map"
    __table_args__ = (UniqueConstraint("project_id", name="uk_ticket_log_pull_project_vendor_map_project"),)

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, nullable=False, unique=True, default=snowIdWorker.get_id, comment="映射ID"
    )
    project_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="项目ID")
    project_name: Mapped[str] = mapped_column(String(120), nullable=False, default="", comment="项目名称")
    vender_no: Mapped[str] = mapped_column(String(30), nullable=False, default="", comment="商户编号")
    created: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, comment="创建时间")
    modifid: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, comment="修改时间")
