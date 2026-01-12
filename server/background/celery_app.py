from celery import Celery
from kombu import Queue, Exchange
import os

REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")

celery_app = Celery(
    "my_app",
    broker=REDIS_URL,
    backend=REDIS_URL,
)

celery_app.conf.update(
    beat_scheduler="redbeat.RedBeatScheduler",
    redbeat_redis_url="redis://localhost:6379/2",
    result_backend="redis://localhost:6379/2",
    timezone="Asia/Shanghai",
    enable_utc=False,

    task_queues=(
        Queue("control", Exchange("control"), routing_key="control.#"),
        Queue("pressure", Exchange("pressure"), routing_key="pressure.#"),
        Queue("report", Exchange("report"), routing_key="report.#"),
    ),

    task_routes={
        "worker.tasks.control.*": {"queue": "control"},
        "worker.tasks.pressure.*": {"queue": "pressure"},
        "worker.tasks.report.*": {"queue": "report"},
    },

    task_default_queue="control",
    task_default_exchange="control",
    task_default_routing_key="control.default",

    result_backend_transport_options={
        "visibility_timeout": 3600
    },

    worker_prefetch_multiplier=1,
    task_acks_late=True,
)

celery_app.autodiscover_tasks(["worker.tasks"])

