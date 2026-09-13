import json
import threading

from loguru import logger


class EventBus:
    """
    后台线程 → 前端事件推送总线。

    pywebview 中替代原 Qt Signal 的统一出口：任意后台线程通过 push 把事件
    （如 mitm 流量、Agent 状态、日志 tail、更新进度）投递到前端页面。
    前端在 window 上挂全局分发函数 __qtrDispatch(eventName, payloadJson)，
    各页面模块自行订阅，语义与原 Signal 连接一一对应。

    线程安全说明：evaluate_js 本身可在任意线程调用，这里额外用锁保护
    窗口引用的读写，窗口关闭期间静默丢弃事件，避免退出阶段报错。
    """

    def __init__(self):
        self._window = None
        self._lock = threading.Lock()

    def bind(self, window) -> None:
        """
        绑定 pywebview 窗口，绑定后事件才能推送到前端。
        """
        with self._lock:
            self._window = window

    def unbind(self) -> None:
        with self._lock:
            self._window = None

    @property
    def window(self):
        with self._lock:
            return self._window

    def push(self, event: str, payload=None) -> None:
        """
        向前端推送事件。

        :param event: 事件名，前端按此分发（如 "mitm_flow_new"）。
        :param payload: 任意可 JSON 序列化的数据，非序列化字段用 str 兜底。
        """
        window = self.window
        if window is None:
            return

        try:
            payload_json = json.dumps(payload or {}, ensure_ascii=False, default=str)
        except Exception as e:
            logger.warning(f"事件序列化失败 event={event}: {e}")
            return

        try:
            window.evaluate_js(f"window.__qtrDispatch({json.dumps(event)}, {payload_json});")
        except Exception as e:
            # 窗口销毁或 WebView 忙碌时推送失败属正常现象，降级记日志即可。
            logger.debug(f"事件推送失败 event={event}: {e}")


# 模块级单例：所有 api 子模块共享同一个推送出口。
event_bus = EventBus()
