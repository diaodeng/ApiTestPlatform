import logging
import os
import sys
import time
import asyncio
import datetime

from loguru import logger

current_file_size = 0
max_file_size = 1024 * 1024 * 1024
log_dir = os.path.join(os.getcwd(), 'logs')
if not os.path.exists(log_dir):
    os.mkdir(log_dir)

def request_id():
    try:
        return asyncio.current_task().get_name()
    except:
        return ''

def rotation_handler(message, file):
    global current_file_size
    # current_file_size += len(message.record["message"].encode("utf-8"))
    current_file_size = os.path.getsize(file.name)
    if current_file_size >= max_file_size:
        current_file_size = 0
        return True
    elif message.record["time"].strftime("%Y-%m-%d") != time.strftime("%Y-%m-%d"):
        current_file_size = 0
        return True
    else:
        return False


log_path = os.path.join(log_dir, f'{time.strftime("%Y-%m-%d")}.log')
log_path_error = os.path.join(log_dir, f'error_{time.strftime("%Y-%m-%d")}.log')
log_path_mock = os.path.join(log_dir, f'mock_{time.strftime("%Y-%m-%d")}_test.log')

logger.remove()
logger.add(sys.stderr)
logger.add(log_path, rotation=rotation_handler, encoding="utf-8", enqueue=True, filter=lambda record: record["extra"].get("name", "") != "mock_request")
logger.add(log_path_error, rotation=rotation_handler, encoding="utf-8", enqueue=True, filter=lambda record: record["level"].no >= logging.ERROR)


logger_mock = logger.bind(name="mock_request")
logger_mock.add(log_path_mock, rotation=rotation_handler, encoding="utf-8", enqueue=True, filter=lambda record: record["extra"].get("name", "") == "mock_request")




