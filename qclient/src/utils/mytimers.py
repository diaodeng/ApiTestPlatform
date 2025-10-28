from threading import Timer
from concurrent.futures import ThreadPoolExecutor, as_completed
from utils.logger import log
import threading

thread_tasks = []

_thread_pool = None


# 全局计时器
_active_timers = []

def add_timer(timer):
    """新增计时器"""
    _active_timers.append(timer)

def add_timer_and_start(interval, function, *args, **kwargs):
    """新增计时器并启动"""

    timer = Timer(interval, function, *args, **kwargs)
    if timer in _active_timers:
        log.warning(f"计时器已存在:{timer}")
        return
    _active_timers.append(timer)
    timer.start()
    log.info(f"新增计时器并启动:{timer}")

def clear_all_timers():
    """清理所有计时器"""
    for task in thread_tasks:
        task.cancel()
    for t in _active_timers:
        t.cancel()
    _active_timers.clear()
    thread_tasks.clear()
    log.info("所有计时器已取消并清除")


class ThreadPool:
    @classmethod
    def thread_pool(cls) -> ThreadPoolExecutor:
        global _thread_pool
        if _thread_pool is None:
            _thread_pool = ThreadPoolExecutor(max_workers=10)
        return _thread_pool

    @classmethod
    def add_thread_task(cls, func, *args, **kwargs):
        """
        添加一个任务到线程池
        :param func: 要执行的函数
        :param args: 传给 func 的位置参数
        :param kwargs: 传给 func 的关键字参数
        :return: Future 对象
        """
        future = cls.thread_pool().submit(func, *args, **kwargs)
        thread_tasks.append(future)
        return future

    @classmethod
    def add_task(cls, func, interval, count=None, *args, **kwargs):
        """
        添加一个重复执行的任务到线程池
        :param func: 要执行的函数
        :param interval: 每次执行间隔（秒）
        :param count: 执行次数（None 表示无限循环）
        :param args: 传给 func 的位置参数
        :param kwargs: 传给 func 的关键字参数
        :return: Future 对象
        """
        future = RepeatedTask(func, interval, count, *args, **kwargs)
        thread_tasks.append(future)
        future.start()
        return future


class RepeatedTask(threading.Thread):
    def __init__(self, func, interval, count=None, *args, **kwargs):
        """
        :param func: 要执行的函数
        :param interval: 每次执行间隔（秒）
        :param count: 执行次数（None 表示无限循环）
        :param args: 传给 func 的位置参数
        :param kwargs: 传给 func 的关键字参数
        """
        super().__init__()
        self.func = func
        self.interval = interval
        self.count = count
        self.args = args
        self.kwargs = kwargs
        self._cancel_event = threading.Event()

    def run(self):
        executed = 0
        while not self._cancel_event.is_set():
            # 检查次数
            if self.count is not None and executed >= self.count:
                break

            # 执行任务
            self.func(*self.args, **self.kwargs)
            executed += 1

            # 等待间隔，但允许随时取消
            if self._cancel_event.wait(self.interval):
                break

    def cancel(self):
        """立即停止任务"""
        self._cancel_event.set()