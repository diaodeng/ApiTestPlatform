# app/pressure/events/publisher.py
import time
import json
from redis import Redis

redis = Redis(host="redis", port=6379, decode_responses=True)

def publish_event(job_id: int, event_type: str, payload: dict):
    redis.xadd(
        f"pressure:events:{job_id}",
        {
            "type": event_type,
            "timestamp": int(time.time()),
            "payload": json.dumps(payload),
        },
        maxlen=2000
    )


def publish_progress(test_id, data: dict):
    redis.xadd(
        f"test:progress:{test_id}",
        data,
        maxlen=1000,  # 防止无限增长
        approximate=True,
    )
