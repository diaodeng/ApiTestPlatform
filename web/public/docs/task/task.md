celery任务路由

```python
celery_app.conf.task_routes = {
    "app.tasks.image_tasks.*": {"queue": "images"},
    "app.tasks.email_tasks.*": {"queue": "emails"},
}

```

worker启动方式
```shell
celery -A worker.celery_app worker -Q images -l info --concurrency=4

celery -A worker.celery_app worker -Q emails -l info --concurrency=20


```

beat(定时任务)
```shell
celery -A worker.celery_app beat -l info


```

dockercompose中只启动worker
```shell
docker compose up --scale worker=3

```




```python
# worker启动脚本示例
###
#!/usr/bin/env bash

export REDIS_URL=redis://redis-server:6379/0
export PYTHONPATH=/opt/pressure-worker/app

WORKER_NAME="pressure@$(hostname)"

celery -A worker.celery_app worker \
    -Q pressure \
    -n ${WORKER_NAME} \
    --loglevel=INFO \
    --concurrency=8 \
    --pool=prefork \
    --without-gossip \
    --without-mingle \
    --without-heartbeat

"""

# 生产用systemd启动
"""
[Unit]
Description=Pressure Celery Worker
After=network.target

[Service]
Type=simple
User=pressure
WorkingDirectory=/opt/pressure-worker
ExecStart=/opt/pressure-worker/start_worker.sh
Restart=always
RestartSec=5
LimitNOFILE=100000

[Install]
WantedBy=multi-user.target

"""

"""
systemctl daemon-reload
systemctl enable pressure-worker
systemctl start pressure-worker

"""
```


任务的执行
```python
# 独立任务
task.delay(1, 2)
# 与上面的等价
task.apply_async(args=[1, 2])

## 链式任务，类似任务执行计划
from celery import chain

chain(
    prepare_env.s(test_id),
    run_pressure.s(),
    generate_report.s(),
).apply_async()


# 跨队列chain
chain(
    prepare_env.s(test_id).set(queue="control"),
    run_pressure.s().set(queue="pressure"),
    generate_report.s().set(queue="report"),
).apply_async()

## 并发执行
from celery import chord

chord(
    [
        run_case.s(case_id=1),
        run_case.s(case_id=2),
        run_case.s(case_id=3),
    ],
    generate_report.s(test_id=1001),
).apply_async()

# 队列隔离
chord(
    [
        run_case.s(case_id=1).set(queue="pressure"),
        run_case.s(case_id=2).set(queue="pressure"),
        run_case.s(case_id=3).set(queue="pressure"),
    ],
    generate_report.s(test_id).set(queue="report"),
).apply_async()

# 执行任务时兜底异常
chord(
    case_tasks,
    generate_report.s(test_id),
).apply_async(
    link_error=handle_chord_error.s(test_id)
)


```

# 大批量任务同时执行
```python
from more_itertools import chunked

def build_batches(case_ids, batch_size=100):
    return list(chunked(case_ids, batch_size))


batch_chords = [
    chord(
        [run_case.s(cid).set(queue="pressure") for cid in batch],
        collect_batch_result.s(test_id)
    )
    for batch in build_batches(case_ids)
]

chord(
    batch_chords,
    generate_report.s(test_id)
).apply_async()



```

###
```python
@app.task(bind=True)
def run_case(self, case_id, test_id):
    runner = start_locust(
        script=get_script(case_id),
        users=500,
        spawn_rate=50,
    )

    while runner.running:
        if is_cancelled(test_id):
            runner.stop()
            break
        time.sleep(1)

    return runner.collect_stats()

```

# 系统职责划分
```markdown
| 状态            | 驱动者             |
| ------------- | --------------- |
| WAIT_RESOURCE | ScheduleService |
| READY         | 自动判断            |
| SCHEDULED     | Beat / API      |
| STARTING      | Celery          |
| RUNNING       | Locust          |
| FINISHED      | Locust + Celery |
| FAILED        | Celery / 超时     |

```

# worker启动时注册
```python
class WorkerRegisterReq(BaseModel):
    worker_id: str
    host: str
    cpu: int
    memory_gb: int
    max_users: int
    labels: list[str]

@app.post("/api/workers/register")
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

```

# master定时上报worker状态
```python
class WorkerHeartbeat(BaseModel):
    worker_id: str
    current_users: int
    rps: float
    fail_rate: float

@app.post("/api/workers/heartbeat")
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

```

# 避免多个多个任务抢占worker
```python
#使用redis锁
@contextmanager
def worker_lock(worker_id):
    lock = redis.lock(f"lock:worker:{worker_id}", timeout=10)
    lock.acquire()
    try:
        yield
    finally:
        lock.release()
# 使用
with worker_lock(worker_id):
    # 再次确认 capacity
    # 分配用户

```

# master心跳
```python
@app.post("/api/masters/heartbeat")
def master_heartbeat(master_id: str, worker_count: int):
    redis.hset(
        f"master:{master_id}",
        mapping={
            "worker_count": worker_count,
            "last_seen": time.time(),
        }
    )

```