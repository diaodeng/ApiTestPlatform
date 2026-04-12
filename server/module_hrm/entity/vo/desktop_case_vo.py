from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from module_admin.annotation.pydantic_annotation import as_form, as_query
from module_hrm.entity.vo.common_vo import CommonDataModel, QueryModel


class DesktopJsonModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True, populate_by_name=True)


class DesktopPointModel(DesktopJsonModel):
    x: int = 0
    y: int = 0


class DesktopRegionModel(DesktopJsonModel):
    name: str | None = None
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0
    exclude: bool = True


class DesktopImageAssetModel(DesktopJsonModel):
    asset_id: int | str | None = None
    asset_type: str = ""
    source_type: str = ""
    file_name: str | None = None
    file_path: str | None = None
    preview_url: str | None = None
    resolution_key: str | None = None
    width: int = 0
    height: int = 0
    file_size: int = 0
    region: DesktopRegionModel | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    image_base64: str | None = None


class DesktopViewportConfigModel(DesktopJsonModel):
    viewport_mode: str = "screen"
    viewport_x: int | None = None
    viewport_y: int | None = None
    viewport_width: int | None = None
    viewport_height: int | None = None
    logical_width: int | None = None
    logical_height: int | None = None
    resize_active_window: bool = False


class DesktopImageStorageFtpConfigModel(DesktopJsonModel):
    host: str | None = None
    port: int = 21
    username: str | None = None
    password: str | None = None
    base_dir: str | None = None
    passive: bool = True
    timeout_sec: int = 15
    encoding: str = "utf-8"


class DesktopImageStorageSftpConfigModel(DesktopJsonModel):
    host: str | None = None
    port: int = 22
    username: str | None = None
    password: str | None = None
    base_dir: str | None = None
    timeout_sec: int = 15


class DesktopImageStorageConfigModel(DesktopJsonModel):
    mode: str = "local"
    local_directory: str | None = None
    ftp: DesktopImageStorageFtpConfigModel = Field(default_factory=DesktopImageStorageFtpConfigModel)
    sftp: DesktopImageStorageSftpConfigModel = Field(default_factory=DesktopImageStorageSftpConfigModel)
    effective_local_directory: str | None = None
    sftp_available: bool = False


class DesktopComparePipelineModel(DesktopJsonModel):
    use_hash: bool = True
    use_ssim: bool = True
    use_ocr: bool = False
    use_local_diff: bool = True
    use_full_diff: bool = True
    hash_threshold: int = 6
    ssim_threshold: float = 0.995
    pixel_diff_threshold: float = 0.01
    template_threshold: float = 0.9
    preprocess_grayscale: bool = True
    preprocess_blur: bool = True
    blur_kernel: int = 3


class DesktopStepModel(DesktopJsonModel):
    step_id: int | str | None = None
    step_index: int = 0
    step_name: str = ""
    step_level: str = "MID"
    action_type: str = ""
    enabled: bool = True
    timeout_ms: int | None = None
    continue_on_failure: bool = False
    record_origin: str = "manual"
    params: dict[str, Any] = Field(default_factory=dict)
    target_image: DesktopImageAssetModel | None = None
    baseline_images: list[DesktopImageAssetModel] = Field(default_factory=list)
    mask_regions: list[DesktopRegionModel] = Field(default_factory=list)
    compare_config: DesktopComparePipelineModel = Field(default_factory=DesktopComparePipelineModel)
    raw_event: dict[str, Any] = Field(default_factory=dict)


class DesktopCaseModel(CommonDataModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        from_attributes=True,
        populate_by_name=True,
    )

    desktop_case_id: int | str | None = None
    case_name: str | None = None
    project_id: int | None = None
    module_id: int | None = None
    app_path: str | None = None
    app_args: list[str] = Field(default_factory=list)
    runtime_settings: dict[str, Any] = Field(default_factory=dict)
    notes: str | None = None
    sort: int = 0
    status: int = 2
    remark: str | None = None


class DesktopCaseDetailModel(DesktopCaseModel):
    steps: list[DesktopStepModel] = Field(default_factory=list)


class DesktopCaseQueryModel(QueryModel):
    desktop_case_id: int | str | None = None
    case_name: str | None = None
    project_id: int | None = None
    module_id: int | None = None


@as_query
@as_form
class DesktopCasePageQueryModel(DesktopCaseQueryModel):
    pass


class AddDesktopCaseModel(DesktopCaseDetailModel):
    pass


class DeleteDesktopCaseModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel)

    desktop_case_ids: str
    update_by: str | None = None
    update_time: datetime | None = None


