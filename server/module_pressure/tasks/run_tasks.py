# modules/pressure/tasks/run_tasks.py
from celery import shared_task
from sqlalchemy.orm import Session

from core.database import SessionLocal
from module_pressure.enums import PressureRunStatus
from module_pressure.dao.repository import PressureRunRepo
from module_pressure.service.run_service import PressureRunService


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=5,
    retry_kwargs={"max_retries": 3},
)
def start_pressure_run(self, run_id: int):
    db: Session = SessionLocal()
    try:
        repo = PressureRunRepo(db)
        service = PressureRunService(repo)

        run = repo.get(run_id)
        if run.status not in (
            PressureRunStatus.PENDING,
            PressureRunStatus.INIT,
        ):
            return

        service.start_run(run_id)

    finally:
        db.close()

    monitor_pressure_run.delay(args=[run_id], countdown=5)
    timeout_guard.delay(args=[run_id, 3600])


@shared_task
def stop_pressure_run(run_id: int):
    db = SessionLocal()
    try:
        repo = PressureRunRepo(db)
        service = PressureRunService(repo)
        service.stop_run(run_id)
    finally:
        db.close()


@shared_task(bind=True)
def monitor_pressure_run(self, run_id: int):
    """
    监控
    """
    db = SessionLocal()
    try:
        repo = PressureRunRepo(db)
        run = repo.get(run_id)

        if run.status != PressureRunStatus.RUNNING:
            return

        from module_pressure.service.locust_service import locust_service
        status = locust_service.status()

        if status["state"] == "stopped":
            repo.update_status(run_id, PressureRunStatus.FINISHED)

        else:
            # 继续监控
            self.apply_async(
                args=[run_id],
                countdown=5,
            )
    finally:
        db.close()


@shared_task
def timeout_guard(run_id: int, timeout_sec: int):
    import time
    time.sleep(timeout_sec)

    db = SessionLocal()
    try:
        repo = PressureRunRepo(db)
        run = repo.get(run_id)

        if run.status == PressureRunStatus.RUNNING:
            from module_pressure.service.locust_service import locust_service
            locust_service.force_stop()
            repo.update_status(
                run_id,
                PressureRunStatus.FAILED,
                error="timeout",
            )
    finally:
        db.close()
