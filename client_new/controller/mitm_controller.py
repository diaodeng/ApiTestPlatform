import json
import sys
from datetime import datetime
from pathlib import Path

from loguru import logger
from PySide6.QtCore import QObject, QProcess, QTimer, Signal

from emitter.mitm_flow_emitter import flow_emitter
from models.mitmproxy_models import FlowItem
from server.config import MitmproxyConfig


class MitmController(QObject):
    data_signal = Signal(dict)

    def __init__(self, widget):
        super().__init__()
        self.widget = widget
        self.config = MitmproxyConfig.read()

        self.helper: QProcess | None = None
        self.helper_state = "stopped"
        self._stdout_buffer = ""
        self._stderr_buffer = ""
        self._shutting_down = False

        self.timer = QTimer()
        self.timer.timeout.connect(self._sync_ui_state)
        self.timer.start(200)

        self._force_stop_timer = QTimer(self)
        self._force_stop_timer.setSingleShot(True)
        self._force_stop_timer.timeout.connect(self._force_stop_helper_if_needed)

        self._bind()
        self.widget.apply_config(self.config, self.helper_state)
        self._sync_ui_state()

    def _bind(self):
        self.widget.start_clicked.connect(self.start)
        self.widget.stop_clicked.connect(self.stop)
        self.widget.save_clicked.connect(self.save)

    def start(self):
        logger.info("启动 mitmproxy")
        try:
            self.config = MitmproxyConfig.read()
            self._ensure_helper()
            if self.helper_state in {"starting", "running", "stopping"}:
                logger.warning(f"启动请求被忽略，当前状态: {self.helper_state}")
                return

            self.helper_state = "starting"
            self._send_command("start", config=self.config.model_dump())
            self._sync_ui_state()
        except Exception as e:
            self.helper_state = "stopped"
            self._sync_ui_state()
            logger.exception(f"启动 mitmproxy 失败: {e}")

    def stop(self):
        logger.info("停止 mitmproxy")
        try:
            if not self._is_helper_running():
                self.helper_state = "stopped"
                self._sync_ui_state()
                return

            if self.helper_state in {"stopped", "stopping"}:
                return

            self.config = MitmproxyConfig.read()
            self.helper_state = "stopping"
            self._send_command("stop", timeout=10.0)
            self._start_force_stop_timer()
            self._sync_ui_state()
        except Exception as e:
            logger.exception(f"停止 mitmproxy 失败: {e}")

    def save(self, data):
        try:
            MitmproxyConfig.write(data)
            self.config = MitmproxyConfig.read()
            self.widget.apply_config(self.config, self.helper_state)

            if self._is_helper_running():
                self._send_command("update", config=self.config.model_dump())

            logger.info("配置已保存")
        except Exception as e:
            logger.exception(f"保存 mitmproxy 配置失败: {e}")

    def shutdown(self):
        self._shutting_down = True
        if not self.helper:
            return

        try:
            if self._is_helper_running():
                self._send_command("shutdown", timeout=5.0)
                if not self.helper.waitForFinished(5000):
                    self.helper.terminate()
                    if not self.helper.waitForFinished(2000):
                        self.helper.kill()
        except Exception as e:
            logger.exception(f"关闭 mitmproxy helper 失败: {e}")

        self._dispose_helper()

    def _sync_ui_state(self):
        running = self.helper_state in {"starting", "running", "stopping"}
        if self.helper_state == "stopped":
            self._force_stop_timer.stop()
        self.widget.proxy_state = self.helper_state
        self.widget.set_running(running)

    def _ensure_helper(self):
        if self._is_helper_running():
            return

        if self.helper:
            self._dispose_helper()

        helper = QProcess(self)
        helper.setWorkingDirectory(str(Path(__file__).resolve().parent.parent))
        helper.setProcessChannelMode(QProcess.SeparateChannels)
        helper.readyReadStandardOutput.connect(self._on_helper_stdout)
        helper.readyReadStandardError.connect(self._on_helper_stderr)
        helper.finished.connect(self._on_helper_finished)
        helper.errorOccurred.connect(self._on_helper_error)

        if getattr(sys, "frozen", False):
            program = sys.executable
            arguments = ["--mitm-helper"]
        else:
            app_main = Path(__file__).resolve().parents[1] / "main.py"
            program = sys.executable
            arguments = ["-Xfrozen_modules=off", "-u", str(app_main), "--mitm-helper"]

        helper.start(program, arguments)

        if not helper.waitForStarted(3000):
            raise RuntimeError("mitmproxy helper 进程启动失败")

        self.helper = helper
        self.helper_state = "stopped"
        self._stdout_buffer = ""
        self._stderr_buffer = ""

    def _dispose_helper(self):
        if not self.helper:
            return

        try:
            self.helper.readyReadStandardOutput.disconnect(self._on_helper_stdout)
            self.helper.readyReadStandardError.disconnect(self._on_helper_stderr)
            self.helper.finished.disconnect(self._on_helper_finished)
            self.helper.errorOccurred.disconnect(self._on_helper_error)
        except Exception:
            pass

        self.helper.deleteLater()
        self.helper = None
        self._force_stop_timer.stop()
        self.helper_state = "stopped"
        self._stdout_buffer = ""
        self._stderr_buffer = ""

    def _is_helper_running(self) -> bool:
        return bool(self.helper and self.helper.state() != QProcess.NotRunning)

    def _send_command(self, cmd: str, **payload):
        if not self.helper:
            raise RuntimeError("mitmproxy helper 未启动")

        message = json.dumps({"cmd": cmd, **payload}, ensure_ascii=False) + "\n"
        written = self.helper.write(message.encode("utf-8"))
        if written == -1:
            raise RuntimeError(f"发送命令失败: {cmd}")
        self.helper.waitForBytesWritten(1000)

    def _on_helper_stdout(self):
        if not self.helper:
            return

        chunk = bytes(self.helper.readAllStandardOutput()).decode(
            "utf-8", errors="replace"
        )
        self._stdout_buffer += chunk

        while "\n" in self._stdout_buffer:
            line, self._stdout_buffer = self._stdout_buffer.split("\n", 1)
            line = line.strip()
            if not line:
                continue

            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                logger.warning(f"helper stdout 非协议消息: {line}")
                continue

            self._handle_helper_message(message)

    def _on_helper_stderr(self):
        if not self.helper:
            return

        chunk = bytes(self.helper.readAllStandardError()).decode(
            "utf-8", errors="replace"
        )
        self._stderr_buffer += chunk

        while "\n" in self._stderr_buffer:
            line, self._stderr_buffer = self._stderr_buffer.split("\n", 1)
            line = line.strip()
            if line:
                logger.warning(f"mitmproxy helper: {line}")

    def _handle_helper_message(self, message: dict):
        msg_type = message.get("type")
        self.data_signal.emit(message)

        if msg_type == "ready":
            return

        if msg_type == "state":
            self.helper_state = message.get("state", "stopped")
            self._sync_ui_state()
            return

        if msg_type == "flow_new":
            item = self._build_flow_item(message.get("item") or {})
            flow_emitter.new_flow.emit(item)
            return

        if msg_type == "flow_update":
            item = self._build_flow_item(message.get("item") or {})
            flow_emitter.update_flow.emit(item)
            return

        if msg_type == "result":
            if not message.get("ok", False):
                logger.warning(
                    f"helper 命令失败 cmd={message.get('cmd')}: {message.get('message')}"
                )
                if message.get("cmd") in {"start", "stop"}:
                    self.helper_state = "stopped"
                    self._sync_ui_state()
            return

        if msg_type == "error":
            logger.error(message.get("message", "mitmproxy helper 发生未知错误"))
            detail = message.get("detail")
            if detail:
                logger.debug(detail)
            if self.helper_state == "starting":
                self.helper_state = "stopped"
                self._sync_ui_state()

    def _build_flow_item(self, payload: dict) -> FlowItem:
        raw_time = payload.get("time")
        if raw_time:
            try:
                parsed_time = datetime.fromisoformat(raw_time)
            except ValueError:
                parsed_time = datetime.now()
        else:
            parsed_time = datetime.now()

        return FlowItem(
            id=payload.get("id", ""),
            method=payload.get("method", ""),
            url=payload.get("url", ""),
            path=payload.get("path", ""),
            status_code=payload.get("status_code"),
            size=payload.get("size", 0),
            time=parsed_time,
            request_scheme=payload.get("request_scheme", ""),
            request_host=payload.get("request_host", ""),
            request_port=payload.get("request_port"),
            request_http_version=payload.get("request_http_version", ""),
            request_query=payload.get("request_query", ""),
            request_headers=payload.get("request_headers", ""),
            request_cookies=payload.get("request_cookies", ""),
            request_form=payload.get("request_form", ""),
            request_body=payload.get("request_body", ""),
            request_content_type=payload.get("request_content_type", ""),
            client_address=payload.get("client_address", ""),
            server_address=payload.get("server_address", ""),
            response_reason=payload.get("response_reason", ""),
            response_http_version=payload.get("response_http_version", ""),
            response_headers=payload.get("response_headers", ""),
            response_body=payload.get("response_body", ""),
            response_content_type=payload.get("response_content_type", ""),
            duration_ms=payload.get("duration_ms"),
        )

    def _on_helper_finished(self, exit_code: int, exit_status):
        if not self._shutting_down:
            logger.warning(
                f"mitmproxy helper 已退出 exit_code={exit_code}, exit_status={exit_status}"
            )
        self._force_stop_timer.stop()
        self.helper_state = "stopped"
        self._sync_ui_state()
        self._dispose_helper()

    def _on_helper_error(self, error):
        logger.error(f"mitmproxy helper 进程错误: {error}")
        self.helper_state = "stopped"
        self._sync_ui_state()

    def _start_force_stop_timer(self):
        self._force_stop_timer.stop()
        self._force_stop_timer.start(15000)

    def _force_stop_helper_if_needed(self):
        if self._shutting_down:
            return
        if self.helper_state != "stopping":
            return
        if not self._is_helper_running():
            return

        logger.warning("mitmproxy 停止超时，强制结束 helper 进程")
        try:
            self.helper.terminate()
            if not self.helper.waitForFinished(3000):
                self.helper.kill()
                self.helper.waitForFinished(2000)
        except Exception as e:
            logger.exception(f"强制结束 mitmproxy helper 失败: {e}")
