import threading


class RuntimeConfig:
    _lock = threading.Lock()
    _config = None

    @classmethod
    def set(cls, config):
        with cls._lock:
            cls._config = config

    @classmethod
    def get(cls):
        with cls._lock:
            return cls._config
