from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from module_admin.annotation.pydantic_annotation import as_form, as_query
from module_hrm.entity.vo.common_vo import CommonDataModel, QueryModel


class WebJsonModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True, populate_by_name=True)


class WebLocatorModel(WebJsonModel):
    locator_snapshot_id: int | str | None = None
    locator_type: str = ""
    locator_value: dict[str, Any] | list[Any] | str | int | float | bool | None = None
    priority: int = 0
    enabled: bool = True


class WebTargetContextModel(WebJsonModel):
    page_url: str | None = None
    frame_url: str | None = None
    frame_chain: list[WebLocatorModel] = Field(default_factory=list)
    shadow_chain: list[WebLocatorModel] = Field(default_factory=list)


class WebTargetSnapshotModel(WebJsonModel):
    target_snapshot_id: int | str | None = None
    fingerprint: str | None = None
    element_text: str | None = None
    stable_score: float = 0
    context: WebTargetContextModel = Field(default_factory=WebTargetContextModel)
    locators: list[WebLocatorModel] = Field(default_factory=list)


class WebAssertionModel(WebJsonModel):
    assert_type: str = ""
    expected: Any = None
    operator: str | None = None
    actual_source: str | None = None
    enabled: bool = True
    wait_ms: int | None = None
    target_snapshot: WebTargetSnapshotModel | None = None


class WebPersistContextScopeModel(WebJsonModel):
    """保留浏览器状态作用域配置。"""

    key: str = ""
    label: str = ""
    host_patterns: list[str] = Field(default_factory=list)
    enabled: bool = True
    remark: str | None = None


class WebStepModel(WebJsonModel):
    step_id: int | str | None = None
    step_index: int = 0
    step_name: str = ""
    action_type: str = ""
    enabled: bool = True
    timeout_ms: int | None = None
    continue_on_failure: bool = False
    record_origin: str = "manual"
    element_id: int | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    assertions: list[WebAssertionModel] = Field(default_factory=list)
    raw_event: dict[str, Any] = Field(default_factory=dict)
    target_snapshot: WebTargetSnapshotModel | None = None


class WebCaseModel(CommonDataModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        from_attributes=True,
        populate_by_name=True,
    )

    web_case_id: int | str | None = None
    case_name: str | None = None
    project_id: int | None = None
    module_id: int | None = None
    start_url: str | None = None
    browser_name: str = "chromium"
    headless: bool = False
    runtime_settings: dict[str, Any] = Field(default_factory=dict)
    notes: str | None = None
    sort: int = 0
    status: int = 2
    remark: str | None = None


class WebCaseDetailModel(WebCaseModel):
    steps: list[WebStepModel] = Field(default_factory=list)


class WebCaseQueryModel(QueryModel):
    web_case_id: int | str | None = None
    case_name: str | None = None
    project_id: int | None = None
    module_id: int | None = None
    browser_name: str | None = None
    manager: int | None = None


@as_query
@as_form
class WebCasePageQueryModel(WebCaseQueryModel):
    pass


class AddWebCaseModel(WebCaseDetailModel):
    pass


class DeleteWebCaseModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel)

    web_case_ids: str
    update_by: str | None = None
    update_time: datetime | None = None


class WebRecordingOptionsModel(WebJsonModel):
    mode: str = "custom"
    capture_navigation: bool = True
    capture_clicks: bool = True
    capture_inputs: bool = True
    capture_assertions: bool = True
    capture_hover: bool = False
    auto_assert_text_on_click: bool = False
    assertion_attach_mode: str = "inside_step"
    include_iframe_context: bool = True
    include_shadow_context: bool = True
    save_html_snapshot: bool = False
    text_assertion_max_length: int = 120
    close_browser_on_stop: bool | None = None
    prefer_locator_order: list[str] = Field(
        default_factory=lambda: ["role", "label", "placeholder", "text", "test_id", "css", "xpath"]
    )


class WebRecordingSessionModel(CommonDataModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        from_attributes=True,
        populate_by_name=True,
    )

    recording_id: int | str | None = None
    web_case_id: int | None = None
    agent_id: int | None = None
    agent_code: str | None = None
    session_name: str | None = None
    start_url: str | None = None
    browser_name: str = "chromium"
    headless: bool = False
    options: WebRecordingOptionsModel = Field(default_factory=WebRecordingOptionsModel)
    status: int = 1
    started_at: datetime | None = None
    ended_at: datetime | None = None
    last_event_at: datetime | None = None
    error_message: str | None = None
    result_summary: dict[str, Any] = Field(default_factory=dict)


class WebRecordingEventModel(CommonDataModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        from_attributes=True,
        populate_by_name=True,
    )

    event_id: int | str | None = None
    recording_id: int | None = None
    event_index: int = 0
    event_type: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)


class WebRecordingDetailModel(WebRecordingSessionModel):
    events: list[WebRecordingEventModel] = Field(default_factory=list)
    steps: list[WebStepModel] = Field(default_factory=list)


class WebRecordingSessionQueryModel(QueryModel):
    recording_id: int | str | None = None
    web_case_id: int | None = None
    agent_id: int | None = None
    agent_code: str | None = None
    session_name: str | None = None


@as_query
class WebRecordingSessionPageQueryModel(WebRecordingSessionQueryModel):
    pass


class WebCaseRunRecordModel(CommonDataModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        from_attributes=True,
        populate_by_name=True,
    )

    web_case_run_id: int | str | None = None
    web_case_id: int | None = None
    agent_id: int | None = None
    agent_code: str | None = None
    trigger_type: str = "manual"
    status: int = 9
    started_at: datetime | None = None
    ended_at: datetime | None = None
    duration_ms: int = 0
    result: dict[str, Any] = Field(default_factory=dict)
    error_message: str | None = None


