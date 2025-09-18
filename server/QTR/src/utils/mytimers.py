
# 全局计时器
active_timers = []

def add_timer(timer):
    """新增计时器"""
    active_timers.append(timer)

def clear_all_timers():
    """清理所有计时器"""
    for t in active_timers:
        t.cancel()