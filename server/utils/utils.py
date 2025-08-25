import asyncio
import functools
import os
import platform
import time
import uuid
from utils.log_util import logger
from redlock import RedLock, RedLockError
from config.env import RedisConfig


def get_platform() -> dict:
    return {
        "httprunner_version": f"Httprunner None",
        "python_version": "{} {}".format(
            platform.python_implementation(),
            platform.python_version()
        ),
        "platform": platform.platform(),
        "pytest_version": f"pytest None",
    }


def modify_key_value(data, key_to_find, new_value=None):
    """替换字典中指定key的值"""
    if isinstance(data, dict):
        for k, v in data.items():
            if k == key_to_find:
                data[k] = new_value if new_value is not None else str(uuid.uuid4())
            elif isinstance(v, (dict, list)):
                data[k] = modify_key_value(v, key_to_find, new_value)
    elif isinstance(data, list):
        for i in range(len(data)):
            data[i] = modify_key_value(data[i], key_to_find, new_value)
    return data


def get_time_stamp(mark=13, time_str=None):
    """
    获取时间戳
    :param mark: 响应结果为10位或13位时间戳
    :param time_str: 入参时间，不传值则为当前系统时间
    :return:
    """
    if time_str:
        try:
            if mark == 10:
                time_stamp = int(time.mktime(time.strptime(time_str, '%Y-%m-%d %H:%M:%S')))
            else:
                print(time_str)
                time_stamp = int(time.mktime(time.strptime(time_str, '%Y-%m-%d %H:%M:%S')) * 1000)
        except Exception as e:
            print('日期格式错误', e)
            return None
    else:
        if mark == 10:
            time_stamp = int(round(time.time()))
        else:
            time_stamp = int(round(time.time() * 1000))
    return time_stamp


def red_lock(key):
    """
    redis分布式锁，基于redlock
    :param key: 唯一key，确保所有任务一致，但不与其他任务冲突
    :return:
    """
    connect = [{
        'host': RedisConfig.redis_host,
        'port': RedisConfig.redis_port,
        'db': RedisConfig.redis_database,
        'password': RedisConfig.redis_password
    }]

    def decorator(func):
        if asyncio.iscoroutinefunction(func):
            logger.info(f"执行了")

            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                try:
                    with RedLock(
                            f"distributed_lock:{func.__name__}:{key}:{str(args)}",
                            connection_details=connect,
                            ttl=30000,  # 锁释放时间为30s
                    ):
                        return await func(*args, **kwargs)
                except RedLockError:
                    print(
                        f"进程: {os.getpid()}获取任务失败"
                    )

        else:
            logger.info(f"else执行了")

            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                try:
                    lock_key = f"distributed_lock:{func.__name__}:{key}:{str(args)}"
                    logger.info(f"Trying to acquire lock for key: {lock_key}")
                    with RedLock(
                            f"distributed_lock:{func.__name__}:{key}:{str(args)}",
                            connection_details=connect,
                            ttl=30000,  # 锁释放时间为30s
                    ):
                        logger.info(f"Lock acquired for key: {lock_key}")
                        return func(*args, **kwargs)
                except RedLockError:
                    logger.error(
                        f"Failed to acquire lock for key: {lock_key}"
                    )
                    print(
                        f"进程: {os.getpid()}获取任务失败"
                    )

        return wrapper

    return decorator
