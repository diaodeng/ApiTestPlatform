import logging
import os
import sys
from os import environ

from loguru import logger

current_file_size = 0
max_file_size = 1024 * 1024 * 1024
log_dir = os.path.join(os.getcwd(), 'logs')
if not os.path.exists(log_dir):
    os.mkdir(log_dir)
env_debug = environ.get("QTRDEBUG", "false").lower() == "true"
log_to_console = environ.get("LOG_TO_CONSOLE", "false").lower() == "true"
level_name = "DEBUG" if env_debug else "INFO"
logger.level(level_name)

logger.remove()
if log_to_console:
    logger.add(sys.stderr)
logger.add(
    os.path.join(log_dir, "{time:YYYY-MM-DD}.log"),
    rotation="00:00",
    encoding="utf-8",
    retention="7 days",
    enqueue=True,
    filter=lambda record: record["extra"].get("name", "") != "mock_request",
)
logger.add(
    os.path.join(log_dir, "error_{time:YYYY-MM-DD}.log"),
    rotation="00:00",
    encoding="utf-8",
    retention="30 days",
    enqueue=True,
    filter=lambda record: record["level"].no >= logging.ERROR,
)


logger_mock = logger.bind(name="mock_request")
logger_mock.add(
    os.path.join(log_dir, "mock_{time:YYYY-MM-DD}.log"),
    rotation="00:00",
    encoding="utf-8",
    retention="7 days",
    enqueue=True,
    filter=lambda record: record["extra"].get("name", "") == "mock_request",
)


# 拦截标准 logging 日志，交给 loguru
class InterceptHandler(logging.Handler):
    def emit(self, record):
        logger_opt = logger.bind(name=record.name).opt(depth=6, exception=record.exc_info)
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


