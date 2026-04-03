from loguru import logger
from PySide6.QtCore import QObject

from model.config import AgentConfigModel
from server.config import AgentConfig
from services.agent_client_service import AgentClientService
from utils.common import get_active_mac


class AgentController(QObject):
    def __init__(self, widget):
        super().__init__()
        self.widget = widget
        self.config = AgentConfig.read_config()
        self.local_mac = get_active_mac() or ""
        self.connection_state = "stopped"
        self.service = AgentClientService()

        self._bind_widget()
        self._bind_service()

        self.widget.apply_config(self.config, self.connection_state, self.local_mac)
        self.widget.set_running(False)
        self.widget.set_status_message("就绪")

    def _bind_widget(self):
        self.widget.start_clicked.connect(self.start)
        self.widget.stop_clicked.connect(self.stop)
        self.widget.save_clicked.connect(self.save)

    def _bind_service(self):
        self.service.state_changed.connect(self._on_service_state_changed)
        self.service.status_message.connect(self._on_service_status)
        self.service.request_message.connect(self._on_service_request)
        self.service.response_message.connect(self._on_service_response)
        self.service.error_message.connect(self._on_service_error)

    def start(self):
        self.local_mac = get_active_mac() or self.local_mac
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
        try:
            config = AgentConfigModel.model_validate(data)
        except Exception as e:
            logger.exception(f"保存 Agent 配置失败: {e}")
            self.widget.set_status_message(f"配置无效: {e}")
            return

        AgentConfig.save_config(config)
        self.config = AgentConfig.read_config()
        self.service.update_runtime_config(self.config)
        self.widget.apply_config(self.config, self.connection_state, self.local_mac)
        self._sync_ui_state()

    def shutdown(self):
        try:
            self.service.shutdown()
        except Exception as e:
            logger.exception(f"关闭 Agent 服务失败: {e}")

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

    def _build_connect_url(self, server: str) -> str:
        base = (server or "").strip().rstrip("/")
        if not self.local_mac:
            return base
        return f"{base}/{self.local_mac}"
