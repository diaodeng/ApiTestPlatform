class PosManager:
    _instance = None

    def __init__(self):
        self.current = None  # {path, pid}

    @classmethod
    def instance(cls):
        if not cls._instance:
            cls._instance = cls()
        return cls._instance

    def set_running(self, path, pid):
        self.current = {"path": path, "pid": pid}

    def clear(self):
        self.current = None

    def get(self):
        return self.current
