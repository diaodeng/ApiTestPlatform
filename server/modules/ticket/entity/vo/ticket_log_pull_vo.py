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


class TicketLogPullStoreOptionModel(TicketLogPullBaseModel):
    """
    日志拉取门店选项模型。
    """

    store_id: str = Field(description="门店org_no，作为日志拉取实际提交值")
    store_code: str | None = Field(default=None, description="门店编码，通常与org_no一致")
    sap_org_no: str | None = Field(default=None, description="SAP机构编号")
    store_name: str = Field(description="门店名称")


class TicketLogPullVendorOptionModel(TicketLogPullBaseModel):
    """
    日志拉取商家选项模型。
    """

    vendor_id: int = Field(description="商家ID")
    vendor_code: str | None = Field(default=None, description="商家编码")
    vendor_name: str = Field(description="商家名称")
    stores: list[TicketLogPullStoreOptionModel] = Field(default_factory=list, description="商家下门店列表")


class TicketLogPullVendorStoreOptionsModel(TicketLogPullBaseModel):
    """
    日志拉取商家门店联动选项模型。
    """

    vendors: list[TicketLogPullVendorOptionModel] = Field(default_factory=list, description="商家列表")


class TicketLogPullStoreConfigBaseModel(TicketLogPullBaseModel):
    """
    工单日志拉取门店配置基础模型。
    """

    id: int | None = None
    group_no: str = Field(default="", description="集团编号")
    vender_no: str = Field(default="", description="商户编号")
    region_no: str = Field(default="", description="区域编号")
    org_no: str | None = Field(default=None, description="机构编号")
    org_name: str | None = Field(default=None, description="机构名称")
    sap_org_no: str | None = Field(default=None, description="SAP机构编号")
    platform_no: str = Field(default="", description="会员渠道编号")
    parent_org_no: str | None = Field(default=None, description="上级机构编号")
    perm_node_id: int = Field(default=0, description="权限树节点ID")
    org_type: int = Field(default=1, description="机构类型：1-大区 2-业态 3-区本 4-门店")
    company_no: str = Field(default="", description="所属公司代码")
    city_no: str = Field(default="", description="城市编号")
    biz_type_no: str = Field(default="1", description="业态编号")
    status: int = Field(default=1, description="状态：0-未开 1-启用 2-关闭")
    created: datetime | None = Field(default=None, description="创建时间")
    modifid: datetime | None = Field(default=None, description="修改时间")
    open_date: date | None = Field(default=None, description="开业日期")
    language_desc: str | None = Field(default="zh_HK", description="默认语言")


@as_query
class TicketLogPullStoreConfigQueryModel(QueryModel):
    """
    工单日志拉取门店配置查询模型。
    """

    group_no: str | None = Field(default=None, description="集团编号")
    vender_no: str | None = Field(default=None, description="商户编号")
    org_no: str | None = Field(default=None, description="机构编号")
    sap_org_no: str | None = Field(default=None, description="SAP机构编号")
    keyword: str | None = Field(default=None, description="机构名称或编号关键字")


class TicketLogPullStoreConfigModel(TicketLogPullStoreConfigBaseModel):
    """
    工单日志拉取门店配置返回模型。
    """

    pass


class TicketLogPullStoreImportModel(TicketLogPullBaseModel):
    """
    工单日志拉取门店配置导入模型。
    """

    import_mode: str = Field(default="incremental", description="导入方式：incremental 增量，overwrite 覆盖")


class TicketLogPullProjectVendorMapBaseModel(TicketLogPullBaseModel):
    """
    工单日志拉取项目商家映射基础模型。
    """

    id: int | None = None
    project_id: int = Field(default=0, description="项目ID")
    project_name: str = Field(default="", description="项目名称")
    vender_no: str = Field(default="", description="商户编号")
    created: datetime | None = Field(default=None, description="创建时间")
    modifid: datetime | None = Field(default=None, description="修改时间")


@as_query
class TicketLogPullProjectVendorMapQueryModel(QueryModel):
    """
    工单日志拉取项目商家映射查询模型。
    """

    project_id: int | None = Field(default=None, description="项目ID")
    keyword: str | None = Field(default=None, description="项目名称或商户编号关键字")


class TicketLogPullProjectVendorMapModel(TicketLogPullProjectVendorMapBaseModel):
    """
    工单日志拉取项目商家映射返回模型。
    """

    pass


class TicketLogPullProjectVendorMapUpsertModel(TicketLogPullProjectVendorMapBaseModel):
    """
    工单日志拉取项目商家映射保存模型。
    """

    project_id: int = Field(description="项目ID")
    vender_no: str = Field(description="商户编号")


