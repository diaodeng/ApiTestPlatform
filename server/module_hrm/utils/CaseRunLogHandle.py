import logging
from io import StringIO
import threading


log_context = threading.local()


class CustomStackLevelLogger(logging.Logger):
    def __init__(self, name, stacklevel=2):
        super().__init__(name)
        self.stacklevel = stacklevel

    def _log_with_stacklevel(self, level, msg, args, exc_info=None, extra=None, stack_info=False):
        self._log(level, msg, args, exc_info, extra, stack_info, stacklevel=self.stacklevel)

    def debug(self, msg, *args, **kwargs):
        self._log_with_stacklevel(logging.DEBUG, msg, args, **kwargs)

    def info(self, msg, *args, **kwargs):
        self._log_with_stacklevel(logging.INFO, msg, args, **kwargs)

    def warning(self, msg, *args, **kwargs):
        self._log_with_stacklevel(logging.WARNING, msg, args, **kwargs)

    def error(self, msg, *args, **kwargs):
        self._log_with_stacklevel(logging.ERROR, msg, args, **kwargs)

    def critical(self, msg, *args, **kwargs):
        self._log_with_stacklevel(logging.CRITICAL, msg, args, **kwargs)


class RunLogCaptureHandler(logging.Handler):
    """
    执行用例的时候单独获取日志的处理器
    """
    def __init__(self):
        super().__init__()
        self.log_capture_string = StringIO()
        self.setFormatter(logging.Formatter('%(asctime)s | %(levelname)-8s | %(name)s:%(module)s:%(funcName)s:%(lineno)d - %(message)s'))

    def emit(self, record):
        log_entry = self.format(record)
        self.log_capture_string.write(log_entry + '\n')

    def get_log(self):
        log_data = self.log_capture_string.getvalue()
        self.log_capture_string.seek(0)
        self.log_capture_string.truncate(0)
        return log_data

    def reset(self):
        self.log_capture_string = StringIO()


class TestLog:
    def __init__(self):
        self.logger_name = f'test_logger_{threading.get_ident()}'
        # self.logger = logging.getLogger(f'{self.logger_name}')

        self.logger = CustomStackLevelLogger(self.logger_name, 3)

        self.logger.setLevel(logging.DEBUG)
        self.handler = RunLogCaptureHandler()
        self.logger.addHandler(self.handler)

        log_context.logger = self.logger
        log_context.handler = self.handler

    def get_logger(self):
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

    def add_handler(self):
        handler = RunLogCaptureHandler()
        self.logger.addHandler(self.handler)
        return handler