from __future__ import annotations

from sqlalchemy.orm import Session

from module_admin.entity.vo.common_vo import DataScopeExpr
from module_hrm.entity.do.desktop_case_do import (
    HrmDesktopCase,
    HrmDesktopCaseRun,
    HrmDesktopCaseStep,
    HrmDesktopImageAsset,
    HrmDesktopRecordingEvent,
    HrmDesktopRecordingSession,
)
from module_hrm.entity.vo.desktop_case_vo import (
    DesktopCasePageQueryModel,
    DesktopCaseRunRecordPageQueryModel,
    DesktopRecordingSessionPageQueryModel,
)
from utils.page_util import PageUtil


class DesktopCaseDao:
    """桌面测试模块数据库访问层。"""

    @classmethod
    def get_desktop_case_list(
        cls,
        db: Session,
        page_object: DesktopCasePageQueryModel,
        data_scope_sql: DataScopeExpr = True,
    ):
        query = (
            db.query(HrmDesktopCase)
            .filter(
                HrmDesktopCase.case_name.like(f"%{page_object.case_name}%") if page_object.case_name else True,
                HrmDesktopCase.project_id == page_object.project_id if page_object.project_id else True,
                HrmDesktopCase.module_id == page_object.module_id if page_object.module_id else True,
                HrmDesktopCase.status == page_object.status if page_object.status else True,
                data_scope_sql,
            )
            .order_by(HrmDesktopCase.sort.asc(), HrmDesktopCase.update_time.desc(), HrmDesktopCase.create_time.desc())
        )
        return PageUtil.paginate(query, page_object.page_num, page_object.page_size, page_object.is_page)

    @classmethod
    def get_desktop_case_by_id(cls, db: Session, desktop_case_id: int):
        return db.query(HrmDesktopCase).filter(HrmDesktopCase.desktop_case_id == desktop_case_id).first()

    @classmethod
    def get_desktop_case_by_name(cls, db: Session, case_name: str):
        return db.query(HrmDesktopCase).filter(HrmDesktopCase.case_name == case_name).first()

    @classmethod
    def add_desktop_case(cls, db: Session, desktop_case: HrmDesktopCase) -> HrmDesktopCase:
        db.add(desktop_case)
        db.flush()
        return desktop_case

    @classmethod
    def edit_desktop_case(cls, db: Session, desktop_case_id: int, update_data: dict) -> None:
        db.query(HrmDesktopCase).filter(HrmDesktopCase.desktop_case_id == desktop_case_id).update(update_data)

    @classmethod
    def delete_desktop_case(cls, db: Session, desktop_case_id: int) -> None:
        db.query(HrmDesktopCase).filter(HrmDesktopCase.desktop_case_id == desktop_case_id).delete()

    @classmethod
    def list_steps(cls, db: Session, desktop_case_id: int) -> list[HrmDesktopCaseStep]:
        return (
            db.query(HrmDesktopCaseStep)
            .filter(HrmDesktopCaseStep.desktop_case_id == desktop_case_id)
            .order_by(HrmDesktopCaseStep.step_index.asc(), HrmDesktopCaseStep.create_time.asc())
            .all()
        )

    @classmethod
    def delete_steps_by_case_id(cls, db: Session, desktop_case_id: int) -> None:
        steps = cls.list_steps(db, desktop_case_id)
        step_ids = [step.step_id for step in steps]
        if step_ids:
            db.query(HrmDesktopImageAsset).filter(
                HrmDesktopImageAsset.step_id.in_(step_ids),
                HrmDesktopImageAsset.desktop_case_run_id.is_(None),
            ).delete(synchronize_session=False)
            db.query(HrmDesktopCaseStep).filter(HrmDesktopCaseStep.step_id.in_(step_ids)).delete(synchronize_session=False)

    @classmethod
    def create_recording_session(
        cls,
        db: Session,
        session_data: HrmDesktopRecordingSession,
    ) -> HrmDesktopRecordingSession:
        db.add(session_data)
        db.flush()
        return session_data

    @classmethod
    def update_recording_session(cls, db: Session, recording_id: int, update_data: dict) -> None:
        db.query(HrmDesktopRecordingSession).filter(HrmDesktopRecordingSession.recording_id == recording_id).update(update_data)

    @classmethod
    def get_recording_session(cls, db: Session, recording_id: int):
        return db.query(HrmDesktopRecordingSession).filter(HrmDesktopRecordingSession.recording_id == recording_id).first()

    @classmethod
    def list_recording_sessions(cls, db: Session, page_object: DesktopRecordingSessionPageQueryModel):
        query = (
            db.query(HrmDesktopRecordingSession)
            .filter(
                HrmDesktopRecordingSession.recording_id == page_object.recording_id if page_object.recording_id else True,
                HrmDesktopRecordingSession.desktop_case_id == page_object.desktop_case_id
                if page_object.desktop_case_id
                else True,
                HrmDesktopRecordingSession.agent_code == page_object.agent_code if page_object.agent_code else True,
                HrmDesktopRecordingSession.status == page_object.status if page_object.status else True,
                HrmDesktopRecordingSession.session_name.like(f"%{page_object.session_name}%")
                if page_object.session_name
                else True,
            )
            .order_by(HrmDesktopRecordingSession.create_time.desc())
        )
        return PageUtil.paginate(query, page_object.page_num, page_object.page_size, page_object.is_page)

    @classmethod
    def add_recording_event(cls, db: Session, event_data: HrmDesktopRecordingEvent) -> HrmDesktopRecordingEvent:
        db.add(event_data)
        db.flush()
        return event_data

    @classmethod
    def list_recording_events(cls, db: Session, recording_id: int) -> list[HrmDesktopRecordingEvent]:
        return (
            db.query(HrmDesktopRecordingEvent)
            .filter(HrmDesktopRecordingEvent.recording_id == recording_id)
            .order_by(HrmDesktopRecordingEvent.event_index.asc(), HrmDesktopRecordingEvent.create_time.asc())
            .all()
        )

    @classmethod
    def get_recording_event(cls, db: Session, event_id: int):
        return db.query(HrmDesktopRecordingEvent).filter(HrmDesktopRecordingEvent.event_id == event_id).first()

    @classmethod
    def get_recording_event_by_index(cls, db: Session, recording_id: int, event_index: int):
        return (
            db.query(HrmDesktopRecordingEvent)
            .filter(
                HrmDesktopRecordingEvent.recording_id == recording_id,
                HrmDesktopRecordingEvent.event_index == event_index,
            )
            .first()
        )

    @classmethod
    def update_recording_event(cls, db: Session, event_id: int, update_data: dict) -> None:
        db.query(HrmDesktopRecordingEvent).filter(HrmDesktopRecordingEvent.event_id == event_id).update(update_data)

    @classmethod
    def create_run_record(cls, db: Session, run_data: HrmDesktopCaseRun) -> HrmDesktopCaseRun:
        db.add(run_data)
        db.flush()
        return run_data

    @classmethod
    def update_run_record(cls, db: Session, desktop_case_run_id: int, update_data: dict) -> None:
        db.query(HrmDesktopCaseRun).filter(HrmDesktopCaseRun.desktop_case_run_id == desktop_case_run_id).update(update_data)

    @classmethod
    def get_run_record(cls, db: Session, desktop_case_run_id: int):
        return db.query(HrmDesktopCaseRun).filter(HrmDesktopCaseRun.desktop_case_run_id == desktop_case_run_id).first()

    @classmethod
    def list_run_records(cls, db: Session, page_object: DesktopCaseRunRecordPageQueryModel):
        query = (
            db.query(HrmDesktopCaseRun)
            .filter(
                HrmDesktopCaseRun.desktop_case_run_id == page_object.desktop_case_run_id
                if page_object.desktop_case_run_id
                else True,
                HrmDesktopCaseRun.desktop_case_id == page_object.desktop_case_id if page_object.desktop_case_id else True,
                HrmDesktopCaseRun.agent_code == page_object.agent_code if page_object.agent_code else True,
                HrmDesktopCaseRun.status == page_object.status if page_object.status else True,
                HrmDesktopCaseRun.trigger_type == page_object.trigger_type if page_object.trigger_type else True,
            )
            .order_by(HrmDesktopCaseRun.started_at.desc(), HrmDesktopCaseRun.create_time.desc())
        )
        return PageUtil.paginate(query, page_object.page_num, page_object.page_size, page_object.is_page)

    @classmethod
    def add_image_asset(cls, db: Session, asset: HrmDesktopImageAsset) -> HrmDesktopImageAsset:
        db.add(asset)
        db.flush()
        return asset

    @classmethod
    def get_image_asset(cls, db: Session, asset_id: int):
        return db.query(HrmDesktopImageAsset).filter(HrmDesktopImageAsset.asset_id == asset_id).first()

    @classmethod
    def delete_assets_by_recording(cls, db: Session, recording_id: int) -> None:
        db.query(HrmDesktopImageAsset).filter(HrmDesktopImageAsset.recording_id == recording_id).delete(synchronize_session=False)

    @classmethod
    def get_next_recording_event_index(cls, db: Session, recording_id: int) -> int:
        event = (
            db.query(HrmDesktopRecordingEvent)
            .filter(HrmDesktopRecordingEvent.recording_id == recording_id)
            .order_by(HrmDesktopRecordingEvent.event_index.desc())
            .first()
        )
        return (event.event_index + 1) if event else 1
