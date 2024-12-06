from utils.log_util import logger
from datetime import datetime


def job(*args, **kwargs):
    logger.info(args)
    logger.info(kwargs)
    logger.info(f"{datetime.now()}执行了")
