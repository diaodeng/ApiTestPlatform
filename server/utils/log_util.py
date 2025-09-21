import logging
import os
import sys
import time
import asyncio
import datetime

from loguru import logger

log_dir = os.path.join(os.getcwd(), 'logs')
if not os.path.exists(log_dir):
    os.mkdir(log_dir)

def request_id():
    try:
        return asyncio.current_task().get_name()
    except:
        return ''

log_path = os.path.join(log_dir, f'{time.strftime("%Y-%m-%d")}.log')
log_path_error = os.path.join(log_dir, f'error_{time.strftime("%Y-%m-%d")}.log')
log_path_mock = os.path.join(log_dir, f'mock_{time.strftime("%Y-%m-%d")}_test.log')

logger.remove()
logger.add(sys.stderr)
logger.add(log_path, rotation=datetime.timedelta(days=1), encoding="utf-8", enqueue=True, filter=lambda record: record["extra"].get("name", "") != "mock_request")
logger.add(log_path_error, rotation=datetime.timedelta(days=1), encoding="utf-8", enqueue=True, filter=lambda record: record["level"].no >= logging.ERROR)


logger_mock = logger.bind(name="mock_request")
logger_mock.add(log_path_mock, rotation=datetime.timedelta(days=1), encoding="utf-8", enqueue=True, filter=lambda record: record["extra"].get("name", "") == "mock_request")




