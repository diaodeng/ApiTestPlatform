from datetime import datetime

from utils.log_util import logger

from .task_register import register_job


@register_job("module_task.scheduler_test.job")
def job(*args, **kwargs):
    logger.info(args)
    logger.info(kwargs)
    logger.info(f"{datetime.now()}执行了")
