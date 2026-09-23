import logging
import os
import sys

from loguru import logger

from utils.common import get_client_root_dir

# 日志目录基准：打包态固定为 exe 所在目录，源码态为 client_new 项目根。
# 不能用 cwd：启动方式导致的 cwd 漂移会让日志散落到其他目录。
_LOG_DIR = str(get_client_root_dir() / "logs")

os.makedirs(_LOG_DIR, exist_ok=True)
is_debug = False
if os.getenv("debug") and os.getenv("debug") == "1":
    is_debug = True

if not is_debug:
    sys.stdout = open(os.path.join(_LOG_DIR, "control.log"), "a", encoding="utf-8", buffering=1)
    sys.stderr = open(os.path.join(_LOG_DIR, "control_error.log"), "a", encoding="utf-8", buffering=1)

    class InterceptHandler(logging.Handler):
        def emit(self, record):
            logger_opt = logger.opt(depth=6, exception=record.exc_info)
            logger_opt.log(record.levelno, record.getMessage())

    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)


class Logger:
    """
    按日期生成日志文件的日志记录器
    每天自动创建以日期命名的日志文件
    """

    retention = "30 days"
    rotation = "00:00"
    log_dir = _LOG_DIR
    log_format = (
        "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {file}:{line} - {message}"
    )

    def __init__(self, log_dir=None, rotation="00:00", retention="30 days"):
        """
        初始化日志记录器
        :param log_dir: 日志目录路径，缺省使用应用根目录下的 logs
        :param rotation: 日志轮转时间
        :param retention: 日志保留时间
        """
        self.log_dir = log_dir or _LOG_DIR
        self._ensure_log_dir()

        self.change_log_level("INFO")

    def _ensure_log_dir(self):
        """确保日志目录存在"""
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)

    def get_logger(self):
        """获取配置好的logger实例"""
        return logger

    @classmethod
    def change_log_level(cls, level):
        logger.remove()
        if is_debug:
            logger.add(sys.stdout, level=level)
        logger.add(
            os.path.join(_LOG_DIR, "{time:YYYY-MM-DD}.log"),
            format=cls.log_format,
            rotation=cls.rotation,
            retention=cls.retention,
            encoding="utf-8",
            level=level,
        )
        # logger.level(level)
        logger.info(f"日志等级已切换为{level}")


log = Logger().get_logger()
