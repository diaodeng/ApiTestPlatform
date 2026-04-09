import asyncio
import json
import threading
import traceback

from loguru import logger
from PySide6.QtCore import QObject, Signal

from model.config import AgentConfigModel

_AGENT_SERVER_MODULE = None


def _agent_server_module():
    global _AGENT_SERVER_MODULE
    if _AGENT_SERVER_MODULE is None:
        from server import agent_server

        _AGENT_SERVER_MODULE = agent_server
    return _AGENT_SERVER_MODULE


def _websocket_client_class():
    return getattr(_agent_server_module(), "WebSocketClient")


class AgentClientService(QObject):
    state_changed = Signal(str)
    status_message = Signal(str)
    request_message = Signal(str)
    response_message = Signal(str)
    error_message = Signal(str)

    def __init__(self):
        super().__init__()
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._client: WebSocketClient | None = None
        self._state = "stopped"
        self._stop_requested = False

    @property
    def state(self) -> str:
        with self._lock:
            return self._state

    def start(self, config: AgentConfigModel, connect_url: str) -> tuple[bool, str]:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return False, f"Agent 当前状态为 {self._state}"

            self._stop_requested = False
            self._state = "starting"

        try:
            agent_server_module = _agent_server_module()
            agent_server_module.MAX_MESSAGE_SIZE = agent_server_module.clamp_message_size(
                config.max_send_size
            )
        except Exception as e:
            logger.exception(f"加载 Agent 通信模块失败: {e}")
            with self._lock:
                self._state = "stopped"
            self.state_changed.emit("stopped")
            return False, f"加载 Agent 通信模块失败: {e}"

        self.state_changed.emit("starting")
        self.status_message.emit(f"开始连接服务器：{connect_url}")

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

        self.state_changed.emit("stopping")
        self.status_message.emit("正在断开 Agent 连接...")

        if loop and client:
            try:
                asyncio.run_coroutine_threadsafe(client.send_close(), loop)
            except Exception as e:
                logger.exception(f"停止 Agent 客户端失败: {e}")
                self.error_message.emit(f"停止 Agent 客户端失败: {e}")

        return True, "Agent 停止请求已发送"

    def update_runtime_config(self, config: AgentConfigModel):
        try:
            agent_server_module = _agent_server_module()
            agent_server_module.MAX_MESSAGE_SIZE = agent_server_module.clamp_message_size(
                config.max_send_size
            )
        except Exception as e:
            logger.warning(f"更新 Agent 通信配置失败: {e}")

        with self._lock:
            client = self._client

        if client:
            client.retry = config.retry
            client.max_retry_num = config.retry_times
            client.interval_time = config.retry_interval

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
                )
            )
        except Exception as e:
            logger.exception(f"Agent 客户端线程异常: {e}")
            self.error_message.emit(f"Agent 客户端异常: {e}")
            self.status_message.emit(str(e))
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

            self.state_changed.emit("stopped")
            if stop_requested or terminal_state in {"running", "stopping"}:
                self.status_message.emit("Agent 已断开")

    def _handle_before_request(self, data: dict):
        self.request_message.emit(self._format_object(data))

    def _handle_after_request(self, data: dict):
        if not isinstance(data, dict):
            self.response_message.emit(self._format_object(data))
            return

        payload = data.get("text")
        if isinstance(payload, str):
            try:
                self.response_message.emit(
                    json.dumps(json.loads(payload), ensure_ascii=False, indent=2)
                )
                return
            except Exception:
                pass

        self.response_message.emit(self._format_object(payload or data))

    def _handle_client_status(self, event_type: str, message: str):
        logger.info(f"Agent 状态[{event_type}] {message}")
        self.status_message.emit(message)

        if event_type == "connected":
            with self._lock:
                self._state = "running"
            self.state_changed.emit("running")
            return

        if event_type == "retry":
            with self._lock:
                self._state = "starting"
            self.state_changed.emit("starting")
            return

        if event_type == "error":
            self.error_message.emit(message)

    def _format_object(self, data) -> str:
        if data in (None, ""):
            return ""
        if isinstance(data, str):
            return data
        try:
            return json.dumps(data, ensure_ascii=False, indent=2)
        except Exception:
            return str(data)
