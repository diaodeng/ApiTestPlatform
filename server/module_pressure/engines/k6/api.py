from module_pressure.engines import PressureEngine


class K6Engine(PressureEngine):
    """k6 引擎适配器占位，用于保留统一引擎抽象。"""

    def start(self, job):
        """启动 k6 任务，后续扩展实现。"""
        raise NotImplementedError("k6 引擎尚未接入")

    def stop(self, job):
        """停止 k6 任务，后续扩展实现。"""
        raise NotImplementedError("k6 引擎尚未接入")

    def status(self, job):
        """查询 k6 任务状态，后续扩展实现。"""
        raise NotImplementedError("k6 引擎尚未接入")

    def metrics(self, job):
        """查询 k6 指标，后续扩展实现。"""
        raise NotImplementedError("k6 引擎尚未接入")
