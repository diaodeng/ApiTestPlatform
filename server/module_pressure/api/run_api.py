# modules/pressure/api/run_api.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel

from core.database import get_db
from module_pressure.service.run_service import PressureRunService
from module_pressure.dao.repository import PressureRunRepo
from starlette.websockets import WebSocket

from module_pressure.tasks.run_tasks import start_pressure_run

router = APIRouter(prefix="/pressure/run", tags=["PressureRun"])


@router.post("/create")
def create_run(
    project_id: int,
    scenario_id: int,
    users: int,
    spawn_rate: int,
    db: Session = Depends(get_db),
):
    service = PressureRunService(PressureRunRepo(db))
    run = service.create_run(
        project_id, scenario_id, users, spawn_rate
    )
    return run


@router.post("/{run_id}/start")
def start_run(
    run_id: int
):
    start_pressure_run.delay(run_id)
    return {
        "message": "run scheduled",
        "run_id": run_id,
    }


@router.post("/{run_id}/stop")
def stop_run(
    run_id: int,
    db: Session = Depends(get_db),
):
    service = PressureRunService(PressureRunRepo(db))
    service.stop_run(run_id)
    return {"message": "stopped"}


@router.post("/force-stop")
def force_stop(run_id: int,
    db: Session = Depends(get_db),):
    service = PressureRunService(PressureRunRepo(db))
    service.force_stop()
    return {"message": "force stopped"}


@router.get("/status")
def status(run_id: int,
    db: Session = Depends(get_db),):
    service = PressureRunService(PressureRunRepo(db))
    data = service.status()

    return data


class WorkerRegisterReq(BaseModel):
    worker_id: str
    host: str
    cpu: int
    memory_gb: int
    max_users: int
    labels: list[str]

# worker启动时的注册接口
@router.post("/api/workers/register")
def register_worker(req: WorkerRegisterReq):
    redis.hset(
        f"worker:{req.worker_id}",
        mapping={
            "host": req.host,
            "cpu": req.cpu,
            "memory": req.memory_gb,
            "max_users": req.max_users,
            "labels": json.dumps(req.labels),
            "status": "idle",
            "current_users": 0,
            "last_seen": time.time(),
        }
    )


class WorkerHeartbeat(BaseModel):
    worker_id: str
    current_users: int
    rps: float
    fail_rate: float


# master定时上报worker状态的接口
@router.post("/api/workers/heartbeat")
def heartbeat(req: WorkerHeartbeat):
    redis.hset(
        f"worker:{req.worker_id}",
        mapping={
            "current_users": req.current_users,
            "rps": req.rps,
            "fail_rate": req.fail_rate,
            "last_seen": time.time(),
        }
    )



"""
master注册模型
{
  "master_id": "locust-master-01",
  "endpoint": "http://10.0.0.10:8089",
  "max_workers": 50,
  "labels": ["prod", "internal"],
  "last_seen": 1735281000,
  "status": "ready"
}
"""
# master心跳
@router.post("/api/masters/heartbeat")
def master_heartbeat(master_id: str, worker_count: int):
    redis.hset(
        f"master:{master_id}",
        mapping={
            "worker_count": worker_count,
            "last_seen": time.time(),
        }
    )


@router.websocket("/ws/tests/{test_id}")
async def test_ws(ws: WebSocket, test_id: int):
    await ws.accept()

    last_id = "$"
    stream = f"test:progress:{test_id}"

    while True:
        events = redis.xread(
            {stream: last_id},
            block=5000,
            count=10,
        )
        for _, messages in events:
            for msg_id, data in messages:
                await ws.send_json(data)
                last_id = msg_id