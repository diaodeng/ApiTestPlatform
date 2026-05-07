from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from module_pressure.entity.do.models import (
    PressureRun,
    PressureScenario,
    PressureWorker,
    PressureWorkerCapacityProfile,
    PressureWorkerHeartbeat,
)
from module_pressure.enums import PressureRunStatus


class PressureScenarioRepo:
    """封装性能测试场景的数据库读写。"""

    def __init__(self, db: Session):
        self.db = db

    def create(self, **kwargs) -> PressureScenario:
        """创建场景，参数来自 API 入参，返回落库后的场景对象。"""
        scenario = PressureScenario(**kwargs)
        self.db.add(scenario)
        self.db.commit()
        self.db.refresh(scenario)
        return scenario

    def get(self, scenario_id: int) -> PressureScenario | None:
        """按主键查询场景，未找到时返回 None。"""
        return self.db.get(PressureScenario, scenario_id)

    def get_by_scenario_id(self, scenario_id: int) -> PressureScenario | None:
        """按主键查询场景，未找到时返回 None。"""
        return self.db.query(PressureScenario).filter(PressureScenario.scenario_id == scenario_id).first()

    def list(self, project_id: int | None = None, module_id: int | None = None) -> list[PressureScenario]:
        """查询场景列表，可按项目和模块过滤。"""
        stmt = select(PressureScenario).order_by(PressureScenario.id.desc())
        if project_id is not None:
            stmt = stmt.where(PressureScenario.project_id == project_id)
        if module_id is not None:
            stmt = stmt.where(PressureScenario.module_id == module_id)
        return list(self.db.execute(stmt).scalars().all())

    def update(self, scenario_id: int, **kwargs) -> PressureScenario | None:
        """更新场景字段，返回更新后的对象。"""
        scenario = self.get(scenario_id)
        if not scenario:
            return None
        for key, value in kwargs.items():
            setattr(scenario, key, value)
        scenario.update_time = datetime.now()
        self.db.commit()
        self.db.refresh(scenario)
        return scenario


class PressureRunRepo:
    """封装性能测试运行记录的数据库读写。"""

    def __init__(self, db: Session):
        self.db = db

    def create(self, **kwargs) -> PressureRun:
        """创建运行记录，返回落库后的运行对象。"""
        run = PressureRun(**kwargs)
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        return run

    def get(self, run_id: int) -> PressureRun | None:
        """按主键查询运行记录，未找到时返回 None。"""
        return self.db.get(PressureRun, run_id)

    def list(self, scenario_id: int | None = None, limit: int = 20) -> list[PressureRun]:
        """查询运行历史，可按场景过滤，默认返回最近 20 条。"""
        stmt = select(PressureRun).order_by(PressureRun.id.desc()).limit(limit)
        if scenario_id is not None:
            stmt = stmt.where(PressureRun.scenario_id == scenario_id)
        return list(self.db.execute(stmt).scalars().all())

    def update(self, run_id: int, **kwargs) -> PressureRun | None:
        """更新运行字段，返回更新后的对象。"""
        run = self.get(run_id)
        if not run:
            return None
        for key, value in kwargs.items():
            setattr(run, key, value)
        run.update_time = datetime.now()
        self.db.commit()
        self.db.refresh(run)
        return run

    def update_status(
        self,
        run_id: int,
        status: PressureRunStatus | str,
        error: str | None = None,
        **kwargs,
    ) -> PressureRun | None:
        """更新运行状态，可同时写入错误信息和其他字段。"""
        status_value = status.value if isinstance(status, PressureRunStatus) else status
        if error:
            kwargs["error_message"] = error
        return self.update(run_id, status=status_value, **kwargs)


