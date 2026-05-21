from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel

from module_admin.annotation.pydantic_annotation import as_query
from module_hrm.entity.vo.common_vo import QueryModel


class TicketLogPullBaseModel(BaseModel):
    """
    工单日志拉取通用模型。
    """

    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True, populate_by_name=True)


class TicketLogPullStorageFtpConfigModel(TicketLogPullBaseModel):
    """
    日志拉取 FTP 存储配置模型。
    """

    host: str | None = Field(default=None, description="FTP主机地址")
    port: int = Field(default=21, description="FTP端口")
    username: str | None = Field(default=None, description="FTP用户名")
    password: str | None = Field(default=None, description="FTP密码")
    base_dir: str | None = Field(default=None, description="FTP保存目录")
    passive: bool = Field(default=True, description="是否启用被动模式")
    timeout_sec: int = Field(default=15, description="FTP连接超时时间，单位秒")
    encoding: str = Field(default="utf-8", description="FTP编码")


class TicketLogPullStorageConfigModel(TicketLogPullBaseModel):
    """
    工单日志拉取存储与轮询配置模型。
    """

    mode: str = Field(default="local", description="默认存储模式，支持 local/ftp")
    local_directory: str | None = Field(default=None, description="本地保存目录")
    ftp: TicketLogPullStorageFtpConfigModel = Field(
        default_factory=TicketLogPullStorageFtpConfigModel, description="FTP配置"
    )
    effective_local_directory: str | None = Field(default=None, description="生效的本地保存目录")
    poll_interval_sec: int = Field(default=20, description="轮询外部接口间隔秒数")
    poll_timeout_sec: int = Field(default=1800, description="日志拉取轮询超时时间，单位秒")
    download_timeout_sec: int = Field(default=300, description="压缩包下载超时时间，单位秒")
    max_content_chars: int = Field(default=500000, description="压缩入库允许的最大文本字符数，超出则失败")


class TicketLogPullCreateModel(TicketLogPullBaseModel):
    """
    提交工单日志拉取申请模型。
    """

    vendor_id: int = Field(description="外部接口 venderId")
    store_id: int = Field(description="外部接口 storeId")
    pos_no: int = Field(description="外部接口 posNo")
    command_data_type: int = Field(default=1, description="数据类型：1日志，2DB")
    modify_time: date | str | None = Field(default=None, description="命令内容里的修改日期")
    path: str | None = Field(default=None, description="命令内容里的指定路径")
    file_max_size: int = Field(default=500, description="单文件最大大小")
    zip_max_size: int = Field(default=500, description="压缩包最大大小")
    log_begin_time: datetime | str | None = Field(default=None, description="日志筛选开始时间")
    log_end_time: datetime | str | None = Field(default=None, description="日志筛选结束时间")
    log_point_time: datetime | str | None = Field(default=None, description="日志时间点，用于按时间点生成前后范围")
    range_before_minutes: int | None = Field(default=None, description="时间点前回溯分钟数")
    range_after_minutes: int | None = Field(default=None, description="时间点后延伸分钟数")
    storage_mode: str | None = Field(default=None, description="本次任务使用的存储模式，支持 local/ftp")

    @model_validator(mode="after")
    def validate_command_content(self):
        """
        校验命令内容与日志时间范围。
        :return: 当前模型
        """
        if not self.modify_time and not str(self.path or "").strip():
            raise ValueError("modifyTime 和 path 至少需要填写一个")
        has_direct_range = bool(self.log_begin_time or self.log_end_time)
        has_point_range = bool(
            self.log_point_time
            or self.range_before_minutes is not None
            or self.range_after_minutes is not None
        )
        if has_direct_range and has_point_range:
            raise ValueError("日志时间范围请二选一：开始/结束时间 或 时间点前后范围")
        if has_direct_range:
            if not self.log_begin_time or not self.log_end_time:
                raise ValueError("开始时间和结束时间需要同时填写")
            return self
        if not self.log_point_time:
            raise ValueError("日志时间范围必填，请填写开始/结束时间或时间点前后范围")

        before_minutes = int(self.range_before_minutes or 0)
        after_minutes = int(self.range_after_minutes or 0)
        if before_minutes < 0 or after_minutes < 0:
            raise ValueError("时间点前后范围不能为负数")
        if self.range_before_minutes is None and self.range_after_minutes is None:
            raise ValueError("请选择时间点前后时长范围")
        if before_minutes == 0 and after_minutes == 0:
            raise ValueError("时间点前后时长至少需要填写一侧大于 0")
        return self


@as_query
class TicketLogPullQueryModel(QueryModel):
    """
    工单日志拉取记录查询模型。
    """

    status: str | None = Field(default=None, description="内部处理状态")


