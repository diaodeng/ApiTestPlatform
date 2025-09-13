from threading import Timer

from utils.logger import log

# 全局计时器
active_timers = []

def add_timer(timer):
    """新增计时器"""
    active_timers.append(timer)

def add_timer_and_start(interval, function, *args, **kwargs):
    """新增计时器并启动"""
    timer = Timer(interval, function, *args, **kwargs)
    if timer in active_timers:
        log.warning(f"计时器已存在:{timer}")
        return
    active_timers.append(timer)
    timer.start()
    log.info(f"新增计时器并启动:{timer}")

def clear_all_timers():
    """清理所有计时器"""
    for t in active_timers:
        t.cancel()