from module_pressure.engines.base import PressureEngine


class EngineFactory:
    """多压测引擎工厂占位，当前生产实现由 PressureRunService 调用 Locust 子进程执行器。"""

    @staticmethod
    def get(engine: str):
        """返回引擎标识，后续扩展 k6/JMeter 适配器时保持统一入口。"""
        if engine not in {"locust", "k6", "jmeter"}:
            raise ValueError(f"不支持的压测引擎: {engine}")
        return engine
