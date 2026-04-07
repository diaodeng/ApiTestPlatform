from __future__ import annotations

import base64
import binascii
import json
import uuid
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any

from sqlalchemy.orm import Session

from config.env import UploadConfig
from module_admin.dao.config_dao import ConfigDao
from module_admin.entity.vo.config_vo import ConfigModel
from module_hrm.dao.desktop_case_dao import DesktopCaseDao
from module_hrm.entity.do.desktop_case_do import (
    HrmDesktopCase,
    HrmDesktopCaseRun,
    HrmDesktopCaseStep,
    HrmDesktopImageAsset,
    HrmDesktopRecordingEvent,
    HrmDesktopRecordingSession,
)
from module_hrm.entity.vo.agent_vo import AgentModel
from module_hrm.entity.vo.common_vo import CrudResponseModel
from module_hrm.entity.vo.desktop_case_vo import (
    AddDesktopCaseModel,
    DesktopCaseDetailModel,
    DesktopCaseModel,
    DesktopCasePageQueryModel,
    DesktopCaseRunDetailModel,
    DesktopCaseRunRecordModel,
    DesktopCaseRunRecordPageQueryModel,
    DesktopCaseRunRequestModel,
    DesktopComparePipelineModel,
    DesktopImageAssetModel,
    DesktopImageStorageConfigModel,
    DesktopRecordingApplyRequestModel,
    DesktopRecordingDetailModel,
    DesktopRecordingEventModel,
    DesktopRecordingEventUpdateRequestModel,
    DesktopRecordingReplayRequestModel,
    DesktopRecordingSaveCaseRequestModel,
    DesktopRecordingSessionPageQueryModel,
    DesktopRecordingStartRequestModel,
    DesktopRecordingStopRequestModel,
    DesktopReplaceBaselineRequestModel,
    DesktopStepModel,
    DesktopViewportConfigModel,
)
from module_hrm.enums.enums import AgentResponseEnum, CaseRunStatus, TstepTypeEnum
from module_hrm.service.agent_service import AgentService
from module_hrm.utils.desktop_asset_storage import (
    build_storage_path,
    build_storage_metadata,
    default_local_root_dir,
    legacy_default_local_root_dir,
    normalize_storage_config,
    public_asset_metadata,
    read_asset_bytes,
    resolve_local_root_dir,
    store_asset_bytes,
)
from module_qtr.service.agent_service import AgentResponseWebUI, send_message
from utils.log_util import logger
from utils.page_util import PageResponseModel


