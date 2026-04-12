from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from module_admin.entity.do.config_do import SysConfig
from module_hrm.dao.web_case_dao import WebCaseDao
from module_hrm.entity.do.web_case_do import (
    HrmWebCase,
    HrmWebCaseLocatorSnapshot,
    HrmWebCaseRun,
    HrmWebCaseStep,
    HrmWebCaseStepTargetSnapshot,
    HrmWebElement,
    HrmWebElementCandidate,
    HrmWebElementLocator,
    HrmWebRecordingEvent,
    HrmWebRecordingSession,
)
from module_hrm.entity.vo.agent_vo import AgentModel
from module_hrm.entity.vo.common_vo import CrudResponseModel
from module_hrm.entity.vo.web_case_vo import (
    AddWebCaseModel,
    WebAssertionModel,
    WebCaseDetailModel,
    WebCaseModel,
    WebCasePageQueryModel,
    WebCaseRunDetailModel,
    WebCaseRunCancelRequestModel,
    WebCaseRunRecordModel,
    WebCaseRunRecordPageQueryModel,
    WebCaseRunContinueRequestModel,
    WebCaseRunStopRequestModel,
    WebCaseRunRequestModel,
    WebLocatorModel,
    WebRuntimeProfileModel,
    WebRuntimeProfilePageQueryModel,
    WebRuntimeProfileSaveModel,
    WebRecordingApplyRequestModel,
    WebRecordingCancelRequestModel,
    WebRecordingContinueRequestModel,
    WebRecordingDetailModel,
    WebRecordingEventModel,
    WebRecordingReplayRequestModel,
    WebRecordingSaveCaseRequestModel,
    WebRecordingSessionPageQueryModel,
    WebRecordingStartRequestModel,
    WebRecordingStopRequestModel,
    WebStepModel,
    WebTargetSnapshotModel,
)
from module_hrm.enums.enums import AgentResponseEnum, CaseRunStatus, TstepTypeEnum
from module_hrm.service.agent_service import AgentService
from module_qtr.service.agent_service import AgentResponseWebUI, send_message
from utils.log_util import logger
from utils.page_util import PageResponseModel