class PressureWorkerRepo:
    """封装 Worker 注册、心跳、占用和能力画像的数据库读写。"""

    def __init__(self, db: Session):
        self.db = db

    def upsert_worker(self, worker_id: str, **kwargs) -> PressureWorker:
        """注册或更新 Worker 基础信息，返回最新 Worker 对象。"""
        worker = self.get(worker_id)
        now = datetime.now()
        if worker is None:
            worker = PressureWorker(worker_id=worker_id, last_heartbeat=now, **kwargs)
            self.db.add(worker)
        else:
            for key, value in kwargs.items():
                setattr(worker, key, value)
            worker.last_heartbeat = now
            worker.update_time = now
        self.db.commit()
        self.db.refresh(worker)
        return worker

    def get(self, worker_id: str) -> PressureWorker | None:
        """按 worker_id 查询 Worker。"""
        stmt = select(PressureWorker).where(PressureWorker.worker_id == worker_id)
        return self.db.execute(stmt).scalars().first()

    def list(self, include_unhealthy: bool = False) -> list[PressureWorker]:
        """查询 Worker 列表，默认排除不健康节点。"""
        # 兼容 MySQL/SQLite: 避免生成 `NULLS LAST`，改用 `IS NULL + DESC` 实现空值后置。
        stmt = select(PressureWorker).order_by(
            PressureWorker.last_heartbeat.is_(None),
            PressureWorker.last_heartbeat.desc(),
        )
        if not include_unhealthy:
            stmt = stmt.where(PressureWorker.status != "unhealthy")
        return list(self.db.execute(stmt).scalars().all())

    def healthy_workers(self, engine: str, heartbeat_ttl_seconds: int = 15) -> list[PressureWorker]:
        """返回心跳未过期、支持指定引擎且未被占用的 Worker。"""
        threshold = datetime.now() - timedelta(seconds=heartbeat_ttl_seconds)
        workers = self.list(include_unhealthy=False)
        return [
            worker
            for worker in workers
            if worker.last_heartbeat
            and worker.last_heartbeat >= threshold
            and worker.status == "idle"
            and engine in (worker.engine_types or [])
        ]

    def set_busy(self, worker_ids: list[str], run_id: int) -> None:
        """把选中的 Worker 标记为忙，避免被其他任务重复选择。"""
        for worker_id in worker_ids:
            worker = self.get(worker_id)
            if worker:
                worker.status = "busy"
                worker.busy_run_id = run_id
                worker.update_time = datetime.now()
        self.db.commit()

    def release_by_run(self, run_id: int) -> None:
        """释放指定运行占用的 Worker，运行完成、失败或停止时调用。"""
        stmt = select(PressureWorker).where(PressureWorker.busy_run_id == run_id)
        workers = self.db.execute(stmt).scalars().all()
        for worker in workers:
            worker.status = "idle"
            worker.busy_run_id = None
            worker.current_users = 0
            worker.update_time = datetime.now()
        self.db.commit()

    def heartbeat(
        self,
        worker_id: str,
        *,
        run_id: int | None = None,
        current_users: int = 0,
        cpu_usage: float = 0,
        memory_usage: float = 0,
        rps: float = 0,
        fail_rate: float = 0,
        latency_ms: float = 0,
        status: str | None = None,
    ) -> PressureWorker:
        """记录 Worker 心跳并同步 Worker 当前状态。"""
        worker = self.get(worker_id)
        if worker is None:
            worker = PressureWorker(
                worker_id=worker_id,
                host="",
                engine_types=["locust"],
                labels=[],
            )
            self.db.add(worker)

        worker.current_users = current_users
        worker.cpu_usage = cpu_usage
        worker.memory_usage = memory_usage
        worker.rps = rps
        worker.fail_rate = fail_rate
        worker.latency_ms = latency_ms
        worker.last_heartbeat = datetime.now()
        if status:
            worker.status = status
        elif worker.busy_run_id:
            worker.status = "busy"

        self.db.add(
            PressureWorkerHeartbeat(
                worker_id=worker_id,
                run_id=run_id,
                cpu_usage=cpu_usage,
                memory_usage=memory_usage,
                current_users=current_users,
                rps=rps,
                fail_rate=fail_rate,
                latency_ms=latency_ms,
            )
        )
        self.db.commit()
        self.db.refresh(worker)
        return worker

    def get_profile(self, worker_id: str, engine: str) -> PressureWorkerCapacityProfile | None:
        """查询 Worker 在指定引擎下的能力画像。"""
        stmt = (
            select(PressureWorkerCapacityProfile)
            .where(PressureWorkerCapacityProfile.worker_id == worker_id)
            .where(PressureWorkerCapacityProfile.engine == engine)
        )
        return self.db.execute(stmt).scalars().first()

    def upsert_profile(self, worker_id: str, engine: str, **kwargs) -> PressureWorkerCapacityProfile:
        """新增或更新 Worker 能力画像。"""
        profile = self.get_profile(worker_id, engine)
        now = datetime.now()
        if profile is None:
            profile = PressureWorkerCapacityProfile(worker_id=worker_id, engine=engine, **kwargs)
            self.db.add(profile)
        else:
            for key, value in kwargs.items():
                setattr(profile, key, value)
            profile.update_time = now
        profile.last_updated = now
        self.db.commit()
        self.db.refresh(profile)
        return profile