class DesktopCaseService:
    """桌面测试模块服务层。"""

    IMAGE_DIR_NAME = "desktop-test"
    PUBLIC_ASSET_ROUTE_PREFIX = "/hrm/desktop-case/assets"
    DEFAULT_COMPARE_CONFIG_KEY = "hrm.desktop.compare.default"
    IMAGE_STORAGE_CONFIG_KEY = "hrm.desktop.asset.storage"
    IMAGE_STORAGE_CONFIG_NAME = "桌面截图存储配置"
    VIEWPORT_RUNTIME_KEYS = (
        "viewportMode",
        "viewportX",
        "viewportY",
        "viewportWidth",
        "viewportHeight",
        "logicalWidth",
        "logicalHeight",
        "resizeActiveWindow",
    )

    @staticmethod
    def _dumps(value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            return value
        return json.dumps(value, ensure_ascii=False)

    @staticmethod
    def _loads(value: str | None, default: Any):
        if value in (None, ""):
            return default
        if isinstance(value, (dict, list)):
            return value
        try:
            return json.loads(value)
        except Exception:
            return default

    @classmethod
    def _merge_compare_config(cls, *configs: Any) -> dict[str, Any]:
        merged = DesktopComparePipelineModel().model_dump(by_alias=True)
        for config in configs:
            if isinstance(config, DesktopComparePipelineModel):
                payload = config.model_dump(by_alias=True)
            elif isinstance(config, str):
                payload = cls._loads(config, {})
            elif isinstance(config, dict):
                payload = config
            else:
                payload = {}
            if isinstance(payload, dict):
                merged.update({key: value for key, value in payload.items() if value is not None})
        return merged

    @classmethod
    def _default_compare_config(cls, query_db: Session) -> dict[str, Any]:
        try:
            config = ConfigDao.get_config_detail_by_info(query_db, ConfigModel(config_key=cls.DEFAULT_COMPARE_CONFIG_KEY))
        except Exception:
            config = None
        if not config or not getattr(config, "config_value", None):
            return DesktopComparePipelineModel().model_dump(by_alias=True)
        return cls._merge_compare_config(getattr(config, "config_value", None))

    @classmethod
    def _default_storage_config(cls) -> dict[str, Any]:
        config = normalize_storage_config({})
        config["effectiveLocalDirectory"] = str(default_local_root_dir())
        return config

    @classmethod
    def _load_storage_config(cls, query_db: Session) -> dict[str, Any]:
        try:
            config = ConfigDao.get_config_detail_by_info(query_db, ConfigModel(config_key=cls.IMAGE_STORAGE_CONFIG_KEY))
        except Exception:
            config = None
        if not config or not getattr(config, "config_value", None):
            return cls._default_storage_config()
        return normalize_storage_config(cls._loads(getattr(config, "config_value", None), {}))

    @classmethod
    def get_image_storage_config_services(cls, query_db: Session) -> DesktopImageStorageConfigModel:
        storage_config = cls._load_storage_config(query_db)
        storage_config["effectiveLocalDirectory"] = str(resolve_local_root_dir(storage_config.get("localDirectory")))
        return DesktopImageStorageConfigModel.model_validate(storage_config)

    @classmethod
    def save_image_storage_config_services(
        cls,
        query_db: Session,
        config_model: DesktopImageStorageConfigModel,
        *,
        user_name: str | None,
    ) -> CrudResponseModel:
        payload = normalize_storage_config(config_model.model_dump(by_alias=True))
        payload.pop("effectiveLocalDirectory", None)
        payload.pop("sftpAvailable", None)
        config_value = json.dumps(payload, ensure_ascii=False)
        existing = ConfigDao.get_config_detail_by_info(query_db, ConfigModel(config_key=cls.IMAGE_STORAGE_CONFIG_KEY))
        try:
            if existing:
                ConfigDao.edit_config_dao(
                    query_db,
                    {
                        "config_id": existing.config_id,
                        "config_name": existing.config_name or cls.IMAGE_STORAGE_CONFIG_NAME,
                        "config_key": cls.IMAGE_STORAGE_CONFIG_KEY,
                        "config_value": config_value,
                        "config_type": existing.config_type or "N",
                        "update_by": user_name or existing.update_by or "system",
                        "update_time": datetime.now(),
                        "remark": "桌面测试截图存储配置",
                    },
                )
            else:
                ConfigDao.add_config_dao(
                    query_db,
                    ConfigModel(
                        config_name=cls.IMAGE_STORAGE_CONFIG_NAME,
                        config_key=cls.IMAGE_STORAGE_CONFIG_KEY,
                        config_value=config_value,
                        config_type="N",
                        create_by=user_name or "system",
                        update_by=user_name or "system",
                        remark="桌面测试截图存储配置",
                    ),
                )
            query_db.commit()
            return CrudResponseModel(is_success=True, message="截图存储配置已保存")
        except Exception as exc:
            query_db.rollback()
            raise exc

    @classmethod
    def _extract_viewport_settings(cls, settings: Any) -> dict[str, Any]:
        try:
            model = DesktopViewportConfigModel.model_validate(settings or {})
        except Exception:
            return {}
        payload = model.model_dump(by_alias=True)
        if (
            payload.get("viewportMode") == "screen"
            and payload.get("viewportX") is None
            and payload.get("viewportY") is None
            and payload.get("viewportWidth") is None
            and payload.get("viewportHeight") is None
            and payload.get("logicalWidth") is None
            and payload.get("logicalHeight") is None
            and not bool(payload.get("resizeActiveWindow"))
        ):
            return {}
        return {
            key: value
            for key, value in payload.items()
            if value not in (None, "") and not (key == "resizeActiveWindow" and value is False)
        }

    @classmethod
    def _merge_viewport_settings(
        cls,
        runtime_settings: Any,
        viewport_settings: Any,
        *,
        overwrite: bool = True,
    ) -> dict[str, Any]:
        merged_runtime_settings = dict(runtime_settings or {}) if isinstance(runtime_settings, dict) else {}
        cleaned_runtime_settings = {
            key: value for key, value in merged_runtime_settings.items() if key not in cls.VIEWPORT_RUNTIME_KEYS
        }
        if not overwrite and cls._extract_viewport_settings(merged_runtime_settings):
            cleaned_runtime_settings.update(cls._extract_viewport_settings(merged_runtime_settings))
            return cleaned_runtime_settings
        viewport_payload = cls._extract_viewport_settings(viewport_settings)
        cleaned_runtime_settings.update(viewport_payload)
        return cleaned_runtime_settings

    @classmethod
    def _apply_default_runtime_settings(
        cls,
        query_db: Session,
        runtime_settings: dict[str, Any] | None,
        *,
        compare_config: Any = None,
    ) -> dict[str, Any]:
        merged_runtime_settings = dict(runtime_settings or {})
        merged_runtime_settings["compareConfig"] = cls._merge_compare_config(
            cls._default_compare_config(query_db),
            merged_runtime_settings.get("compareConfig"),
            compare_config,
        )
        return merged_runtime_settings

    @classmethod
    def _build_asset_model(cls, asset: HrmDesktopImageAsset) -> DesktopImageAssetModel:
        metadata = cls._loads(asset.metadata_json, {})
        return DesktopImageAssetModel(
            assetId=asset.asset_id,
            assetType=asset.asset_type,
            sourceType=asset.source_type,
            fileName=asset.file_name,
            filePath=asset.file_path,
            previewUrl=cls._build_public_asset_url(asset.asset_id, asset.file_path),
            resolutionKey=asset.resolution_key,
            width=asset.width,
            height=asset.height,
            fileSize=asset.file_size,
            region=cls._loads(asset.region_json, None),
            metadata=public_asset_metadata(metadata),
        )

    @classmethod
    def _build_public_asset_url(
        cls,
        asset_id: int | str | None,
        file_path: str | None,
    ) -> str | None:
        if asset_id not in (None, "", 0, "0"):
            return f"{cls.PUBLIC_ASSET_ROUTE_PREFIX}/{asset_id}"
        normalized = cls._normalize_public_asset_path(file_path)
        if not normalized:
            return None
        return f"/{normalized}"

    @classmethod
    def _normalize_public_asset_path(cls, file_path: str | None) -> str:
        raw_value = str(file_path or "").strip().replace("\\", "/")
        if not raw_value:
            return ""
        normalized = PurePosixPath(raw_value.lstrip("/"))
        if any(part in ("", ".", "..") for part in normalized.parts):
            return ""
        return normalized.as_posix()

    @classmethod
    def _build_case_model(cls, desktop_case: HrmDesktopCase) -> DesktopCaseModel:
        return DesktopCaseModel(
            id=desktop_case.id,
            desktopCaseId=desktop_case.desktop_case_id,
            caseName=desktop_case.case_name,
            projectId=desktop_case.project_id,
            moduleId=desktop_case.module_id,
            appPath=desktop_case.app_path,
            appArgs=cls._loads(desktop_case.app_args_json, []),
            runtimeSettings=cls._loads(desktop_case.runtime_settings_json, {}),
            notes=desktop_case.notes,
            sort=desktop_case.sort,
            status=desktop_case.status,
            remark=desktop_case.remark,
            manager=desktop_case.manager,
            deptId=desktop_case.dept_id,
            createBy=desktop_case.create_by,
            updateBy=desktop_case.update_by,
            createTime=desktop_case.create_time,
            updateTime=desktop_case.update_time,
        )

    @classmethod
    def _build_step_model(cls, step: HrmDesktopCaseStep) -> DesktopStepModel:
        return DesktopStepModel(
            stepId=step.step_id,
            stepIndex=step.step_index,
            stepName=step.step_name,
            stepLevel=step.step_level,
            actionType=step.action_type,
            enabled=step.enabled,
            timeoutMs=step.timeout_ms,
            continueOnFailure=step.continue_on_failure,
            recordOrigin=step.record_origin,
            params=cls._loads(step.params_json, {}),
            targetImage=cls._loads(step.target_image_json, None),
            baselineImages=cls._loads(step.baseline_images_json, []),
            maskRegions=cls._loads(step.mask_regions_json, []),
            compareConfig=cls._loads(step.compare_config_json, DesktopComparePipelineModel().model_dump(by_alias=True)),
            rawEvent=cls._loads(step.raw_event_json, {}),
        )

    @classmethod
    def _build_detail_model(cls, query_db: Session, desktop_case: HrmDesktopCase) -> DesktopCaseDetailModel:
        base_case = cls._build_case_model(desktop_case)
        steps = DesktopCaseDao.list_steps(query_db, desktop_case.desktop_case_id)
        return DesktopCaseDetailModel(
            **base_case.model_dump(by_alias=True),
            steps=[cls._build_step_model(item) for item in steps],
        )

    @classmethod
    def _clone_step_for_persist(cls, step: DesktopStepModel, step_index: int) -> DesktopStepModel:
        cloned_step = DesktopStepModel.model_validate(step.model_dump(mode="python", by_alias=True))
        cloned_step.step_id = None
        cloned_step.step_index = step_index
        cloned_step.record_origin = cloned_step.record_origin or "recording"
        return cloned_step

    @classmethod
    def _normalize_recording_step(cls, payload: dict[str, Any], step_index: int) -> DesktopStepModel | None:
        if not payload:
            return None
        try:
            step = DesktopStepModel.model_validate(payload)
        except Exception:
            logger.warning(f"桌面录制事件转换步骤失败，step_index={step_index}")
            return None
        if not step.action_type:
            return None
        if not step.step_name:
            step.step_name = f"{step.action_type}-{step_index}"
        step.step_index = step_index
        if not step.record_origin:
            step.record_origin = "recording"
        return step

    @classmethod
    def _build_steps_from_recording_events(cls, events: list[HrmDesktopRecordingEvent]) -> list[DesktopStepModel]:
        steps: list[DesktopStepModel] = []
        for index, event in enumerate(events, start=1):
            step = cls._normalize_recording_step(cls._loads(event.payload_json, {}), index)
            if step is not None:
                steps.append(step)
        return steps

    @classmethod
    def _build_run_record_model(
        cls,
        run_record: HrmDesktopCaseRun,
        *,
        case_name: str | None = None,
    ) -> DesktopCaseRunDetailModel:
        return DesktopCaseRunDetailModel(
            desktopCaseRunId=run_record.desktop_case_run_id,
            desktopCaseId=run_record.desktop_case_id,
            caseName=case_name,
            agentId=run_record.agent_id,
            agentCode=run_record.agent_code,
            triggerType=run_record.trigger_type,
            status=run_record.status,
            startedAt=run_record.started_at,
            endedAt=run_record.ended_at,
            durationMs=run_record.duration_ms,
            result=cls._loads(run_record.result_json, {}),
            errorMessage=run_record.error_message,
            createTime=run_record.create_time,
            updateTime=run_record.update_time,
            createBy=run_record.create_by,
            updateBy=run_record.update_by,
            manager=run_record.manager,
            deptId=run_record.dept_id,
        )

    @classmethod
    def _extract_run_error_message(cls, response_result: dict[str, Any]) -> str | None:
        if not isinstance(response_result, dict):
            return None
        for key in ("error", "errorMessage", "message"):
            value = response_result.get(key)
            if value:
                return str(value)
        step_results = response_result.get("steps")
        if not isinstance(step_results, list):
            return None
        for item in step_results:
            if not isinstance(item, dict):
                continue
            if item.get("status") in ("passed", "success", 1, "ok"):
                continue
            return str(item.get("error") or item.get("message") or item.get("stepName") or "步骤执行失败")
        return None

    @classmethod
    def _extract_desktop_run_response(cls, response) -> tuple[bool, dict[str, Any], str | None]:
        response_payload = response.response
        response_result: dict[str, Any] = {}
        success = True
        message = response.message
        if isinstance(response_payload, AgentResponseWebUI):
            success = bool(response_payload.success)
            if isinstance(response_payload.result, dict):
                response_result = response_payload.result
            elif isinstance(response_payload.data, dict):
                response_result = response_payload.data
            message = response_payload.message or message
        elif isinstance(response_payload, dict):
            success = bool(response_payload.get("success", True))
            if isinstance(response_payload.get("result"), dict):
                response_result = response_payload["result"]
            elif isinstance(response_payload.get("data"), dict):
                response_result = response_payload["data"]
            message = response_payload.get("message") or message
        if not success and not message:
            message = cls._extract_run_error_message(response_result) or "执行失败"
        return success, response_result, message

    @classmethod
    def _upsert_steps(
        cls,
        query_db: Session,
        desktop_case: HrmDesktopCase,
        steps: list[DesktopStepModel],
        *,
        manager: int | None,
        dept_id: int | None,
        create_by: str | None,
        update_by: str | None,
    ) -> None:
        DesktopCaseDao.delete_steps_by_case_id(query_db, desktop_case.desktop_case_id)
        for index, step in enumerate(steps, start=1):
            normalized_step = DesktopStepModel.model_validate(step.model_dump(mode="python", by_alias=True))
            step_orm = HrmDesktopCaseStep(
                desktop_case_id=desktop_case.desktop_case_id,
                step_id=int(normalized_step.step_id) if normalized_step.step_id else None,
                step_index=normalized_step.step_index if normalized_step.step_index else index,
                step_name=normalized_step.step_name or f"步骤{index}",
                step_level=normalized_step.step_level or "MID",
                action_type=normalized_step.action_type,
                enabled=normalized_step.enabled,
                timeout_ms=normalized_step.timeout_ms,
                continue_on_failure=normalized_step.continue_on_failure,
                record_origin=normalized_step.record_origin,
                params_json=cls._dumps(normalized_step.params),
                target_image_json=cls._dumps(
                    normalized_step.target_image.model_dump(by_alias=True) if normalized_step.target_image else None
                ),
                baseline_images_json=cls._dumps([item.model_dump(by_alias=True) for item in normalized_step.baseline_images]),
                mask_regions_json=cls._dumps([item.model_dump(by_alias=True) for item in normalized_step.mask_regions]),
                compare_config_json=cls._dumps(normalized_step.compare_config.model_dump(by_alias=True)),
                raw_event_json=cls._dumps(normalized_step.raw_event),
                manager=manager,
                dept_id=dept_id or -1,
                create_by=create_by or "",
                update_by=update_by or "",
            )
            query_db.add(step_orm)
            query_db.flush()
            step_payload = cls._persist_step_assets(
                query_db,
                normalized_step.model_dump(mode="python", by_alias=True),
                desktop_case_id=desktop_case.desktop_case_id,
                step_id=int(step_orm.step_id) if step_orm.step_id else None,
                recording_id=None,
                desktop_case_run_id=None,
                source_type="case",
            )
            normalized_asset_step = DesktopStepModel.model_validate(step_payload)
            step_orm.target_image_json = cls._dumps(
                normalized_asset_step.target_image.model_dump(by_alias=True) if normalized_asset_step.target_image else None
            )
            step_orm.baseline_images_json = cls._dumps(
                [item.model_dump(by_alias=True) for item in normalized_asset_step.baseline_images]
            )
            step_orm.mask_regions_json = cls._dumps(
                [item.model_dump(by_alias=True) for item in normalized_asset_step.mask_regions]
            )

    @classmethod
    def get_desktop_case_list_services(
        cls,
        query_db: Session,
        query_object: DesktopCasePageQueryModel,
        data_scope_sql=True,
    ) -> PageResponseModel:
        return DesktopCaseDao.get_desktop_case_list(query_db, query_object, data_scope_sql)

    @classmethod
    def desktop_case_detail_services(cls, query_db: Session, desktop_case_id: int) -> DesktopCaseDetailModel | None:
        desktop_case = DesktopCaseDao.get_desktop_case_by_id(query_db, desktop_case_id)
        if desktop_case is None:
            return None
        detail = cls._build_detail_model(query_db, desktop_case)
        detail.steps = cls._hydrate_step_assets_for_response(query_db, detail.steps)
        return detail

    @classmethod
    def add_desktop_case_services(cls, query_db: Session, page_object: AddDesktopCaseModel) -> CrudResponseModel:
        case = DesktopCaseDao.get_desktop_case_by_name(query_db, page_object.case_name or "")
        if case:
            return CrudResponseModel(is_success=False, message="桌面用例名称已存在")
        try:
            desktop_case = HrmDesktopCase(
                desktop_case_id=int(page_object.desktop_case_id) if page_object.desktop_case_id else None,
                case_name=page_object.case_name or "新增桌面用例",
                project_id=page_object.project_id,
                module_id=page_object.module_id,
                app_path=page_object.app_path,
                app_args_json=cls._dumps(page_object.app_args),
                runtime_settings_json=cls._dumps(page_object.runtime_settings),
                notes=page_object.notes,
                sort=page_object.sort,
                status=page_object.status,
                remark=page_object.remark,
                manager=page_object.manager,
                dept_id=page_object.dept_id or -1,
                create_by=page_object.create_by or "",
                update_by=page_object.update_by or "",
            )
            DesktopCaseDao.add_desktop_case(query_db, desktop_case)
            cls._upsert_steps(
                query_db,
                desktop_case,
                page_object.steps,
                manager=page_object.manager,
                dept_id=page_object.dept_id,
                create_by=page_object.create_by,
                update_by=page_object.update_by,
            )
            query_db.commit()
            detail = cls._build_detail_model(query_db, desktop_case)
            return CrudResponseModel(is_success=True, message="新增成功", result=detail.model_dump(by_alias=True))
        except Exception as exc:
            query_db.rollback()
            raise exc

    @classmethod
    def edit_desktop_case_services(cls, query_db: Session, page_object: DesktopCaseDetailModel) -> CrudResponseModel:
        if not page_object.desktop_case_id:
            return CrudResponseModel(is_success=False, message="桌面用例不存在")
        desktop_case = DesktopCaseDao.get_desktop_case_by_id(query_db, int(page_object.desktop_case_id))
        if desktop_case is None:
            return CrudResponseModel(is_success=False, message="桌面用例不存在")
        if page_object.case_name and page_object.case_name != desktop_case.case_name:
            existed = DesktopCaseDao.get_desktop_case_by_name(query_db, page_object.case_name)
            if existed and existed.desktop_case_id != desktop_case.desktop_case_id:
                return CrudResponseModel(is_success=False, message="桌面用例名称已存在")
        try:
            DesktopCaseDao.edit_desktop_case(
                query_db,
                int(page_object.desktop_case_id),
                {
                    "case_name": page_object.case_name or desktop_case.case_name,
                    "project_id": page_object.project_id,
                    "module_id": page_object.module_id,
                    "app_path": page_object.app_path,
                    "app_args_json": cls._dumps(page_object.app_args),
                    "runtime_settings_json": cls._dumps(page_object.runtime_settings),
                    "notes": page_object.notes,
                    "sort": page_object.sort,
                    "status": page_object.status,
                    "remark": page_object.remark,
                    "update_by": page_object.update_by or desktop_case.update_by,
                    "update_time": datetime.now(),
                },
            )
            refreshed_case = DesktopCaseDao.get_desktop_case_by_id(query_db, int(page_object.desktop_case_id))
            cls._upsert_steps(
                query_db,
                refreshed_case,
                page_object.steps,
                manager=page_object.manager or refreshed_case.manager,
                dept_id=page_object.dept_id or refreshed_case.dept_id,
                create_by=page_object.create_by or refreshed_case.create_by,
                update_by=page_object.update_by or refreshed_case.update_by,
            )
            query_db.commit()
            return CrudResponseModel(is_success=True, message="更新成功")
        except Exception as exc:
            query_db.rollback()
            raise exc

    @classmethod
    def delete_desktop_case_services(cls, query_db: Session, desktop_case_ids: str) -> CrudResponseModel:
        if not desktop_case_ids:
            return CrudResponseModel(is_success=False, message="传入桌面用例ID为空")
        try:
            for case_id in desktop_case_ids.split(","):
                case_id_int = int(case_id)
                DesktopCaseDao.delete_steps_by_case_id(query_db, case_id_int)
                DesktopCaseDao.delete_desktop_case(query_db, case_id_int)
            query_db.commit()
            return CrudResponseModel(is_success=True, message="删除成功")
        except Exception as exc:
            query_db.rollback()
            raise exc

    @classmethod
    def _resolve_agent(cls, query_db: Session, agent_id: int | None, agent_code: str | None) -> AgentModel | None:
        try:
            if agent_code:
                return AgentService.get_agent_detail_services(query_db, agent_code)
            if agent_id:
                return AgentService.agent_detail_services(query_db, agent_id)
        except Exception:
            return None
        return None

    @classmethod
    def list_recording_services(
        cls,
        query_db: Session,
        query_object: DesktopRecordingSessionPageQueryModel,
    ) -> PageResponseModel:
        return DesktopCaseDao.list_recording_sessions(query_db, query_object)

    @classmethod
    def recording_detail_services(cls, query_db: Session, recording_id: int) -> DesktopRecordingDetailModel | None:
        session_obj = DesktopCaseDao.get_recording_session(query_db, recording_id)
        if session_obj is None:
            return None
        events = DesktopCaseDao.list_recording_events(query_db, recording_id)
        steps = cls._hydrate_step_assets_for_response(query_db, cls._build_steps_from_recording_events(events))
        return DesktopRecordingDetailModel(
            recordingId=session_obj.recording_id,
            desktopCaseId=session_obj.desktop_case_id,
            agentId=session_obj.agent_id,
            agentCode=session_obj.agent_code,
            sessionName=session_obj.session_name,
            appPath=session_obj.app_path,
            appArgs=cls._loads(session_obj.app_args_json, []),
            options=cls._loads(session_obj.options_json, {}),
            status=session_obj.status,
            startedAt=session_obj.started_at,
            endedAt=session_obj.ended_at,
            lastEventAt=session_obj.last_event_at,
            errorMessage=session_obj.error_message,
            resultSummary=cls._loads(session_obj.result_summary_json, {}),
            events=[
                DesktopRecordingEventModel(
                    eventId=item.event_id,
                    recordingId=item.recording_id,
                    eventIndex=item.event_index,
                    eventType=item.event_type,
                    payload=cls._loads(item.payload_json, {}),
                    createTime=item.create_time,
                    updateTime=item.update_time,
                    createBy=item.create_by,
                    updateBy=item.update_by,
                    manager=item.manager,
                    deptId=item.dept_id,
                )
                for item in events
            ],
            steps=steps,
            createTime=session_obj.create_time,
            updateTime=session_obj.update_time,
            createBy=session_obj.create_by,
            updateBy=session_obj.update_by,
            manager=session_obj.manager,
            deptId=session_obj.dept_id,
        )

    @classmethod
    def update_recording_event_services(
        cls,
        query_db: Session,
        request_model: DesktopRecordingEventUpdateRequestModel,
        *,
        user_name: str | None,
    ) -> CrudResponseModel:
        session_obj = DesktopCaseDao.get_recording_session(query_db, request_model.recording_id)
        if session_obj is None:
            return CrudResponseModel(is_success=False, message="录制会话不存在")

        event_obj = None
        if request_model.event_id:
            event_obj = DesktopCaseDao.get_recording_event(query_db, int(request_model.event_id))
        elif request_model.event_index:
            event_obj = DesktopCaseDao.get_recording_event_by_index(
                query_db,
                request_model.recording_id,
                int(request_model.event_index),
            )
        else:
            return CrudResponseModel(is_success=False, message="缺少 eventId 或 eventIndex")

        if event_obj is None or int(event_obj.recording_id) != int(request_model.recording_id):
            return CrudResponseModel(is_success=False, message="录制步骤不存在")

        try:
            normalized_payload = DesktopStepModel.model_validate(request_model.payload or {}).model_dump(
                mode="python",
                by_alias=True,
            )
            normalized_payload["recordOrigin"] = normalized_payload.get("recordOrigin") or "recording"
        except Exception as exc:
            return CrudResponseModel(is_success=False, message=f"录制步骤数据无效: {exc}")

        sanitized_payload = cls._persist_step_assets(
            query_db,
            normalized_payload,
            desktop_case_id=session_obj.desktop_case_id,
            step_id=None,
            recording_id=int(session_obj.recording_id),
            desktop_case_run_id=None,
            source_type="recording",
        )
        now = datetime.now()
        DesktopCaseDao.update_recording_event(
            query_db,
            int(event_obj.event_id),
            {
                "event_type": sanitized_payload.get("actionType") or sanitized_payload.get("eventType") or event_obj.event_type,
                "payload_json": cls._dumps(sanitized_payload),
                "update_by": user_name or event_obj.update_by,
                "update_time": now,
            },
        )
        DesktopCaseDao.update_recording_session(
            query_db,
            int(session_obj.recording_id),
            {
                "last_event_at": now,
                "update_by": user_name or session_obj.update_by,
                "update_time": now,
            },
        )
        query_db.commit()

        updated_step = cls._normalize_recording_step(sanitized_payload, event_obj.event_index)
        result = {
            "recordingId": request_model.recording_id,
            "eventId": event_obj.event_id,
            "eventIndex": event_obj.event_index,
            "payload": sanitized_payload,
        }
        if updated_step is not None:
            result["step"] = updated_step.model_dump(by_alias=True)
        return CrudResponseModel(is_success=True, message="录制步骤已更新", result=result)

    @classmethod
    async def start_recording_services(
        cls,
        query_db: Session,
        request_model: DesktopRecordingStartRequestModel,
        *,
        manager: int | None,
        dept_id: int | None,
        user_name: str | None,
    ) -> CrudResponseModel:
        agent = cls._resolve_agent(query_db, request_model.agent_id, request_model.agent_code)
        if agent is None or not agent.agent_code:
            return CrudResponseModel(is_success=False, message="未找到可用的Agent")

        session_name = request_model.session_name or f"桌面录制-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        recording_options_payload = request_model.recording_options.model_dump(by_alias=True)
        recording_options_payload["compareConfig"] = cls._merge_compare_config(
            cls._default_compare_config(query_db),
            recording_options_payload.get("compareConfig"),
        )
        recording_session = HrmDesktopRecordingSession(
            session_name=session_name,
            app_path=request_model.app_path,
            app_args_json=cls._dumps(request_model.app_args),
            desktop_case_id=request_model.desktop_case_id,
            agent_id=agent.agent_id,
            agent_code=agent.agent_code,
            options_json=cls._dumps(recording_options_payload),
            status=2,
            started_at=datetime.now(),
            last_event_at=datetime.now(),
            manager=manager,
            dept_id=dept_id or -1,
            create_by=user_name or "",
            update_by=user_name or "",
        )

        try:
            DesktopCaseDao.create_recording_session(query_db, recording_session)
            query_db.commit()
            query_db.refresh(recording_session)
        except Exception as exc:
            query_db.rollback()
            raise exc

        message = {
            "requestType": TstepTypeEnum.desktopui.value,
            "command": "start_recording",
            "recordingId": recording_session.recording_id,
            "sessionName": recording_session.session_name,
            "appPath": recording_session.app_path,
            "appArgs": request_model.app_args,
            "recordingOptions": recording_options_payload,
        }
        result = await send_message(agent.agent_code, message)
        if result.status_code != AgentResponseEnum.SUCCESS.value:
            DesktopCaseDao.update_recording_session(
                query_db,
                recording_session.recording_id,
                {
                    "status": 4,
                    "error_message": result.message,
                    "ended_at": datetime.now(),
                },
            )
            query_db.commit()
            return CrudResponseModel(is_success=False, message=result.message)

        return CrudResponseModel(
            is_success=True,
            message="录制已启动",
            result={"recordingId": recording_session.recording_id},
        )

    @classmethod
    async def stop_recording_services(
        cls,
        query_db: Session,
        request_model: DesktopRecordingStopRequestModel,
    ) -> CrudResponseModel:
        session_obj = DesktopCaseDao.get_recording_session(query_db, request_model.recording_id)
        if session_obj is None:
            return CrudResponseModel(is_success=False, message="录制会话不存在")

        agent = cls._resolve_agent(
            query_db,
            request_model.agent_id or session_obj.agent_id,
            request_model.agent_code or session_obj.agent_code,
        )
        if agent is None or not agent.agent_code:
            return CrudResponseModel(is_success=False, message="未找到可用的Agent")

        stop_message = {
            "requestType": TstepTypeEnum.desktopui.value,
            "command": "stop_recording",
            "recordingId": session_obj.recording_id,
        }
        updated_options: dict[str, Any] | None = None
        if request_model.close_app_on_stop is not None:
            updated_options = cls._loads(session_obj.options_json, {})
            updated_options["closeAppOnStop"] = request_model.close_app_on_stop
            stop_message["closeAppOnStop"] = request_model.close_app_on_stop

        result = await send_message(agent.agent_code, stop_message)
        if result.status_code != AgentResponseEnum.SUCCESS.value:
            return CrudResponseModel(is_success=False, message=result.message)

        if updated_options is not None:
            DesktopCaseDao.update_recording_session(
                query_db,
                session_obj.recording_id,
                {
                    "options_json": cls._dumps(updated_options),
                    "update_time": datetime.now(),
                },
            )
            query_db.commit()
        return CrudResponseModel(is_success=True, message="录制停止指令已发送")

    @classmethod
    def apply_recording_to_case_services(
        cls,
        query_db: Session,
        request_model: DesktopRecordingApplyRequestModel,
        *,
        manager: int | None,
        dept_id: int | None,
        user_name: str | None,
    ) -> CrudResponseModel:
        session_obj = DesktopCaseDao.get_recording_session(query_db, request_model.recording_id)
        if session_obj is None:
            return CrudResponseModel(is_success=False, message="录制会话不存在")

        desktop_case_id = request_model.desktop_case_id or session_obj.desktop_case_id
        if not desktop_case_id:
            return CrudResponseModel(is_success=False, message="缺少目标桌面用例ID")

        desktop_case = DesktopCaseDao.get_desktop_case_by_id(query_db, desktop_case_id)
        if desktop_case is None:
            return CrudResponseModel(is_success=False, message="目标桌面用例不存在")

        events = DesktopCaseDao.list_recording_events(query_db, request_model.recording_id)
        recording_steps = cls._build_steps_from_recording_events(events)
        if not recording_steps:
            return CrudResponseModel(is_success=False, message="录制会话中没有可用步骤")

        detail = cls._build_detail_model(query_db, desktop_case)
        merged_steps: list[DesktopStepModel] = []
        if not request_model.replace_steps:
            for index, step in enumerate(detail.steps, start=1):
                step.step_index = index
                merged_steps.append(step)

        for step in recording_steps:
            merged_steps.append(cls._clone_step_for_persist(step, len(merged_steps) + 1))

        detail.steps = merged_steps
        detail.update_by = user_name
        detail.create_by = detail.create_by or user_name
        detail.manager = manager or detail.manager
        detail.dept_id = dept_id or detail.dept_id
        detail.runtime_settings = cls._merge_viewport_settings(
            detail.runtime_settings,
            cls._loads(session_obj.options_json, {}),
            overwrite=bool(request_model.replace_steps or not cls._extract_viewport_settings(detail.runtime_settings)),
        )
        result = cls.edit_desktop_case_services(query_db, detail)
        if result.is_success:
            DesktopCaseDao.update_recording_session(
                query_db,
                request_model.recording_id,
                {
                    "desktop_case_id": desktop_case_id,
                    "update_by": user_name or session_obj.update_by,
                    "update_time": datetime.now(),
                },
            )
            query_db.commit()
        return result

    @classmethod
    def save_recording_as_case_services(
        cls,
        query_db: Session,
        request_model: DesktopRecordingSaveCaseRequestModel,
        *,
        manager: int | None,
        dept_id: int | None,
        user_name: str | None,
    ) -> CrudResponseModel:
        session_obj = DesktopCaseDao.get_recording_session(query_db, request_model.recording_id)
        if session_obj is None:
            return CrudResponseModel(is_success=False, message="录制会话不存在")

        events = DesktopCaseDao.list_recording_events(query_db, request_model.recording_id)
        recording_steps = cls._build_steps_from_recording_events(events)
        if not recording_steps:
            return CrudResponseModel(is_success=False, message="录制会话中没有可用步骤")

        source_case = None
        if session_obj.desktop_case_id:
            source_case = DesktopCaseDao.get_desktop_case_by_id(query_db, session_obj.desktop_case_id)

        add_case = AddDesktopCaseModel(
            caseName=request_model.case_name,
            projectId=request_model.project_id
            if request_model.project_id is not None
            else getattr(source_case, "project_id", None),
            moduleId=request_model.module_id if request_model.module_id is not None else getattr(source_case, "module_id", None),
            appPath=request_model.app_path if request_model.app_path is not None else (session_obj.app_path or getattr(source_case, "app_path", None)),
            appArgs=request_model.app_args
            if request_model.app_args
            else cls._loads(session_obj.app_args_json, cls._loads(getattr(source_case, "app_args_json", None), [])),
            runtimeSettings=cls._merge_viewport_settings(
                cls._loads(getattr(source_case, "runtime_settings_json", None), {}),
                cls._loads(session_obj.options_json, {}),
                overwrite=True,
            ),
            notes=request_model.notes
            if request_model.notes is not None
            else (getattr(source_case, "notes", None) or f"由录制[{session_obj.session_name}]生成"),
            status=request_model.status,
            remark=request_model.remark,
            steps=[cls._clone_step_for_persist(step, index) for index, step in enumerate(recording_steps, start=1)],
            manager=manager,
            deptId=dept_id,
            createBy=user_name,
            updateBy=user_name,
        )
        result = cls.add_desktop_case_services(query_db, add_case)
        if result.is_success:
            created_case_id = None
            if isinstance(result.result, dict):
                created_case_id = result.result.get("desktopCaseId") or result.result.get("desktop_case_id")
            DesktopCaseDao.update_recording_session(
                query_db,
                session_obj.recording_id,
                {
                    "desktop_case_id": created_case_id,
                    "update_by": user_name or session_obj.update_by,
                    "update_time": datetime.now(),
                },
            )
            query_db.commit()
        return result

    @classmethod
    def _build_relative_asset_path(
        cls,
        *,
        file_name: str,
        desktop_case_id: int | None,
        recording_id: int | None,
        desktop_case_run_id: int | None,
        date_part: str,
    ) -> PurePosixPath:
        if recording_id:
            return PurePosixPath(cls.IMAGE_DIR_NAME) / "recording" / str(recording_id) / date_part / str(file_name)
        if desktop_case_run_id:
            return PurePosixPath(cls.IMAGE_DIR_NAME) / "run" / str(desktop_case_run_id) / date_part / str(file_name)
        if desktop_case_id:
            return PurePosixPath(cls.IMAGE_DIR_NAME) / "case" / str(desktop_case_id) / date_part / str(file_name)
        return PurePosixPath(cls.IMAGE_DIR_NAME) / "common" / date_part / str(file_name)

    @classmethod
    def _decode_base64_image(cls, image_base64: str) -> tuple[bytes, str]:
        header = ""
        encoded = image_base64.strip()
        if encoded.startswith("data:") and "," in encoded:
            header, encoded = encoded.split(",", 1)
        extension = "png"
        if "image/jpeg" in header:
            extension = "jpg"
        elif "image/webp" in header:
            extension = "webp"
        try:
            return base64.b64decode(encoded), extension
        except (ValueError, binascii.Error) as exc:
            raise ValueError("图片 base64 数据无效") from exc

    @classmethod
    def _persist_image_asset(
        cls,
        query_db: Session,
        image_payload: Any,
        *,
        desktop_case_id: int | None,
        step_id: int | None,
        recording_id: int | None,
        desktop_case_run_id: int | None,
        asset_type: str,
        source_type: str,
        force_resolution_key: str | None = None,
    ) -> dict[str, Any] | None:
        if not image_payload:
            return None
        if isinstance(image_payload, DesktopImageAssetModel):
            payload = image_payload.model_dump(mode="python", by_alias=True)
        elif isinstance(image_payload, dict):
            payload = dict(image_payload)
        else:
            return None

        image_base64 = payload.pop("imageBase64", None) or payload.pop("image_base64", None)
        if payload.get("assetId") or payload.get("asset_id"):
            try:
                asset_model = DesktopImageAssetModel.model_validate(payload)
                return asset_model.model_dump(by_alias=True)
            except Exception:
                pass
        if not image_base64:
            try:
                asset_model = DesktopImageAssetModel.model_validate(payload)
                return asset_model.model_dump(by_alias=True)
            except Exception:
                return None

        image_bytes, extension = cls._decode_base64_image(str(image_base64))
        now = datetime.now()
        date_part = now.strftime("%Y%m%d")
        file_name = payload.get("fileName") or payload.get("file_name") or f"{asset_type}-{uuid.uuid4().hex}.{extension}"
        if "." not in str(file_name):
            file_name = f"{file_name}.{extension}"
        relative_path = cls._build_relative_asset_path(
            file_name=str(file_name),
            desktop_case_id=desktop_case_id,
            recording_id=recording_id,
            desktop_case_run_id=desktop_case_run_id,
            date_part=date_part,
        )
        storage_config = cls._load_storage_config(query_db)
        storage_type, storage_path = store_asset_bytes(
            storage_config,
            relative_path=relative_path,
            image_bytes=image_bytes,
        )
        region = payload.get("region")
        metadata = build_storage_metadata(
            payload.get("metadata") or {},
            storage_type=storage_type,
            storage_path=storage_path,
        )
        resolution_key = force_resolution_key or payload.get("resolutionKey") or payload.get("resolution_key")
        width = int(payload.get("width") or metadata.get("width") or 0)
        height = int(payload.get("height") or metadata.get("height") or 0)
        asset = HrmDesktopImageAsset(
            desktop_case_id=desktop_case_id,
            step_id=step_id,
            recording_id=recording_id,
            desktop_case_run_id=desktop_case_run_id,
            resolution_key=resolution_key,
            asset_type=asset_type,
            source_type=source_type,
            file_name=str(file_name),
            file_path=relative_path.as_posix(),
            file_size=len(image_bytes),
            width=width,
            height=height,
            region_json=cls._dumps(region),
            metadata_json=cls._dumps(metadata),
            create_by="system",
            update_by="system",
        )
        DesktopCaseDao.add_image_asset(query_db, asset)
        return cls._build_asset_model(asset).model_dump(by_alias=True)

    @classmethod
    def _legacy_asset_file_path(cls, asset_file_url: str | None) -> Path | None:
        if not asset_file_url:
            return None
        file_url = str(asset_file_url)
        if not file_url.startswith(UploadConfig.UPLOAD_PREFIX):
            normalized = cls._normalize_public_asset_path(file_url)
            if not normalized:
                return None
            current_default_path = resolve_local_root_dir() / Path(normalized)
            if current_default_path.exists():
                return current_default_path
            legacy_path = legacy_default_local_root_dir() / Path(normalized)
            if legacy_path.exists():
                return legacy_path
            return current_default_path
        relative = file_url.replace(UploadConfig.UPLOAD_PREFIX, "", 1).lstrip("/\\")
        return Path(UploadConfig.UPLOAD_PATH) / Path(relative)

    @classmethod
    def read_asset_bytes_services(
        cls,
        query_db: Session,
        asset_id: int,
    ) -> tuple[HrmDesktopImageAsset, bytes] | None:
        asset = DesktopCaseDao.get_image_asset(query_db, asset_id)
        if asset is None:
            return None
        payload = cls._build_asset_model(asset).model_dump(mode="python", by_alias=True)
        asset_bytes = cls._read_asset_bytes(query_db, payload)
        if asset_bytes is None:
            return None
        return asset, asset_bytes

    @classmethod
    def read_asset_bytes_by_path_services(
        cls,
        query_db: Session,
        file_path: str,
    ) -> bytes | None:
        normalized = cls._normalize_public_asset_path(file_path)
        if not normalized:
            return None

        relative_path = PurePosixPath(normalized)
        storage_config = cls._load_storage_config(query_db)
        storage_type, storage_path = build_storage_path(
            storage_config,
            relative_path=relative_path,
        )

        try:
            if storage_type == "local":
                local_root = resolve_local_root_dir(storage_config.get("localDirectory"))
                local_path = Path(storage_path).resolve()
                try:
                    local_path.relative_to(local_root)
                except ValueError:
                    return None
                if not local_path.exists():
                    legacy_path = (legacy_default_local_root_dir() / Path(normalized)).resolve()
                    if legacy_path.exists():
                        return legacy_path.read_bytes()
            return read_asset_bytes(
                storage_config,
                storage_type=storage_type,
                storage_path=storage_path,
            )
        except Exception as exc:
            logger.warning(f"按路径读取桌面图片资产失败: path={normalized}, error={exc}")
            return None

    @classmethod
    def _read_asset_bytes(cls, query_db: Session, asset_payload: Any) -> bytes | None:
        if not asset_payload:
            return None
        if isinstance(asset_payload, DesktopImageAssetModel):
            payload = asset_payload.model_dump(mode="python", by_alias=True)
        elif isinstance(asset_payload, dict):
            payload = dict(asset_payload)
        else:
            return None

        metadata = payload.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}
        storage_type = metadata.get("_storageType")
        storage_path = metadata.get("_storagePath")
        if storage_type and storage_path:
            try:
                return read_asset_bytes(
                    cls._load_storage_config(query_db),
                    storage_type=str(storage_type),
                    storage_path=str(storage_path),
                )
            except Exception as exc:
                logger.warning(f"读取桌面图片资产失败: {exc}")

        file_path = cls._legacy_asset_file_path(payload.get("filePath") or payload.get("file_path"))
        if file_path is None or not file_path.exists():
            return None
        return file_path.read_bytes()

    @classmethod
    def _inject_asset_base64(cls, query_db: Session, asset_payload: Any) -> dict[str, Any] | None:
        if not asset_payload:
            return None
        if isinstance(asset_payload, DesktopImageAssetModel):
            payload = asset_payload.model_dump(mode="python", by_alias=True)
        elif isinstance(asset_payload, dict):
            payload = dict(asset_payload)
        else:
            return None
        asset_bytes = cls._read_asset_bytes(query_db, payload)
        payload["metadata"] = public_asset_metadata(payload.get("metadata"))
        if asset_bytes:
            payload["imageBase64"] = base64.b64encode(asset_bytes).decode("ascii")
        return payload

    @classmethod
    def _hydrate_step_assets_for_response(cls, query_db: Session, steps: list[DesktopStepModel]) -> list[DesktopStepModel]:
        hydrated_steps: list[DesktopStepModel] = []
        for step in steps:
            payload = step.model_dump(mode="python", by_alias=True)
            if payload.get("targetImage"):
                payload["targetImage"] = cls._inject_asset_base64(query_db, payload.get("targetImage"))
            baseline_images = payload.get("baselineImages") or []
            payload["baselineImages"] = [
                item for item in (cls._inject_asset_base64(query_db, asset) for asset in baseline_images) if item
            ]
            hydrated_steps.append(DesktopStepModel.model_validate(payload))
        return hydrated_steps

    @classmethod
    def _hydrate_run_result_assets_for_response(cls, query_db: Session, result_payload: dict[str, Any]) -> dict[str, Any]:
        result = dict(result_payload or {})
        if result.get("finalScreenshot"):
            result["finalScreenshot"] = cls._inject_asset_base64(query_db, result.get("finalScreenshot"))
        hydrated_steps: list[dict[str, Any]] = []
        for step in result.get("steps") or []:
            if not isinstance(step, dict):
                hydrated_steps.append(step)
                continue
            item = dict(step)
            for key in ("currentImage", "diffImage", "matchedTargetImage"):
                if item.get(key):
                    item[key] = cls._inject_asset_base64(query_db, item.get(key))
            hydrated_steps.append(item)
        result["steps"] = hydrated_steps
        return result

    @classmethod
    def _hydrate_case_assets_for_agent(cls, query_db: Session, detail: DesktopCaseDetailModel) -> dict[str, Any]:
        case_data = detail.model_dump(mode="json", by_alias=True)
        for step in case_data.get("steps") or []:
            if not isinstance(step, dict):
                continue
            if step.get("targetImage"):
                step["targetImage"] = cls._inject_asset_base64(query_db, step["targetImage"])
            baseline_images = step.get("baselineImages") or []
            step["baselineImages"] = [
                item for item in (cls._inject_asset_base64(query_db, asset) for asset in baseline_images) if item
            ]
        return case_data

    @classmethod
    def _persist_step_assets(
        cls,
        query_db: Session,
        step_payload: dict[str, Any],
        *,
        desktop_case_id: int | None,
        step_id: int | None,
        recording_id: int | None,
        desktop_case_run_id: int | None,
        source_type: str,
    ) -> dict[str, Any]:
        payload = dict(step_payload)
        raw_target = payload.get("targetImage") or payload.get("target_image")
        if raw_target:
            payload["targetImage"] = cls._persist_image_asset(
                query_db,
                raw_target,
                desktop_case_id=desktop_case_id,
                step_id=step_id,
                recording_id=recording_id,
                desktop_case_run_id=desktop_case_run_id,
                asset_type="target",
                source_type=source_type,
            )
        baseline_images = payload.get("baselineImages") or payload.get("baseline_images") or []
        sanitized_baselines: list[dict[str, Any]] = []
        for image_payload in baseline_images:
            asset_payload = cls._persist_image_asset(
                query_db,
                image_payload,
                desktop_case_id=desktop_case_id,
                step_id=step_id,
                recording_id=recording_id,
                desktop_case_run_id=desktop_case_run_id,
                asset_type="baseline",
                source_type=source_type,
                force_resolution_key=(image_payload or {}).get("resolutionKey") if isinstance(image_payload, dict) else None,
            )
            if asset_payload:
                sanitized_baselines.append(asset_payload)
        payload["baselineImages"] = sanitized_baselines
        return payload

    @classmethod
    def _persist_run_result_assets(
        cls,
        query_db: Session,
        response_result: dict[str, Any],
        *,
        desktop_case_id: int | None,
        desktop_case_run_id: int | None,
    ) -> dict[str, Any]:
        if not isinstance(response_result, dict):
            return {}
        result = dict(response_result)
        steps = result.get("steps") or []
        sanitized_steps: list[dict[str, Any]] = []
        for item in steps:
            if not isinstance(item, dict):
                sanitized_steps.append(item)
                continue
            step_id = item.get("stepId") or item.get("step_id")
            sanitized = dict(item)
            resolution_key = sanitized.get("resolutionKey") or sanitized.get("resolution_key")
            for key, asset_type in (("currentImage", "current"), ("diffImage", "diff"), ("matchedTargetImage", "match")):
                if sanitized.get(key):
                    sanitized[key] = cls._persist_image_asset(
                        query_db,
                        sanitized.get(key),
                        desktop_case_id=desktop_case_id,
                        step_id=int(step_id) if step_id else None,
                        recording_id=None,
                        desktop_case_run_id=desktop_case_run_id,
                        asset_type=asset_type,
                        source_type="run",
                        force_resolution_key=resolution_key,
                    )
            sanitized_steps.append(sanitized)
        result["steps"] = sanitized_steps
        if result.get("finalScreenshot"):
            result["finalScreenshot"] = cls._persist_image_asset(
                query_db,
                result.get("finalScreenshot"),
                desktop_case_id=desktop_case_id,
                step_id=None,
                recording_id=None,
                desktop_case_run_id=desktop_case_run_id,
                asset_type="final",
                source_type="run",
                force_resolution_key=result.get("resolutionKey"),
            )
        return result

    @classmethod
    async def replay_recording_services(
        cls,
        query_db: Session,
        request_model: DesktopRecordingReplayRequestModel,
    ) -> CrudResponseModel:
        session_obj = DesktopCaseDao.get_recording_session(query_db, request_model.recording_id)
        if session_obj is None:
            return CrudResponseModel(is_success=False, message="录制会话不存在")

        recording_detail = cls.recording_detail_services(query_db, request_model.recording_id)
        if recording_detail is None or not recording_detail.steps:
            return CrudResponseModel(is_success=False, message="录制会话中没有可回放步骤")

        agent = cls._resolve_agent(query_db, request_model.agent_id or session_obj.agent_id, request_model.agent_code or session_obj.agent_code)
        if agent is None or not agent.agent_code:
            return CrudResponseModel(is_success=False, message="未找到可用的Agent")

        runtime_options = request_model.model_dump(
            mode="json",
            by_alias=True,
            exclude={"recording_id", "agent_id", "agent_code"},
        )
        if isinstance(recording_detail.options, dict):
            recording_options = recording_detail.options
        elif hasattr(recording_detail.options, "model_dump"):
            recording_options = recording_detail.options.model_dump(by_alias=True)
        else:
            recording_options = {}
        case_data = DesktopCaseDetailModel(
            desktopCaseId=recording_detail.desktop_case_id or 0,
            caseName=recording_detail.session_name or f"桌面录制回放-{recording_detail.recording_id}",
            appPath=request_model.app_path or recording_detail.app_path,
            appArgs=request_model.app_args or recording_detail.app_args,
            runtimeSettings=cls._apply_default_runtime_settings(
                query_db,
                cls._merge_viewport_settings({}, recording_options, overwrite=True),
                compare_config=recording_options.get("compareConfig") or recording_options.get("compare_config"),
            ),
            steps=recording_detail.steps,
        )
        response = await send_message(
            agent.agent_code,
            {
                "requestType": TstepTypeEnum.desktopui.value,
                "command": "run_case",
                "caseData": cls._hydrate_case_assets_for_agent(query_db, case_data),
                "runtimeOptions": runtime_options,
            },
        )
        if response.status_code != AgentResponseEnum.SUCCESS.value:
            return CrudResponseModel(is_success=False, message=response.message)

        success, response_result, failure_message = cls._extract_desktop_run_response(response)
        return CrudResponseModel(
            is_success=success,
            message="回放完成" if success else (failure_message or "回放失败"),
            result={
                "recordingId": recording_detail.recording_id,
                "sessionName": recording_detail.session_name,
                "status": "passed" if success else "failed",
                "result": response_result,
                "errorMessage": None if success else failure_message,
            },
        )

    @classmethod
    def list_run_record_services(
        cls,
        query_db: Session,
        query_object: DesktopCaseRunRecordPageQueryModel,
    ) -> PageResponseModel:
        return DesktopCaseDao.list_run_records(query_db, query_object)

    @classmethod
    def run_record_detail_services(cls, query_db: Session, desktop_case_run_id: int) -> DesktopCaseRunDetailModel | None:
        run_record = DesktopCaseDao.get_run_record(query_db, desktop_case_run_id)
        if run_record is None:
            return None
        desktop_case = DesktopCaseDao.get_desktop_case_by_id(query_db, run_record.desktop_case_id)
        detail = cls._build_run_record_model(run_record, case_name=desktop_case.case_name if desktop_case else None)
        detail.result = cls._hydrate_run_result_assets_for_response(query_db, detail.result)
        return detail

    @classmethod
    async def run_desktop_case_services(
        cls,
        query_db: Session,
        request_model: DesktopCaseRunRequestModel,
        *,
        manager: int | None,
        dept_id: int | None,
        user_name: str | None,
    ) -> CrudResponseModel:
        detail = cls.desktop_case_detail_services(query_db, request_model.desktop_case_id)
        if detail is None:
            return CrudResponseModel(is_success=False, message="桌面用例不存在")

        agent = cls._resolve_agent(query_db, request_model.agent_id, request_model.agent_code)
        if agent is None or not agent.agent_code:
            return CrudResponseModel(is_success=False, message="未找到可用的Agent")

        started_at = datetime.now()
        run_record = HrmDesktopCaseRun(
            desktop_case_id=int(detail.desktop_case_id),
            agent_id=agent.agent_id,
            agent_code=agent.agent_code,
            trigger_type=request_model.trigger_type,
            status=CaseRunStatus.running.value,
            started_at=started_at,
            manager=manager,
            dept_id=dept_id or -1,
            create_by=user_name or "",
            update_by=user_name or "",
        )
        DesktopCaseDao.create_run_record(query_db, run_record)
        query_db.commit()

        if request_model.app_path:
            detail.app_path = request_model.app_path
        if request_model.app_args:
            detail.app_args = request_model.app_args
        detail.runtime_settings = cls._apply_default_runtime_settings(query_db, detail.runtime_settings)

        runtime_options = request_model.model_dump(
            mode="json",
            by_alias=True,
            exclude={"desktop_case_id", "agent_id", "agent_code"},
        )
        response = await send_message(
            agent.agent_code,
            {
                "requestType": TstepTypeEnum.desktopui.value,
                "command": "run_case",
                "caseData": cls._hydrate_case_assets_for_agent(query_db, detail),
                "runtimeOptions": runtime_options,
            },
        )
        ended_at = datetime.now()
        duration_ms = int((ended_at - started_at).total_seconds() * 1000)

        if response.status_code != AgentResponseEnum.SUCCESS.value:
            DesktopCaseDao.update_run_record(
                query_db,
                run_record.desktop_case_run_id,
                {
                    "status": CaseRunStatus.failed.value,
                    "ended_at": ended_at,
                    "duration_ms": duration_ms,
                    "error_message": response.message,
                    "update_by": user_name or run_record.update_by,
                    "update_time": datetime.now(),
                },
            )
            query_db.commit()
            return CrudResponseModel(is_success=False, message=response.message)

        success, response_result, failure_message = cls._extract_desktop_run_response(response)
        response_result = cls._persist_run_result_assets(
            query_db,
            response_result,
            desktop_case_id=int(detail.desktop_case_id) if detail.desktop_case_id else None,
            desktop_case_run_id=run_record.desktop_case_run_id,
        )
        run_status = CaseRunStatus.passed.value if success else CaseRunStatus.failed.value
        DesktopCaseDao.update_run_record(
            query_db,
            run_record.desktop_case_run_id,
            {
                "status": run_status,
                "ended_at": ended_at,
                "duration_ms": duration_ms,
                "result_json": cls._dumps(response_result),
                "error_message": None if success else failure_message,
                "update_by": user_name or run_record.update_by,
                "update_time": datetime.now(),
            },
        )
        query_db.commit()

        return CrudResponseModel(
            is_success=success,
            message="执行完成" if success else (failure_message or "执行失败"),
            result=DesktopCaseRunRecordModel(
                desktopCaseRunId=run_record.desktop_case_run_id,
                desktopCaseId=run_record.desktop_case_id,
                agentId=run_record.agent_id,
                agentCode=run_record.agent_code,
                triggerType=run_record.trigger_type,
                status=run_status,
                startedAt=started_at,
                endedAt=ended_at,
                durationMs=duration_ms,
                result=response_result,
                errorMessage=None if success else failure_message,
            ).model_dump(by_alias=True),
        )

    @classmethod
    def replace_baseline_services(
        cls,
        query_db: Session,
        request_model: DesktopReplaceBaselineRequestModel,
        *,
        user_name: str | None,
    ) -> CrudResponseModel:
        run_record = DesktopCaseDao.get_run_record(query_db, request_model.desktop_case_run_id)
        if run_record is None:
            return CrudResponseModel(is_success=False, message="执行记录不存在")

        detail = cls.desktop_case_detail_services(query_db, run_record.desktop_case_id)
        if detail is None:
            return CrudResponseModel(is_success=False, message="桌面用例不存在")

        source_asset = DesktopCaseDao.get_image_asset(query_db, request_model.asset_id)
        if source_asset is None:
            return CrudResponseModel(is_success=False, message="目标图片不存在")

        target_step = None
        for step in detail.steps:
            if int(step.step_id or 0) == int(request_model.step_id):
                target_step = step
                break
        if target_step is None:
            return CrudResponseModel(is_success=False, message="目标步骤不存在")

        new_asset = HrmDesktopImageAsset(
            desktop_case_id=run_record.desktop_case_id,
            step_id=request_model.step_id,
            recording_id=None,
            desktop_case_run_id=None,
            resolution_key=request_model.resolution_key or source_asset.resolution_key,
            asset_type="baseline",
            source_type="replace",
            file_name=source_asset.file_name,
            file_path=source_asset.file_path,
            file_size=source_asset.file_size,
            width=source_asset.width,
            height=source_asset.height,
            region_json=source_asset.region_json,
            metadata_json=source_asset.metadata_json,
            manager=source_asset.manager,
            dept_id=source_asset.dept_id,
            create_by=user_name or source_asset.create_by,
            update_by=user_name or source_asset.update_by,
        )
        DesktopCaseDao.add_image_asset(query_db, new_asset)
        new_asset_model = cls._build_asset_model(new_asset)

        replaced = False
        for index, asset in enumerate(target_step.baseline_images):
            if (
                asset.resolution_key
                and new_asset_model.resolution_key
                and asset.resolution_key == new_asset_model.resolution_key
            ):
                target_step.baseline_images[index] = new_asset_model
                replaced = True
                break
        if not replaced:
            target_step.baseline_images.append(new_asset_model)

        detail.update_by = user_name or detail.update_by
        result = cls.edit_desktop_case_services(query_db, detail)
        if result.is_success:
            query_db.commit()
            return CrudResponseModel(
                is_success=True,
                message="基准图片已替换",
                result=new_asset_model.model_dump(by_alias=True),
            )
        return result

    @classmethod
    def handle_agent_recording_event(
        cls,
        query_db: Session,
        agent_code: str,
        message_data: dict[str, Any],
    ) -> None:
        recording_id = message_data.get("recording_id") or message_data.get("recordingId")
        if not recording_id:
            return

        session_obj = DesktopCaseDao.get_recording_session(query_db, int(recording_id))
        if session_obj is None:
            logger.warning(f"未找到桌面录制会话，recording_id={recording_id}")
            return

        message_type = message_data.get("type")
        payload = message_data.get("payload") or {}
        now = datetime.now()

        if message_type == "desktop_record_event":
            payload = cls._persist_step_assets(
                query_db,
                payload,
                desktop_case_id=session_obj.desktop_case_id,
                step_id=None,
                recording_id=int(recording_id),
                desktop_case_run_id=None,
                source_type="recording",
            )
            event_index = message_data.get("event_index") or message_data.get("eventIndex")
            if event_index is None:
                event_index = DesktopCaseDao.get_next_recording_event_index(query_db, int(recording_id))
            event_obj = HrmDesktopRecordingEvent(
                recording_id=int(recording_id),
                event_index=int(event_index),
                event_type=payload.get("actionType") or payload.get("eventType") or "event",
                payload_json=cls._dumps(payload),
                manager=session_obj.manager,
                dept_id=session_obj.dept_id,
                create_by=session_obj.create_by,
                update_by=session_obj.update_by,
            )
            DesktopCaseDao.add_recording_event(query_db, event_obj)
            DesktopCaseDao.update_recording_session(
                query_db,
                int(recording_id),
                {
                    "status": 2,
                    "last_event_at": now,
                    "agent_code": agent_code,
                    "update_time": now,
                },
            )
            query_db.commit()
            return

        if message_type == "desktop_record_finished":
            DesktopCaseDao.update_recording_session(
                query_db,
                int(recording_id),
                {
                    "status": 3,
                    "ended_at": now,
                    "last_event_at": now,
                    "result_summary_json": cls._dumps(payload),
                    "error_message": None,
                    "update_time": now,
                },
            )
            query_db.commit()
            return

        if message_type == "desktop_record_error":
            DesktopCaseDao.update_recording_session(
                query_db,
                int(recording_id),
                {
                    "status": 4,
                    "ended_at": now,
                    "last_event_at": now,
                    "error_message": message_data.get("message") or payload.get("message"),
                    "result_summary_json": cls._dumps(payload),
                    "update_time": now,
                },
            )
            query_db.commit()
            return

        if message_type == "desktop_record_status":
            DesktopCaseDao.update_recording_session(
                query_db,
                int(recording_id),
                {
                    "last_event_at": now,
                    "result_summary_json": cls._dumps(payload),
                    "update_time": now,
                },
            )
            query_db.commit()
