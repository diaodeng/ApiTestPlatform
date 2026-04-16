from __future__ import annotations

from sqlalchemy.orm import Session

from module_admin.entity.vo.common_vo import DataScopeExpr
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
from module_hrm.entity.vo.web_case_vo import (
    WebCasePageQueryModel,
    WebCaseRunRecordPageQueryModel,
    WebRecordingSessionPageQueryModel,
)
from utils.page_util import PageUtil


class WebCaseDao:
    """Web 测试模块数据库访问层。"""

    @classmethod
    def get_web_case_list(
        cls,
        db: Session,
        page_object: WebCasePageQueryModel,
        data_scope_sql: DataScopeExpr = True,
    ):
        query = (
            db.query(HrmWebCase)
            .filter(
                HrmWebCase.case_name.like(f"%{page_object.case_name}%") if page_object.case_name else True,
                HrmWebCase.project_id == page_object.project_id if page_object.project_id else True,
                HrmWebCase.module_id == page_object.module_id if page_object.module_id else True,
                HrmWebCase.browser_name == page_object.browser_name if page_object.browser_name else True,
                HrmWebCase.status == page_object.status if page_object.status else True,
                data_scope_sql,
            )
            .order_by(HrmWebCase.create_time.desc(), HrmWebCase.update_time.desc())
        )
        return PageUtil.paginate(query, page_object.page_num, page_object.page_size, page_object.is_page)

    @classmethod
    def get_web_case_by_id(cls, db: Session, web_case_id: int):
        return db.query(HrmWebCase).filter(HrmWebCase.web_case_id == web_case_id).first()

    @classmethod
    def get_web_case_by_name(cls, db: Session, case_name: str):
        return db.query(HrmWebCase).filter(HrmWebCase.case_name == case_name).first()

    @classmethod
    def add_web_case(cls, db: Session, web_case: HrmWebCase) -> HrmWebCase:
        db.add(web_case)
        db.flush()
        return web_case

    @classmethod
    def edit_web_case(cls, db: Session, web_case_id: int, update_data: dict) -> None:
        db.query(HrmWebCase).filter(HrmWebCase.web_case_id == web_case_id).update(update_data)

    @classmethod
    def delete_web_case(cls, db: Session, web_case_id: int) -> None:
        db.query(HrmWebCase).filter(HrmWebCase.web_case_id == web_case_id).delete()

    @classmethod
    def list_steps(cls, db: Session, web_case_id: int) -> list[HrmWebCaseStep]:
        return (
            db.query(HrmWebCaseStep)
            .filter(HrmWebCaseStep.web_case_id == web_case_id)
            .order_by(HrmWebCaseStep.step_index.asc(), HrmWebCaseStep.create_time.asc())
            .all()
        )

    @classmethod
    def list_targets_by_step_ids(cls, db: Session, step_ids: list[int]) -> list[HrmWebCaseStepTargetSnapshot]:
        if not step_ids:
            return []
        return db.query(HrmWebCaseStepTargetSnapshot).filter(HrmWebCaseStepTargetSnapshot.step_id.in_(step_ids)).all()

    @classmethod
    def list_locators_by_target_ids(cls, db: Session, target_ids: list[int]) -> list[HrmWebCaseLocatorSnapshot]:
        if not target_ids:
            return []
        return (
            db.query(HrmWebCaseLocatorSnapshot)
            .filter(HrmWebCaseLocatorSnapshot.target_snapshot_id.in_(target_ids))
            .order_by(HrmWebCaseLocatorSnapshot.priority.asc(), HrmWebCaseLocatorSnapshot.create_time.asc())
            .all()
        )

    @classmethod
    def list_locators_by_ids(cls, db: Session, locator_ids: list[int]) -> list[HrmWebCaseLocatorSnapshot]:
        """
        根据定位器快照ID列表查询定位器记录。

        :param db: 数据库会话。
        :param locator_ids: 定位器快照ID列表。
        :return: 定位器快照对象列表。
        """
        if not locator_ids:
            return []
        return (
            db.query(HrmWebCaseLocatorSnapshot)
            .filter(HrmWebCaseLocatorSnapshot.locator_snapshot_id.in_(locator_ids))
            .all()
        )

    @classmethod
    def update_locator_snapshot(cls, db: Session, locator_snapshot_id: int, update_data: dict) -> None:
        """
        更新单条定位器快照记录。

        :param db: 数据库会话。
        :param locator_snapshot_id: 定位器快照ID。
        :param update_data: 待更新字段字典。
        :return: 无。
        """
        db.query(HrmWebCaseLocatorSnapshot).filter(
            HrmWebCaseLocatorSnapshot.locator_snapshot_id == locator_snapshot_id
        ).update(update_data)

    @classmethod
    def delete_steps_by_case_id(cls, db: Session, web_case_id: int) -> None:
        steps = cls.list_steps(db, web_case_id)
        step_ids = [step.step_id for step in steps]
        targets = cls.list_targets_by_step_ids(db, step_ids)
        target_ids = [target.target_snapshot_id for target in targets]
        if target_ids:
            db.query(HrmWebCaseLocatorSnapshot).filter(
                HrmWebCaseLocatorSnapshot.target_snapshot_id.in_(target_ids)
            ).delete(synchronize_session=False)
        if step_ids:
            db.query(HrmWebCaseStepTargetSnapshot).filter(
                HrmWebCaseStepTargetSnapshot.step_id.in_(step_ids)
            ).delete(synchronize_session=False)
            db.query(HrmWebCaseStep).filter(HrmWebCaseStep.step_id.in_(step_ids)).delete(synchronize_session=False)

    @classmethod
    def create_recording_session(cls, db: Session, session_data: HrmWebRecordingSession) -> HrmWebRecordingSession:
        db.add(session_data)
        db.flush()
        return session_data

    @classmethod
    def update_recording_session(cls, db: Session, recording_id: int, update_data: dict) -> None:
        db.query(HrmWebRecordingSession).filter(HrmWebRecordingSession.recording_id == recording_id).update(update_data)

    @classmethod
    def get_recording_session(cls, db: Session, recording_id: int):
        return db.query(HrmWebRecordingSession).filter(HrmWebRecordingSession.recording_id == recording_id).first()

    @classmethod
    def list_recording_sessions_by_ids(cls, db: Session, recording_ids: list[int]) -> list[HrmWebRecordingSession]:
        if not recording_ids:
            return []
        return db.query(HrmWebRecordingSession).filter(HrmWebRecordingSession.recording_id.in_(recording_ids)).all()

    @classmethod
    def list_recording_sessions(cls, db: Session, page_object: WebRecordingSessionPageQueryModel):
        query = (
            db.query(HrmWebRecordingSession)
            .filter(
                HrmWebRecordingSession.recording_id == page_object.recording_id if page_object.recording_id else True,
                HrmWebRecordingSession.web_case_id == page_object.web_case_id if page_object.web_case_id else True,
                HrmWebRecordingSession.agent_code == page_object.agent_code if page_object.agent_code else True,
                HrmWebRecordingSession.status == page_object.status if page_object.status else True,
                HrmWebRecordingSession.session_name.like(f"%{page_object.session_name}%")
                if page_object.session_name
                else True,
            )
            .order_by(
                HrmWebRecordingSession.create_time.desc(),
                HrmWebRecordingSession.update_time.desc(),
            )
        )
        return PageUtil.paginate(query, page_object.page_num, page_object.page_size, page_object.is_page)

    @classmethod
    def add_recording_event(cls, db: Session, event_data: HrmWebRecordingEvent) -> HrmWebRecordingEvent:
        db.add(event_data)
        db.flush()
        return event_data

    @classmethod
    def list_recording_events(cls, db: Session, recording_id: int) -> list[HrmWebRecordingEvent]:
        return (
            db.query(HrmWebRecordingEvent)
            .filter(HrmWebRecordingEvent.recording_id == recording_id)
            .order_by(HrmWebRecordingEvent.event_index.asc(), HrmWebRecordingEvent.create_time.asc())
            .all()
        )

    @classmethod
    def delete_recording_events(cls, db: Session, recording_id: int) -> None:
        db.query(HrmWebRecordingEvent).filter(HrmWebRecordingEvent.recording_id == recording_id).delete(
            synchronize_session=False
        )

    @classmethod
    def delete_recording_events_by_ids(cls, db: Session, recording_ids: list[int]) -> None:
        if not recording_ids:
            return
        db.query(HrmWebRecordingEvent).filter(HrmWebRecordingEvent.recording_id.in_(recording_ids)).delete(
            synchronize_session=False
        )

    @classmethod
    def delete_recording_session(cls, db: Session, recording_id: int) -> None:
        db.query(HrmWebRecordingSession).filter(HrmWebRecordingSession.recording_id == recording_id).delete(
            synchronize_session=False
        )

    @classmethod
    def create_run_record(cls, db: Session, run_data: HrmWebCaseRun) -> HrmWebCaseRun:
        db.add(run_data)
        db.flush()
        return run_data

    @classmethod
    def update_run_record(cls, db: Session, web_case_run_id: int, update_data: dict) -> None:
        db.query(HrmWebCaseRun).filter(HrmWebCaseRun.web_case_run_id == web_case_run_id).update(update_data)

    @classmethod
    def get_run_record(cls, db: Session, web_case_run_id: int):
        return db.query(HrmWebCaseRun).filter(HrmWebCaseRun.web_case_run_id == web_case_run_id).first()

    @classmethod
    def list_run_records_by_ids(cls, db: Session, run_ids: list[int]) -> list[HrmWebCaseRun]:
        if not run_ids:
            return []
        return db.query(HrmWebCaseRun).filter(HrmWebCaseRun.web_case_run_id.in_(run_ids)).all()

    @classmethod
    def delete_run_record(cls, db: Session, web_case_run_id: int) -> None:
        db.query(HrmWebCaseRun).filter(HrmWebCaseRun.web_case_run_id == web_case_run_id).delete(
            synchronize_session=False
        )

    @classmethod
    def list_run_records(cls, db: Session, page_object: WebCaseRunRecordPageQueryModel):
        query = (
            db.query(HrmWebCaseRun)
            .filter(
                HrmWebCaseRun.web_case_run_id == page_object.web_case_run_id if page_object.web_case_run_id else True,
                HrmWebCaseRun.web_case_id == page_object.web_case_id if page_object.web_case_id else True,
                HrmWebCaseRun.agent_code == page_object.agent_code if page_object.agent_code else True,
                HrmWebCaseRun.status == page_object.status if page_object.status else True,
                HrmWebCaseRun.trigger_type == page_object.trigger_type if page_object.trigger_type else True,
            )
            .order_by(
                HrmWebCaseRun.create_time.desc(),
                HrmWebCaseRun.update_time.desc(),
            )
        )
        return PageUtil.paginate(query, page_object.page_num, page_object.page_size, page_object.is_page)

    @classmethod
    def get_element_candidate(
        cls,
        db: Session,
        project_id: int | None,
        module_id: int | None,
        fingerprint: str,
    ):
        return (
            db.query(HrmWebElementCandidate)
            .filter(
                HrmWebElementCandidate.project_id == project_id,
                HrmWebElementCandidate.module_id == module_id,
                HrmWebElementCandidate.fingerprint == fingerprint,
            )
            .first()
        )

    @classmethod
    def get_element_by_fingerprint(
        cls,
        db: Session,
        project_id: int | None,
        module_id: int | None,
        fingerprint: str,
    ):
        return (
            db.query(HrmWebElement)
            .filter(
                HrmWebElement.project_id == project_id,
                HrmWebElement.module_id == module_id,
                HrmWebElement.fingerprint == fingerprint,
            )
            .first()
        )

    @classmethod
    def add_element_candidate(cls, db: Session, candidate: HrmWebElementCandidate) -> HrmWebElementCandidate:
        db.add(candidate)
        db.flush()
        return candidate

    @classmethod
    def touch_candidate(cls, db: Session, candidate_id: int, update_data: dict) -> None:
        db.query(HrmWebElementCandidate).filter(HrmWebElementCandidate.candidate_id == candidate_id).update(update_data)

    @classmethod
    def add_element(cls, db: Session, element: HrmWebElement) -> HrmWebElement:
        db.add(element)
        db.flush()
        return element

    @classmethod
    def add_element_locator(cls, db: Session, locator: HrmWebElementLocator) -> HrmWebElementLocator:
        db.add(locator)
        db.flush()
        return locator

    @classmethod
    def get_next_recording_event_index(cls, db: Session, recording_id: int) -> int:
        event = (
            db.query(HrmWebRecordingEvent)
            .filter(HrmWebRecordingEvent.recording_id == recording_id)
            .order_by(HrmWebRecordingEvent.event_index.desc())
            .first()
        )
        return (event.event_index + 1) if event else 1
