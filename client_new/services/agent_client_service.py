import asyncio
import json
import threading
import traceback
from collections import defaultdict
from collections.abc import Callable
from typing import Any

from loguru import logger

from model.config import AgentConfigModel

_AGENT_SERVER_MODULE = None
# 重型模块导入锁：首次导入 server.agent_server 约需 1.5 秒（含 playwright、
# pyautogui、cv2 等重依赖），必须保证只在后台线程发生一次，避免 UI 线程卡顿。
_AGENT_SERVER_LOCK = threading.Lock()


def _agent_server_module():
    global _AGENT_SERVER_MODULE
    # 已导入时直接返回，避免无谓的锁竞争。
    if _AGENT_SERVER_MODULE is not None:
        return _AGENT_SERVER_MODULE
    with _AGENT_SERVER_LOCK:
        if _AGENT_SERVER_MODULE is None:
            from server import agent_server

            _AGENT_SERVER_MODULE = agent_server
        return _AGENT_SERVER_MODULE


def _websocket_client_class():
    return getattr(_agent_server_module(), "WebSocketClient")


class AgentClientService:
    """
    Agent 通信服务（pywebview 版，纯 Python 实现）。

    原 PySide6 版本基于 QObject + Signal 向界面推送事件；迁移到 pywebview 后
    改为监听器回调注册制：界面桥接层通过 add_listener 订阅事件，回调里再经
    EventBus 推送到前端。事件名保持与原 Signal 同名，语义一致：

    - state_changed: 连接状态（stopped/starting/running/stopping）
    - status_message: 状态提示文本
    - request_message / response_message: 请求/响应日志（JSON 文本）
    - error_message: 错误信息
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._client: Any | None = None
        self._state = "stopped"
        self._stop_requested = False
        self._listeners: dict[str, list[Callable]] = defaultdict(list)

    # ===== 事件订阅 =====

    def add_listener(self, event: str, callback: Callable) -> None:
        """
        注册事件监听器。

        :param event: 事件名（state_changed/status_message/request_message/response_message/error_message）
        :param callback: 回调函数，签名 callback(*args)
        """
        with self._lock:
            listeners = list(self._listeners[event])
        if callback not in listeners:
            with self._lock:
                self._listeners[event].append(callback)

    def remove_listener(self, event: str, callback: Callable) -> None:
        with self._lock:
            listeners = self._listeners.get(event)
            if callback in listeners:
                listeners.remove(callback)

    def _emit(self, event: str, *args) -> None:
        """
        向所有订阅者分发事件；回调异常只记录日志，不影响服务主流程。
        """
        with self._lock:
            listeners = list(self._listeners.get(event, ()))
        for callback in listeners:
            try:
                callback(*args)
            except Exception as e:
                logger.exception(f"Agent 服务事件回调异常 event={event}: {e}")

    @property
    def state(self) -> str:
        with self._lock:
            return self._state

    def is_running(self) -> bool:
        """
        是否存在存活的后台连接线程（用于区分"连接准备中"与"已启动连接"）。
        """
        with self._lock:
            return bool(self._thread and self._thread.is_alive())

    def start(self, config: AgentConfigModel, connect_url: str) -> tuple[bool, str]:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return False, f"Agent 当前状态为 {self._state}"

            self._stop_requested = False
            self._state = "starting"

        self._emit("state_changed", "starting")
        self._emit("status_message", f"开始连接服务器：{connect_url}")

        config_copy = config.model_copy(deep=True)
        thread = threading.Thread(
            target=self._thread_main,
            args=(config_copy, connect_url),
            name="agent-client-loop",
            daemon=True,
        )

        with self._lock:
            self._thread = thread

        thread.start()
        return True, "Agent 连接中"

    def stop(self) -> tuple[bool, str]:
        with self._lock:
            thread = self._thread
            loop = self._loop
            client = self._client

            if not thread or not thread.is_alive():
                self._state = "stopped"
                return True, "Agent 已停止"

            if self._state == "stopping":
                return True, "Agent 停止中"

            self._state = "stopping"
            self._stop_requested = True

        self._emit("state_changed", "stopping")
        self._emit("status_message", "正在断开 Agent 连接...")

        if loop and client:
            try:
                asyncio.run_coroutine_threadsafe(client.send_close(), loop)
            except Exception as e:
                logger.exception(f"停止 Agent 客户端失败: {e}")
                self._emit("error_message", f"停止 Agent 客户端失败: {e}")

        return True, "Agent 停止请求已发送"

    def update_runtime_config(self, config: AgentConfigModel):
        # 仅在通信模块已加载时同步分片配置；模块未加载说明还没有连接过，
        # 此时不在界面线程触发首次导入（约 1.5 秒），保存配置等动作会另行处理。
        if _AGENT_SERVER_MODULE is not None:
            try:
                agent_server_module = _agent_server_module()
                agent_server_module.MAX_MESSAGE_SIZE = (
                    agent_server_module.clamp_message_size(config.max_send_size)
                )
            except Exception as e:
                logger.warning(f"更新 Agent 通信配置失败: {e}")

        with self._lock:
            client = self._client

        if client:
            client.retry = config.retry
            client.max_retry_num = config.retry_times
            client.interval_time = config.retry_interval
            client.retry_forever = config.retry_forever
            client.retry_forever_interval = config.retry_forever_interval

    def shutdown(self, timeout: float = 5.0) -> tuple[bool, str]:
        ok, message = self.stop()

        thread = None
        with self._lock:
            thread = self._thread

        if thread and thread.is_alive():
            thread.join(timeout=timeout)
            if thread.is_alive():
                ok = False
                message = "Agent 关闭超时"

        return ok, message

    def _thread_main(self, config: AgentConfigModel, connect_url: str):
        # 重型模块首次导入统一放在本后台线程执行，避免阻塞界面线程。
        try:
            agent_server_module = _agent_server_module()
            agent_server_module.MAX_MESSAGE_SIZE = agent_server_module.clamp_message_size(
                config.max_send_size
            )
        except Exception as e:
            logger.exception(f"加载 Agent 通信模块失败: {e}")
            with self._lock:
                self._loop = None
                self._client = None
                self._thread = None
                self._state = "stopped"
                self._stop_requested = False
            self._emit("state_changed", "stopped")
            self._emit("error_message", f"加载 Agent 通信模块失败: {e}")
            return

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        with self._lock:
            self._loop = loop

        client_cls = _websocket_client_class()
        client = client_cls(
            connect_url,
            before_request_call=self._handle_before_request,
            after_request_call=self._handle_after_request,
            status_callback=self._handle_client_status,
        )

        with self._lock:
            self._client = client

        try:
            loop.run_until_complete(
                client.connect(
                    connect_url,
                    retry=config.retry,
                    retry_num=config.retry_times,
                    interval_time=config.retry_interval,
                    retry_forever=config.retry_forever,
                    retry_forever_interval=config.retry_forever_interval,
                )
            )
        except Exception as e:
            logger.exception(f"Agent 客户端线程异常: {e}")
            self._emit("error_message", f"Agent 客户端异常: {e}")
            self._emit("status_message", str(e))
            logger.debug(traceback.format_exc())
        finally:
            terminal_state = None
            stop_requested = False
            with self._lock:
                terminal_state = self._state
                stop_requested = self._stop_requested

            try:
                pending = asyncio.all_tasks(loop)
                for task in pending:
                    task.cancel()
                if pending:
                    loop.run_until_complete(
                        asyncio.gather(*pending, return_exceptions=True)
                    )
            except Exception:
                pass
            finally:
                loop.close()

            with self._lock:
                self._loop = None
                self._client = None
                self._thread = None
                self._state = "stopped"
                self._stop_requested = False

            self._emit("state_changed", "stopped")
            if stop_requested or terminal_state in {"running", "stopping"}:
                self._emit("status_message", "Agent 已断开")

    def _handle_before_request(self, data: dict):
        self._emit("request_message", self._format_object(data))

    def _handle_after_request(self, data: dict):
        if not isinstance(data, dict):
            self._emit("response_message", self._format_object(data))
            return

        payload = data.get("text")
        if isinstance(payload, str):
            try:
                self._emit(
                    "response_message",
                    json.dumps(json.loads(payload), ensure_ascii=False, indent=2),
                )
                return
            except Exception:
                pass

        self._emit("response_message", self._format_object(payload or data))

    def _handle_client_status(self, event_type: str, message: str):
        logger.info(f"Agent 状态[{event_type}] {message}")
        self._emit("status_message", message)

        if event_type == "connected":
            with self._lock:
                self._state = "running"
            self._emit("state_changed", "running")
            return

        if event_type == "retry":
            with self._lock:
                self._state = "starting"
            self._emit("state_changed", "starting")
            return

        if event_type == "error":
            self._emit("error_message", message)

    def _format_object(self, data) -> str:
        if data in (None, ""):
            return ""
        if isinstance(data, str):
            return data
        try:
            return json.dumps(data, ensure_ascii=False, indent=2)
        except Exception:
            return str(data)
