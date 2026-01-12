WorkerScoreInput = {
    "max_users": 8000,           # 理论上限
    "current_users": 2000,       # 当前压测用户
    "cpu_usage": 0.35,
    "memory_usage": 0.40,
    "rps_capacity": 12000,       # 历史统计
    "latency_ms": 12,
    "heartbeat_age": 1.2,        # 秒
    "status": "idle|running",
}



def calc_worker_free_capacity(w):
    if w.status not in ("idle", "running"):
        return 0

    if w.heartbeat_age > 5:
        return 0

    safety_factor = 0.8

    free_users = w.max_users - w.current_users
    free_users *= safety_factor

    if w.cpu_usage > 0.85:
        free_users *= 0.5

    if w.memory_usage > 0.9:
        free_users = 0

    return int(max(free_users, 0))


def worker_score(w):
    capacity = calc_worker_free_capacity(w)
    stability = 1.0 - w.fail_rate
    latency_penalty = max(1, w.latency_ms / 50)

    return capacity * stability / latency_penalty


def select_workers(workers, required_users):
    selected = []
    remaining = required_users

    for w in sorted(workers, key=worker_score, reverse=True):
        cap = calc_worker_free_capacity(w)
        if cap <= 0:
            continue

        selected.append((w.worker_id, min(cap, remaining)))
        remaining -= cap

        if remaining <= 0:
            break

    if remaining > 0:
        raise ResourceNotEnough()

    return selected


from module_pressure.engines.locust.engine import LocustEngine

def dispatch_job(job_id: int):
    job = load_job_from_db(job_id)

    engine = LocustEngine(job)
    engine.prepare()
    engine.start()

    # 轮询 / WebSocket / 回调
    engine.wait_until_finish()

    engine.collect_result()
    engine.cleanup()
