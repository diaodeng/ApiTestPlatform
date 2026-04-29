from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from config.database import Base
from config.sqlalchemy_types import long_text_type
from module_hrm.entity.do.common_do import BaseModel
from utils.snowflake import snowIdWorker


class HrmDesktopCase(Base, BaseModel):
    """桌面自动化用例主表。"""

    __tablename__ = "hrm_desktop_case"
    __table_args__ = (
        Index("idx_desktop_case_project_module", "project_id", "module_id"),
        Index("idx_desktop_case_manager_status", "manager", "status"),
    )

    desktop_case_id: Mapped[int] = mapped_column(
        BigInteger,
        unique=True,
        nullable=False,
        default=snowIdWorker.get_id,
        comment="桌面用例ID",
    )
    case_name: Mapped[str] = mapped_column(String(500), nullable=False, comment="用例名称")
    project_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, default=None, comment="项目ID")
    module_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, default=None, comment="模块ID")
    app_path: Mapped[str | None] = mapped_column(String(2048), nullable=True, default=None, comment="应用启动路径")
    app_args_json: Mapped[str | None] = mapped_column(
        long_text_type(),
        nullable=True,
        default=None,
        comment="应用启动参数JSON",
    )
    runtime_settings_json: Mapped[str | None] = mapped_column(
        long_text_type(),
        nullable=True,
        default=None,
        comment="运行参数JSON",
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True, default=None, comment="说明")
    sort: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="排序")
    status: Mapped[int] = mapped_column(Integer, nullable=False, default=2, comment="状态，1禁用 2正常")
    remark: Mapped[str | None] = mapped_column(Text, nullable=True, default=None, comment="备注")


class HrmDesktopCaseStep(Base, BaseModel):
    """桌面自动化步骤表。"""

    __tablename__ = "hrm_desktop_case_step"
    __table_args__ = (
        Index("idx_desktop_case_step_case_order", "desktop_case_id", "step_index"),
        Index("idx_desktop_case_step_case_enabled", "desktop_case_id", "enabled"),
    )

    step_id: Mapped[int] = mapped_column(
        BigInteger,
        unique=True,
        nullable=False,
        default=snowIdWorker.get_id,
        comment="步骤ID",
    )
    desktop_case_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="桌面用例ID")
    step_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="步骤序号")
    step_name: Mapped[str] = mapped_column(String(500), nullable=False, comment="步骤名称")
    step_level: Mapped[str] = mapped_column(String(32), nullable=False, default="MID", comment="步骤级别 NAV/MID/RES")
    action_type: Mapped[str] = mapped_column(String(120), nullable=False, comment="动作类型")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, comment="是否启用")
    timeout_ms: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None, comment="步骤超时毫秒")
    continue_on_failure: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="失败是否继续",
    )
    record_origin: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="manual",
        comment="步骤来源，manual/recording",
    )
    params_json: Mapped[str | None] = mapped_column(long_text_type(), nullable=True, default=None, comment="动作参数JSON")
    target_image_json: Mapped[str | None] = mapped_column(
        long_text_type(),
        nullable=True,
        default=None,
        comment="目标图片JSON",
    )
    baseline_images_json: Mapped[str | None] = mapped_column(
        long_text_type(),
        nullable=True,
        default=None,
        comment="基准图片列表JSON",
    )
    mask_regions_json: Mapped[str | None] = mapped_column(
        long_text_type(),
        nullable=True,
        default=None,
        comment="遮罩区域JSON",
    )
    compare_config_json: Mapped[str | None] = mapped_column(
        long_text_type(),
        nullable=True,
        default=None,
        comment="比对配置JSON",
    )
    raw_event_json: Mapped[str | None] = mapped_column(
        long_text_type(),
        nullable=True,
        default=None,
        comment="录制原始事件JSON",
    )


