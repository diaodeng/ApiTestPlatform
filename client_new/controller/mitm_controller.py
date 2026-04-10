import json
import queue
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path

from loguru import logger
from PySide6.QtCore import QObject, QThread, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QMessageBox

from emitter.mitm_flow_emitter import flow_emitter
from models.mitmproxy_common import FlowItem
from server.config import MitmproxyConfig
from utils.mitmproxy_cert import (
    describe_windows_cert_status,
    install_mitmproxy_cert_for_current_user,
    resolve_mitmproxy_cert_path,
)


class _CertStatusThread(QThread):
    done = Signal(bool, bool, str, str)

    def __init__(self, config):
        super().__init__()
        self._config = (
            config.model_copy(deep=True) if hasattr(config, "model_copy") else config
        )

    def run(self):
        try:
            trusted, can_install, cert_path, message = describe_windows_cert_status(
                self._config
            )
            self.done.emit(trusted, can_install, cert_path, message)
        except Exception as e:
            cert_path = str(resolve_mitmproxy_cert_path(self._config))
            self.done.emit(
                False,
                False,
                cert_path,
                f"检查 mitmproxy 证书状态失败: {e}",
            )


class _PipeReaderThread(threading.Thread):
    def __init__(self, stream, target_queue: queue.Queue[str], name: str):
        super().__init__(name=name, daemon=True)
        self._stream = stream
        self._target_queue = target_queue

    def run(self):
        if self._stream is None:
            return
        try:
            for line in iter(self._stream.readline, ""):
                if not line:
                    break
                self._target_queue.put(line)
        except Exception:
            return


