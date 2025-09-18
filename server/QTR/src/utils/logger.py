import os
from loguru import logger


class Logger:
    """
    按日期生成日志文件的日志记录器
    每天自动创建以日期命名的日志文件
    """

    def __init__(self, log_dir="logs", rotation="00:00", retention="30 days"):
        """
        初始化日志记录器
        :param log_dir: 日志目录路径
        :param rotation: 日志轮转时间
        :param retention: 日志保留时间
        """
        self.log_dir = log_dir
        self._ensure_log_dir()

        # 配置日志格式
        log_format = "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {file}:{line} - {message}"

        # 添加文件处理器
        logger.add(
            os.path.join(log_dir, "{time:YYYY-MM-DD}.log"),
            format=log_format,
            rotation=rotation,
            retention=retention,
            encoding="utf-8",
            level="DEBUG"
        )

    def _ensure_log_dir(self):
        """确保日志目录存在"""
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)

    def get_logger(self):
        """获取配置好的logger实例"""
        return logger

log = Logger().get_logger()