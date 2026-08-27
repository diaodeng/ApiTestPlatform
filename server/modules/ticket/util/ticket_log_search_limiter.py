from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager


class TicketLogSearchLimiter:
    """
    控制单进程内同时执行的工单日志搜索数量。
    """

    DEFAULT_LIMIT = 2
    MIN_LIMIT = 1
    MAX_LIMIT = 8

    def __init__(self, default_limit: int = DEFAULT_LIMIT) -> None:
        """
        初始化日志搜索并发限制器。
        :param default_limit: 默认最大并发搜索数
        """
        self._condition = threading.Condition()
        self._local = threading.local()
        self._limit = self._normalize_limit(default_limit)
        self._active = 0

    @classmethod
    def _normalize_limit(cls, value: int | str | None) -> int:
        """
        归一化日志搜索并发上限。
        :param value: 原始并发配置
        :return: 受范围保护的并发上限
        """
        try:
            parsed = int(cls.DEFAULT_LIMIT if value is None else value)
        except (TypeError, ValueError):
            parsed = cls.DEFAULT_LIMIT
        return min(max(parsed, cls.MIN_LIMIT), cls.MAX_LIMIT)

    @contextmanager
    def slot(self, requested_limit: int | str | None = None) -> Iterator[None]:
        """
        获取一个日志搜索执行槽，并在离开作用域时释放。
        :param requested_limit: 当前请求读取到的最大并发搜索数
        :return: 无
        """
        depth = int(getattr(self._local, "depth", 0) or 0)
        if depth > 0:
            self._local.depth = depth + 1
            try:
                yield
            finally:
                self._local.depth = depth
            return

        requested = self._normalize_limit(requested_limit)
        with self._condition:
            self._limit = requested
            self._condition.notify_all()
            while self._active >= self._limit:
                self._condition.wait()
            self._active += 1
            self._local.depth = 1
        try:
            yield
        finally:
            with self._condition:
                self._active -= 1
                self._condition.notify_all()
            self._local.depth = 0

    @property
    def active(self) -> int:
        """
        返回当前已占用的搜索槽数量。
        :return: 正在执行的搜索数量
        """
        with self._condition:
            return self._active

    @property
    def limit(self) -> int:
        """
        返回当前生效的搜索并发上限。
        :return: 最大并发搜索数
        """
        with self._condition:
            return self._limit
