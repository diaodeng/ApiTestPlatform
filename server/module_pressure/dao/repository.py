# modules/pressure/repository.py
from sqlalchemy.orm import Session
from .models import PressureRun
from .enums import PressureRunStatus


class PressureRunRepo:

    def __init__(self, db: Session):
        self.db = db

    def create(self, **kwargs) -> PressureRun:
        run = PressureRun(**kwargs)
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        return run

    def get(self, run_id: int) -> PressureRun:
        return self.db.query(PressureRun).get(run_id)

    def update_status(
        self,
        run_id: int,
        status: PressureRunStatus,
        error: str | None = None
    ):
        run = self.get(run_id)
        run.status = status
        if error:
            run.error_message = error
        self.db.commit()
