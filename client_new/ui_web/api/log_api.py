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
    "log_tail" 事件：{source, path, lines: [...]}。
    每个来源（local=本地日志 / app=程序日志）各自持有独立线程，互不影响。
    """

    def __init__(self, source: str, file_path: str):
        super().__init__(name=f"log-tail-{source}", daemon=True)
        self.source = source
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
                        event_bus.push(
                            "log_tail",
                            {"source": self.source, "path": self.file_path, "lines": lines},
                        )
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

    本地日志（local）与程序日志（app）两路 tail 相互独立：
    - 每个来源各自维护一个 LogTailThread，启动其中一路不会停止另一路；
    - "log_tail" 事件携带 source 字段，前端据此分发到对应页签。
    """

    def __init__(self):
        # 按来源隔离的 tail 线程：{"local": LogTailThread, "app": LogTailThread}
        self._tails: dict[str, LogTailThread] = {}
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

    def get_app_log_file(self) -> dict:
        """
        返回当前应用日志文件路径（程序日志页监控目标）。

        优先取当天日期命名的日志（logs/YYYY-MM-DD.log，与原版一致）；
        不存在时回退最新的 .log 文件；目录为空返回 ok=False。
        """
        logs_dir = Path("logs")
        if not logs_dir.is_dir():
            return {"ok": False, "message": "logs 目录不存在"}

        today = logs_dir / (time.strftime("%Y-%m-%d") + ".log")
        if today.exists():
            return {"ok": True, "path": str(today)}

        candidates = [
            item for item in logs_dir.glob("*.log") if item.is_file()
        ]
        if not candidates:
            return {"ok": False, "message": "未找到 .log 应用日志文件"}
        latest = max(candidates, key=lambda p: p.stat().st_mtime)
        return {"ok": True, "path": str(latest)}

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

    def start_tail(self, source: str, path: str) -> dict:
        """
        开始增量推送指定来源（local/app）的指定文件日志。

        同一来源重复启动会先停掉旧线程再启动新线程；不同来源互不影响。
        """
        src = str(source or "").strip() or "local"
        self.stop_tail(src)
        with self._lock:
            thread = LogTailThread(src, path)
            self._tails[src] = thread
            thread.start()
        return {"ok": True}

    def stop_tail(self, source: str = "") -> dict:
        """
        停止指定来源的 tail；source 为空时停止所有来源（应用退出清理用）。
        """
        src = str(source or "").strip()
        with self._lock:
            if src:
                threads = [self._tails.pop(src)] if src in self._tails else []
            else:
                threads = list(self._tails.values())
                self._tails.clear()
        for thread in threads:
            thread.stop()
        return {"ok": True}

    def get_tail_status(self) -> dict:
        """
        返回各来源当前的 tail 状态（文件路径、是否在跟踪），供页面恢复现场。
        """
        with self._lock:
            return {
                "ok": True,
                "tails": {
                    src: {"path": thread.file_path, "tailing": True}
                    for src, thread in self._tails.items()
                },
            }

    def shutdown(self) -> dict:
        """
        应用退出时停止全部 tail 线程（Bridge.shutdown 调用）。
        """
        return self.stop_tail()
