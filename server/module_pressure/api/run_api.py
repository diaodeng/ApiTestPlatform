from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from config.get_db import get_db
from module_admin.aspect.interface_auth import CheckUserInterfaceAuth
from module_pressure.dao.repository import PressureRunRepo, PressureScenarioRepo, PressureWorkerRepo
from module_pressure.entity.vo.model import (
    RunCompareReq,
    RunCreateReq,
    ScenarioCreateReq,
    ScenarioUpdateReq,
    WorkerHeartbeatReq,
    WorkerReadyReq,
    WorkerRegisterReq,
)
from module_pressure.service.run_service import PressureRunService
from utils.log_util import logger
from utils.response_util import ResponseUtil

pressureController = APIRouter(prefix="/pressure", tags=["性能测试"])


def _service(db: Session) -> PressureRunService:
    """构造运行服务，统一注入三个仓储。"""
    return PressureRunService(
        PressureRunRepo(db),
        PressureScenarioRepo(db),
        PressureWorkerRepo(db),
    )


def _serialize_scenario(scenario) -> dict:
    """把 ORM 场景对象转换成接口返回的 dict。"""
    return {
        "id": scenario.id,
        "scenario_id": scenario.scenario_id,
        "project_id": scenario.project_id,
        "module_id": scenario.module_id,
        "name": scenario.name,
        "engine": scenario.engine,
        "base_url": scenario.base_url,
        "dsl": scenario.dsl,
        "csv_text": scenario.csv_text,
        "remark": scenario.remark,
        "create_time": scenario.create_time,
        "update_time": scenario.update_time,
    }


def _serialize_worker(worker) -> dict:
    """把 ORM Worker 对象转换成接口返回的 dict。"""
    return {
        "id": worker.id,
        "worker_id": worker.worker_id,
        "host": worker.host,
        "hostname": worker.hostname,
        "cpu_cores": worker.cpu_cores,
        "memory_mb": worker.memory_mb,
        "max_users": worker.max_users,
        "current_users": worker.current_users,
        "engine_types": worker.engine_types or [],
        "labels": worker.labels or [],
        "status": worker.status,
        "cpu_usage": worker.cpu_usage,
        "memory_usage": worker.memory_usage,
        "rps": worker.rps,
        "fail_rate": worker.fail_rate,
        "latency_ms": worker.latency_ms,
        "busy_run_id": worker.busy_run_id,
        "last_heartbeat": worker.last_heartbeat,
    }


@pressureController.post("/scenarios", dependencies=[Depends(CheckUserInterfaceAuth("hrm:pressure:scenario:add"))])
async def create_scenario(req: ScenarioCreateReq, db: Session = Depends(get_db)):
    """创建性能测试场景，保存 DSL 和 CSV 参数化数据。"""
    try:
        scenario = PressureScenarioRepo(db).create(**req.model_dump())
        return ResponseUtil.success(data=_serialize_scenario(scenario))
    except Exception as exc:
        return ResponseUtil.error(msg=str(exc))


@pressureController.get("/scenarios", dependencies=[Depends(CheckUserInterfaceAuth("hrm:pressure:list"))])
async def list_scenarios(
    project_id: int | None = None,
    module_id: int | None = None,
    db: Session = Depends(get_db),
):
    """查询性能测试场景列表。"""
    try:
        scenarios = PressureScenarioRepo(db).list(project_id=project_id, module_id=module_id)
        return ResponseUtil.success(data=[_serialize_scenario(item) for item in scenarios])
    except Exception as exc:
        return ResponseUtil.error(msg=str(exc))


@pressureController.get(
    "/scenarios/{scenario_id}",
    dependencies=[
        Depends(CheckUserInterfaceAuth(["hrm:pressure:scenario:detail", "hrm:pressure:scenario:edit"], False))
    ],
)
async def get_scenario(scenario_id: int, db: Session = Depends(get_db)):
    """查询性能测试场景详情。"""
    try:
        scenario = PressureScenarioRepo(db).get(scenario_id)
        if not scenario:
            return ResponseUtil.failure(msg="场景不存在")
        return ResponseUtil.success(data=_serialize_scenario(scenario))
    except Exception as exc:
        return ResponseUtil.error(msg=str(exc))


