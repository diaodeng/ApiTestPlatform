JOB_REGISTRY = {}


def register_job(name):
    def decorator(func):
        if name in JOB_REGISTRY:
            raise KeyError(f"任务id重复：{name}")
        JOB_REGISTRY[name] = func
        return func
    return decorator