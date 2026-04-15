import os
from urllib.parse import quote

from celery import Celery

from config.env import RedisConfig


def build_redis_url(database: int) -> str:
    """
    构建 Redis 连接地址。

    :param database: Redis 数据库编号，用于区分不同业务数据。
    :return: Celery 可直接使用的 Redis URL。
    """
    username = (RedisConfig.redis_username or "").strip()
    password = (RedisConfig.redis_password or "").strip()
    auth = ""
    if username and password:
        auth = f"{quote(username)}:{quote(password)}@"
    elif password:
        auth = f":{quote(password)}@"
    elif username:
        auth = f"{quote(username)}@"

    return f"redis://{auth}{RedisConfig.redis_host}:{RedisConfig.redis_port}/{database}"


broker_db = RedisConfig.redis_celery_database
result_db = RedisConfig.redis_celery_database
broker_url = build_redis_url(broker_db)
result_backend = build_redis_url(result_db)

celery_app = Celery(
    "qtr_celery",
    broker=broker_url,
    backend=result_backend,
    include=["module_task.celery_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Shanghai",
    enable_utc=False,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    beat_scheduler="config.celery_scheduler:DatabaseScheduler",
    beat_max_loop_interval=5,
)

# Windows 上 prefork/spawn 池稳定性较差，默认切换为单进程池。
if os.name == "nt":
    celery_app.conf.update(
        worker_pool="solo",
        worker_concurrency=1,
    )