class HrmDesktopImageAsset(Base, BaseModel):
    """桌面测试图片资产表。"""

    __tablename__ = "hrm_desktop_image_asset"
    __table_args__ = (
        Index("idx_desktop_asset_case_step", "desktop_case_id", "step_id"),
        Index("idx_desktop_asset_recording_run", "recording_id", "desktop_case_run_id"),
        Index("idx_desktop_asset_type_resolution", "asset_type", "resolution_key"),
    )

    asset_id: Mapped[int] = mapped_column(
        BigInteger,
        unique=True,
        nullable=False,
        default=snowIdWorker.get_id,
        comment="图片资产ID",
    )
    desktop_case_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, default=None, comment="桌面用例ID")
    step_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, default=None, comment="步骤ID")
    recording_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, default=None, comment="录制会话ID")
    desktop_case_run_id: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        default=None,
        comment="执行记录ID",
    )
    resolution_key: Mapped[str | None] = mapped_column(String(64), nullable=True, default=None, comment="分辨率键")
    asset_type: Mapped[str] = mapped_column(String(64), nullable=False, comment="资产类型")
    source_type: Mapped[str] = mapped_column(String(64), nullable=False, default="manual", comment="来源类型")
    file_name: Mapped[str] = mapped_column(String(255), nullable=False, comment="文件名")
    file_path: Mapped[str] = mapped_column(String(2048), nullable=False, comment="访问路径")
    file_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="文件大小")
    width: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="宽度")
    height: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="高度")
    region_json: Mapped[str | None] = mapped_column(long_text_type(), nullable=True, default=None, comment="截图区域JSON")
    metadata_json: Mapped[str | None] = mapped_column(
        long_text_type(),
        nullable=True,
        default=None,
        comment="附加元数据JSON",
    )


class HrmDesktopRecordingSession(Base, BaseModel):
    """桌面录制会话表。"""

    __tablename__ = "hrm_desktop_recording_session"
    __table_args__ = (
        Index("idx_desktop_recording_case_status", "desktop_case_id", "status"),
        Index("idx_desktop_recording_agent_status", "agent_code", "status"),
    )

    recording_id: Mapped[int] = mapped_column(
        BigInteger,
        unique=True,
        nullable=False,
        default=snowIdWorker.get_id,
        comment="录制会话ID",
    )
    desktop_case_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, default=None, comment="关联桌面用例ID")
    agent_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, default=None, comment="Agent ID")
    agent_code: Mapped[str | None] = mapped_column(String(120), nullable=True, default=None, comment="Agent编码")
    session_name: Mapped[str] = mapped_column(String(500), nullable=False, comment="录制会话名称")
    app_path: Mapped[str | None] = mapped_column(String(2048), nullable=True, default=None, comment="应用启动路径")
    app_args_json: Mapped[str | None] = mapped_column(
        long_text_type(),
        nullable=True,
        default=None,
        comment="应用启动参数JSON",
    )
    options_json: Mapped[str | None] = mapped_column(long_text_type(), nullable=True, default=None, comment="录制配置JSON")
    status: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        comment="录制状态，1草稿 2录制中 3已完成 4失败 5已停止",
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None, comment="开始时间")
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None, comment="结束时间")
    last_event_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None, comment="最近事件时间")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True, default=None, comment="异常信息")
    result_summary_json: Mapped[str | None] = mapped_column(
        long_text_type(),
        nullable=True,
        default=None,
        comment="录制摘要JSON",
    )


class HrmDesktopRecordingEvent(Base, BaseModel):
    """桌面录制事件表。"""

    __tablename__ = "hrm_desktop_recording_event"
    __table_args__ = (
        Index("idx_desktop_recording_event_recording_order", "recording_id", "event_index"),
    )

    event_id: Mapped[int] = mapped_column(
        BigInteger,
        unique=True,
        nullable=False,
        default=snowIdWorker.get_id,
        comment="录制事件ID",
    )
    recording_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="录制会话ID")
    event_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="事件序号")
    event_type: Mapped[str] = mapped_column(String(120), nullable=False, comment="事件类型")
    payload_json: Mapped[str | None] = mapped_column(long_text_type(), nullable=True, default=None, comment="事件载荷JSON")


class HrmDesktopCaseRun(Base, BaseModel):
    """桌面用例执行记录表。"""

    __tablename__ = "hrm_desktop_case_run"
    __table_args__ = (
        Index("idx_desktop_case_run_case_time", "desktop_case_id", "started_at"),
        Index("idx_desktop_case_run_agent_time", "agent_code", "started_at"),
    )

    desktop_case_run_id: Mapped[int] = mapped_column(
        BigInteger,
        unique=True,
        nullable=False,
        default=snowIdWorker.get_id,
        comment="桌面用例执行记录ID",
    )
    desktop_case_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="桌面用例ID")
    agent_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, default=None, comment="Agent ID")
    agent_code: Mapped[str | None] = mapped_column(String(120), nullable=True, default=None, comment="Agent编码")
    trigger_type: Mapped[str] = mapped_column(String(64), nullable=False, default="manual", comment="触发方式")
    status: Mapped[int] = mapped_column(Integer, nullable=False, default=9, comment="执行状态，复用CaseRunStatus")
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None, comment="开始时间")
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None, comment="结束时间")
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="执行时长毫秒")
    result_json: Mapped[str | None] = mapped_column(long_text_type(), nullable=True, default=None, comment="执行结果JSON")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True, default=None, comment="异常信息")