class MitmController(QObject):
    data_signal = Signal(dict)
    RESTART_SENSITIVE_FIELDS = {
        "port": "代理端口",
        "web_port": "Web端口",
        "web_open_browser": "启动浏览器",
        "ssl_insecure": "忽略 SSL 校验",
        "mitmproxy_config_dir": "配置目录",
        "cert_path": "证书路径",
        "script_path": "脚本路径",
        "startup_mode": "启动方式",
        "proxy_model": "代理模式",
        "proxy_model_value": "代理模式值",
    }

    def __init__(self, widget):
        super().__init__()
        self.widget = widget
        self.config = MitmproxyConfig.read()

        self.helper: subprocess.Popen | None = None
        self.helper_state = "stopped"
        self._stdout_buffer = ""
        self._stderr_buffer = ""
        self._shutting_down = False
        self._restart_after_stop = False
        self._restart_reason = ""
        self._current_web_url = ""
        self._cert_status_thread: _CertStatusThread | None = None
        self._cert_status_refresh_pending = False
        self._cert_status_check_seq = 0
        self._helper_stdout_queue: queue.Queue[str] = queue.Queue()
        self._helper_stderr_queue: queue.Queue[str] = queue.Queue()
        self._helper_stdout_thread: _PipeReaderThread | None = None
        self._helper_stderr_thread: _PipeReaderThread | None = None
        self._helper_finished_emitted = False

        self.timer = QTimer()
        self.timer.timeout.connect(self._sync_ui_state)
        self.timer.start(200)

        self._helper_io_timer = QTimer(self)
        self._helper_io_timer.setInterval(30)
        self._helper_io_timer.timeout.connect(self._poll_helper_io)
        self._helper_io_timer.start()

        self._force_stop_timer = QTimer(self)
        self._force_stop_timer.setSingleShot(True)
        self._force_stop_timer.timeout.connect(self._force_stop_helper_if_needed)

        self._bind()
        self.widget.apply_config(self.config, self.helper_state)
        self._sync_ui_state()
        self._refresh_cert_status_async()

    def _bind(self):
        self.widget.start_clicked.connect(self.start)
        self.widget.stop_clicked.connect(self.stop)
        self.widget.save_clicked.connect(self.save)
        self.widget.install_cert_clicked.connect(self.install_cert)
        self.widget.open_web_clicked.connect(self.open_web_page)

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
            self._restart_after_stop = False
            self._restart_reason = ""
            if not self._is_proxy_active():
                self.helper_state = "stopped"
                self._sync_ui_state()
                return

            if self.helper_state in {"stopped", "stopping"}:
                return

            self.config = MitmproxyConfig.read()
            self._request_proxy_stop()
        except Exception as e:
            logger.exception(f"停止 mitmproxy 失败: {e}")

    def save(self, data):
        try:
            old_config = self.config
            MitmproxyConfig.write(data)
            self.config = MitmproxyConfig.read()
            self.widget.apply_config(self.config, self.helper_state)
            self._refresh_cert_status_async()

            if self._is_proxy_active():
                changed_fields = self._changed_restart_sensitive_fields(
                    old_config,
                    self.config,
                )
                if changed_fields:
                    self._restart_after_stop = True
                    self._restart_reason = "、".join(changed_fields)
                    logger.info(
                        f"mitmproxy 关键配置已变更，准备重启后应用：{self._restart_reason}"
                    )
                    self._request_proxy_stop()
                else:
                    self._send_command("update", config=self.config.model_dump())

            logger.info("配置已保存")
        except Exception as e:
            logger.exception(f"保存 mitmproxy 配置失败: {e}")

    def install_cert(self):
        try:
            self.config = MitmproxyConfig.read()
            ok, message, _cert_path = install_mitmproxy_cert_for_current_user(
                self.config
            )
            self._refresh_cert_status_async()
            if ok:
                logger.info(message)
                QMessageBox.information(self.widget, "mitmproxy 证书", message)
            else:
                logger.warning(message)
                QMessageBox.warning(self.widget, "mitmproxy 证书", message)
        except Exception as e:
            logger.exception(f"安装 mitmproxy 证书失败: {e}")
            QMessageBox.warning(self.widget, "mitmproxy 证书", str(e))

    def shutdown(self):
        self._shutting_down = True
        if self._helper_io_timer.isActive():
            self._helper_io_timer.stop()
        if self._cert_status_thread and self._cert_status_thread.isRunning():
            try:
                self._cert_status_thread.done.disconnect(self._on_cert_status_done)
                self._cert_status_thread.finished.disconnect(
                    self._on_cert_status_thread_finished
                )
            except Exception:
                pass
            self._cert_status_thread.wait(1500)
        self._cert_status_thread = None
        self._current_web_url = ""
        self.widget.set_web_url("")
        if not self.helper:
            return

        try:
            if self._is_helper_running():
                self._send_command("shutdown", timeout=5.0)
                try:
                    self.helper.wait(timeout=5.0)
                except subprocess.TimeoutExpired:
                    self.helper.terminate()
                    try:
                        self.helper.wait(timeout=2.0)
                    except subprocess.TimeoutExpired:
                        self.helper.kill()
                        self.helper.wait(timeout=2.0)
        except Exception as e:
            logger.exception(f"关闭 mitmproxy helper 失败: {e}")

        self._dispose_helper()

    def _sync_ui_state(self):
        running = self.helper_state in {"starting", "running", "stopping"}
        if self.helper_state == "stopped":
            self._force_stop_timer.stop()
            self._current_web_url = ""
            self.widget.set_web_url("")
        self.widget.proxy_state = self.helper_state
        self.widget.set_running(running)

    def _ensure_helper(self):
        if self._is_helper_running():
            return

        if self.helper:
            self._dispose_helper()

        program, arguments = self._resolve_helper_command()
        command = [program, *arguments]
        popen_kwargs = {
            "args": command,
            "cwd": str(Path(__file__).resolve().parent.parent),
            "stdin": subprocess.PIPE,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "text": True,
            "encoding": "utf-8",
            "errors": "replace",
            "bufsize": 1,
        }
        if sys.platform.startswith("win"):
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= getattr(subprocess, "STARTF_USESHOWWINDOW", 0)
            startupinfo.wShowWindow = getattr(subprocess, "SW_HIDE", 0)
            popen_kwargs["creationflags"] = creationflags
            popen_kwargs["startupinfo"] = startupinfo

        helper = subprocess.Popen(**popen_kwargs)
        if helper.poll() is not None:
            raise RuntimeError("mitmproxy helper 进程启动失败")

        self.helper = helper
        self.helper_state = "stopped"
        self._stdout_buffer = ""
        self._stderr_buffer = ""
        self._helper_finished_emitted = False
        self._helper_stdout_queue = queue.Queue()
        self._helper_stderr_queue = queue.Queue()
        self._helper_stdout_thread = _PipeReaderThread(
            helper.stdout,
            self._helper_stdout_queue,
            "mitmproxy-helper-stdout",
        )
        self._helper_stderr_thread = _PipeReaderThread(
            helper.stderr,
            self._helper_stderr_queue,
            "mitmproxy-helper-stderr",
        )
        self._helper_stdout_thread.start()
        self._helper_stderr_thread.start()

    def _dispose_helper(self):
        if not self.helper:
            return

        for stream_name in ("stdin", "stdout", "stderr"):
            stream = getattr(self.helper, stream_name, None)
            if stream is None:
                continue
            try:
                stream.close()
            except Exception:
                pass

        self.helper = None
        self._force_stop_timer.stop()
        self.helper_state = "stopped"
        self._stdout_buffer = ""
        self._stderr_buffer = ""
        self._helper_finished_emitted = False
        self._helper_stdout_thread = None
        self._helper_stderr_thread = None
        self._helper_stdout_queue = queue.Queue()
        self._helper_stderr_queue = queue.Queue()

    def _is_helper_running(self) -> bool:
        return bool(self.helper and self.helper.poll() is None)

    def _is_proxy_active(self) -> bool:
        return self.helper_state in {"starting", "running", "stopping"}

    def _request_proxy_stop(self):
        if not self._is_proxy_active():
            self.helper_state = "stopped"
            self._sync_ui_state()
            return

        self.helper_state = "stopping"
        self._send_command("stop", timeout=10.0)
        self._start_force_stop_timer()
        self._sync_ui_state()

    def _changed_restart_sensitive_fields(self, old_config, new_config) -> list[str]:
        changed_fields = []
        for field_name, display_name in self.RESTART_SENSITIVE_FIELDS.items():
            if getattr(old_config, field_name, None) != getattr(
                new_config, field_name, None
            ):
                changed_fields.append(display_name)
        return changed_fields

    def _refresh_cert_status(self):
        trusted, can_install, cert_path, message = describe_windows_cert_status(
            self.config
        )
        self.widget.set_cert_status(
            message=message,
            trusted=trusted,
            can_install=can_install,
            cert_path=cert_path,
        )

    def _refresh_cert_status_async(self):
        cert_path = str(resolve_mitmproxy_cert_path(self.config))
        self.widget.set_cert_status(
            message="正在检查 mitmproxy CA...",
            trusted=False,
            can_install=False,
            cert_path=cert_path,
        )
        self._cert_status_check_seq += 1
        check_seq = self._cert_status_check_seq
        QTimer.singleShot(
            25000,
            lambda seq=check_seq, path=cert_path: self._on_cert_status_timeout(
                seq, path
            ),
        )

        if self._cert_status_thread and self._cert_status_thread.isRunning():
            self._cert_status_refresh_pending = True
            return

        self._cert_status_refresh_pending = False
        self._cert_status_thread = _CertStatusThread(self.config)
        self._cert_status_thread.done.connect(self._on_cert_status_done)
        self._cert_status_thread.finished.connect(self._on_cert_status_thread_finished)
        self._cert_status_thread.start()

    def _on_cert_status_done(
        self,
        trusted: bool,
        can_install: bool,
        cert_path: str,
        message: str,
    ):
        if self._shutting_down:
            return
        self.widget.set_cert_status(
            message=message,
            trusted=trusted,
            can_install=can_install,
            cert_path=cert_path,
        )

    def _on_cert_status_thread_finished(self):
        self._cert_status_thread = None
        if self._cert_status_refresh_pending and not self._shutting_down:
            self._cert_status_refresh_pending = False
            QTimer.singleShot(0, self._refresh_cert_status_async)

    def _on_cert_status_timeout(self, check_seq: int, cert_path: str):
        if self._shutting_down:
            return
        if check_seq != self._cert_status_check_seq:
            return
        if not self._cert_status_thread or not self._cert_status_thread.isRunning():
            return

        can_install = Path(cert_path).exists()
        logger.warning("mitmproxy 证书状态检查超时")
        self.widget.set_cert_status(
            message="检查 mitmproxy CA 超时，状态暂未确认，可继续使用或稍后重试。",
            trusted=False,
            can_install=can_install,
            cert_path=cert_path,
        )

    def _resolve_helper_command(self) -> tuple[str, list[str]]:
        if getattr(sys, "frozen", False):
            helper_executable = self._find_frozen_helper_executable()
            if helper_executable is not None:
                return str(helper_executable), []
            return str(sys.executable), ["--mitm-helper"]

        helper_main = Path(__file__).resolve().parents[1] / "mitm_helper_main.py"
        program = self._resolve_helper_program()
        return program, ["-Xfrozen_modules=off", "-u", str(helper_main)]

    def _find_frozen_helper_executable(self) -> Path | None:
        executable_dir = Path(sys.executable).resolve().parent
        candidates = (
            "QTRClientNewMitmHelper.exe",
            "QTRMitmHelper.exe",
        )
        for name in candidates:
            candidate = executable_dir / name
            if candidate.exists():
                return candidate
        return None

    def _resolve_helper_program(self) -> str:
        return str(Path(sys.executable))
        program_path = Path(sys.executable)
        if not sys.platform.startswith("win"):
            return str(program_path)

        if program_path.name.lower() == "python.exe":
            pythonw_path = program_path.with_name("pythonw.exe")
            if pythonw_path.exists():
                return str(pythonw_path)

        return str(program_path)

    def _send_command(self, cmd: str, **payload):
        if not self.helper:
            raise RuntimeError("mitmproxy helper 未启动")

        message = json.dumps({"cmd": cmd, **payload}, ensure_ascii=False) + "\n"
        stdin = self.helper.stdin
        if stdin is None:
            raise RuntimeError(f"发送命令失败: {cmd}")
        try:
            stdin.write(message)
            stdin.flush()
        except Exception as e:
            raise RuntimeError(f"发送命令失败: {cmd}: {e}") from e

    def _poll_helper_io(self):
        self._drain_helper_stdout()
        self._drain_helper_stderr()
        if not self.helper or self._helper_finished_emitted:
            return

        exit_code = self.helper.poll()
        if exit_code is None:
            return

        self._helper_finished_emitted = True
        exit_status = "NormalExit" if exit_code == 0 else "CrashExit"
        self._on_helper_finished(exit_code, exit_status)

    def _drain_helper_stdout(self):
        while True:
            try:
                line = self._helper_stdout_queue.get_nowait()
            except queue.Empty:
                break

            self._stdout_buffer += line

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

    def _drain_helper_stderr(self):
        while True:
            try:
                line = self._helper_stderr_queue.get_nowait()
            except queue.Empty:
                break

            self._stderr_buffer += line

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
            self._current_web_url = str(message.get("web_url") or "")
            self.widget.set_web_url(self._current_web_url)
            self.helper_state = message.get("state", "stopped")
            self._sync_ui_state()
            if (
                self.helper_state == "stopped"
                and self._restart_after_stop
                and not self._shutting_down
            ):
                restart_reason = self._restart_reason
                self._restart_after_stop = False
                self._restart_reason = ""
                if restart_reason:
                    logger.info(
                        f"mitmproxy 已停止，开始重新启动以应用配置：{restart_reason}"
                    )
                QTimer.singleShot(0, self.start)
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

    def open_web_page(self):
        self.config = MitmproxyConfig.read()
        if (
            str(getattr(self.config, "startup_mode", "dump") or "dump").strip().lower()
            != "web"
        ):
            QMessageBox.information(self.widget, "mitmproxy Web", "当前不是 Web 模式")
            return

        if self.helper_state != "running":
            QMessageBox.information(
                self.widget,
                "mitmproxy Web",
                "请先启动 mitmproxy，再打开 Web 页面",
            )
            return

        web_url = self._current_web_url.strip()
        if not web_url:
            web_url = f"http://127.0.0.1:{self.config.web_port}/"

        if QDesktopServices.openUrl(QUrl(web_url)):
            logger.info(f"已打开 mitmproxy Web 页面: {web_url}")
            return

        logger.warning(f"打开 mitmproxy Web 页面失败: {web_url}")
        QMessageBox.warning(
            self.widget,
            "mitmproxy Web",
            f"打开 Web 页面失败，请手动访问：{web_url}",
        )

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
        self._drain_helper_stdout()
        self._drain_helper_stderr()
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
            try:
                self.helper.wait(timeout=3.0)
            except subprocess.TimeoutExpired:
                self.helper.kill()
                self.helper.wait(timeout=2.0)
        except Exception as e:
            logger.exception(f"强制结束 mitmproxy helper 失败: {e}")
