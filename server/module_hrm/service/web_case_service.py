from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

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
    WebCaseRunRecordModel,
    WebCaseRunRecordPageQueryModel,
    WebCaseRunRequestModel,
    WebLocatorModel,
    WebRecordingApplyRequestModel,
    WebRecordingDetailModel,
    WebRecordingEventModel,
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

        session_name = request_model.session_name or f"录制-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        recording_session = HrmWebRecordingSession(
            session_name=session_name,
            start_url=request_model.start_url,
            browser_name=request_model.browser_name,
            headless=request_model.headless,
            web_case_id=request_model.web_case_id,
            agent_id=agent.agent_id,
            agent_code=agent.agent_code,
            options_json=cls._dumps(request_model.recording_options.model_dump(by_alias=True)),
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
        result = await send_message(agent.agent_code, message)
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

        result = await send_message(
            agent.agent_code,
            {
                "requestType": TstepTypeEnum.webui.value,
                "command": "stop_recording",
                "recordingId": session_obj.recording_id,
            },
        )
        if result.status_code != AgentResponseEnum.SUCCESS.value:
            return CrudResponseModel(is_success=False, message=result.message)

        WebCaseDao.update_recording_session(
            query_db,
            session_obj.recording_id,
            {
                "status": 5,
                "ended_at": datetime.now(),
                "last_event_at": datetime.now(),
            },
        )
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
        steps: list[WebStepModel] = []
        for index, event in enumerate(events, start=1):
            payload = cls._loads(event.payload_json, {})
            if not payload:
                continue
            try:
                step = WebStepModel.model_validate(payload)
            except Exception:
                logger.warning(f"录制事件转换步骤失败，event_id={event.event_id}")
                continue
            if not step.action_type:
                continue
            if not step.step_name:
                step.step_name = f"{step.action_type}-{index}"
            step.step_index = index
            steps.append(step)

        detail = cls._build_detail_model(query_db, web_case)
        detail.steps = steps
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
    def list_run_record_services(
        cls,
        query_db: Session,
        query_object: WebCaseRunRecordPageQueryModel,
    ) -> PageResponseModel:
        return WebCaseDao.list_run_records(query_db, query_object)

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

        response = await send_message(
            agent.agent_code,
            {
                "requestType": TstepTypeEnum.webui.value,
                "command": "run_case",
                "caseData": detail.model_dump(by_alias=True),
                "runtimeOptions": request_model.model_dump(
                    by_alias=True,
                    exclude={"web_case_id", "agent_id", "agent_code"},
                ),
            },
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

        response_payload = response.response
        response_result: dict[str, Any] = {}
        success = True
        if isinstance(response_payload, AgentResponseWebUI):
            success = bool(response_payload.success)
            if isinstance(response_payload.result, dict):
                response_result = response_payload.result
            elif isinstance(response_payload.data, dict):
                response_result = response_payload.data
        elif isinstance(response_payload, dict):
            success = bool(response_payload.get("success", True))
            if isinstance(response_payload.get("result"), dict):
                response_result = response_payload["result"]
            elif isinstance(response_payload.get("data"), dict):
                response_result = response_payload["data"]

        run_status = CaseRunStatus.passed.value if success else CaseRunStatus.failed.value
        WebCaseDao.update_run_record(
            query_db,
            run_record.web_case_run_id,
            {
                "status": run_status,
                "ended_at": ended_at,
                "duration_ms": duration_ms,
                "result_json": cls._dumps(response_result),
                "error_message": None if success else response.message,
                "update_by": user_name or run_record.update_by,
                "update_time": datetime.now(),
            },
        )
        if success:
            cls._record_element_candidates(query_db, detail, response_result, manager, dept_id, user_name)
        query_db.commit()

        return CrudResponseModel(
            is_success=success,
            message="执行完成" if success else "执行失败",
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
            ).model_dump(by_alias=True),
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