class TicketLogPullCreateModel(TicketLogPullBaseModel):
    """
    提交工单日志拉取申请模型。
    """

    ticket_id: int | None = Field(default=None, description="关联工单ID，可为空表示独立管理记录")
    vendor_id: int = Field(description="外部接口 venderId")
    store_id: str = Field(description="外部接口 storeId，实际使用门店org_no")
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
    auto_ai_enabled: bool = Field(default=False, description="日志拉取成功后是否自动发起AI分析")
    ai_agent_code: str | None = Field(default=None, description="自动AI分析使用的Agent编码")
    ai_provider_code: str | None = Field(default=None, description="自动AI分析使用的Provider编码")
    notify_config: dict[str, Any] | None = Field(default=None, description="日志拉取后的通知配置")

    @model_validator(mode="before")
    @classmethod
    def normalize_optional_ticket_id(cls, data):
        """
        兼容前端将关联工单ID传为空字符串的情况。
        :param data: 原始请求数据
        :return: 归一化后的请求数据
        """
        if not isinstance(data, dict):
            return data

        normalized = dict(data)
        ticket_id = normalized.get("ticketId")
        if ticket_id in ("", None):
            normalized["ticketId"] = None
        return normalized

    @model_validator(mode="after")
    def validate_command_content(self):
        """
        校验命令内容与日志时间范围。
        :return: 当前模型
        """
        if not self.modify_time and not str(self.path or "").strip():
            raise ValueError("modifyTime 和 path 至少需要填写一个")
        fields_set = getattr(self, "model_fields_set", set()) or set()
        has_direct_range = any(field in fields_set for field in ("log_begin_time", "log_end_time"))
        has_point_range = any(
            field in fields_set
            for field in ("log_point_time", "range_before_minutes", "range_after_minutes")
        )
        if has_direct_range and has_point_range:
            raise ValueError("日志时间范围请二选一：开始/结束时间 或 时间点前后范围")
        if has_direct_range:
            if not self.log_begin_time or not self.log_end_time:
                raise ValueError("开始时间和结束时间需要同时填写")
        elif has_point_range:
            if not self.log_point_time:
                raise ValueError("时间点前后范围模式下时间点必填")
            before_minutes = int(self.range_before_minutes or 0)
            after_minutes = int(self.range_after_minutes or 0)
            if before_minutes < 0 or after_minutes < 0:
                raise ValueError("时间点前后范围不能为负数")
            if self.range_before_minutes is None and self.range_after_minutes is None:
                raise ValueError("请选择时间点前后时长范围")
            if before_minutes == 0 and after_minutes == 0:
                raise ValueError("时间点前后时长至少需要填写一侧大于 0")
        self.auto_ai_enabled = bool(self.auto_ai_enabled)
        self.ai_agent_code = str(self.ai_agent_code or "").strip() or None
        self.ai_provider_code = str(self.ai_provider_code or "").strip() or None
        if self.auto_ai_enabled and not (self.ai_provider_code or self.ai_agent_code):
            raise ValueError("日志拉取后自动AI分析时必须选择Provider或Agent")
        if self.auto_ai_enabled and not self.ticket_id:
            raise ValueError("未关联工单时不能启用自动AI分析")
        self.store_id = str(self.store_id or "").strip()
        if not self.store_id:
            raise ValueError("storeId 不能为空")
        return self


@as_query
class TicketLogPullQueryModel(QueryModel):
    """
    工单日志拉取记录查询模型。
    """

    ticket_id: int | None = Field(default=None, description="关联工单ID")
    ticket_no: str | None = Field(default=None, description="工单编号")
    keyword: str | None = Field(default=None, description="关键字")
    status: str | None = Field(default=None, description="内部处理状态")
    vendor_id: int | None = Field(default=None, description="商家vendorId")
    store_id: str | None = Field(default=None, description="门店org_no")
    pos_no: int | None = Field(default=None, description="POS编号")
    modify_time: date | str | None = Field(default=None, description="页面配置的拉取日期")


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
    vendor_id: int | None = Field(default=None, description="商家ID")
    store_id: str | None = Field(default=None, description="门店ID")
    pos_no: int | None = Field(default=None, description="POS编号")
    modify_time: date | str | None = Field(default=None, description="日志拉取日期")
    create_time: datetime | None = None


class TicketLogPullListItemModel(TicketLogPullSummaryModel):
    """
    工单日志拉取列表项模型。
    """

    ticket_id: int | None = None
    ticket_no: str | None = Field(default=None, description="工单编号")
    ticket_title: str | None = Field(default=None, description="工单标题")
    project_name: str | None = Field(default=None, description="项目名称")
    module_name: str | None = Field(default=None, description="模块名称")
    vendor_id: int | None = None
    store_id: str | None = None
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
