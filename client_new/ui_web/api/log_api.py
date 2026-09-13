import os
import threading
import time
from pathlib import Path

from loguru import logger

from ui_web.event_bus import event_bus

# 日志 tail 轮询间隔（秒），与原 _FileTailThread 一致。
_POLL_INTERVAL = 0.25
# 单行截断上限（字符），避免超长行刷爆界面（原值 16KB）。
_MAX_LINE_LENGTH = 16 * 1024


class LogTailThread(threading.Thread):
    """
    日志文件 tail 线程（替代原 Qt _FileTailThread）。

    按 offset 增量读取文件新增内容，整批经 EventBus 推送
    "log_tail" 事件：{path, lines: [...], eof: bool}。
    """

    def __init__(self, file_path: str):
        super().__init__(name="log-tail", daemon=True)
        self.file_path = file_path
        self._stop_event = threading.Event()

    def run(self):
        offset = 0
        logger.info(f"开始 tail 日志文件: {self.file_path}")
        try:
            # 首次启动先跳过历史内容，只看新增（与原实现一致：从末尾开始）。
            offset = os.path.getsize(self.file_path)
        except OSError:
            offset = 0

        while not self._stop_event.is_set():
            try:
                size = os.path.getsize(self.file_path)
                if size < offset:
                    # 文件被轮转/清空，从头开始读
                    offset = 0
                if size > offset:
                    lines = self._read_new_lines(offset)
                    if lines:
                        event_bus.push("log_tail", {"path": self.file_path, "lines": lines})
                    offset = size
            except FileNotFoundError:
                pass
            except Exception as e:
                logger.debug(f"tail 读取异常: {e}")
            self._stop_event.wait(_POLL_INTERVAL)
        logger.info(f"停止 tail 日志文件: {self.file_path}")

    def _read_new_lines(self, offset: int) -> list[str]:
        with open(self.file_path, "r", encoding="utf-8", errors="replace") as f:
            f.seek(offset)
            content = f.read()
        lines = [self._truncate(line) for line in content.splitlines() if line.strip()]
        return lines

    @staticmethod
    def _truncate(line: str) -> str:
        if len(line) <= _MAX_LINE_LENGTH:
            return line
        return line[:_MAX_LINE_LENGTH] + " ...(已截断)"

    def stop(self):
        self._stop_event.set()


class LogApi:
    """
    日志页面后端桥（替代原 Qt 页面的本地文件 tail 与应用日志列表）。

    原 SSH 页签在旧版本即为占位（提示“未实现”），本次迁移不再保留。
    """

    def __init__(self):
        self._tail_thread: LogTailThread | None = None
        self._lock = threading.Lock()

    def list_log_files(self) -> dict:
        """
        列出应用 logs 目录下的日志文件（名称、路径、大小、修改时间）。
        """
        logs_dir = Path("logs")
        files = []
        if logs_dir.is_dir():
            for item in sorted(logs_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
                if item.is_file():
                    try:
                        stat = item.stat()
                        files.append(
                            {
                                "name": item.name,
                                "path": str(item),
                                "size": stat.st_size,
                                "mtime": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime)),
                            }
                        )
                    except OSError:
                        continue
        return {"ok": True, "files": files}

    def read_head(self, path: str, max_lines: int = 500) -> dict:
        """
        读取日志文件末尾若干行，用于打开文件时先展示近期内容。
        """
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            tail_lines = [line.rstrip("\n") for line in lines[-max_lines:]]
            return {"ok": True, "lines": tail_lines}
        except Exception as e:
            logger.exception(f"读取日志文件失败: {e}")
            return {"ok": False, "message": str(e)}

    def start_tail(self, path: str) -> dict:
        """
        开始增量推送指定文件的日志（先停止旧任务）。
        """
        self.stop_tail()
        with self._lock:
            self._tail_thread = LogTailThread(path)
            self._tail_thread.start()
        return {"ok": True}

    def stop_tail(self) -> dict:
        with self._lock:
            thread = self._tail_thread
            self._tail_thread = None
        if thread:
            thread.stop()
        return {"ok": True}