class DesktopRecordingOptionsModel(DesktopJsonModel):
    close_app_on_stop: bool | None = None
    capture_baseline_after_action: bool = True
    capture_target_image: bool = True
    target_image_size: int = 96
    capture_delay_ms: int = 400
    include_keyboard_text: bool = True
    double_click_interval_ms: int = 320
    drag_threshold_px: int = 12
    default_step_level: str = "MID"
    compare_config: dict[str, Any] = Field(default_factory=dict)
    viewport_mode: str = "screen"
    viewport_x: int | None = None
    viewport_y: int | None = None
    viewport_width: int | None = None
    viewport_height: int | None = None
    logical_width: int | None = None
    logical_height: int | None = None
    resize_active_window: bool = False
    annotation_wait_mode: str = "disabled"


class DesktopRecordingSessionModel(CommonDataModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        from_attributes=True,
        populate_by_name=True,
    )

    recording_id: int | str | None = None
    desktop_case_id: int | None = None
    agent_id: int | None = None
    agent_code: str | None = None
    session_name: str | None = None
    app_path: str | None = None
    app_args: list[str] = Field(default_factory=list)
    options: DesktopRecordingOptionsModel = Field(default_factory=DesktopRecordingOptionsModel)
    status: int = 1
    started_at: datetime | None = None
    ended_at: datetime | None = None
    last_event_at: datetime | None = None
    error_message: str | None = None
    result_summary: dict[str, Any] = Field(default_factory=dict)


class DesktopRecordingEventModel(CommonDataModel):
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


class DesktopRecordingDetailModel(DesktopRecordingSessionModel):
    events: list[DesktopRecordingEventModel] = Field(default_factory=list)
    steps: list[DesktopStepModel] = Field(default_factory=list)


class DesktopRecordingSessionQueryModel(QueryModel):
    recording_id: int | str | None = None
    desktop_case_id: int | None = None
    agent_id: int | None = None
    agent_code: str | None = None
    session_name: str | None = None


@as_query
class DesktopRecordingSessionPageQueryModel(DesktopRecordingSessionQueryModel):
    pass


class DesktopCaseRunRecordModel(CommonDataModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        from_attributes=True,
        populate_by_name=True,
    )

    desktop_case_run_id: int | str | None = None
    desktop_case_id: int | None = None
    agent_id: int | None = None
    agent_code: str | None = None
    trigger_type: str = "manual"
    status: int = 9
    started_at: datetime | None = None
    ended_at: datetime | None = None
    duration_ms: int = 0
    result: dict[str, Any] = Field(default_factory=dict)
    error_message: str | None = None


class DesktopCaseRunDetailModel(DesktopCaseRunRecordModel):
    case_name: str | None = None


class DesktopCaseRunRecordQueryModel(QueryModel):
    desktop_case_run_id: int | str | None = None
    desktop_case_id: int | None = None
    agent_id: int | None = None
    agent_code: str | None = None
    trigger_type: str | None = None


@as_query
class DesktopCaseRunRecordPageQueryModel(DesktopCaseRunRecordQueryModel):
    pass


class DesktopCaseRunRequestModel(DesktopJsonModel):
    desktop_case_id: int
    agent_id: int | None = None
    agent_code: str | None = None
    app_path: str | None = None
    app_args: list[str] = Field(default_factory=list)
    close_app_on_finish: bool | None = None
    run_timeout_sec: int = 120
    runtime_overrides: dict[str, Any] = Field(default_factory=dict)
    continue_on_failure: bool = False
    trigger_type: str = "manual"


class DesktopRecordingStartRequestModel(DesktopJsonModel):
    desktop_case_id: int | None = None
    agent_id: int | None = None
    agent_code: str | None = None
    session_name: str | None = None
    app_path: str | None = None
    app_args: list[str] = Field(default_factory=list)
    recording_options: DesktopRecordingOptionsModel = Field(default_factory=DesktopRecordingOptionsModel)


class DesktopRecordingStopRequestModel(DesktopJsonModel):
    recording_id: int
    agent_id: int | None = None
    agent_code: str | None = None
    close_app_on_stop: bool | None = None


class DesktopRecordingEventUpdateRequestModel(DesktopJsonModel):
    recording_id: int
    event_id: int | str | None = None
    event_index: int | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class DesktopRecordingApplyRequestModel(DesktopJsonModel):
    recording_id: int
    desktop_case_id: int | None = None
    replace_steps: bool = True


class DesktopRecordingSaveCaseRequestModel(DesktopJsonModel):
    recording_id: int
    case_name: str
    project_id: int | None = None
    module_id: int | None = None
    app_path: str | None = None
    app_args: list[str] = Field(default_factory=list)
    notes: str | None = None
    status: int = 2
    remark: str | None = None


class DesktopRecordingReplayRequestModel(DesktopJsonModel):
    recording_id: int
    agent_id: int | None = None
    agent_code: str | None = None
    app_path: str | None = None
    app_args: list[str] = Field(default_factory=list)
    close_app_on_finish: bool | None = None
    runtime_overrides: dict[str, Any] = Field(default_factory=dict)
    continue_on_failure: bool = False


class DesktopReplaceBaselineRequestModel(DesktopJsonModel):
    desktop_case_run_id: int
    step_id: int
    asset_id: int
    resolution_key: str | None = None
