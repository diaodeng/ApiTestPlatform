import logging
import os
import sys
from os import environ

from loguru import logger
from context.request_context import request_id_var

def inject_context(record):
    record["extra"]["request_id"] = request_id_var.get()
    return record

log_formate = "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>[{extra[request_id]}] {message}</level>"

current_file_size = 0
max_file_size = 1024 * 1024 * 1024
log_dir = os.path.join(os.getcwd(), 'logs')
if not os.path.exists(log_dir):
    os.mkdir(log_dir)
env_debug = environ.get("QTRDEBUG", "false").lower() == "true"
log_to_console = environ.get("LOG_TO_CONSOLE", "false").lower() == "true"
level_name = "DEBUG" if env_debug else "INFO"
logger.level(level_name)
use_enqueue = os.name != "nt"

logger.remove()
logger.configure(patcher=inject_context)

if log_to_console:
    logger.add(sys.stderr, format=log_formate)
logger.add(
    os.path.join(log_dir, "{time:YYYY-MM-DD}.log"),
    format=log_formate,
    rotation="00:00",
    encoding="utf-8",
    retention="7 days",
    enqueue=use_enqueue,
    filter=lambda record: record["extra"].get("name", "") != "mock_request",
)
logger.add(
    os.path.join(log_dir, "error_{time:YYYY-MM-DD}.log"),
    format=log_formate,
    rotation="00:00",
    encoding="utf-8",
    retention="30 days",
    enqueue=use_enqueue,
    filter=lambda record: record["level"].no >= logging.ERROR,
)


logger_mock = logger.bind(name="mock_request")
logger_mock.add(
    os.path.join(log_dir, "mock_{time:YYYY-MM-DD}.log"),
    format=log_formate,
    rotation="00:00",
    encoding="utf-8",
    retention="7 days",
    enqueue=use_enqueue,
    filter=lambda record: record["extra"].get("name", "") == "mock_request",
)


# 拦截标准 logging 日志，交给 loguru
class InterceptHandler(logging.Handler):
    def emit(self, record):
        logger_opt = logger.opt(depth=6, exception=record.exc_info).bind(name=record.name,request_id=request_id_var.get())
        logger_opt.log(record.levelname, record.getMessage())

logging.basicConfig(handlers=[InterceptHandler()], level=logging.DEBUG if env_debug else logging.INFO, force=True)
logging.captureWarnings(True)  # 捕获 warnings
# warnings.simplefilter("default")  # 或 "ignore" / "always"
# uvicorn_logger = logging.getLogger("uvicorn")
# uvicorn_logger.handlers = [InterceptHandler()]
# uvicorn_logger.propagate = False
# logging.getLogger("uvicorn.access").handlers = [InterceptHandler()]
# logging.getLogger("uvicorn.error").handlers = [InterceptHandler(level=logging.ERROR)]
# print(logging.getLogger("fastapi").handlers)
# logging.getLogger("fastapi").handlers = [InterceptHandler()]


