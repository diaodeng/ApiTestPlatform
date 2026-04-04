from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Float, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import Mapped, mapped_column

from config.database import Base
from module_hrm.entity.do.common_do import BaseModel
from utils.snowflake import snowIdWorker


class HrmWebCase(Base, BaseModel):
    """Web 自动化用例主表。"""

    __tablename__ = "hrm_web_case"
    __table_args__ = (
        Index("idx_web_case_project_module", "project_id", "module_id"),
        Index("idx_web_case_manager_status", "manager", "status"),
    )

    web_case_id: Mapped[int] = mapped_column(
        BigInteger,
        unique=True,
        nullable=False,
        default=snowIdWorker.get_id,
        comment="Web用例ID",
    )
    case_name: Mapped[str] = mapped_column(String(500), nullable=False, comment="用例名称")
    project_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, default=None, comment="项目ID")
    module_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, default=None, comment="模块ID")
    start_url: Mapped[str | None] = mapped_column(String(2048), nullable=True, default=None, comment="起始URL")
    browser_name: Mapped[str] = mapped_column(String(32), nullable=False, default="chromium", comment="浏览器类型")
    headless: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="是否无头模式")
    runtime_settings_json: Mapped[str | None] = mapped_column(
        LONGTEXT,
        nullable=True,
        default=None,
        comment="运行参数JSON",
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True, default=None, comment="说明")
    sort: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="排序")
    status: Mapped[int] = mapped_column(Integer, nullable=False, default=2, comment="状态，1禁用 2正常")
    remark: Mapped[str | None] = mapped_column(Text, nullable=True, default=None, comment="备注")


class HrmWebCaseStep(Base, BaseModel):
    """Web 自动化步骤表。"""

    __tablename__ = "hrm_web_case_step"
    __table_args__ = (
        Index("idx_web_case_step_case_order", "web_case_id", "step_index"),
        Index("idx_web_case_step_case_enabled", "web_case_id", "enabled"),
    )

    step_id: Mapped[int] = mapped_column(
        BigInteger,
        unique=True,
        nullable=False,
        default=snowIdWorker.get_id,
        comment="步骤ID",
    )
    web_case_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="Web用例ID")
    step_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="步骤序号")
    step_name: Mapped[str] = mapped_column(String(500), nullable=False, comment="步骤名称")
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
    element_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, default=None, comment="元素库引用ID")
    params_json: Mapped[str | None] = mapped_column(LONGTEXT, nullable=True, default=None, comment="动作参数JSON")
    assertions_json: Mapped[str | None] = mapped_column(LONGTEXT, nullable=True, default=None, comment="断言JSON")
    raw_event_json: Mapped[str | None] = mapped_column(LONGTEXT, nullable=True, default=None, comment="录制原始事件JSON")


class HrmWebCaseStepTargetSnapshot(Base, BaseModel):
    """步骤目标快照表。"""

    __tablename__ = "hrm_web_case_step_target_snapshot"
    __table_args__ = (
        UniqueConstraint("step_id", name="uq_web_case_step_target_snapshot_step"),
        Index("idx_web_case_target_step", "step_id"),
    )

    target_snapshot_id: Mapped[int] = mapped_column(
        BigInteger,
        unique=True,
        nullable=False,
        default=snowIdWorker.get_id,
        comment="目标快照ID",
    )
    step_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="步骤ID")
    context_json: Mapped[str | None] = mapped_column(LONGTEXT, nullable=True, default=None, comment="上下文JSON")
    fingerprint: Mapped[str | None] = mapped_column(String(128), nullable=True, default=None, comment="元素指纹")
    element_text: Mapped[str | None] = mapped_column(String(1000), nullable=True, default=None, comment="元素文本")
    stable_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="稳定性评分")


class HrmWebCaseLocatorSnapshot(Base, BaseModel):
    """步骤目标定位器快照表。"""

    __tablename__ = "hrm_web_case_locator_snapshot"
    __table_args__ = (
        Index("idx_web_case_locator_target_priority", "target_snapshot_id", "priority"),
    )

    locator_snapshot_id: Mapped[int] = mapped_column(
        BigInteger,
        unique=True,
        nullable=False,
        default=snowIdWorker.get_id,
        comment="定位器快照ID",
    )
    target_snapshot_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="目标快照ID")
    locator_type: Mapped[str] = mapped_column(String(120), nullable=False, comment="定位器类型")
    locator_value_json: Mapped[str | None] = mapped_column(
        LONGTEXT,
        nullable=True,
        default=None,
        comment="定位器内容JSON",
    )
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="优先级")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, comment="是否启用")


class HrmWebElement(Base, BaseModel):
    """Web 元素库主表。"""

    __tablename__ = "hrm_web_element"
    __table_args__ = (
        Index("idx_web_element_project_module", "project_id", "module_id"),
        UniqueConstraint("project_id", "module_id", "fingerprint", name="uq_web_element_fingerprint"),
    )

    element_id: Mapped[int] = mapped_column(
        BigInteger,
        unique=True,
        nullable=False,
        default=snowIdWorker.get_id,
        comment="元素ID",
    )
    project_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, default=None, comment="项目ID")
    module_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, default=None, comment="模块ID")
    element_name: Mapped[str] = mapped_column(String(500), nullable=False, comment="元素名称")
    fingerprint: Mapped[str] = mapped_column(String(128), nullable=False, comment="元素指纹")
    description: Mapped[str | None] = mapped_column(Text, nullable=True, default=None, comment="元素描述")
    status: Mapped[int] = mapped_column(Integer, nullable=False, default=2, comment="状态，1禁用 2正常")


