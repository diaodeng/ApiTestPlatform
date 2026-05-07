from __future__ import annotations

import time
from datetime import datetime
from typing import Any

from config.env import AppConfig
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

    TERMINAL_LOCUST_STATES = {"stopped", "ready"}

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
        script_delivery_mode: str = "shared_path",
        worker_ids: list[str] | None = None,
    ):
        """基于场景创建一次压测运行记录，尚不启动。"""
        scenario = self.scenario_repo.get(scenario_id)
        if not scenario:
            raise ValueError(f"场景不存在: {scenario_id}")

        return self.run_repo.create(
            project_id=scenario.project_id,
            scenario_id=scenario.scenario_id,
            engine=scenario.engine,
            user_count=users,
            spawn_rate=spawn_rate,
            run_time=run_time,
            target_qps=target_qps,
            worker_mode=worker_mode,
            script_delivery_mode=script_delivery_mode,
            requested_worker_ids=worker_ids or [],
            worker_ready_state={},
            status=PressureRunStatus.PENDING.value,
        )

    def start_run(self, run_id: int):
        """启动压测，生成脚本和数据，分配 Worker，启动 Locust 并触发开始。"""
        run = self.run_repo.get(run_id)
        if not run:
            raise ValueError(f"运行记录不存在: {run_id}")
        if run.status not in {PressureRunStatus.PENDING.value, PressureRunStatus.FAILED.value}:
            raise RuntimeError(f"当前状态不允许启动: {run.status}")

        scenario = self.scenario_repo.get_by_scenario_id(run.scenario_id)
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
                    finish_callback_urls=self._build_finish_callback_urls(run_id),
                )
            else:
                process = self.locust.start_standalone(
                    script_path=artifacts["script_path"],
                    artifact_dir=artifacts["artifact_dir"],
                    web_port=web_port,
                    finish_callback_urls=self._build_finish_callback_urls(run_id),
                )

            self.run_repo.update(
                run_id,
                allocated_worker_ids=worker_ids,
                worker_ready_state={
                    worker_id: {"status": "assigned", "message": "", "updated_at": datetime.now().isoformat()}
                    for worker_id in worker_ids
                },
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
            if worker_ids:
                self.wait_workers_ready(run_id, worker_ids)
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
        if run.status in {
            PressureRunStatus.FINISHED.value,
            PressureRunStatus.CANCELED.value,
            PressureRunStatus.FAILED.value,
        }:
            return run
        if run.status == PressureRunStatus.STOPPING.value:
            return run
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
        if run.status in {PressureRunStatus.CANCELED.value, PressureRunStatus.FINISHED.value}:
            return run
        self.locust.terminate(run.master_pid)
        self.worker_repo.release_by_run(run_id)
        return self.run_repo.update_status(run_id, PressureRunStatus.CANCELED, end_at=datetime.now())

    def auto_finish_run(self, run_id: int):
        """执行结束后自动收尾。

        方法作用:
            由 Locust `test_stop` 事件回调触发，自动把运行从 running 收敛到 finished。
        参数作用:
            run_id: 运行记录 ID。
        响应值:
            返回收尾后的运行记录；如果当前状态无需处理则原样返回。
        """
        run = self.run_repo.get(run_id)
        if not run:
            raise ValueError(f"运行记录不存在: {run_id}")
        if run.status != PressureRunStatus.RUNNING.value:
            return run
        return self.stop_run(run_id)

    def status(self, run_id: int) -> dict:
        """查询运行状态，运行中优先返回 Locust 实时统计。"""
        run = self.run_repo.get(run_id)
        if not run:
            raise ValueError(f"运行记录不存在: {run_id}")
        data = self._serialize_run(run)
        if run.master_web_port and run.status == PressureRunStatus.RUNNING.value:
            locust_stats: dict[str, Any] | None = None
            locust_error: Exception | None = None
            try:
                locust_stats = self.locust.stats(port=run.master_web_port)
            except Exception as exc:
                locust_error = exc

            # 运行查询时顺便做状态收敛：检测到 Locust 已停止后自动执行收尾。
            run = self._reconcile_running_run(
                run_id=run_id,
                locust_stats=locust_stats,
                locust_error=locust_error,
            )
            data = self._serialize_run(run)
            if locust_stats is not None:
                data["locust"] = locust_stats
            if locust_error is not None and run.status == PressureRunStatus.RUNNING.value:
                data["locust_error"] = str(locust_error)
        return data

    def list_runs(self, scenario_id: int | None = None, limit: int = 20) -> list[dict]:
        """查询运行历史，供报告列表和历史对比使用。"""
        runs = self.run_repo.list(scenario_id=scenario_id, limit=limit)

        # 列表查询也执行一次状态收敛，避免运行结束后长期停留在 running。
        needs_refresh = False
        for run in runs:
            if run.status != PressureRunStatus.RUNNING.value:
                continue
            reconciled = self._reconcile_running_run(run.id)
            if reconciled and reconciled.status != run.status:
                needs_refresh = True
        if needs_refresh:
            runs = self.run_repo.list(scenario_id=scenario_id, limit=limit)
        return [self._serialize_run(run) for run in runs]

    def compare_runs(self, run_ids: list[int]) -> list[dict]:
        """返回多次运行的核心摘要，供前端做历史对比。"""
        result = []
        for run_id in run_ids:
            run = self.run_repo.get(run_id)
            if not run:
                continue
            if run.status == PressureRunStatus.RUNNING.value:
                run = self._reconcile_running_run(run_id)
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

    def mark_worker_ready(self, run_id: int, worker_id: str, status: str, message: str | None = None):
        """记录 Worker 已完成脚本准备和 locust worker 启动。"""
        run = self.run_repo.get(run_id)
        if not run:
            raise ValueError(f"运行记录不存在: {run_id}")
        if worker_id not in (run.allocated_worker_ids or []):
            raise ValueError(f"Worker 未分配到该运行: {worker_id}")

        ready_state = dict(run.worker_ready_state or {})
        ready_state[worker_id] = {
            "status": status,
            "message": message or "",
            "updated_at": datetime.now().isoformat(),
        }
        return self.run_repo.update(run_id, worker_ready_state=ready_state)

    def wait_workers_ready(self, run_id: int, worker_ids: list[str], timeout_seconds: int = 120) -> None:
        """等待所有已分配 Worker 上报 ready，失败或超时则终止启动。"""
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            self.run_repo.db.expire_all()
            run = self.run_repo.get(run_id)
            ready_state = run.worker_ready_state or {}
            failed = {
                worker_id: item
                for worker_id, item in ready_state.items()
                if item.get("status") == "failed"
            }
            if failed:
                raise RuntimeError(f"Worker 准备失败: {failed}")
            if all(ready_state.get(worker_id, {}).get("status") == "ready" for worker_id in worker_ids):
                return
            time.sleep(1)
        raise TimeoutError(f"等待 Worker 准备就绪超时: {worker_ids}")

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

    @staticmethod
    def _build_finish_callback_urls(run_id: int) -> str:
        """构建 Locust test_stop 回调地址列表。

        方法作用:
            兼容是否使用 root_path 的两种部署，给 Locust 提供可重试的回调 URL 集合。
        参数作用:
            run_id: 运行记录 ID。
        响应值:
            逗号分隔的 URL 字符串，供子进程通过环境变量读取。
        """
        base = f"http://127.0.0.1:{AppConfig.app_port}"
        urls = [f"{base}/pressure/runs/{run_id}/auto-finish"]
        root_path = str(AppConfig.app_root_path or "").strip().strip("/")
        if root_path:
            urls.append(f"{base}/{root_path}/pressure/runs/{run_id}/auto-finish")
        return ",".join(urls)

    def _reconcile_running_run(
        self,
        run_id: int,
        locust_stats: dict[str, Any] | None = None,
        locust_error: Exception | None = None,
    ):
        """收敛运行状态。

        方法作用:
            当运行记录处于 running 时，依据 Locust 状态/进程存活性自动收尾，避免卡在 running。
        参数作用:
            run_id: 运行记录 ID。
            locust_stats: 可选的 Locust 实时统计，已查询时可复用，避免重复请求。
            locust_error: 查询 Locust 统计时的异常，可选。
        响应值:
            返回收敛后的最新运行记录对象；如果无需变更则返回当前记录。
        """
        run = self.run_repo.get(run_id)
        if not run or run.status != PressureRunStatus.RUNNING.value:
            return run
        if not self._should_finalize_running_run(run, locust_stats=locust_stats, locust_error=locust_error):
            return run
        return self.stop_run(run_id)

    def _should_finalize_running_run(
        self,
        run,
        locust_stats: dict[str, Any] | None = None,
        locust_error: Exception | None = None,
    ) -> bool:
        """判断运行是否应自动结束。

        方法作用:
            判定 running 状态是否已经满足“可自动收尾”的条件。
        参数作用:
            run: 运行记录对象。
            locust_stats: Locust 实时统计。
            locust_error: 查询 Locust 实时统计时的异常。
        响应值:
            True 表示应自动结束，False 表示继续保持 running。
        """
        locust_state = self._extract_locust_state(locust_stats)
        if locust_state in self.TERMINAL_LOCUST_STATES:
            return True
        if locust_error is None:
            return False
        # 当 Locust API 不可达时，用 master 进程存活性做兜底判定。
        return not self.locust.is_process_alive(run.master_pid)

    @staticmethod
    def _extract_locust_state(locust_stats: dict[str, Any] | None) -> str:
        """提取 Locust 状态字段。

        方法作用:
            从 Locust `/stats/requests` 返回结构中提取统一的小写状态值。
        参数作用:
            locust_stats: Locust 实时统计。
        响应值:
            状态字符串，提取失败时返回空字符串。
        """
        if not isinstance(locust_stats, dict):
            return ""
        value = locust_stats.get("state")
        if value is None:
            return ""
        return str(value).strip().lower()

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
            "script_delivery_mode": run.script_delivery_mode,
            "requested_worker_ids": run.requested_worker_ids or [],
            "allocated_worker_ids": run.allocated_worker_ids or [],
            "worker_ready_state": run.worker_ready_state or {},
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