class WebCaseService:
    """Web 测试模块服务层。"""

    ELEMENT_PROMOTION_THRESHOLD = 3
    RUNTIME_PROFILE_CONFIG_KEY_PREFIX = "hrm.web.runtime.profile."
    RUNTIME_VARIABLE_KEYS = (
        "variables",
        "runtimeVariables",
        "runtime_variables",
        "cookieVariables",
        "cookie_variables",
    )
    RUNTIME_COOKIE_RULE_KEYS = (
        "cookieRules",
        "cookie_rules",
        "cookieScopes",
        "cookie_scopes",
        "cookieProfiles",
        "cookie_profiles",
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
    def _runtime_profile_config_key(cls, profile_id: str) -> str:
        return f"{cls.RUNTIME_PROFILE_CONFIG_KEY_PREFIX}{profile_id}"

    @classmethod
    def _runtime_profile_id_from_key(cls, config_key: str | None) -> str:
        key = str(config_key or "")
        if key.startswith(cls.RUNTIME_PROFILE_CONFIG_KEY_PREFIX):
            return key[len(cls.RUNTIME_PROFILE_CONFIG_KEY_PREFIX):]
        return key

    @staticmethod
    def _to_optional_int(value: Any) -> int | None:
        if value in (None, ""):
            return None
        try:
            return int(value)
        except Exception:
            return None

    @staticmethod
    def _to_bool(value: Any, *, default: bool = True) -> bool:
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        normalized = str(value).strip().lower()
        if normalized in {"1", "true", "yes", "on", "enabled"}:
            return True
        if normalized in {"0", "false", "no", "off", "disabled"}:
            return False
        return default

    @staticmethod
    def _normalize_manual_login_wait_sec(value: Any, *, default: int = 120) -> int:
        """标准化手动登录等待秒数，避免无效值导致执行链路异常。"""
        try:
            wait_sec = int(value)
        except Exception:
            wait_sec = int(default)
        return max(0, min(wait_sec, 3600))

    @staticmethod
    def _parse_csv_int_ids(raw_ids: str) -> list[int]:
        """将逗号分隔ID字符串转换为去重后的整型列表。"""
        if not raw_ids:
            return []
        values: list[int] = []
        for item in str(raw_ids).split(","):
            text = str(item or "").strip()
            if not text:
                continue
            try:
                values.append(int(text))
            except Exception:
                continue
        return sorted(set(values))

    @classmethod
    def _merge_run_result_payload(
        cls,
        run_record: HrmWebCaseRun,
        extra_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """合并执行记录结果载荷，用于停止/取消时保留上下文信息。"""
        merged_result = cls._loads(run_record.result_json, {})
        if not isinstance(merged_result, dict):
            merged_result = {}
        if isinstance(extra_payload, dict):
            merged_result.update(extra_payload)
        return merged_result

    @classmethod
    def _is_run_waiting_manual_confirm(cls, run_record: HrmWebCaseRun) -> bool:
        """判断执行记录是否处于“等待手工登录确认继续”状态。"""
        result_payload = cls._loads(run_record.result_json, {})
        if not isinstance(result_payload, dict):
            return False
        if result_payload.get("awaitingManualConfirm") is True:
            return True
        manual_gate = result_payload.get("manualLoginGate")
        if not isinstance(manual_gate, dict):
            runtime_debug = result_payload.get("runtimeDebug")
            if isinstance(runtime_debug, dict):
                manual_gate = runtime_debug.get("manualLoginGate")
        if isinstance(manual_gate, dict) and manual_gate.get("waitingConfirm") is True:
            return True
        status_text = str(result_payload.get("manualLoginStatus") or "").strip().lower()
        return status_text == "waiting_manual_login"

    @classmethod
    def _normalize_targets(cls, raw_targets: Any) -> list[str]:
        values: list[str] = []
        if isinstance(raw_targets, list):
            values = [str(item or "").strip().lower() for item in raw_targets]
        elif isinstance(raw_targets, str):
            values = [item.strip().lower() for item in raw_targets.split(",")]
        elif raw_targets not in (None, ""):
            values = [str(raw_targets).strip().lower()]
        normalized = [item for item in values if item]
        if not normalized:
            return ["web"]
        seen: set[str] = set()
        result: list[str] = []
        for item in normalized:
            if item in seen:
                continue
            seen.add(item)
            result.append(item)
        return result

    @classmethod
    def _collect_runtime_variables(cls, runtime_overrides: dict[str, Any] | None) -> dict[str, Any]:
        source = runtime_overrides or {}
        if not isinstance(source, dict):
            return {}
        result: dict[str, Any] = {}
        for key in cls.RUNTIME_VARIABLE_KEYS:
            value = source.get(key)
            if isinstance(value, dict):
                result.update(value)
        return result

    @classmethod
    def _collect_cookie_rules(cls, runtime_overrides: dict[str, Any] | None) -> list[dict[str, Any]]:
        source = runtime_overrides or {}
        if not isinstance(source, dict):
            return []
        result: list[dict[str, Any]] = []
        for key in cls.RUNTIME_COOKIE_RULE_KEYS:
            value = source.get(key)
            if isinstance(value, list):
                result.extend([item for item in value if isinstance(item, dict)])
        return result

    @classmethod
    def _merge_runtime_overrides(
        cls,
        base_runtime_overrides: dict[str, Any] | None,
        override_runtime_overrides: dict[str, Any] | None,
    ) -> dict[str, Any]:
        base = base_runtime_overrides if isinstance(base_runtime_overrides, dict) else {}
        override = override_runtime_overrides if isinstance(override_runtime_overrides, dict) else {}
        merged: dict[str, Any] = {**base}
        for key, value in override.items():
            if value is not None:
                merged[key] = value

        merged_variables = cls._collect_runtime_variables(base)
        merged_variables.update(cls._collect_runtime_variables(override))
        if merged_variables:
            merged["variables"] = merged_variables
        for key in cls.RUNTIME_VARIABLE_KEYS:
            if key != "variables":
                merged.pop(key, None)

        merged_rules = cls._collect_cookie_rules(base) + cls._collect_cookie_rules(override)
        if merged_rules:
            merged["cookieRules"] = merged_rules
        for key in cls.RUNTIME_COOKIE_RULE_KEYS:
            if key != "cookieRules":
                merged.pop(key, None)
        return merged

    @classmethod
    def _normalize_runtime_profile_payload(cls, payload: dict[str, Any] | None) -> dict[str, Any]:
        source = payload if isinstance(payload, dict) else {}
        runtime_overrides = cls._loads(
            source.get("runtimeOverrides") if source.get("runtimeOverrides") is not None else source.get("runtime_overrides"),
            {},
        )
        if not isinstance(runtime_overrides, dict):
            runtime_overrides = {}
        variables = cls._loads(source.get("variables"), {})
        if not isinstance(variables, dict):
            variables = {}
        cookie_rules = cls._loads(source.get("cookieRules") if source.get("cookieRules") is not None else source.get("cookie_rules"), [])
        if not isinstance(cookie_rules, list):
            cookie_rules = []

        profile_name = str(source.get("profileName") or source.get("profile_name") or "").strip()
        profile_type = str(source.get("profileType") or source.get("profile_type") or "runtime").strip().lower() or "runtime"
        profile_id = str(source.get("profileId") or source.get("profile_id") or "").strip()

        try:
            sort = int(source.get("sort") or 0)
        except Exception:
            sort = 0

        project_id = source.get("projectId")
        if project_id is None:
            project_id = source.get("project_id")
        module_id = source.get("moduleId")
        if module_id is None:
            module_id = source.get("module_id")

        return {
            "profileId": profile_id or None,
            "profileName": profile_name,
            "profileType": profile_type,
            "targets": cls._normalize_targets(source.get("targets")),
            "enabled": cls._to_bool(source.get("enabled"), default=True),
            "projectId": cls._to_optional_int(project_id),
            "moduleId": cls._to_optional_int(module_id),
            "sort": max(sort, 0),
            "runtimeOverrides": runtime_overrides,
            "variables": variables,
            "cookieRules": [item for item in cookie_rules if isinstance(item, dict)],
            "remark": source.get("remark"),
        }

    @classmethod
    def _build_runtime_profile_model_from_config(cls, config: SysConfig) -> WebRuntimeProfileModel | None:
        payload = cls._loads(getattr(config, "config_value", None), {})
        if not isinstance(payload, dict):
            payload = {}
        if not payload.get("profileId") and not payload.get("profile_id"):
            payload["profileId"] = cls._runtime_profile_id_from_key(getattr(config, "config_key", ""))
        if not payload.get("profileName") and not payload.get("profile_name"):
            payload["profileName"] = getattr(config, "config_name", "") or ""
        if payload.get("remark") in (None, ""):
            payload["remark"] = getattr(config, "remark", None)
        normalized = cls._normalize_runtime_profile_payload(payload)
        if not normalized.get("profileId"):
            return None
        return WebRuntimeProfileModel(
            **normalized,
            createBy=getattr(config, "create_by", None),
            updateBy=getattr(config, "update_by", None),
            createTime=getattr(config, "create_time", None),
            updateTime=getattr(config, "update_time", None),
        )

    @classmethod
    def _compose_runtime_overrides_from_profile(cls, profile_model: WebRuntimeProfileModel) -> dict[str, Any]:
        runtime_overrides = (
            dict(profile_model.runtime_overrides)
            if isinstance(profile_model.runtime_overrides, dict)
            else {}
        )
        if profile_model.variables:
            existing_variables = cls._collect_runtime_variables(runtime_overrides)
            runtime_overrides["variables"] = {**existing_variables, **profile_model.variables}
        if profile_model.cookie_rules:
            existing_rules = cls._collect_cookie_rules(runtime_overrides)
            runtime_overrides["cookieRules"] = [*existing_rules, *profile_model.cookie_rules]
        for key in cls.RUNTIME_VARIABLE_KEYS:
            if key != "variables":
                runtime_overrides.pop(key, None)
        for key in cls.RUNTIME_COOKIE_RULE_KEYS:
            if key != "cookieRules":
                runtime_overrides.pop(key, None)
        return runtime_overrides

    @classmethod
    def _resolve_runtime_profile_runtime_overrides(
        cls,
        query_db: Session,
        profile_id: str | None,
    ) -> dict[str, Any]:
        profile_id_value = str(profile_id or "").strip()
        if not profile_id_value:
            return {}

        config_key = cls._runtime_profile_config_key(profile_id_value)
        config_row = query_db.query(SysConfig).filter(SysConfig.config_key == config_key).first()
        if config_row is None:
            raise ValueError("所选Cookie配置不存在，请刷新后重试")

        profile_model = cls._build_runtime_profile_model_from_config(config_row)
        if profile_model is None:
            raise ValueError("所选Cookie配置无效，请检查配置内容")
        if not profile_model.enabled:
            raise ValueError("所选Cookie配置已停用")

        targets = set(cls._normalize_targets(profile_model.targets))
        if not {"web", "all", "*"}.intersection(targets):
            raise ValueError("所选Cookie配置不支持Web链路")
        return cls._compose_runtime_overrides_from_profile(profile_model)

    @classmethod
    def _build_case_model(cls, web_case: HrmWebCase) -> WebCaseModel:
        return WebCaseModel(
            id=web_case.id,
            webCaseId=web_case.web_case_id,
            caseName=web_case.case_name,
            projectId=web_case.project_id,
            moduleId=web_case.module_id,
            startUrl=web_case.start_url,
            browserName=web_case.browser_name,
            headless=web_case.headless,
            runtimeSettings=cls._loads(web_case.runtime_settings_json, {}),
            notes=web_case.notes,
            sort=web_case.sort,
            status=web_case.status,
            remark=web_case.remark,
            manager=web_case.manager,
            deptId=web_case.dept_id,
            createBy=web_case.create_by,
            updateBy=web_case.update_by,
            createTime=web_case.create_time,
            updateTime=web_case.update_time,
        )

    @classmethod
    def _build_target_model(
        cls,
        snapshot: HrmWebCaseStepTargetSnapshot | None,
        locator_map: dict[int, list[HrmWebCaseLocatorSnapshot]],
    ) -> WebTargetSnapshotModel | None:
        if snapshot is None:
            return None
        locators = [
            WebLocatorModel(
                locatorSnapshotId=item.locator_snapshot_id,
                locatorType=item.locator_type,
                locatorValue=cls._loads(item.locator_value_json, {}),
                priority=item.priority,
                enabled=item.enabled,
            )
            for item in locator_map.get(snapshot.target_snapshot_id, [])
        ]
        return WebTargetSnapshotModel(
            targetSnapshotId=snapshot.target_snapshot_id,
            fingerprint=snapshot.fingerprint,
            elementText=snapshot.element_text,
            stableScore=snapshot.stable_score,
            context=cls._loads(snapshot.context_json, {}),
            locators=locators,
        )

    @classmethod
    def _build_step_model(
        cls,
        step: HrmWebCaseStep,
        target_map: dict[int, HrmWebCaseStepTargetSnapshot],
        locator_map: dict[int, list[HrmWebCaseLocatorSnapshot]],
    ) -> WebStepModel:
        return WebStepModel(
            stepId=step.step_id,
            stepIndex=step.step_index,
            stepName=step.step_name,
            actionType=step.action_type,
            enabled=step.enabled,
            timeoutMs=step.timeout_ms,
            continueOnFailure=step.continue_on_failure,
            recordOrigin=step.record_origin,
            elementId=step.element_id,
            params=cls._loads(step.params_json, {}),
            assertions=cls._loads(step.assertions_json, []),
            rawEvent=cls._loads(step.raw_event_json, {}),
            targetSnapshot=cls._build_target_model(target_map.get(step.step_id), locator_map),
        )

    @classmethod
    def _build_detail_model(cls, query_db: Session, web_case: HrmWebCase) -> WebCaseDetailModel:
        base_case = cls._build_case_model(web_case)
        steps = WebCaseDao.list_steps(query_db, web_case.web_case_id)
        step_ids = [item.step_id for item in steps]
        targets = WebCaseDao.list_targets_by_step_ids(query_db, step_ids)
        target_map = {item.step_id: item for item in targets}
        locator_map: dict[int, list[HrmWebCaseLocatorSnapshot]] = {item.target_snapshot_id: [] for item in targets}
        for item in WebCaseDao.list_locators_by_target_ids(query_db, list(locator_map.keys())):
            locator_map.setdefault(item.target_snapshot_id, []).append(item)
        return WebCaseDetailModel(
            **base_case.model_dump(by_alias=True),
            steps=[cls._build_step_model(item, target_map, locator_map) for item in steps],
        )

    @classmethod
    def _serialize_assertions(cls, assertions: list[WebAssertionModel] | list[dict[str, Any]]) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for item in assertions:
            if isinstance(item, WebAssertionModel):
                result.append(item.model_dump(by_alias=True))
            elif isinstance(item, dict):
                result.append(item)
        return result

    @classmethod
    def _is_recording_assert_pick_event(cls, payload: dict[str, Any]) -> bool:
        if not payload:
            return False
        raw_event = cls._loads(payload.get("rawEvent") or payload.get("raw_event"), {})
        if isinstance(raw_event, dict):
            event_type = str(raw_event.get("eventType") or raw_event.get("event_type") or "").strip().lower()
            if event_type == "assert_pick_attach_prev":
                return True
            if event_type == "assert_pick":
                attach_mode = str(raw_event.get("assertionAttachMode") or raw_event.get("assertion_attach_mode") or "").strip().lower()
                if attach_mode == "inside_step":
                    return True
            if raw_event.get("attachToPreviousStep") is True or raw_event.get("attach_to_previous_step") is True:
                return True
        return False

    @classmethod
    def _build_assertion_from_recording_payload(cls, payload: dict[str, Any]) -> WebAssertionModel | None:
        action_type = str(payload.get("actionType") or payload.get("action_type") or "").strip().lower()
        params = cls._loads(payload.get("params"), {})
        if not isinstance(params, dict):
            params = {}

        assert_type = ""
        expected: Any = None
        actual_source: str | None = None
        if action_type == "assert_text_contains":
            assert_type = "text_contains"
            expected = params.get("expected") or params.get("text")
            actual_source = "text"
        elif action_type == "assert_text_equals":
            assert_type = "text_equals"
            expected = params.get("expected") or params.get("text")
            actual_source = "text"
        elif action_type in {"wait_visible", "assert_visible"}:
            assert_type = "visible"
        else:
            return None

        target_snapshot = payload.get("targetSnapshot")
        if target_snapshot is None:
            target_snapshot = payload.get("target_snapshot")

        wait_ms = params.get("waitMs")
        if wait_ms in (None, ""):
            wait_ms = params.get("wait_ms")

        assertion_payload = {
            "assertType": assert_type,
            "expected": expected,
            "actualSource": actual_source,
            "enabled": True,
            "waitMs": wait_ms if wait_ms not in (None, "") else None,
            "targetSnapshot": target_snapshot,
        }
        try:
            return WebAssertionModel.model_validate(assertion_payload)
        except Exception:
            logger.warning("录制断言转换失败，已忽略")
            return None

    @classmethod
    def _attach_recording_assertion_to_previous_step(cls, steps: list[WebStepModel], payload: dict[str, Any]) -> bool:
        if not steps:
            return False
        assertion_model = cls._build_assertion_from_recording_payload(payload)
        if assertion_model is None:
            return False
        previous_step = steps[-1]
        previous_step.assertions.append(assertion_model)
        return True

    @classmethod
    def _normalize_recording_step(cls, payload: dict[str, Any], step_index: int) -> WebStepModel | None:
        if not payload:
            return None
        try:
            step = WebStepModel.model_validate(payload)
        except Exception:
            logger.warning(f"录制事件转换步骤失败，step_index={step_index}")
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
    def _build_steps_from_recording_events(cls, events: list[HrmWebRecordingEvent]) -> list[WebStepModel]:
        steps: list[WebStepModel] = []
        for event in events:
            payload = cls._loads(event.payload_json, {})
            if cls._is_recording_assert_pick_event(payload):
                if cls._attach_recording_assertion_to_previous_step(steps, payload):
                    continue
            step = cls._normalize_recording_step(payload, len(steps) + 1)
            if step is not None:
                steps.append(step)
        return steps

    @classmethod
    def _clone_step_for_persist(cls, step: WebStepModel, step_index: int) -> WebStepModel:
        cloned_step = WebStepModel.model_validate(step.model_dump(mode="python", by_alias=True))
        cloned_step.step_id = None
        cloned_step.step_index = step_index
        cloned_step.record_origin = cloned_step.record_origin or "recording"
        if cloned_step.target_snapshot is not None:
            cloned_step.target_snapshot.target_snapshot_id = None
            for locator in cloned_step.target_snapshot.locators:
                locator.locator_snapshot_id = None
        return cloned_step

    @classmethod
    def _build_run_record_model(
        cls,
        run_record: HrmWebCaseRun,
        *,
        case_name: str | None = None,
    ) -> WebCaseRunDetailModel:
        return WebCaseRunDetailModel(
            webCaseRunId=run_record.web_case_run_id,
            webCaseId=run_record.web_case_id,
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
        step_results = response_result.get("steps")
        if isinstance(step_results, list):
            for item in step_results:
                if not isinstance(item, dict):
                    continue
                if item.get("status") in ("passed", "success", 1, "ok", "skipped", "skip"):
                    continue
                step_name = str(item.get("stepName") or item.get("step_name") or item.get("stepId") or "未知步骤").strip()
                reason_candidates = (
                    item.get("error"),
                    item.get("errorMessage"),
                    item.get("message"),
                    item.get("reason"),
                    item.get("errorType"),
                    item.get("error_type"),
                )
                reason = ""
                for candidate in reason_candidates:
                    candidate_text = str(candidate or "").strip()
                    if candidate_text:
                        reason = candidate_text
                        break
                if reason and step_name and step_name not in reason:
                    return f"[{step_name}] {reason}"
                if reason:
                    return reason
                return f"[{step_name}] 执行失败（无详细错误）"

        for key in ("error", "errorMessage", "message"):
            value = response_result.get(key)
            value_text = str(value or "").strip()
            if value_text:
                return value_text
        return None

    @classmethod
    def _is_generic_success_message(cls, message: str | None) -> bool:
        normalized = str(message or "").strip().lower()
        return normalized in {"操作成功", "success", "ok", "执行成功", "执行完成"}

    @classmethod
    def _infer_run_success_from_result(cls, response_result: dict[str, Any]) -> bool | None:
        if not isinstance(response_result, dict):
            return None
        raw_success = response_result.get("success")
        if isinstance(raw_success, bool):
            return raw_success

        step_results = response_result.get("steps")
        if not isinstance(step_results, list) or not step_results:
            return None

        for item in step_results:
            if not isinstance(item, dict):
                continue
            step_status = item.get("status")
            if step_status in ("passed", "success", 1, "ok", True, "skipped", "skip"):
                continue
            return False
        return True

    @classmethod
    def _extract_webui_run_response(cls, response) -> tuple[bool, dict[str, Any], str | None]:
        response_payload = response.response
        response_result: dict[str, Any] = {}
        success = True
        message: str | None = None
        payload_status = ""

        if isinstance(response_payload, AgentResponseWebUI):
            success = bool(response_payload.success)
            payload_status = str(response_payload.status or "").strip().lower()
            if isinstance(response_payload.result, dict):
                response_result = response_payload.result
            elif isinstance(response_payload.data, dict):
                response_result = response_payload.data
            message = response_payload.message
        elif isinstance(response_payload, dict):
            if "success" in response_payload:
                success = bool(response_payload.get("success"))
            payload_status = str(response_payload.get("status") or "").strip().lower()
            if isinstance(response_payload.get("result"), dict):
                response_result = response_payload["result"]
            elif isinstance(response_payload.get("data"), dict):
                response_result = response_payload["data"]
            message = response_payload.get("message")

        inferred_success = cls._infer_run_success_from_result(response_result)
        if inferred_success is not None:
            success = inferred_success
        elif payload_status in {"failed", "fail", "error"}:
            success = False

        if not success:
            extracted_error = cls._extract_run_error_message(response_result)
            if extracted_error and (not message or cls._is_generic_success_message(message)):
                message = extracted_error
            if not message or cls._is_generic_success_message(message):
                message = extracted_error or "执行失败"
        return success, response_result, message

    @classmethod
    def _extract_agent_webui_payload(cls, response) -> tuple[bool, str, dict[str, Any], str | None]:
        """提取 Agent WebUI 响应中的成功态、状态码、结果与消息。"""
        response_payload = response.response
        success = True
        status = ""
        result: dict[str, Any] = {}
        message: str | None = None
        if isinstance(response_payload, AgentResponseWebUI):
            success = bool(response_payload.success)
            status = str(response_payload.status or "").strip().lower()
            message = response_payload.message
            if isinstance(response_payload.result, dict):
                result = response_payload.result
            elif isinstance(response_payload.data, dict):
                result = response_payload.data
        elif isinstance(response_payload, dict):
            if "success" in response_payload:
                success = bool(response_payload.get("success"))
            status = str(response_payload.get("status") or "").strip().lower()
            message = response_payload.get("message")
            if isinstance(response_payload.get("result"), dict):
                result = response_payload.get("result")
            elif isinstance(response_payload.get("data"), dict):
                result = response_payload.get("data")
        return success, status, result, message

    @classmethod
    def _build_fingerprint(cls, target_snapshot: WebTargetSnapshotModel) -> str:
        locator_items = [
            {
                "type": locator.locator_type,
                "value": locator.locator_value,
                "priority": locator.priority,
            }
            for locator in target_snapshot.locators
            if locator.enabled
        ]
        raw_value = json.dumps(locator_items, sort_keys=True, ensure_ascii=False)
        return hashlib.sha1(raw_value.encode("utf-8")).hexdigest()

    @classmethod
    def _upsert_steps(
        cls,
        query_db: Session,
        web_case: HrmWebCase,
        steps: list[WebStepModel],
        *,
        manager: int | None,
        dept_id: int | None,
        create_by: str | None,
        update_by: str | None,
    ) -> None:
        WebCaseDao.delete_steps_by_case_id(query_db, web_case.web_case_id)
        for index, step in enumerate(steps, start=1):
            step_orm = HrmWebCaseStep(
                web_case_id=web_case.web_case_id,
                step_id=int(step.step_id) if step.step_id else None,
                step_index=step.step_index if step.step_index else index,
                step_name=step.step_name or f"步骤{index}",
                action_type=step.action_type,
                enabled=step.enabled,
                timeout_ms=step.timeout_ms,
                continue_on_failure=step.continue_on_failure,
                record_origin=step.record_origin,
                element_id=step.element_id,
                params_json=cls._dumps(step.params),
                assertions_json=cls._dumps(cls._serialize_assertions(step.assertions)),
                raw_event_json=cls._dumps(step.raw_event),
                manager=manager,
                dept_id=dept_id or -1,
                create_by=create_by or "",
                update_by=update_by or "",
            )
            query_db.add(step_orm)
            query_db.flush()

            target_snapshot = step.target_snapshot
            if target_snapshot is None:
                continue

            target_orm = HrmWebCaseStepTargetSnapshot(
                step_id=step_orm.step_id,
                target_snapshot_id=int(target_snapshot.target_snapshot_id)
                if target_snapshot.target_snapshot_id
                else None,
                context_json=cls._dumps(target_snapshot.context.model_dump(by_alias=True)),
                fingerprint=target_snapshot.fingerprint or cls._build_fingerprint(target_snapshot),
                element_text=target_snapshot.element_text,
                stable_score=target_snapshot.stable_score,
                manager=manager,
                dept_id=dept_id or -1,
                create_by=create_by or "",
                update_by=update_by or "",
            )
            query_db.add(target_orm)
            query_db.flush()

            for locator_index, locator in enumerate(target_snapshot.locators):
                locator_orm = HrmWebCaseLocatorSnapshot(
                    target_snapshot_id=target_orm.target_snapshot_id,
                    locator_snapshot_id=int(locator.locator_snapshot_id) if locator.locator_snapshot_id else None,
                    locator_type=locator.locator_type,
                    locator_value_json=cls._dumps(locator.locator_value),
                    priority=locator.priority if locator.priority else locator_index,
                    enabled=locator.enabled,
                    manager=manager,
                    dept_id=dept_id or -1,
                    create_by=create_by or "",
                    update_by=update_by or "",
                )
                query_db.add(locator_orm)

    @classmethod
    def get_web_case_list_services(
        cls,
        query_db: Session,
        query_object: WebCasePageQueryModel,
        data_scope_sql=True,
    ) -> PageResponseModel:
        return WebCaseDao.get_web_case_list(query_db, query_object, data_scope_sql)

    @classmethod
    def list_runtime_profile_services(
        cls,
        query_db: Session,
        query_object: WebRuntimeProfilePageQueryModel,
    ) -> list[WebRuntimeProfileModel]:
        records = (
            query_db.query(SysConfig)
            .filter(SysConfig.config_key.like(f"{cls.RUNTIME_PROFILE_CONFIG_KEY_PREFIX}%"))
            .order_by(SysConfig.update_time.desc(), SysConfig.config_id.desc())
            .all()
        )
        result: list[WebRuntimeProfileModel] = []
        name_keyword = str(query_object.profile_name or "").strip().lower()
        target_filter = str(query_object.target or "").strip().lower()
        for item in records:
            profile = cls._build_runtime_profile_model_from_config(item)
            if profile is None:
                continue
            if name_keyword and name_keyword not in str(profile.profile_name or "").lower():
                continue
            if query_object.enabled is not None and bool(profile.enabled) != bool(query_object.enabled):
                continue
            if query_object.project_id is not None and profile.project_id not in (None, int(query_object.project_id)):
                continue
            if query_object.module_id is not None and profile.module_id not in (None, int(query_object.module_id)):
                continue
            if target_filter and target_filter not in cls._normalize_targets(profile.targets):
                continue
            result.append(profile)
        result.sort(
            key=lambda profile: (
                int(profile.sort or 0),
                str(profile.profile_name or ""),
                str(profile.profile_id or ""),
            )
        )
        return result

    @classmethod
    def save_runtime_profile_services(
        cls,
        query_db: Session,
        profile_model: WebRuntimeProfileSaveModel,
        *,
        user_name: str | None,
        require_existing: bool,
    ) -> CrudResponseModel:
        normalized = cls._normalize_runtime_profile_payload(profile_model.model_dump(by_alias=True))
        profile_name = str(normalized.get("profileName") or "").strip()
        if not profile_name:
            return CrudResponseModel(is_success=False, message="配置名称不能为空")

        provided_profile_id = str(normalized.get("profileId") or "").strip()
        profile_id = provided_profile_id or uuid.uuid4().hex
        config_key = cls._runtime_profile_config_key(profile_id)

        current_time = datetime.now()
        existed_row = query_db.query(SysConfig).filter(SysConfig.config_key == config_key).first()
        if require_existing and existed_row is None:
            return CrudResponseModel(is_success=False, message="配置不存在或已被删除")
        if (not require_existing) and existed_row is not None and not provided_profile_id:
            profile_id = uuid.uuid4().hex
            config_key = cls._runtime_profile_config_key(profile_id)
            existed_row = None

        payload_to_save = {
            **normalized,
            "profileId": profile_id,
            "schemaVersion": 1,
            "updatedAt": current_time.isoformat(),
            "updatedBy": user_name or (existed_row.update_by if existed_row else "system"),
        }
        if existed_row is None:
            payload_to_save["createdAt"] = current_time.isoformat()
            payload_to_save["createdBy"] = user_name or "system"

        try:
            if existed_row is None:
                query_db.add(
                    SysConfig(
                        config_name=profile_name,
                        config_key=config_key,
                        config_value=cls._dumps(payload_to_save),
                        config_type="N",
                        create_by=user_name or "system",
                        update_by=user_name or "system",
                        remark=normalized.get("remark") or "Web运行Cookie配置",
                    )
                )
            else:
                existed_row.config_name = profile_name
                existed_row.config_value = cls._dumps(payload_to_save)
                existed_row.remark = normalized.get("remark") or existed_row.remark
                existed_row.update_by = user_name or existed_row.update_by or "system"
                existed_row.update_time = current_time

            query_db.commit()
            saved_row = query_db.query(SysConfig).filter(SysConfig.config_key == config_key).first()
            saved_model = cls._build_runtime_profile_model_from_config(saved_row) if saved_row is not None else None
            return CrudResponseModel(
                is_success=True,
                message="保存成功",
                result=saved_model.model_dump(mode="json", by_alias=True) if saved_model else None,
            )
        except Exception as exc:
            query_db.rollback()
            raise exc

    @classmethod
    def delete_runtime_profile_services(
        cls,
        query_db: Session,
        profile_id: str,
    ) -> CrudResponseModel:
        profile_id_value = str(profile_id or "").strip()
        if not profile_id_value:
            return CrudResponseModel(is_success=False, message="配置ID不能为空")
        config_key = cls._runtime_profile_config_key(profile_id_value)
        existed_row = query_db.query(SysConfig).filter(SysConfig.config_key == config_key).first()
        if existed_row is None:
            return CrudResponseModel(is_success=False, message="配置不存在或已被删除")
        try:
            query_db.delete(existed_row)
            query_db.commit()
            return CrudResponseModel(is_success=True, message="删除成功")
        except Exception as exc:
            query_db.rollback()
            raise exc

    @classmethod
    def web_case_detail_services(cls, query_db: Session, web_case_id: int) -> WebCaseDetailModel | None:
        web_case = WebCaseDao.get_web_case_by_id(query_db, web_case_id)
        if web_case is None:
            return None
        return cls._build_detail_model(query_db, web_case)

    @classmethod
    def add_web_case_services(cls, query_db: Session, page_object: AddWebCaseModel) -> CrudResponseModel:
        case = WebCaseDao.get_web_case_by_name(query_db, page_object.case_name or "")
        if case:
            return CrudResponseModel(is_success=False, message="Web用例名称已存在")

        try:
            web_case = HrmWebCase(
                web_case_id=int(page_object.web_case_id) if page_object.web_case_id else None,
                case_name=page_object.case_name or "新增Web用例",
                project_id=page_object.project_id,
                module_id=page_object.module_id,
                start_url=page_object.start_url,
                browser_name=page_object.browser_name,
                headless=page_object.headless,
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
            WebCaseDao.add_web_case(query_db, web_case)
            cls._upsert_steps(
                query_db,
                web_case,
                page_object.steps,
                manager=page_object.manager,
                dept_id=page_object.dept_id,
                create_by=page_object.create_by,
                update_by=page_object.update_by,
            )
            query_db.commit()
            detail = cls._build_detail_model(query_db, web_case)
            return CrudResponseModel(is_success=True, message="新增成功", result=detail.model_dump(by_alias=True))
        except Exception as exc:
            query_db.rollback()
            raise exc

    @classmethod
    def edit_web_case_services(cls, query_db: Session, page_object: WebCaseDetailModel) -> CrudResponseModel:
        if not page_object.web_case_id:
            return CrudResponseModel(is_success=False, message="Web用例不存在")
        web_case = WebCaseDao.get_web_case_by_id(query_db, int(page_object.web_case_id))
        if web_case is None:
            return CrudResponseModel(is_success=False, message="Web用例不存在")

        if page_object.case_name and page_object.case_name != web_case.case_name:
            existed = WebCaseDao.get_web_case_by_name(query_db, page_object.case_name)
            if existed and existed.web_case_id != web_case.web_case_id:
                return CrudResponseModel(is_success=False, message="Web用例名称已存在")

        try:
            WebCaseDao.edit_web_case(
                query_db,
                int(page_object.web_case_id),
                {
                    "case_name": page_object.case_name or web_case.case_name,
                    "project_id": page_object.project_id,
                    "module_id": page_object.module_id,
                    "start_url": page_object.start_url,
                    "browser_name": page_object.browser_name,
                    "headless": page_object.headless,
                    "runtime_settings_json": cls._dumps(page_object.runtime_settings),
                    "notes": page_object.notes,
                    "sort": page_object.sort,
                    "status": page_object.status,
                    "remark": page_object.remark,
                    "update_by": page_object.update_by or web_case.update_by,
                    "update_time": datetime.now(),
                },
            )
            refreshed_case = WebCaseDao.get_web_case_by_id(query_db, int(page_object.web_case_id))
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
    def delete_web_case_services(cls, query_db: Session, web_case_ids: str) -> CrudResponseModel:
        if not web_case_ids:
            return CrudResponseModel(is_success=False, message="传入Web用例ID为空")
        try:
            for case_id in web_case_ids.split(","):
                case_id_int = int(case_id)
                WebCaseDao.delete_steps_by_case_id(query_db, case_id_int)
                WebCaseDao.delete_web_case(query_db, case_id_int)
            query_db.commit()
            return CrudResponseModel(is_success=True, message="删除成功")
        except Exception as exc:
            query_db.rollback()
            raise exc

    @classmethod
    async def delete_run_record_services(cls, query_db: Session, web_case_run_ids: str) -> CrudResponseModel:
        """删除执行记录，若仍在执行中会先尝试停止。"""
        run_ids = cls._parse_csv_int_ids(web_case_run_ids)
        if not run_ids:
            return CrudResponseModel(is_success=False, message="传入执行记录ID为空")

        run_records = WebCaseDao.list_run_records_by_ids(query_db, run_ids)
        if not run_records:
            return CrudResponseModel(is_success=False, message="执行记录不存在")

        try:
            for run_record in run_records:
                if int(run_record.status or 0) != CaseRunStatus.running.value:
                    continue
                agent = cls._resolve_agent(query_db, run_record.agent_id, run_record.agent_code)
                if agent is None or not agent.agent_code:
                    continue
                try:
                    await send_message(
                        agent.agent_code,
                        {
                            "requestType": TstepTypeEnum.webui.value,
                            "command": "stop_run_case",
                            "webCaseRunId": run_record.web_case_run_id,
                            "reason": "执行记录删除时自动停止",
                        },
                        timeout_seconds=30,
                    )
                except Exception:
                    logger.exception("删除执行记录时尝试停止运行失败")

            for run_record in run_records:
                WebCaseDao.delete_run_record(query_db, run_record.web_case_run_id)
            query_db.commit()
            return CrudResponseModel(is_success=True, message=f"删除成功，共 {len(run_records)} 条执行记录")
        except Exception as exc:
            query_db.rollback()
            raise exc

    @classmethod
    async def delete_recording_services(cls, query_db: Session, recording_ids: str) -> CrudResponseModel:
        """删除录制记录，若仍在录制中会先尝试停止。"""
        parsed_ids = cls._parse_csv_int_ids(recording_ids)
        if not parsed_ids:
            return CrudResponseModel(is_success=False, message="传入录制记录ID为空")

        sessions = WebCaseDao.list_recording_sessions_by_ids(query_db, parsed_ids)
        if not sessions:
            return CrudResponseModel(is_success=False, message="录制会话不存在")

        try:
            for session_obj in sessions:
                if int(session_obj.status or 0) != 2:
                    continue
                agent = cls._resolve_agent(query_db, session_obj.agent_id, session_obj.agent_code)
                if agent is None or not agent.agent_code:
                    continue
                try:
                    await send_message(
                        agent.agent_code,
                        {
                            "requestType": TstepTypeEnum.webui.value,
                            "command": "stop_recording",
                            "recordingId": session_obj.recording_id,
                            "closeBrowserOnStop": True,
                        },
                        timeout_seconds=30,
                    )
                except Exception:
                    logger.exception("删除录制记录时尝试停止录制失败")

            WebCaseDao.delete_recording_events_by_ids(query_db, [session.recording_id for session in sessions])
            for session_obj in sessions:
                WebCaseDao.delete_recording_session(query_db, session_obj.recording_id)
            query_db.commit()
            return CrudResponseModel(is_success=True, message=f"删除成功，共 {len(sessions)} 条录制记录")
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
        query_object: WebRecordingSessionPageQueryModel,
    ) -> PageResponseModel:
        return WebCaseDao.list_recording_sessions(query_db, query_object)

    @classmethod
    def recording_detail_services(cls, query_db: Session, recording_id: int) -> WebRecordingDetailModel | None:
        session_obj = WebCaseDao.get_recording_session(query_db, recording_id)
        if session_obj is None:
            return None
        events = WebCaseDao.list_recording_events(query_db, recording_id)
        steps = cls._build_steps_from_recording_events(events)
        return WebRecordingDetailModel(
            recordingId=session_obj.recording_id,
            webCaseId=session_obj.web_case_id,
            agentId=session_obj.agent_id,
            agentCode=session_obj.agent_code,
            sessionName=session_obj.session_name,
            startUrl=session_obj.start_url,
            browserName=session_obj.browser_name,
            headless=session_obj.headless,
            options=cls._loads(session_obj.options_json, {}),
            status=session_obj.status,
            startedAt=session_obj.started_at,
            endedAt=session_obj.ended_at,
            lastEventAt=session_obj.last_event_at,
            errorMessage=session_obj.error_message,
            resultSummary=cls._loads(session_obj.result_summary_json, {}),
            events=[
                WebRecordingEventModel(
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
    async def start_recording_services(
        cls,
        query_db: Session,
        request_model: WebRecordingStartRequestModel,
        *,
        manager: int | None,
        dept_id: int | None,
        user_name: str | None,
    ) -> CrudResponseModel:
        agent = cls._resolve_agent(query_db, request_model.agent_id, request_model.agent_code)
        if agent is None or not agent.agent_code:
            return CrudResponseModel(is_success=False, message="未找到可用的Agent")

        try:
            profile_runtime_overrides = cls._resolve_runtime_profile_runtime_overrides(
                query_db,
                request_model.runtime_profile_id,
            )
        except ValueError as exc:
            return CrudResponseModel(is_success=False, message=str(exc))
        merged_runtime_overrides = cls._merge_runtime_overrides(profile_runtime_overrides, request_model.runtime_overrides)
        runtime_options_payload: dict[str, Any] = {}
        if merged_runtime_overrides:
            runtime_options_payload["runtimeOverrides"] = merged_runtime_overrides
        if request_model.runtime_profile_id:
            runtime_options_payload["runtimeProfileId"] = request_model.runtime_profile_id
        manual_login_enabled = bool(request_model.manual_login_enabled)
        manual_login_wait_sec = cls._normalize_manual_login_wait_sec(request_model.manual_login_wait_sec)
        manual_login_require_confirm = bool(request_model.manual_login_require_confirm)
        persist_context_enabled = bool(request_model.persist_context_enabled)
        persist_context_key = str(request_model.persist_context_key or "").strip()
        runtime_options_payload["manualLoginEnabled"] = manual_login_enabled
        runtime_options_payload["manualLoginWaitSec"] = manual_login_wait_sec
        runtime_options_payload["manualLoginRequireConfirm"] = manual_login_require_confirm
        runtime_options_payload["persistContextEnabled"] = persist_context_enabled
        if persist_context_key:
            runtime_options_payload["persistContextKey"] = persist_context_key

        session_name = request_model.session_name or f"录制-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        recording_options_payload = request_model.recording_options.model_dump(by_alias=True)
        if runtime_options_payload:
            recording_options_payload["runtimeOptions"] = runtime_options_payload
        recording_session = HrmWebRecordingSession(
            session_name=session_name,
            start_url=request_model.start_url,
            browser_name=request_model.browser_name,
            headless=request_model.headless,
            web_case_id=request_model.web_case_id,
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
            WebCaseDao.create_recording_session(query_db, recording_session)
            query_db.commit()
            query_db.refresh(recording_session)
        except Exception as exc:
            query_db.rollback()
            raise exc

        message = {
            "requestType": TstepTypeEnum.webui.value,
            "command": "start_recording",
            "recordingId": recording_session.recording_id,
            "sessionName": recording_session.session_name,
            "startUrl": recording_session.start_url,
            "browserName": recording_session.browser_name,
            "headless": recording_session.headless,
            "recordingOptions": request_model.recording_options.model_dump(by_alias=True),
        }
        if runtime_options_payload:
            message["runtimeOptions"] = runtime_options_payload
        start_timeout_seconds: int | None = None
        if manual_login_enabled:
            start_timeout_seconds = max(120, manual_login_wait_sec + 90)
        result = await send_message(agent.agent_code, message, timeout_seconds=start_timeout_seconds)
        if result.status_code != AgentResponseEnum.SUCCESS.value:
            WebCaseDao.update_recording_session(
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
    async def continue_recording_services(
        cls,
        query_db: Session,
        request_model: WebRecordingContinueRequestModel,
    ) -> CrudResponseModel:
        session_obj = WebCaseDao.get_recording_session(query_db, request_model.recording_id)
        if session_obj is None:
            return CrudResponseModel(is_success=False, message="录制会话不存在")

        agent = cls._resolve_agent(
            query_db,
            request_model.agent_id or session_obj.agent_id,
            request_model.agent_code or session_obj.agent_code,
        )
        if agent is None or not agent.agent_code:
            return CrudResponseModel(is_success=False, message="未找到可用的Agent")

        result = await send_message(
            agent.agent_code,
            {
                "requestType": TstepTypeEnum.webui.value,
                "command": "continue_recording",
                "recordingId": session_obj.recording_id,
            },
            timeout_seconds=120,
        )
        if result.status_code != AgentResponseEnum.SUCCESS.value:
            return CrudResponseModel(is_success=False, message=result.message)
        return CrudResponseModel(
            is_success=True,
            message="已确认继续录制",
            result={"recordingId": session_obj.recording_id},
        )

    @classmethod
    async def cancel_recording_services(
        cls,
        query_db: Session,
        request_model: WebRecordingCancelRequestModel,
    ) -> CrudResponseModel:
        """取消录制准备态并释放浏览器资源。"""
        session_obj = WebCaseDao.get_recording_session(query_db, request_model.recording_id)
        if session_obj is None:
            return CrudResponseModel(is_success=False, message="录制会话不存在")

        status_value = int(session_obj.status or 0)
        if status_value != 2:
            return CrudResponseModel(is_success=False, message="当前录制会话不处于可取消状态")

        summary_payload = cls._loads(session_obj.result_summary_json, {})
        waiting_confirm = False
        if isinstance(summary_payload, dict):
            manual_gate = summary_payload.get("manualLoginGate")
            if isinstance(manual_gate, dict):
                waiting_confirm = bool(manual_gate.get("waitingConfirm"))
            waiting_confirm = waiting_confirm or str(summary_payload.get("status") or "").strip().lower() == "waiting_manual_login"
        if not waiting_confirm:
            return CrudResponseModel(is_success=False, message="当前录制会话不处于准备等待确认状态")

        agent = cls._resolve_agent(
            query_db,
            request_model.agent_id or session_obj.agent_id,
            request_model.agent_code or session_obj.agent_code,
        )
        if agent is None or not agent.agent_code:
            return CrudResponseModel(is_success=False, message="未找到可用的Agent")

        cancel_reason = str(request_model.reason or "已取消录制准备").strip() or "已取消录制准备"
        cancel_message = {
            "requestType": TstepTypeEnum.webui.value,
            "command": "cancel_recording_prepare",
            "recordingId": session_obj.recording_id,
            "reason": cancel_reason,
        }
        result = await send_message(
            agent.agent_code,
            cancel_message,
            timeout_seconds=90,
        )
        if result.status_code != AgentResponseEnum.SUCCESS.value:
            return CrudResponseModel(is_success=False, message=result.message)

        now = datetime.now()
        WebCaseDao.update_recording_session(
            query_db,
            session_obj.recording_id,
            {
                "status": 5,
                "ended_at": now,
                "last_event_at": now,
                "error_message": cancel_reason,
                "result_summary_json": cls._dumps(
                    {
                        "status": "cancelled",
                        "message": cancel_reason,
                        "cancelledAt": now.isoformat(),
                    }
                ),
                "update_time": now,
            },
        )
        query_db.commit()
        return CrudResponseModel(
            is_success=True,
            message="已取消录制准备",
            result={"recordingId": session_obj.recording_id},
        )

    @classmethod
    async def stop_recording_services(
        cls,
        query_db: Session,
        request_model: WebRecordingStopRequestModel,
    ) -> CrudResponseModel:
        session_obj = WebCaseDao.get_recording_session(query_db, request_model.recording_id)
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
            "requestType": TstepTypeEnum.webui.value,
            "command": "stop_recording",
            "recordingId": session_obj.recording_id,
        }
        updated_options: dict[str, Any] | None = None
        if request_model.close_browser_on_stop is not None:
            updated_options = cls._loads(session_obj.options_json, {})
            updated_options["closeBrowserOnStop"] = request_model.close_browser_on_stop
            stop_message["closeBrowserOnStop"] = request_model.close_browser_on_stop

        result = await send_message(
            agent.agent_code,
            stop_message,
        )
        if result.status_code != AgentResponseEnum.SUCCESS.value:
            return CrudResponseModel(is_success=False, message=result.message)

        update_data = {
            "status": 5,
            "ended_at": datetime.now(),
            "last_event_at": datetime.now(),
        }
        if updated_options is not None:
            update_data["options_json"] = cls._dumps(updated_options)
        WebCaseDao.update_recording_session(query_db, session_obj.recording_id, update_data)
        query_db.commit()
        return CrudResponseModel(is_success=True, message="录制停止指令已发送")

    @classmethod
    def apply_recording_to_case_services(
        cls,
        query_db: Session,
        request_model: WebRecordingApplyRequestModel,
        *,
        manager: int | None,
        dept_id: int | None,
        user_name: str | None,
    ) -> CrudResponseModel:
        session_obj = WebCaseDao.get_recording_session(query_db, request_model.recording_id)
        if session_obj is None:
            return CrudResponseModel(is_success=False, message="录制会话不存在")

        web_case_id = request_model.web_case_id or session_obj.web_case_id
        if not web_case_id:
            return CrudResponseModel(is_success=False, message="缺少目标Web用例ID")

        web_case = WebCaseDao.get_web_case_by_id(query_db, web_case_id)
        if web_case is None:
            return CrudResponseModel(is_success=False, message="目标Web用例不存在")

        events = WebCaseDao.list_recording_events(query_db, request_model.recording_id)
        recording_steps = cls._build_steps_from_recording_events(events)
        if not recording_steps:
            return CrudResponseModel(is_success=False, message="录制会话中没有可用步骤")

        detail = cls._build_detail_model(query_db, web_case)
        merged_steps: list[WebStepModel] = []
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
        result = cls.edit_web_case_services(query_db, detail)
        if result.is_success:
            WebCaseDao.update_recording_session(
                query_db,
                request_model.recording_id,
                {
                    "web_case_id": web_case_id,
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
        request_model: WebRecordingSaveCaseRequestModel,
        *,
        manager: int | None,
        dept_id: int | None,
        user_name: str | None,
    ) -> CrudResponseModel:
        session_obj = WebCaseDao.get_recording_session(query_db, request_model.recording_id)
        if session_obj is None:
            return CrudResponseModel(is_success=False, message="录制会话不存在")

        events = WebCaseDao.list_recording_events(query_db, request_model.recording_id)
        recording_steps = cls._build_steps_from_recording_events(events)
        if not recording_steps:
            return CrudResponseModel(is_success=False, message="录制会话中没有可用步骤")

        source_case = None
        if session_obj.web_case_id:
            source_case = WebCaseDao.get_web_case_by_id(query_db, session_obj.web_case_id)

        add_case = AddWebCaseModel(
            caseName=request_model.case_name,
            projectId=request_model.project_id if request_model.project_id is not None else getattr(source_case, "project_id", None),
            moduleId=request_model.module_id if request_model.module_id is not None else getattr(source_case, "module_id", None),
            startUrl=request_model.start_url
            if request_model.start_url is not None
            else (session_obj.start_url or getattr(source_case, "start_url", None)),
            browserName=request_model.browser_name or session_obj.browser_name or getattr(source_case, "browser_name", "chromium"),
            headless=request_model.headless
            if request_model.headless is not None
            else bool(session_obj.headless if session_obj.headless is not None else getattr(source_case, "headless", False)),
            runtimeSettings=cls._loads(getattr(source_case, "runtime_settings_json", None), {}),
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
        result = cls.add_web_case_services(query_db, add_case)
        if result.is_success:
            created_case_id = None
            if isinstance(result.result, dict):
                created_case_id = result.result.get("webCaseId") or result.result.get("web_case_id")
            WebCaseDao.update_recording_session(
                query_db,
                session_obj.recording_id,
                {
                    "web_case_id": created_case_id,
                    "update_by": user_name or session_obj.update_by,
                    "update_time": datetime.now(),
                },
            )
            query_db.commit()
        return result

    @classmethod
    async def replay_recording_services(
        cls,
        query_db: Session,
        request_model: WebRecordingReplayRequestModel,
    ) -> CrudResponseModel:
        session_obj = WebCaseDao.get_recording_session(query_db, request_model.recording_id)
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
        start_url = (
            request_model.runtime_overrides.get("startUrl")
            or request_model.runtime_overrides.get("start_url")
            or recording_detail.start_url
        )
        case_data = {
            "webCaseId": recording_detail.web_case_id or 0,
            "caseName": recording_detail.session_name or f"录制回放-{recording_detail.recording_id}",
            "startUrl": start_url,
            "browserName": request_model.browser_name or recording_detail.browser_name,
            "headless": request_model.headless if request_model.headless is not None else recording_detail.headless,
            "steps": [step.model_dump(mode="json", by_alias=True) for step in recording_detail.steps],
        }

        response = await send_message(
            agent.agent_code,
            {
                "requestType": TstepTypeEnum.webui.value,
                "command": "run_case",
                "caseData": case_data,
                "runtimeOptions": runtime_options,
            },
        )
        if response.status_code != AgentResponseEnum.SUCCESS.value:
            return CrudResponseModel(is_success=False, message=response.message)

        success, response_result, failure_message = cls._extract_webui_run_response(response)
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
        query_object: WebCaseRunRecordPageQueryModel,
    ) -> PageResponseModel:
        return WebCaseDao.list_run_records(query_db, query_object)

    @classmethod
    def run_record_detail_services(cls, query_db: Session, web_case_run_id: int) -> WebCaseRunDetailModel | None:
        run_record = WebCaseDao.get_run_record(query_db, web_case_run_id)
        if run_record is None:
            return None
        web_case = WebCaseDao.get_web_case_by_id(query_db, run_record.web_case_id)
        return cls._build_run_record_model(
            run_record,
            case_name=web_case.case_name if web_case else None,
        )

    @classmethod
    async def run_web_case_services(
        cls,
        query_db: Session,
        request_model: WebCaseRunRequestModel,
        *,
        manager: int | None,
        dept_id: int | None,
        user_name: str | None,
    ) -> CrudResponseModel:
        detail = cls.web_case_detail_services(query_db, request_model.web_case_id)
        if detail is None:
            return CrudResponseModel(is_success=False, message="Web用例不存在")

        agent = cls._resolve_agent(query_db, request_model.agent_id, request_model.agent_code)
        if agent is None or not agent.agent_code:
            return CrudResponseModel(is_success=False, message="未找到可用的Agent")

        try:
            profile_runtime_overrides = cls._resolve_runtime_profile_runtime_overrides(
                query_db,
                request_model.runtime_profile_id,
            )
        except ValueError as exc:
            return CrudResponseModel(is_success=False, message=str(exc))
        merged_runtime_overrides = cls._merge_runtime_overrides(profile_runtime_overrides, request_model.runtime_overrides)

        started_at = datetime.now()
        run_record = HrmWebCaseRun(
            web_case_id=int(detail.web_case_id),
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
        WebCaseDao.create_run_record(query_db, run_record)
        query_db.commit()

        case_data = detail.model_dump(mode="json", by_alias=True)
        runtime_options = request_model.model_dump(
            mode="json",
            by_alias=True,
            exclude={"web_case_id", "agent_id", "agent_code", "runtime_profile_id", "runtime_overrides"},
        )
        manual_login_enabled = bool(request_model.manual_login_enabled)
        manual_login_wait_sec = cls._normalize_manual_login_wait_sec(request_model.manual_login_wait_sec)
        manual_login_require_confirm = bool(request_model.manual_login_require_confirm)
        persist_context_enabled = bool(request_model.persist_context_enabled)
        persist_context_key = str(request_model.persist_context_key or "").strip()
        runtime_options["manualLoginEnabled"] = manual_login_enabled
        runtime_options["manualLoginWaitSec"] = manual_login_wait_sec
        runtime_options["manualLoginRequireConfirm"] = manual_login_require_confirm
        runtime_options["persistContextEnabled"] = persist_context_enabled
        if persist_context_key:
            runtime_options["persistContextKey"] = persist_context_key
        if merged_runtime_overrides:
            runtime_options["runtimeOverrides"] = merged_runtime_overrides
        if request_model.runtime_profile_id:
            runtime_options["runtimeProfileId"] = request_model.runtime_profile_id

        if manual_login_enabled and manual_login_require_confirm:
            prepare_response = await send_message(
                agent.agent_code,
                {
                    "requestType": TstepTypeEnum.webui.value,
                    "command": "prepare_run_case",
                    "webCaseRunId": run_record.web_case_run_id,
                    "caseData": case_data,
                    "runtimeOptions": runtime_options,
                },
                timeout_seconds=max(120, manual_login_wait_sec + 90),
            )
            if prepare_response.status_code != AgentResponseEnum.SUCCESS.value:
                ended_at = datetime.now()
                duration_ms = int((ended_at - started_at).total_seconds() * 1000)
                WebCaseDao.update_run_record(
                    query_db,
                    run_record.web_case_run_id,
                    {
                        "status": CaseRunStatus.failed.value,
                        "ended_at": ended_at,
                        "duration_ms": duration_ms,
                        "error_message": prepare_response.message,
                        "update_by": user_name or run_record.update_by,
                        "update_time": datetime.now(),
                    },
                )
                query_db.commit()
                return CrudResponseModel(is_success=False, message=prepare_response.message)

            agent_success, agent_status, prepare_result, prepare_message = cls._extract_agent_webui_payload(prepare_response)
            if not agent_success:
                ended_at = datetime.now()
                duration_ms = int((ended_at - started_at).total_seconds() * 1000)
                failure_message = prepare_message or "执行准备失败"
                WebCaseDao.update_run_record(
                    query_db,
                    run_record.web_case_run_id,
                    {
                        "status": CaseRunStatus.failed.value,
                        "ended_at": ended_at,
                        "duration_ms": duration_ms,
                        "result_json": cls._dumps(prepare_result),
                        "error_message": failure_message,
                        "update_by": user_name or run_record.update_by,
                        "update_time": datetime.now(),
                    },
                )
                query_db.commit()
                return CrudResponseModel(is_success=False, message=failure_message)

            waiting_result = {
                **(prepare_result if isinstance(prepare_result, dict) else {}),
                "awaitingManualConfirm": True,
                "manualLoginStatus": agent_status or "waiting_manual_login",
            }
            WebCaseDao.update_run_record(
                query_db,
                run_record.web_case_run_id,
                {
                    "status": CaseRunStatus.running.value,
                    "result_json": cls._dumps(waiting_result),
                    "error_message": None,
                    "update_by": user_name or run_record.update_by,
                    "update_time": datetime.now(),
                },
            )
            query_db.commit()
            return CrudResponseModel(
                is_success=True,
                message=prepare_message or "浏览器已就绪，请手动登录后继续执行",
                result=WebCaseRunRecordModel(
                    webCaseRunId=run_record.web_case_run_id,
                    webCaseId=run_record.web_case_id,
                    agentId=run_record.agent_id,
                    agentCode=run_record.agent_code,
                    triggerType=run_record.trigger_type,
                    status=CaseRunStatus.running.value,
                    startedAt=started_at,
                    endedAt=None,
                    durationMs=None,
                    result=waiting_result,
                    errorMessage=None,
                ).model_dump(by_alias=True),
            )

        request_timeout_seconds: int | None = None
        if manual_login_enabled:
            request_timeout_seconds = max(120, manual_login_wait_sec + 600)
        response = await send_message(
            agent.agent_code,
            {
                "requestType": TstepTypeEnum.webui.value,
                "command": "run_case",
                "webCaseRunId": run_record.web_case_run_id,
                "caseData": case_data,
                "runtimeOptions": runtime_options,
            },
            timeout_seconds=request_timeout_seconds,
        )
        ended_at = datetime.now()
        duration_ms = int((ended_at - started_at).total_seconds() * 1000)

        if response.status_code != AgentResponseEnum.SUCCESS.value:
            WebCaseDao.update_run_record(
                query_db,
                run_record.web_case_run_id,
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

        success, response_result, failure_message = cls._extract_webui_run_response(response)
        run_status = CaseRunStatus.passed.value if success else CaseRunStatus.failed.value
        WebCaseDao.update_run_record(
            query_db,
            run_record.web_case_run_id,
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
        if success:
            cls._record_element_candidates(query_db, detail, response_result, manager, dept_id, user_name)
        query_db.commit()

        return CrudResponseModel(
            is_success=success,
            message="执行完成" if success else (failure_message or "执行失败"),
            result=WebCaseRunRecordModel(
                webCaseRunId=run_record.web_case_run_id,
                webCaseId=run_record.web_case_id,
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
    async def continue_web_case_services(
        cls,
        query_db: Session,
        request_model: WebCaseRunContinueRequestModel,
    ) -> CrudResponseModel:
        run_record = WebCaseDao.get_run_record(query_db, request_model.web_case_run_id)
        if run_record is None:
            return CrudResponseModel(is_success=False, message="执行记录不存在")
        if int(run_record.status or 0) != CaseRunStatus.running.value:
            return CrudResponseModel(is_success=False, message="当前执行记录不处于可继续状态")

        agent = cls._resolve_agent(
            query_db,
            request_model.agent_id or run_record.agent_id,
            request_model.agent_code or run_record.agent_code,
        )
        if agent is None or not agent.agent_code:
            return CrudResponseModel(is_success=False, message="未找到可用的Agent")

        response = await send_message(
            agent.agent_code,
            {
                "requestType": TstepTypeEnum.webui.value,
                "command": "continue_run_case",
                "webCaseRunId": run_record.web_case_run_id,
            },
            timeout_seconds=3600,
        )
        ended_at = datetime.now()
        started_at = run_record.started_at or ended_at
        duration_ms = int((ended_at - started_at).total_seconds() * 1000)

        if response.status_code != AgentResponseEnum.SUCCESS.value:
            WebCaseDao.update_run_record(
                query_db,
                run_record.web_case_run_id,
                {
                    "status": CaseRunStatus.failed.value,
                    "ended_at": ended_at,
                    "duration_ms": duration_ms,
                    "error_message": response.message,
                    "update_by": run_record.update_by,
                    "update_time": datetime.now(),
                },
            )
            query_db.commit()
            return CrudResponseModel(is_success=False, message=response.message)

        success, response_result, failure_message = cls._extract_webui_run_response(response)
        run_status = CaseRunStatus.passed.value if success else CaseRunStatus.failed.value
        WebCaseDao.update_run_record(
            query_db,
            run_record.web_case_run_id,
            {
                "status": run_status,
                "ended_at": ended_at,
                "duration_ms": duration_ms,
                "result_json": cls._dumps(response_result),
                "error_message": None if success else failure_message,
                "update_by": run_record.update_by,
                "update_time": datetime.now(),
            },
        )
        if success:
            detail = cls.web_case_detail_services(query_db, run_record.web_case_id)
            if detail is not None:
                cls._record_element_candidates(query_db, detail, response_result, run_record.manager, run_record.dept_id, run_record.update_by)
        query_db.commit()

        return CrudResponseModel(
            is_success=success,
            message="执行完成" if success else (failure_message or "执行失败"),
            result=WebCaseRunRecordModel(
                webCaseRunId=run_record.web_case_run_id,
                webCaseId=run_record.web_case_id,
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
    async def _stop_or_cancel_web_case_services(
        cls,
        query_db: Session,
        request_model: WebCaseRunStopRequestModel,
        *,
        command: str,
        default_reason: str,
        require_waiting_confirm: bool,
    ) -> CrudResponseModel:
        """通用执行中断逻辑：用于停止执行与取消准备态。"""
        run_record = WebCaseDao.get_run_record(query_db, request_model.web_case_run_id)
        if run_record is None:
            return CrudResponseModel(is_success=False, message="执行记录不存在")
        if int(run_record.status or 0) != CaseRunStatus.running.value:
            return CrudResponseModel(is_success=False, message="当前执行记录不处于可中断状态")
        if require_waiting_confirm and not cls._is_run_waiting_manual_confirm(run_record):
            return CrudResponseModel(is_success=False, message="当前执行记录不处于准备等待确认状态")

        agent = cls._resolve_agent(
            query_db,
            request_model.agent_id or run_record.agent_id,
            request_model.agent_code or run_record.agent_code,
        )
        if agent is None or not agent.agent_code:
            return CrudResponseModel(is_success=False, message="未找到可用的Agent")

        cancel_reason = str(request_model.reason or default_reason).strip() or default_reason
        response = await send_message(
            agent.agent_code,
            {
                "requestType": TstepTypeEnum.webui.value,
                "command": command,
                "webCaseRunId": run_record.web_case_run_id,
                "reason": cancel_reason,
            },
            timeout_seconds=120,
        )
        if response.status_code != AgentResponseEnum.SUCCESS.value:
            return CrudResponseModel(is_success=False, message=response.message)

        ended_at = datetime.now()
        started_at = run_record.started_at or ended_at
        duration_ms = int((ended_at - started_at).total_seconds() * 1000)
        merged_result = cls._merge_run_result_payload(
            run_record,
            {
                "cancelled": True,
                "cancelReason": cancel_reason,
                "cancelCommand": command,
                "cancelledAt": ended_at.isoformat(),
            },
        )
        WebCaseDao.update_run_record(
            query_db,
            run_record.web_case_run_id,
            {
                "status": CaseRunStatus.failed.value,
                "ended_at": ended_at,
                "duration_ms": duration_ms,
                "result_json": cls._dumps(merged_result),
                "error_message": cancel_reason,
                "update_by": run_record.update_by,
                "update_time": datetime.now(),
            },
        )
        query_db.commit()
        return CrudResponseModel(
            is_success=True,
            message=cancel_reason,
            result=WebCaseRunRecordModel(
                webCaseRunId=run_record.web_case_run_id,
                webCaseId=run_record.web_case_id,
                agentId=run_record.agent_id,
                agentCode=run_record.agent_code,
                triggerType=run_record.trigger_type,
                status=CaseRunStatus.failed.value,
                startedAt=started_at,
                endedAt=ended_at,
                durationMs=duration_ms,
                result=merged_result,
                errorMessage=cancel_reason,
            ).model_dump(by_alias=True),
        )

    @classmethod
    async def stop_web_case_services(
        cls,
        query_db: Session,
        request_model: WebCaseRunStopRequestModel,
    ) -> CrudResponseModel:
        """停止执行中的Web用例。"""
        return await cls._stop_or_cancel_web_case_services(
            query_db,
            request_model,
            command="stop_run_case",
            default_reason="已手动停止执行",
            require_waiting_confirm=False,
        )

    @classmethod
    async def cancel_web_case_services(
        cls,
        query_db: Session,
        request_model: WebCaseRunCancelRequestModel,
    ) -> CrudResponseModel:
        """取消等待确认中的执行准备态。"""
        return await cls._stop_or_cancel_web_case_services(
            query_db,
            request_model,
            command="cancel_run_case",
            default_reason="已取消执行准备",
            require_waiting_confirm=True,
        )

    @classmethod
    def _record_element_candidates(
        cls,
        query_db: Session,
        detail: WebCaseDetailModel,
        response_result: dict[str, Any],
        manager: int | None,
        dept_id: int | None,
        user_name: str | None,
    ) -> None:
        step_results = response_result.get("steps", [])
        if not isinstance(step_results, list):
            return

        step_map = {str(step.step_id): step for step in detail.steps if step.target_snapshot}
        for item in step_results:
            if not isinstance(item, dict):
                continue
            if item.get("status") not in ("passed", "success", 1, "ok"):
                continue

            step_id = str(item.get("stepId") or item.get("step_id") or "")
            step = step_map.get(step_id)
            if step is None or step.target_snapshot is None:
                continue

            target_snapshot = step.target_snapshot
            fingerprint = target_snapshot.fingerprint or cls._build_fingerprint(target_snapshot)
            candidate = WebCaseDao.get_element_candidate(query_db, detail.project_id, detail.module_id, fingerprint)
            if candidate is None:
                candidate = HrmWebElementCandidate(
                    project_id=detail.project_id,
                    module_id=detail.module_id,
                    web_case_id=int(detail.web_case_id) if detail.web_case_id else None,
                    step_id=int(step.step_id) if step.step_id else None,
                    candidate_name=step.step_name or target_snapshot.element_text or "录制元素",
                    fingerprint=fingerprint,
                    context_json=cls._dumps(target_snapshot.context.model_dump(by_alias=True)),
                    locator_summary_json=cls._dumps([loc.model_dump(by_alias=True) for loc in target_snapshot.locators]),
                    success_count=1,
                    status=1,
                    last_seen_at=datetime.now(),
                    manager=manager,
                    dept_id=dept_id or -1,
                    create_by=user_name or "",
                    update_by=user_name or "",
                )
                WebCaseDao.add_element_candidate(query_db, candidate)
            else:
                WebCaseDao.touch_candidate(
                    query_db,
                    candidate.candidate_id,
                    {
                        "success_count": candidate.success_count + 1,
                        "last_seen_at": datetime.now(),
                        "update_by": user_name or candidate.update_by,
                        "update_time": datetime.now(),
                    },
                )
                candidate.success_count += 1

            if candidate.success_count < cls.ELEMENT_PROMOTION_THRESHOLD:
                continue

            existed_element = WebCaseDao.get_element_by_fingerprint(query_db, detail.project_id, detail.module_id, fingerprint)
            if existed_element is not None:
                WebCaseDao.touch_candidate(
                    query_db,
                    candidate.candidate_id,
                    {"status": 2, "update_by": user_name or candidate.update_by, "update_time": datetime.now()},
                )
                continue

            element = HrmWebElement(
                project_id=detail.project_id,
                module_id=detail.module_id,
                element_name=step.step_name or target_snapshot.element_text or "自动沉淀元素",
                fingerprint=fingerprint,
                description=f"来源Web用例[{detail.case_name}]步骤[{step.step_name}]",
                status=2,
                manager=manager,
                dept_id=dept_id or -1,
                create_by=user_name or "",
                update_by=user_name or "",
            )
            WebCaseDao.add_element(query_db, element)
            for locator in target_snapshot.locators:
                WebCaseDao.add_element_locator(
                    query_db,
                    HrmWebElementLocator(
                        element_id=element.element_id,
                        locator_type=locator.locator_type,
                        locator_value_json=cls._dumps(locator.locator_value),
                        priority=locator.priority,
                        enabled=locator.enabled,
                        manager=manager,
                        dept_id=dept_id or -1,
                        create_by=user_name or "",
                        update_by=user_name or "",
                    ),
                )
            WebCaseDao.touch_candidate(
                query_db,
                candidate.candidate_id,
                {"status": 2, "update_by": user_name or candidate.update_by, "update_time": datetime.now()},
            )

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

        session_obj = WebCaseDao.get_recording_session(query_db, int(recording_id))
        if session_obj is None:
            logger.warning(f"未找到录制会话，recording_id={recording_id}")
            return

        message_type = message_data.get("type")
        payload = message_data.get("payload") or {}
        now = datetime.now()

        if message_type == "record_event":
            event_index = message_data.get("event_index") or message_data.get("eventIndex")
            if event_index is None:
                event_index = WebCaseDao.get_next_recording_event_index(query_db, int(recording_id))
            event_obj = HrmWebRecordingEvent(
                recording_id=int(recording_id),
                event_index=int(event_index),
                event_type=payload.get("actionType") or payload.get("eventType") or "event",
                payload_json=cls._dumps(payload),
                manager=session_obj.manager,
                dept_id=session_obj.dept_id,
                create_by=session_obj.create_by,
                update_by=session_obj.update_by,
            )
            WebCaseDao.add_recording_event(query_db, event_obj)
            WebCaseDao.update_recording_session(
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

        if message_type == "record_finished":
            WebCaseDao.update_recording_session(
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

        if message_type == "record_error":
            WebCaseDao.update_recording_session(
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

        if message_type == "record_status":
            WebCaseDao.update_recording_session(
                query_db,
                int(recording_id),
                {
                    "last_event_at": now,
                    "result_summary_json": cls._dumps(payload),
                    "update_time": now,
                },
            )
            query_db.commit()
