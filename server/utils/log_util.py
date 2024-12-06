import os
import sys
import time
import asyncio
import datetime

from loguru import logger

log_path = os.path.join(os.getcwd(), 'logs')
if not os.path.exists(log_path):
    os.mkdir(log_path)

def request_id():
    try:
        return asyncio.current_task().get_name()
    except:
        return ''

log_path_error = os.path.join(log_path, f'{time.strftime("%Y-%m-%d")}.log')

logger.remove()
logger.add(sys.stderr)
logger.add(log_path_error, rotation=datetime.timedelta(days=1), encoding="utf-8", enqueue=True)


