from __future__ import annotations

from urllib.parse import quote

from redis import Redis

from config.env import RedisConfig

TASK_STOP_PREFIX = "celery:task:stop"


class TaskStopRequestedError(RuntimeError):
    """
    任务停止请求异常，用于在任务执行链路中统一中断。
    """


def build_redis_url(database: int) -> str:
    """
    构建 Redis 连接地址。

    :param database: Redis 数据库编号。
    :return: Redis URL。
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


def build_runtime_client() -> Redis:
    """
    创建运行态 Redis 客户端。

    :return: Redis 客户端。
    """
    return Redis.from_url(build_redis_url(RedisConfig.redis_celery_database), decode_responses=True)


def build_task_stop_key(task_id: int) -> str:
    """
    构建任务停止请求键。

    :param task_id: 任务ID。
    :return: Redis 键名。
    """
    return f"{TASK_STOP_PREFIX}:{task_id}"


def is_task_stop_requested(task_id: int) -> bool:
    """
    判断指定任务是否已收到停止请求。

    :param task_id: 任务ID。
    :return: 是否已请求停止。
    """
    if not task_id:
        return False
    client = build_runtime_client()
    try:
        return bool(client.get(build_task_stop_key(task_id)))
    except Exception:
        return False


def clear_task_runtime_state(task_id: int) -> None:
    """
    清理任务停止标记。

    :param task_id: 任务ID。
    :return: 无。
    """
    if not task_id:
        return
    client = build_runtime_client()
    try:
        client.delete(build_task_stop_key(task_id))
    except Exception:
        pass