class HrmWebElementLocator(Base, BaseModel):
    """元素库定位器定义表。"""

    __tablename__ = "hrm_web_element_locator"
    __table_args__ = (
        Index("idx_web_element_locator_element_priority", "element_id", "priority"),
    )

    element_locator_id: Mapped[int] = mapped_column(
        BigInteger,
        unique=True,
        nullable=False,
        default=snowIdWorker.get_id,
        comment="元素定位器ID",
    )
    element_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="元素ID")
    locator_type: Mapped[str] = mapped_column(String(120), nullable=False, comment="定位器类型")
    locator_value_json: Mapped[str | None] = mapped_column(
        LONGTEXT,
        nullable=True,
        default=None,
        comment="定位器内容JSON",
    )
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="优先级")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, comment="是否启用")


class HrmWebElementCandidate(Base, BaseModel):
    """元素库候选表，用于基于多次成功执行沉淀公共元素。"""

    __tablename__ = "hrm_web_element_candidate"
    __table_args__ = (
        Index("idx_web_element_candidate_project_module", "project_id", "module_id"),
        UniqueConstraint("project_id", "module_id", "fingerprint", name="uq_web_element_candidate_fingerprint"),
    )

    candidate_id: Mapped[int] = mapped_column(
        BigInteger,
        unique=True,
        nullable=False,
        default=snowIdWorker.get_id,
        comment="元素候选ID",
    )
    project_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, default=None, comment="项目ID")
    module_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, default=None, comment="模块ID")
    web_case_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, default=None, comment="来源用例ID")
    step_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, default=None, comment="来源步骤ID")
    candidate_name: Mapped[str] = mapped_column(String(500), nullable=False, comment="候选名称")
    fingerprint: Mapped[str] = mapped_column(String(128), nullable=False, comment="元素指纹")
    context_json: Mapped[str | None] = mapped_column(LONGTEXT, nullable=True, default=None, comment="上下文JSON")
    locator_summary_json: Mapped[str | None] = mapped_column(
        LONGTEXT,
        nullable=True,
        default=None,
        comment="定位器摘要JSON",
    )
    success_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="成功次数")
    status: Mapped[int] = mapped_column(Integer, nullable=False, default=1, comment="状态，1观察中 2已提升")
    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        default=None,
        comment="最后一次观察时间",
    )


class HrmWebRecordingSession(Base, BaseModel):
    """录制会话表。"""

    __tablename__ = "hrm_web_recording_session"
    __table_args__ = (
        Index("idx_web_recording_case_status", "web_case_id", "status"),
        Index("idx_web_recording_agent_status", "agent_code", "status"),
    )

    recording_id: Mapped[int] = mapped_column(
        BigInteger,
        unique=True,
        nullable=False,
        default=snowIdWorker.get_id,
        comment="录制会话ID",
    )
    web_case_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, default=None, comment="关联Web用例ID")
    agent_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, default=None, comment="Agent ID")
    agent_code: Mapped[str | None] = mapped_column(String(120), nullable=True, default=None, comment="Agent编码")
    session_name: Mapped[str] = mapped_column(String(500), nullable=False, comment="录制会话名称")
    start_url: Mapped[str] = mapped_column(String(2048), nullable=False, comment="录制起始URL")
    browser_name: Mapped[str] = mapped_column(String(32), nullable=False, default="chromium", comment="浏览器类型")
    headless: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="是否无头")
    options_json: Mapped[str | None] = mapped_column(LONGTEXT, nullable=True, default=None, comment="录制配置JSON")
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
        LONGTEXT,
        nullable=True,
        default=None,
        comment="录制摘要JSON",
    )


class HrmWebRecordingEvent(Base, BaseModel):
    """录制事件表。"""

    __tablename__ = "hrm_web_recording_event"
    __table_args__ = (
        Index("idx_web_recording_event_recording_order", "recording_id", "event_index"),
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
    payload_json: Mapped[str | None] = mapped_column(LONGTEXT, nullable=True, default=None, comment="事件载荷JSON")


class HrmWebCaseRun(Base, BaseModel):
    """Web 用例执行记录表。"""

    __tablename__ = "hrm_web_case_run"
    __table_args__ = (
        Index("idx_web_case_run_case_time", "web_case_id", "started_at"),
        Index("idx_web_case_run_agent_time", "agent_code", "started_at"),
    )

    web_case_run_id: Mapped[int] = mapped_column(
        BigInteger,
        unique=True,
        nullable=False,
        default=snowIdWorker.get_id,
        comment="Web用例执行记录ID",
    )
    web_case_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="Web用例ID")
    agent_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, default=None, comment="Agent ID")
    agent_code: Mapped[str | None] = mapped_column(String(120), nullable=True, default=None, comment="Agent编码")
    trigger_type: Mapped[str] = mapped_column(String(64), nullable=False, default="manual", comment="触发类型")
    status: Mapped[int] = mapped_column(Integer, nullable=False, default=9, comment="执行状态，复用CaseRunStatus")
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None, comment="开始时间")
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None, comment="结束时间")
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="执行时长毫秒")
    result_json: Mapped[str | None] = mapped_column(LONGTEXT, nullable=True, default=None, comment="执行结果JSON")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True, default=None, comment="异常信息")
