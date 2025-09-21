import logging
from io import StringIO
import threading
from utils.log_util import logger
import asyncio


log_context = threading.local()


class CustomStackLevelLogger(logging.Logger):
    def __init__(self, name, stacklevel=2):
        super().__init__(name)
        self.stacklevel = stacklevel
        self.task_id = asyncio.current_task().get_name()

    def _log_with_stacklevel(self, level, msg, args, exc_info=None, extra=None, stack_info=False):
        self._log(level, f"{msg}", args, exc_info, extra, stack_info, stacklevel=self.stacklevel)

    def debug(self, msg, *args, **kwargs):
        logger.opt(depth=1).debug(f"[{self.task_id}]{msg}", *args, **kwargs)
        self._log_with_stacklevel(logging.DEBUG, msg, args, **kwargs)

    def info(self, msg, *args, **kwargs):
        logger.opt(depth=1).info(f"[{self.task_id}]{msg}", *args, **kwargs)
        self._log_with_stacklevel(logging.INFO, msg, args, **kwargs)

    def warning(self, msg, *args, **kwargs):
        logger.opt(depth=1).warning(f"[{self.task_id}]{msg}", *args, **kwargs)
        self._log_with_stacklevel(logging.WARNING, msg, args, **kwargs)

    def error(self, msg, *args, **kwargs):
        logger.opt(depth=1).error(f"[{self.task_id}]{msg}", *args, **kwargs)
        self._log_with_stacklevel(logging.ERROR, msg, args, **kwargs)

    def critical(self, msg, *args, **kwargs):
        logger.opt(depth=1).critical(f"[{self.task_id}]{msg}", *args, **kwargs)
        self._log_with_stacklevel(logging.CRITICAL, msg, args, **kwargs)

    def exception(self, msg, *args, **kwargs):
        logger.opt(depth=1).exception(f"[{self.task_id}]{msg}", *args, **kwargs)
        self._log_with_stacklevel(logging.ERROR, msg, args, **kwargs)


class RunLogCaptureHandler(logging.Handler):
    """
    执行用例的时候单独获取日志的处理器
    """
    def __init__(self):
        super().__init__()
        self.log_capture_string = StringIO()
        self.log_lock = threading.Lock()
        self.setFormatter(logging.Formatter('%(asctime)s | %(levelname)-8s | %(module)s:%(funcName)s:%(lineno)d - %(message)s'))

    def emit(self, record):
        log_entry = self.format(record)
        with self.log_lock:
            self.log_capture_string.write(log_entry + '\n')

    def get_log(self):
        with self.log_lock:
            log_data = self.log_capture_string.getvalue()
            self.log_capture_string.seek(0)
            self.log_capture_string.truncate(0)
        return log_data

    def reset(self):
        self.log_capture_string = StringIO()


class TestLog:
    def __init__(self, logger_name=None, log_level=logging.INFO):
        self.logger_name = f'test_logger_{threading.get_ident()}'
        # self.logger = logging.getLogger(f'{self.logger_name}')

        self.logger = CustomStackLevelLogger(self.logger_name, 2)

        self.logger.setLevel(log_level)
        self.handler = RunLogCaptureHandler()
        self.handler.setLevel(log_level)
        self.logger.addHandler(self.handler)

        log_context.logger = self.logger
        log_context.handler = self.handler

    def get_logger(self) -> CustomStackLevelLogger:
        return self.logger

    def get_log(self):
        log_contents = self.handler.get_log()
        return log_contents

    def reset(self):
        """
        重置资源logger
        """
        self.logger.removeHandler(self.handler)
        self.handler.close()

        del self.logger
        del self.handler

    def remove_handler(self, handler):
        self.logger.removeHandler(handler)
        handler.close()
        del handler

    def add_handler(self, handler: RunLogCaptureHandler):
        self.logger.addHandler(handler)
        return handler