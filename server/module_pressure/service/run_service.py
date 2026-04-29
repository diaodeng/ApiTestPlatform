from __future__ import annotations

from datetime import datetime

from module_pressure.dao.repository import PressureRunRepo, PressureScenarioRepo, PressureWorkerRepo
from module_pressure.engines.locust.dsl_builder import compile_locust
from module_pressure.enums import PressureRunStatus
from module_pressure.service.capacity import (
    ResourceNotEnoughError,
    estimate_required_users,
    select_workers,
    update_profile_sample,
)
from module_pressure.service.locust_process import LocustProcessController


class PressureRunService:
    """性能测试运行服务，负责场景编译、Worker 调度、Locust 启停和报告回收。"""

    def __init__(
        self,
        run_repo: PressureRunRepo,
        scenario_repo: PressureScenarioRepo,
        worker_repo: PressureWorkerRepo,
    ):
        self.run_repo = run_repo
        self.scenario_repo = scenario_repo
        self.worker_repo = worker_repo
        self.locust = LocustProcessController()

    def create_run(
        self,
        *,
        scenario_id: int,
        users: int,
        spawn_rate: float,
        run_time: str | None = None,
        target_qps: float | None = None,
        worker_mode: str = "auto",
        worker_ids: list[str] | None = None,
    ):
        """基于场景创建一次压测运行记录，尚不启动。"""
        scenario = self.scenario_repo.get(scenario_id)
        if not scenario:
            raise ValueError(f"场景不存在: {scenario_id}")

        return self.run_repo.create(
            project_id=scenario.project_id,
            scenario_id=scenario.id,
            engine=scenario.engine,
            user_count=users,
            spawn_rate=spawn_rate,
            run_time=run_time,
            target_qps=target_qps,
            worker_mode=worker_mode,
            requested_worker_ids=worker_ids or [],
            status=PressureRunStatus.PENDING.value,
        )

    def start_run(self, run_id: int):
        """启动压测，生成脚本和数据，分配 Worker，启动 Locust 并触发开始。"""
        run = self.run_repo.get(run_id)
        if not run:
            raise ValueError(f"运行记录不存在: {run_id}")
        if run.status not in {PressureRunStatus.PENDING.value, PressureRunStatus.FAILED.value}:
            raise RuntimeError(f"当前状态不允许启动: {run.status}")

        scenario = self.scenario_repo.get(run.scenario_id)
        if not scenario:
            raise ValueError(f"场景不存在: {run.scenario_id}")
        if scenario.engine != "locust":
            raise ValueError(f"当前仅实现 Locust 执行器: {scenario.engine}")

        self.run_repo.update_status(run_id, PressureRunStatus.STARTING, start_at=datetime.now(), error_message=None)
        try:
            artifacts = compile_locust(scenario.dsl, run_id, scenario.base_url, scenario.csv_text)
            required_users = estimate_required_users(
                target_qps=run.target_qps,
                avg_rt_ms=None,
                configured_users=run.user_count,
            )
            allocations = self._allocate_workers(
                run_id,
                run.worker_mode,
                run.requested_worker_ids or [],
                required_users,
            )
            worker_ids = [allocation.worker_id for allocation in allocations]
            web_port = self.locust.allocate_port()
            bind_port = self.locust.allocate_port()
            master_host = self.locust.discover_master_host()

            if worker_ids:
                process = self.locust.start_master(
                    script_path=artifacts["script_path"],
                    artifact_dir=artifacts["artifact_dir"],
                    master_web_port=web_port,
                    master_bind_port=bind_port,
                    expect_workers=len(worker_ids),
                )
            else:
                process = self.locust.start_standalone(
                    script_path=artifacts["script_path"],
                    artifact_dir=artifacts["artifact_dir"],
                    web_port=web_port,
                )

            self.run_repo.update(
                run_id,
                allocated_worker_ids=worker_ids,
                master_web_port=web_port,
                master_bind_port=bind_port,
                master_host=master_host,
                master_pid=process.pid,
                artifact_dir=artifacts["artifact_dir"],
                script_path=artifacts["script_path"],
                csv_path=artifacts["csv_path"],
                report_path=f'{artifacts["artifact_dir"]}/report.html',
            )
            self.locust.wait_web_ready(web_port)
            self.locust.start_test(
                port=web_port,
                users=run.user_count,
                spawn_rate=run.spawn_rate,
                run_time=run.run_time,
            )
            return self.run_repo.update_status(run_id, PressureRunStatus.RUNNING)
        except Exception as exc:
            self.worker_repo.release_by_run(run_id)
            self.run_repo.update_status(run_id, PressureRunStatus.FAILED, error=str(exc), end_at=datetime.now())
            raise

    def stop_run(self, run_id: int):
        """停止正在执行的压测，采集报告摘要并释放 Worker。"""
        run = self.run_repo.get(run_id)
        if not run:
            raise ValueError(f"运行记录不存在: {run_id}")
        self.run_repo.update_status(run_id, PressureRunStatus.STOPPING)
        if run.master_web_port:
            self.locust.stop_test(port=run.master_web_port)
        summary = self._collect_and_update_summary(run_id)
        self.locust.terminate(run.master_pid)
        self.worker_repo.release_by_run(run_id)
        return self.run_repo.update_status(
            run_id,
            PressureRunStatus.FINISHED,
            end_at=datetime.now(),
            summary=summary,
        )

    def force_stop(self, run_id: int):
        """强制终止压测进程，标记为取消并释放 Worker。"""
        run = self.run_repo.get(run_id)
        if not run:
            raise ValueError(f"运行记录不存在: {run_id}")
        self.locust.terminate(run.master_pid)
        self.worker_repo.release_by_run(run_id)
        return self.run_repo.update_status(run_id, PressureRunStatus.CANCELED, end_at=datetime.now())

    def status(self, run_id: int) -> dict:
        """查询运行状态，运行中优先返回 Locust 实时统计。"""
        run = self.run_repo.get(run_id)
        if not run:
            raise ValueError(f"运行记录不存在: {run_id}")
        data = self._serialize_run(run)
        if run.master_web_port and run.status == PressureRunStatus.RUNNING.value:
            try:
                data["locust"] = self.locust.stats(port=run.master_web_port)
            except Exception as exc:
                data["locust_error"] = str(exc)
        return data

    def list_runs(self, scenario_id: int | None = None, limit: int = 20) -> list[dict]:
        """查询运行历史，供报告列表和历史对比使用。"""
        return [self._serialize_run(run) for run in self.run_repo.list(scenario_id=scenario_id, limit=limit)]

    def compare_runs(self, run_ids: list[int]) -> list[dict]:
        """返回多次运行的核心摘要，供前端做历史对比。"""
        result = []
        for run_id in run_ids:
            run = self.run_repo.get(run_id)
            if not run:
                continue
            summary = run.summary or {}
            result.append(
                {
                    "run_id": run.id,
                    "scenario_id": run.scenario_id,
                    "status": run.status,
                    "users": run.user_count,
                    "spawn_rate": run.spawn_rate,
                    "requests": summary.get("requests", 0),
                    "failures": summary.get("failures", 0),
                    "rps": summary.get("rps", 0),
                    "avg_rt_ms": summary.get("avg_rt_ms", 0),
                    "p95_ms": summary.get("p95_ms", 0),
                    "fail_rate": summary.get("fail_rate", 0),
                    "start_at": run.start_at,
                    "end_at": run.end_at,
                }
            )
        return result

    def refresh_summary(self, run_id: int) -> dict:
        """手动刷新报告摘要，适用于进程已结束但未回填的情况。"""
        summary = self._collect_and_update_summary(run_id)
        self.run_repo.update(run_id, summary=summary)
        return summary

    def _allocate_workers(
        self,
        run_id: int,
        worker_mode: str,
        requested_worker_ids: list[str],
        required_users: int,
    ):
        """根据手动或自动模式分配 Worker，无 Worker 时允许本机单进程执行。"""
        if worker_mode == "manual":
            if not requested_worker_ids:
                raise ResourceNotEnoughError("手动模式必须选择至少一个 Worker")
            workers = [self.worker_repo.get(worker_id) for worker_id in requested_worker_ids]
            workers = [worker for worker in workers if worker and worker.status == "idle"]
            if len(workers) != len(requested_worker_ids):
                raise ResourceNotEnoughError("手动选择的 Worker 不存在或正在执行任务")
        else:
            workers = self.worker_repo.healthy_workers("locust")

        if not workers:
            return []

        allocations = select_workers(
            workers,
            required_users,
            lambda worker_id: self.worker_repo.get_profile(worker_id, "locust"),
        )
        self.worker_repo.set_busy([allocation.worker_id for allocation in allocations], run_id)
        return allocations

    def _collect_and_update_summary(self, run_id: int) -> dict:
        """采集 Locust CSV 摘要，并回填 Worker 能力画像。"""
        run = self.run_repo.get(run_id)
        if not run or not run.artifact_dir:
            return {}
        summary = self.locust.collect_summary(run.artifact_dir)
        for worker_id in run.allocated_worker_ids or []:
            profile = self.worker_repo.get_profile(worker_id, run.engine)
            profile_data = update_profile_sample(
                profile,
                users=max(1, int(run.user_count / max(len(run.allocated_worker_ids or []), 1))),
                qps=float(summary.get("rps") or 0),
                avg_rt_ms=float(summary.get("avg_rt_ms") or 0),
                error_rate=float(summary.get("fail_rate") or 0),
            )
            self.worker_repo.upsert_profile(worker_id, run.engine, **profile_data)
        return summary

    def _serialize_run(self, run) -> dict:
        """把 ORM 运行对象转换成接口返回的 dict。"""
        return {
            "id": run.id,
            "project_id": run.project_id,
            "scenario_id": run.scenario_id,
            "engine": run.engine,
            "user_count": run.user_count,
            "spawn_rate": run.spawn_rate,
            "run_time": run.run_time,
            "target_qps": run.target_qps,
            "worker_mode": run.worker_mode,
            "requested_worker_ids": run.requested_worker_ids or [],
            "allocated_worker_ids": run.allocated_worker_ids or [],
            "status": run.status,
            "master_host": run.master_host,
            "master_web_port": run.master_web_port,
            "master_bind_port": run.master_bind_port,
            "master_pid": run.master_pid,
            "artifact_dir": run.artifact_dir,
            "script_path": run.script_path,
            "csv_path": run.csv_path,
            "report_path": run.report_path,
            "summary": run.summary or {},
            "error_message": run.error_message,
            "start_at": run.start_at,
            "end_at": run.end_at,
        }
