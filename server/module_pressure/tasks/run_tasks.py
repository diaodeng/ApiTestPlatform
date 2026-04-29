from __future__ import annotations

from celery import shared_task

from config.database import SessionLocal
from module_pressure.dao.repository import PressureRunRepo, PressureScenarioRepo, PressureWorkerRepo
from module_pressure.service.run_service import PressureRunService


def _build_service(db) -> PressureRunService:
    """创建 Celery 任务使用的运行服务。"""
    return PressureRunService(
        PressureRunRepo(db),
        PressureScenarioRepo(db),
        PressureWorkerRepo(db),
    )


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=5, retry_kwargs={"max_retries": 3})
def start_pressure_run(self, run_id: int):
    """异步启动压测运行。"""
    with SessionLocal() as db:
        _build_service(db).start_run(run_id)


@shared_task
def stop_pressure_run(run_id: int):
    """异步停止压测运行。"""
    with SessionLocal() as db:
        _build_service(db).stop_run(run_id)


@shared_task
def force_stop_pressure_run(run_id: int):
    """异步强制停止压测运行。"""
    with SessionLocal() as db:
        _build_service(db).force_stop(run_id)
