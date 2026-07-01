import logging
import os
import sys
from os import environ
from datetime import datetime

from loguru import logger
from context.request_context import request_id_var


log_formate = "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>[{extra[request_id]}] {message}</level>"

current_file_size = 0
max_file_size = 1024 * 1024 * 1024
log_dir = os.path.join(os.getcwd(), 'logs')
if not os.path.exists(log_dir):
    os.mkdir(log_dir)
env_debug = environ.get("QTRDEBUG", "false").lower() == "true"
log_to_console = environ.get("LOG_TO_CONSOLE", "false").lower() == "true"
level_name = "DEBUG" if env_debug else "INFO"
use_enqueue = os.name != "nt"

# 存储 sink ID 用于动态修改日志级别
_main_sink_id = None
_error_sink_id = None
_console_sink_id = None
_current_level = level_name


def get_log_path(name="app"):
    date = datetime.now().strftime("%Y-%m-%d")
    day_dir = os.path.join(log_dir, date)

    os.makedirs(day_dir, exist_ok=True)

    return os.path.join(day_dir, f"{name}.log")

def inject_context(record):
    record["extra"]["request_id"] = request_id_var.get()
    return record

logger.remove()
logger.configure(patcher=inject_context)

if log_to_console:
    _console_sink_id = logger.add(sys.stderr, format=log_formate)

_main_sink_id = logger.add(
    get_log_path(),
    format=log_formate,
    level=level_name,
    rotation="500 MB",
    diagnose=False,
    backtrace=False,
    encoding="utf-8",
    retention="7 days",
    enqueue=use_enqueue,
    filter=lambda record: record["extra"].get("name", "") != "mock_request",
)
_error_sink_id = logger.add(
    get_log_path(name="error"),
    format=log_formate,
    level=level_name,
    rotation="500 MB",
    diagnose=False,
    backtrace=False,
    encoding="utf-8",
    retention="30 days",
    enqueue=use_enqueue,
    filter=lambda record: record["level"].no >= logging.ERROR,
)


logger_mock = logger.bind(name="mock_request")
_mock_sink_id = logger_mock.add(
    get_log_path(name="mock"),
    format=log_formate,
    level=level_name,
    rotation="500 MB",
    diagnose=False,
    backtrace=False,
    encoding="utf-8",
    retention="7 days",
    enqueue=use_enqueue,
    filter=lambda record: record["extra"].get("name", "") == "mock_request",
)


def set_log_level(level: str):
    """
    动态修改 loguru 日志级别，支持运行时在 DEBUG/INFO/WARNING/ERROR/CRITICAL 之间切换。
    主要用于生产环境排查问题时临时开启 DEBUG 日志。
    """
    global _current_level, _main_sink_id, _error_sink_id, _console_sink_id, _mock_sink_id

    level = level.upper()
    if level == _current_level:
        return

    _current_level = level

    # --- 重建主日志 sink ---
    if _main_sink_id is not None:
        logger.remove(_main_sink_id)
    _main_sink_id = logger.add(
        get_log_path(),
        format=log_formate,
        level=level,
        rotation="500 MB",
        diagnose=False,
        backtrace=False,
        encoding="utf-8",
        retention="7 days",
        enqueue=use_enqueue,
        filter=lambda record: record["extra"].get("name", "") != "mock_request",
    )

    # --- 重建错误日志 sink ---
    if _error_sink_id is not None:
        logger.remove(_error_sink_id)
    _error_sink_id = logger.add(
        get_log_path(name="error"),
        format=log_formate,
        level=level,
        rotation="500 MB",
        diagnose=False,
        backtrace=False,
        encoding="utf-8",
        retention="30 days",
        enqueue=use_enqueue,
        filter=lambda record: record["level"].no >= logging.ERROR,
    )

    # --- 重建 mock 日志 sink ---
    if _mock_sink_id is not None:
        logger_mock.remove(_mock_sink_id)
    _mock_sink_id = logger_mock.add(
        get_log_path(name="mock"),
        format=log_formate,
        level=level,
        rotation="500 MB",
        diagnose=False,
        backtrace=False,
        encoding="utf-8",
        retention="7 days",
        enqueue=use_enqueue,
        filter=lambda record: record["extra"].get("name", "") == "mock_request",
    )

    # --- 同步更新标准 logging 根级别 + InterceptHandler 重定向 ---
    log_level_num = getattr(logging, level, logging.INFO)
    logging.root.setLevel(log_level_num)

    logger.info(f"日志级别已动态切换为: {level}")


def get_loguru_level() -> str:
    """获取当前 loguru 日志级别"""
    return _current_level


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


