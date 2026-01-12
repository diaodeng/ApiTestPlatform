# modules/pressure/service/run_service.py
from contextlib import contextmanager
from datetime import datetime

from module_pressure.enums import PressureRunStatus
from module_pressure.dao.repository import PressureRunRepo
from module_pressure.engines import EngineFactory


class PressureRunService:

    def __init__(self, repo: PressureRunRepo):
        self.repo = repo

    def create_run(
        self,
        project_id: int,
        scenario_id: int,
        users: int,
        spawn_rate: int
    ):
        return self.repo.create(
            project_id=project_id,
            scenario_id=scenario_id,
            user_count=users,
            spawn_rate=spawn_rate,
            status=PressureRunStatus.PENDING,
        )

    def start_run(self, run_id: int):
        self.repo.update_status(run_id, PressureRunStatus.STARTING)
        job = self.repo.get(run_id)

        try:
            EngineFactory.get(job.engine).start(
                users=self.repo.get(run_id).user_count,
                spawn_rate=self.repo.get(run_id).spawn_rate,
            )
            self.repo.update_status(run_id, PressureRunStatus.RUNNING)
        except Exception as e:
            self.repo.update_status(
                run_id,
                PressureRunStatus.FAILED,
                error=str(e)
            )
            raise

    def stop_run(self, run_id: int):
        self.repo.update_status(run_id, PressureRunStatus.STOPPING)
        job = self.repo.get(run_id)
        EngineFactory.get(job.engine).stop()
        self.repo.update_status(run_id, PressureRunStatus.FINISHED)


@contextmanager
def worker_lock(worker_id):
    lock = redis.lock(f"lock:worker:{worker_id}", timeout=10)
    lock.acquire()
    try:
        yield
    finally:
        lock.release()

