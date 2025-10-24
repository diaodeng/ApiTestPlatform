from celery import Celery

REDIS_URL = "redis://:XEWcHn1Yrx8kMMYwHzXw@192.168.100.204:6633/2"

# 创建Celery实例
app = Celery(
    "fastapi_celery",
    broker=REDIS_URL,  # 消息代理
    backend=REDIS_URL,  # 结果存储
    include=["celery_task"]
)


# 更新Celery配置
app.conf.update(
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
    timezone='Asia/Shanghai',  # 设置时区
    enable_utc=True,
    # 可选：设置任务结果过期时间（秒），避免Redis存储过多数据
    result_expires=3600,
)