class TicketLogPullContentModel(TicketLogPullBaseModel):
    """
    工单日志拉取内容响应模型。
    """

    record_id: int = Field(description="日志拉取记录ID")
    view_begin_time: datetime | None = Field(default=None, description="本次查看的开始时间")
    view_end_time: datetime | None = Field(default=None, description="本次查看的结束时间")
    view_source: str | None = Field(default=None, description="本次查看来源，stored/realtime/fallback")
    content_summary: str | None = Field(default=None, description="日志内容摘要")
    text: str = Field(default="", description="解压后的日志文本")
    content_char_count: int = Field(default=0, description="文本字符数")
    content_truncated: bool = Field(default=False, description="内容是否被截断")
    matched_entry_count: int = Field(default=0, description="命中的日志条目数")
    archive_entry_count: int = Field(default=0, description="压缩包文件数")
    storage_path: str | None = Field(default=None, description="归档文件地址")
    command_result_url: str | None = Field(default=None, description="外部原始压缩包地址")


@as_query
class TicketLogPullContentQueryModel(TicketLogPullBaseModel):
    """
    工单日志拉取内容查看参数模型。
    """

    view_mode: str = Field(default="stored", description="查看模式：stored入库内容，archive原始文档")
    log_begin_time: datetime | str | None = Field(default=None, description="查看日志开始时间")
    log_end_time: datetime | str | None = Field(default=None, description="查看日志结束时间")
    log_point_time: datetime | str | None = Field(default=None, description="查看日志时间点")
    range_before_minutes: int | None = Field(default=None, description="时间点前回溯分钟数")
    range_after_minutes: int | None = Field(default=None, description="时间点后延伸分钟数")

    @model_validator(mode="after")
    def validate_view_range(self):
        """
        校验查看时的日志范围参数。
        :return: 当前模型
        """
        self.view_mode = str(self.view_mode or "stored").strip().lower()
        if self.view_mode not in {"stored", "archive"}:
            raise ValueError("查看模式仅支持 stored 或 archive")

        has_any_value = any(
            value not in (None, "")
            for value in (
                self.log_begin_time,
                self.log_end_time,
                self.log_point_time,
                self.range_before_minutes,
                self.range_after_minutes,
            )
        )
        if not has_any_value:
            return self
        has_direct_range = bool(self.log_begin_time or self.log_end_time)
        has_point_range = bool(
            self.log_point_time
            or self.range_before_minutes is not None
            or self.range_after_minutes is not None
        )
        if has_direct_range and has_point_range:
            raise ValueError("查看日志时间范围请二选一：开始/结束时间 或 时间点前后范围")
        if has_direct_range:
            if not self.log_begin_time or not self.log_end_time:
                raise ValueError("查看日志时开始时间和结束时间需要同时填写")
            return self
        if not self.log_point_time:
            raise ValueError("查看日志时间范围必填，请填写开始/结束时间或时间点前后范围")

        before_minutes = int(self.range_before_minutes or 0)
        after_minutes = int(self.range_after_minutes or 0)
        if before_minutes < 0 or after_minutes < 0:
            raise ValueError("查看日志时间点前后范围不能为负数")
        if self.range_before_minutes is None and self.range_after_minutes is None:
            raise ValueError("请选择查看日志时间点前后时长范围")
        if before_minutes == 0 and after_minutes == 0:
            raise ValueError("查看日志时间点前后时长至少需要填写一侧大于 0")
        return self


class TicketLogPullSummaryModel(TicketLogPullBaseModel):
    """
    工单最新日志拉取摘要模型。
    """

    id: int | None = None
    status: str | None = Field(default=None, description="内部处理状态")
    status_desc: str | None = Field(default=None, description="内部处理状态描述")
    is_error: bool = Field(default=False, description="是否异常")
    error_message: str | None = Field(default=None, description="异常信息")
    create_time: datetime | None = None


class TicketLogPullListItemModel(TicketLogPullSummaryModel):
    """
    工单日志拉取列表项模型。
    """

    ticket_id: int | None = None
    vendor_id: int | None = None
    store_id: int | None = None
    pos_no: int | None = None
    command_data_type: int | None = None
    command_content: dict[str, Any] | None = None
    log_begin_time: datetime | None = None
    log_end_time: datetime | None = None
    storage_mode: str | None = None
    storage_path: str | None = None
    download_file_name: str | None = None
    download_file_size: int | None = None
    external_command_id: int | None = None
    external_serial_number: str | None = None
    external_command_status: int | None = None
    external_command_status_desc: str | None = None
    command_result_url: str | None = None
    archive_entry_count: int = 0
    matched_entry_count: int = 0
    content_char_count: int = 0
    content_truncated: bool = False
    content_summary: str | None = None
    has_content: bool = Field(default=False, description="是否有可展示的日志内容")
    finished_at: datetime | None = None
    update_time: datetime | None = None
