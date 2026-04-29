from module_pressure.service.locust_process import LocustProcessController


class LocustControlService:
    """兼容旧代码的 Locust 控制服务入口。"""

    def __init__(self):
        self.controller = LocustProcessController()

    def status(self, port: int) -> dict:
        """读取指定 Locust Web 端口的实时状态。"""
        return self.controller.stats(port=port)

    def stop(self, port: int) -> None:
        """停止指定 Locust Web 端口对应的压测。"""
        self.controller.stop_test(port=port)


locust_service = LocustControlService()