@pressureController.put(
    "/scenarios/{scenario_id}",
    dependencies=[Depends(CheckUserInterfaceAuth("hrm:pressure:scenario:edit"))],
)
async def update_scenario(scenario_id: int, req: ScenarioUpdateReq, db: Session = Depends(get_db)):
    """更新性能测试场景，修改后下次运行会重新生成 Locust 脚本。"""
    try:
        payload = req.model_dump(exclude_unset=True)
        scenario = PressureScenarioRepo(db).update(scenario_id, **payload)
        if not scenario:
            return ResponseUtil.failure(msg="场景不存在")
        return ResponseUtil.success(data=_serialize_scenario(scenario))
    except Exception as exc:
        return ResponseUtil.error(msg=str(exc))


@pressureController.post("/runs", dependencies=[Depends(CheckUserInterfaceAuth("hrm:pressure:run:add"))])
async def create_run(req: RunCreateReq, db: Session = Depends(get_db)):
    """创建一次性能测试运行记录。"""
    try:
        run = _service(db).create_run(
            scenario_id=req.scenario_id,
            users=req.users,
            spawn_rate=req.spawn_rate,
            run_time=req.run_time,
            target_qps=req.target_qps,
            worker_mode=req.worker_mode,
            script_delivery_mode=req.script_delivery_mode,
            worker_ids=req.worker_ids,
        )
        return ResponseUtil.success(data=_service(db)._serialize_run(run))
    except Exception as exc:
        return ResponseUtil.error(msg=str(exc))


@pressureController.post(
    "/runs/{run_id}/start",
    dependencies=[Depends(CheckUserInterfaceAuth("hrm:pressure:run:start"))],
)
async def start_run(run_id: int, db: Session = Depends(get_db)):
    """启动压测，正在执行的 Worker 会被锁定，避免重复分配。"""
    try:
        run = _service(db).start_run(run_id)
        return ResponseUtil.success(data=_service(db)._serialize_run(run))
    except Exception as exc:
        return ResponseUtil.error(msg=str(exc))


@pressureController.post("/runs/{run_id}/stop", dependencies=[Depends(CheckUserInterfaceAuth("hrm:pressure:run:stop"))])
async def stop_run(run_id: int, db: Session = Depends(get_db)):
    """停止压测，采集报告摘要并释放 Worker。"""
    try:
        run = _service(db).stop_run(run_id)
        return ResponseUtil.success(data=_service(db)._serialize_run(run))
    except Exception as exc:
        return ResponseUtil.error(msg=str(exc))


@pressureController.post("/runs/{run_id}/auto-finish")
async def auto_finish_run(run_id: int, request: Request, db: Session = Depends(get_db)):
    """Locust test_stop 回调入口，自动完成运行收尾。"""
    if not _is_local_request(request):
        return ResponseUtil.failure(msg="forbidden")
    try:
        run = _service(db).auto_finish_run(run_id)
        return ResponseUtil.success(data=_service(db)._serialize_run(run))
    except Exception as exc:
        return ResponseUtil.error(msg=str(exc))


@pressureController.post(
    "/runs/{run_id}/force-stop",
    dependencies=[Depends(CheckUserInterfaceAuth("hrm:pressure:run:stop"))],
)
async def force_stop(run_id: int, db: Session = Depends(get_db)):
    """强制停止压测，适用于 Locust API 无响应的情况。"""
    try:
        run = _service(db).force_stop(run_id)
        return ResponseUtil.success(data=_service(db)._serialize_run(run))
    except Exception as exc:
        return ResponseUtil.error(msg=str(exc))


@pressureController.get(
    "/runs/{run_id}/status",
    dependencies=[Depends(CheckUserInterfaceAuth("hrm:pressure:run:detail"))],
)
async def run_status(run_id: int, db: Session = Depends(get_db)):
    """查询压测运行状态和实时统计。"""
    try:
        return ResponseUtil.success(data=_service(db).status(run_id))
    except Exception as exc:
        return ResponseUtil.error(msg=str(exc))


