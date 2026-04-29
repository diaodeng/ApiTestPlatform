from module_pressure.engines import PressureEngine


class LocustEngine(PressureEngine):
    """Locust 引擎适配器占位，实际启停由 PressureRunService 管理。"""

    def start(self, job):
        """启动 Locust 任务，当前由上层服务实现。"""
        raise NotImplementedError("LocustEngine.start 由 PressureRunService 调用子进程执行器实现")

    def stop(self, job):
        """停止 Locust 任务，当前由上层服务实现。"""
        raise NotImplementedError("LocustEngine.stop 由 PressureRunService 调用子进程执行器实现")

    def status(self, job):
        """查询任务状态，当前由上层服务实现。"""
        raise NotImplementedError("LocustEngine.status 由 PressureRunService 调用子进程执行器实现")

    def metrics(self, job):
        """查询任务指标，当前由上层服务实现。"""
        raise NotImplementedError("LocustEngine.metrics 由 PressureRunService 调用子进程执行器实现")