class WebCaseRunDetailModel(WebCaseRunRecordModel):
    case_name: str | None = None


class WebCaseRunRecordQueryModel(QueryModel):
    web_case_run_id: int | str | None = None
    web_case_id: int | None = None
    agent_id: int | None = None
    agent_code: str | None = None
    trigger_type: str | None = None


@as_query
class WebCaseRunRecordPageQueryModel(WebCaseRunRecordQueryModel):
    pass


class WebCaseRunRequestModel(WebJsonModel):
    web_case_id: int
    agent_id: int | None = None
    agent_code: str | None = None
    browser_name: str | None = None
    headless: bool | None = None
    close_browser_on_finish: bool | None = None
    persist_context_enabled: bool = False
    persist_context_key: str | None = None
    runtime_overrides: dict[str, Any] = Field(default_factory=dict)
    runtime_profile_id: str | None = None
    manual_login_enabled: bool = False
    manual_login_wait_sec: int = 120
    manual_login_require_confirm: bool = False
    save_screenshot_on_failure: bool = True
    continue_on_failure: bool = False
    trigger_type: str = "manual"


class WebRuntimeProfileModel(WebJsonModel):
    profile_id: str | None = None
    profile_name: str = ""
    profile_type: str = "runtime"
    targets: list[str] = Field(default_factory=lambda: ["web"])
    enabled: bool = True
    project_id: int | None = None
    module_id: int | None = None
    sort: int = 0
    runtime_overrides: dict[str, Any] = Field(default_factory=dict)
    variables: dict[str, Any] = Field(default_factory=dict)
    cookie_rules: list[dict[str, Any]] = Field(default_factory=list)
    persist_context_scopes: list[WebPersistContextScopeModel] = Field(default_factory=list)
    remark: str | None = None
    create_by: str | None = None
    update_by: str | None = None
    create_time: datetime | None = None
    update_time: datetime | None = None


class WebRuntimeProfileSaveModel(WebJsonModel):
    profile_id: str | None = None
    profile_name: str = ""
    profile_type: str = "runtime"
    targets: list[str] = Field(default_factory=lambda: ["web"])
    enabled: bool = True
    project_id: int | None = None
    module_id: int | None = None
    sort: int = 0
    runtime_overrides: dict[str, Any] = Field(default_factory=dict)
    variables: dict[str, Any] = Field(default_factory=dict)
    cookie_rules: list[dict[str, Any]] = Field(default_factory=list)
    persist_context_scopes: list[WebPersistContextScopeModel] = Field(default_factory=list)
    remark: str | None = None


class WebRuntimeProfileQueryModel(QueryModel):
    profile_id: str | None = None
    profile_name: str | None = None
    project_id: int | None = None
    module_id: int | None = None
    enabled: bool | None = None
    target: str | None = None


@as_query
class WebRuntimeProfilePageQueryModel(WebRuntimeProfileQueryModel):
    is_page: bool = False


class WebRecordingStartRequestModel(WebJsonModel):
    web_case_id: int | None = None
    agent_id: int | None = None
    agent_code: str | None = None
    session_name: str | None = None
    start_url: str
    browser_name: str = "chromium"
    headless: bool = False
    persist_context_enabled: bool = False
    persist_context_key: str | None = None
    runtime_overrides: dict[str, Any] = Field(default_factory=dict)
    runtime_profile_id: str | None = None
    manual_login_enabled: bool = False
    manual_login_wait_sec: int = 120
    manual_login_require_confirm: bool = False
    recording_options: WebRecordingOptionsModel = Field(default_factory=WebRecordingOptionsModel)


class WebCaseRunContinueRequestModel(WebJsonModel):
    web_case_run_id: int
    agent_id: int | None = None
    agent_code: str | None = None


class WebCaseRunStopRequestModel(WebJsonModel):
    web_case_run_id: int
    agent_id: int | None = None
    agent_code: str | None = None
    reason: str | None = None


class WebCaseRunCancelRequestModel(WebCaseRunStopRequestModel):
    pass


class WebRecordingStopRequestModel(WebJsonModel):
    recording_id: int
    agent_id: int | None = None
    agent_code: str | None = None
    close_browser_on_stop: bool | None = None


class WebRecordingContinueRequestModel(WebJsonModel):
    recording_id: int
    agent_id: int | None = None
    agent_code: str | None = None


class WebRecordingCancelRequestModel(WebJsonModel):
    recording_id: int
    agent_id: int | None = None
    agent_code: str | None = None
    reason: str | None = None


class WebRecordingApplyRequestModel(WebJsonModel):
    recording_id: int
    web_case_id: int | None = None
    replace_steps: bool = True


class WebRecordingSaveCaseRequestModel(WebJsonModel):
    recording_id: int
    case_name: str
    project_id: int | None = None
    module_id: int | None = None
    start_url: str | None = None
    browser_name: str | None = None
    headless: bool | None = None
    notes: str | None = None
    status: int = 2
    remark: str | None = None


class WebRecordingReplayRequestModel(WebJsonModel):
    recording_id: int
    agent_id: int | None = None
    agent_code: str | None = None
    browser_name: str | None = None
    headless: bool | None = None
    close_browser_on_finish: bool | None = None
    runtime_overrides: dict[str, Any] = Field(default_factory=dict)
    save_screenshot_on_failure: bool = True
    continue_on_failure: bool = False