@pressureController.get("/runs", dependencies=[Depends(CheckUserInterfaceAuth("hrm:pressure:list"))])
async def list_runs(
    scenario_id: int | None = None,
    limit: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """查询压测历史记录。"""
    try:
        return ResponseUtil.success(data=_service(db).list_runs(scenario_id=scenario_id, limit=limit))
    except Exception as exc:
        return ResponseUtil.error(msg=str(exc))


@pressureController.post("/runs/compare", dependencies=[Depends(CheckUserInterfaceAuth("hrm:pressure:run:compare"))])
async def compare_runs(req: RunCompareReq, db: Session = Depends(get_db)):
    """对比多次压测报告摘要。"""
    try:
        return ResponseUtil.success(data=_service(db).compare_runs(req.run_ids))
    except Exception as exc:
        return ResponseUtil.error(msg=str(exc))


@pressureController.post(
    "/runs/{run_id}/summary",
    dependencies=[Depends(CheckUserInterfaceAuth("hrm:pressure:run:detail"))],
)
async def refresh_summary(run_id: int, db: Session = Depends(get_db)):
    """手动刷新压测报告摘要。"""
    try:
        return ResponseUtil.success(data=_service(db).refresh_summary(run_id))
    except Exception as exc:
        return ResponseUtil.error(msg=str(exc))


@pressureController.post(
    "/workers/register",
    dependencies=[Depends(CheckUserInterfaceAuth("hrm:pressure:worker:register"))],
)
async def register_worker(req: WorkerRegisterReq, db: Session = Depends(get_db)):
    """注册或更新 Worker 基础信息。"""
    try:
        worker = PressureWorkerRepo(db).upsert_worker(
            req.worker_id,
            host=req.host,
            hostname=req.hostname,
            cpu_cores=req.cpu_cores,
            memory_mb=req.memory_mb,
            max_users=req.max_users,
            engine_types=req.engine_types,
            labels=req.labels,
            status="idle",
        )
        return ResponseUtil.success(data=_serialize_worker(worker))
    except Exception as exc:
        return ResponseUtil.error(msg=str(exc))


@pressureController.post(
    "/workers/heartbeat",
    dependencies=[Depends(CheckUserInterfaceAuth("hrm:pressure:worker:heartbeat"))],
)
async def heartbeat(req: WorkerHeartbeatReq, db: Session = Depends(get_db)):
    """记录 Worker 心跳和当前运行指标。"""
    try:
        worker = PressureWorkerRepo(db).heartbeat(**req.model_dump())
        return ResponseUtil.success(data=_serialize_worker(worker))
    except Exception as exc:
        return ResponseUtil.error(msg=str(exc))


@pressureController.get("/workers", dependencies=[Depends(CheckUserInterfaceAuth("hrm:pressure:list"))])
async def list_workers(include_unhealthy: bool = False, db: Session = Depends(get_db)):
    """查询 Worker 池状态。"""
    try:
        workers = PressureWorkerRepo(db).list(include_unhealthy=include_unhealthy)
        return ResponseUtil.success(data=[_serialize_worker(worker) for worker in workers])
    except Exception as exc:
        logger.error(exc)
        return ResponseUtil.error(msg=str(exc))


@pressureController.get(
    "/workers/{worker_id}/assignment",
    dependencies=[Depends(CheckUserInterfaceAuth("hrm:pressure:worker:assignment"))],
)
async def worker_assignment(worker_id: str, db: Session = Depends(get_db)):
    """Worker agent 拉取当前任务，返回启动 locust worker 的命令参数。"""
    try:
        worker_repo = PressureWorkerRepo(db)
        run_repo = PressureRunRepo(db)
        worker = worker_repo.get(worker_id)
        if not worker or not worker.busy_run_id:
            return ResponseUtil.success(data={"assigned": False})

        run = run_repo.get(worker.busy_run_id)
        if not run or not run.script_path or not run.master_bind_port:
            return ResponseUtil.success(data={"assigned": False})

        script_content = None
        csv_content = None
        scenario_content = None
        artifact_urls = {}
        if run.script_delivery_mode == "inline":
            script_content = _read_text(run.script_path)
            csv_content = _read_text(run.csv_path)
            scenario_content = _read_text(f"{run.artifact_dir}/scenario.json" if run.artifact_dir else None)
        elif run.script_delivery_mode == "fetch":
            artifact_urls = {
                "script": f"/pressure/runs/{run.id}/artifacts/script",
                "csv": f"/pressure/runs/{run.id}/artifacts/csv",
                "scenario": f"/pressure/runs/{run.id}/artifacts/scenario",
            }

        command = [
            "python",
            "-m",
            "locust",
            "-f",
            run.script_path,
            "--worker",
            "--master-host",
            run.master_host,
            "--master-port",
            str(run.master_bind_port),
        ]
        return ResponseUtil.success(
            data={
                "assigned": True,
                "run_id": run.id,
                "status": run.status,
                "engine": run.engine,
                "script_delivery_mode": run.script_delivery_mode,
                "artifact_dir": run.artifact_dir,
                "script_path": run.script_path,
                "csv_path": run.csv_path,
                "master_host": run.master_host,
                "master_port": run.master_bind_port,
                "artifact_urls": artifact_urls,
                "script_content": script_content,
                "csv_content": csv_content,
                "scenario_content": scenario_content,
                "command": command,
            }
        )
    except Exception as exc:
        return ResponseUtil.error(msg=str(exc))


@pressureController.get(
    "/runs/{run_id}/artifacts/script",
    dependencies=[Depends(CheckUserInterfaceAuth("hrm:pressure:worker:assignment"))],
)
async def get_run_script(run_id: int, db: Session = Depends(get_db)):
    """Worker 拉取本次运行的 locustfile.py。"""
    return _artifact_response(db, run_id, "script_path")


@pressureController.get(
    "/runs/{run_id}/artifacts/csv",
    dependencies=[Depends(CheckUserInterfaceAuth("hrm:pressure:worker:assignment"))],
)
async def get_run_csv(run_id: int, db: Session = Depends(get_db)):
    """Worker 拉取本次运行的 CSV 参数化数据。"""
    return _artifact_response(db, run_id, "csv_path")


@pressureController.get(
    "/runs/{run_id}/artifacts/scenario",
    dependencies=[Depends(CheckUserInterfaceAuth("hrm:pressure:worker:assignment"))],
)
async def get_run_scenario(run_id: int, db: Session = Depends(get_db)):
    """Worker 拉取本次运行的 scenario.json。"""
    run = PressureRunRepo(db).get(run_id)
    if not run or not run.artifact_dir:
        return ResponseUtil.failure(msg="运行产物不存在")
    return ResponseUtil.success(data=_read_text(f"{run.artifact_dir}/scenario.json"))


@pressureController.post(
    "/workers/{worker_id}/ready",
    dependencies=[Depends(CheckUserInterfaceAuth("hrm:pressure:worker:assignment"))],
)
async def worker_ready(worker_id: str, req: WorkerReadyReq, db: Session = Depends(get_db)):
    """Worker 完成脚本准备并启动 locust worker 后上报 ready。"""
    try:
        run = _service(db).mark_worker_ready(req.run_id, worker_id, req.status, req.message)
        return ResponseUtil.success(data=_service(db)._serialize_run(run))
    except Exception as exc:
        return ResponseUtil.error(msg=str(exc))


def _read_text(path: str | None) -> str | None:
    """读取运行产物文本，不存在时返回 None。"""
    if not path:
        return None
    from pathlib import Path

    file_path = Path(path)
    if not file_path.exists():
        return None
    return file_path.read_text(encoding="utf-8")


def _artifact_response(db: Session, run_id: int, path_attr: str):
    """读取指定运行产物并使用统一响应格式返回。"""
    run = PressureRunRepo(db).get(run_id)
    if not run:
        return ResponseUtil.failure(msg="运行记录不存在")
    content = _read_text(getattr(run, path_attr, None))
    if content is None:
        return ResponseUtil.failure(msg="运行产物不存在")
    return ResponseUtil.success(data=content)


def _is_local_request(request: Request) -> bool:
    """校验请求是否来自本机，避免对外暴露自动收尾接口。"""
    client_host = (request.client.host if request.client else "") or ""
    return client_host in {"127.0.0.1", "::1", "localhost"}
