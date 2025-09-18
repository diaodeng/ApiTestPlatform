from multiprocessing import Manager
from queue import Queue

_manager = None
_shared = None
_local_log_queue = Queue()

def get_shared():
    global _manager, _shared
    if _shared is None:  # 只初始化一次
        _manager = Manager()
        _shared = _manager.dict()
    return _shared

def get_local_log_queue():
    global _local_log_queue
    return _local_log_queue
