from loguru import logger
from PySide6.QtCore import QObject, QThread, QTimer, Signal

from model.config import AgentConfigModel
from server.config import AgentConfig
from server.remote_config_server import RemoteConfigServer
from services.agent_client_service import AgentClientService
from utils.common import get_active_mac


class _ConfigSyncThread(QThread):
    done = Signal(bool, object, str)

    def __init__(self, config_url: str):
        super().__init__()
        self.config_url = (config_url or "").strip()

    def run(self):
        try:
            result = RemoteConfigServer.sync_agent_config(self.config_url)
            self.done.emit(True, result, "")
        except Exception as e:
            logger.exception(e)
            self.done.emit(False, None, str(e))


class _LocalMacThread(QThread):
    done = Signal(str)

    def run(self):
        try:
            mac = get_active_mac() or ""
        except Exception as e:
            logger.exception(f"获取本机 MAC 失败: {e}")
            mac = ""
        self.done.emit(mac)


class AgentController(QObject):
    def __init__(self, widget):
        super().__init__()
        self.widget = widget
        self.config = AgentConfig.read_config()
        self.local_mac = ""
        self.connection_state = "stopped"
        self.service = AgentClientService()
        self._config_sync_thread: _ConfigSyncThread | None = None
        self._local_mac_thread: _LocalMacThread | None = None

        self._bind_widget()
        self._bind_service()

        self.widget.apply_config(self.config, self.connection_state, self.local_mac)
        self.widget.set_running(False)
        self.widget.set_status_message("就绪")
        QTimer.singleShot(0, self._refresh_local_mac_async)

    def _bind_widget(self):
        self.widget.start_clicked.connect(self.start)
        self.widget.stop_clicked.connect(self.stop)
        self.widget.save_clicked.connect(self.save)
        self.widget.sync_config_clicked.connect(self.sync_config)

    def _bind_service(self):
        self.service.state_changed.connect(self._on_service_state_changed)
        self.service.status_message.connect(self._on_service_status)
        self.service.request_message.connect(self._on_service_request)
        self.service.response_message.connect(self._on_service_response)
        self.service.error_message.connect(self._on_service_error)

    def start(self):
        self.local_mac = get_active_mac() or self.local_mac
        if hasattr(self.widget, "set_local_mac"):
            self.widget.set_local_mac(self.local_mac)
        self.config = AgentConfig.read_config()

        if self.connection_state in {"starting", "running", "stopping"}:
            logger.warning(f"Agent 启动请求被忽略，当前状态: {self.connection_state}")
            return

        server = (self.config.current_server or "").strip()
        if not server:
            self.widget.set_status_message("请先输入或选择服务地址")
            return

        connect_url = self._build_connect_url(server)
        logger.info(f"启动 Agent 连接: {connect_url}")

        self.connection_state = "starting"
        self._sync_ui_state()

        ok, message = self.service.start(self.config, connect_url)
        if not ok:
            logger.warning(message)
            self.connection_state = "stopped"
            self._sync_ui_state()
            self.widget.set_status_message(message)

    def stop(self):
        if self.connection_state in {"stopped", "stopping"}:
            return

        logger.info("停止 Agent 连接")
        self.connection_state = "stopping"
        self._sync_ui_state()

        ok, message = self.service.stop()
        if not ok:
            logger.warning(message)
            self.connection_state = "stopped"
            self._sync_ui_state()
            self.widget.set_status_message(message)

    def save(self, data: dict):
        previous_sync_url = (self.config.config_sync_url or "").strip()
        try:
            config = AgentConfigModel.model_validate(data)
        except Exception as e:
            logger.exception(f"保存 Agent 配置失败: {e}")
            self.widget.set_status_message(f"配置无效: {e}")
            return

        current_sync_url = (config.config_sync_url or "").strip()
        if current_sync_url != previous_sync_url:
            config.config_sync_initialized = False
            config.config_sync_last_sync_at = ""

        AgentConfig.save_config(config)
        self.config = AgentConfig.read_config()
        self.service.update_runtime_config(self.config)
        self.widget.apply_config(self.config, self.connection_state, self.local_mac)
        self._sync_ui_state()

    def sync_config(self):
        self._start_config_sync()

    def shutdown(self):
        try:
            self.service.shutdown()
        except Exception as e:
            logger.exception(f"关闭 Agent 服务失败: {e}")
        if self._config_sync_thread and self._config_sync_thread.isRunning():
            self._config_sync_thread.quit()
            self._config_sync_thread.wait(1000)
        if self._local_mac_thread and self._local_mac_thread.isRunning():
            self._local_mac_thread.quit()
            self._local_mac_thread.wait(500)

    def _on_service_state_changed(self, state: str):
        self.connection_state = state or "stopped"
        self._sync_ui_state()

    def _on_service_status(self, message: str):
        self.widget.set_status_message(message)

    def _on_service_request(self, message: str):
        if self.config.show_logs:
            self.widget.set_request_text(message)

    def _on_service_response(self, message: str):
        if self.config.show_logs:
            self.widget.set_response_text(message)

    def _on_service_error(self, message: str):
        logger.error(message)
        self.widget.set_status_message(message)

    def _sync_ui_state(self):
        running = self.connection_state in {"starting", "running", "stopping"}
        self.widget.apply_config(self.config, self.connection_state, self.local_mac)
        self.widget.set_running(running)

    def _refresh_local_mac_async(self):
        if self._local_mac_thread and self._local_mac_thread.isRunning():
            return

        self._local_mac_thread = _LocalMacThread(self)
        self._local_mac_thread.done.connect(self._on_local_mac_done)
        self._local_mac_thread.finished.connect(self._on_local_mac_finished)
        self._local_mac_thread.start()

    def _on_local_mac_done(self, mac: str):
        resolved_mac = (mac or "").strip()
        if not resolved_mac or resolved_mac == self.local_mac:
            return

        self.local_mac = resolved_mac
        if hasattr(self.widget, "set_local_mac"):
            self.widget.set_local_mac(self.local_mac)

    def _on_local_mac_finished(self):
        self._local_mac_thread = None

    def _build_connect_url(self, server: str) -> str:
        base = (server or "").strip().rstrip("/")
        if not self.local_mac:
            return base
        return f"{base}/{self.local_mac}"

    def _start_config_sync(self):
        if self._config_sync_thread and self._config_sync_thread.isRunning():
            return

        self.config = AgentConfig.read_config()
        config_url = (self.config.config_sync_url or "").strip()
        if not config_url:
            self.widget.set_status_message("请先在服务器管理中填写配置拉取地址")
            return

        self.widget.set_config_syncing(True)
        self.widget.set_status_message("正在更新 Agent 配置...")

        self._config_sync_thread = _ConfigSyncThread(config_url)
        self._config_sync_thread.done.connect(self._on_config_sync_done)
        self._config_sync_thread.finished.connect(self._on_config_sync_finished)
        self._config_sync_thread.start()

    def _on_config_sync_done(self, success: bool, result: object, message: str):
        if success and isinstance(result, dict):
            self.config = AgentConfig.read_config()
            self.service.update_runtime_config(self.config)
            self.widget.apply_config(self.config, self.connection_state, self.local_mac)
            updated_at = str(result.get("updated_at") or "").strip()
            prefix = "Agent 配置已更新"
            if updated_at:
                prefix = f"{prefix}，服务端更新时间：{updated_at}"
            self.widget.set_status_message(prefix)
            if hasattr(self.widget, "on_config_sync_result"):
                self.widget.on_config_sync_result(True, prefix)
            return

        error_message = f"更新 Agent 配置失败: {message}"
        self.widget.set_status_message(error_message)
        if hasattr(self.widget, "on_config_sync_result"):
            self.widget.on_config_sync_result(False, error_message)

    def _on_config_sync_finished(self):
        self.widget.set_config_syncing(False)
        self._config_sync_thread = None
