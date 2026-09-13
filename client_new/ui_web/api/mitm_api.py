import json
import queue
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path

from loguru import logger

from server.config import MitmproxyConfig
from ui_web.event_bus import event_bus
from utils.mitmproxy_cert import (
    describe_windows_cert_status,
    install_mitmproxy_cert_for_current_user,
    resolve_mitmproxy_cert_path,
)

# helper 子进程状态轮询间隔（秒）：负责 IO 队列消费与进程退出检测。
_MONITOR_INTERVAL = 0.05
# 证书状态检查超时（秒），超过后提示状态未确认（与原 Qt 版一致）。
_CERT_CHECK_TIMEOUT = 25.0


class _PipeReaderThread(threading.Thread):
    """
    helper 子进程管道读取线程：逐行读入队列，避免阻塞监控线程。
    """

    def __init__(self, stream, target_queue: queue.Queue, name: str):
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


class MitmApi:
    """
    mitmproxy 页面后端桥（替代原 Qt MitmController）。

    与原实现一致的职责：
    - 以 stdin/stdout JSON 行协议驱动 mitm helper 子进程；
    - 维护 helper 状态机（stopped/starting/running/stopping）；
    - 消费 flow_new/flow_update/state/result/error 消息并推送前端；
    - 配置保存后判定重启敏感字段，运行中自动重启生效。
    Qt 依赖的替换：QTimer 轮询 → 监控线程；Signal → EventBus；
    QMessageBox → 返回结果由前端提示。
    """

    # 修改这些字段后需要重启 helper 才能生效
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

    def __init__(self):
        self.config = MitmproxyConfig.read()
        self.helper: subprocess.Popen | None = None
        self.helper_state = "stopped"
        self.web_url = ""
        self._stdout_buffer = ""
        self._stderr_buffer = ""
        self._shutting_down = False
        self._restart_after_stop = False
        self._restart_reason = ""
        self._helper_stdout_queue: queue.Queue = queue.Queue()
        self._helper_stderr_queue: queue.Queue = queue.Queue()
        self._helper_stdout_thread: _PipeReaderThread | None = None
        self._helper_stderr_thread: _PipeReaderThread | None = None
        self._monitor_thread: threading.Thread | None = None
        self._monitor_stop = threading.Event()
        self._helper_finished_emitted = False
        self._cert_thread: threading.Thread | None = None
        self._cert_refresh_pending = False
        self._lock = threading.Lock()
        self._start_monitor()

    # ===== 前端调用的接口 =====

    def get_state(self) -> dict:
        """
        返回当前运行状态、配置与证书状态，前端首次进入页面时调用。
        """
        self.config = MitmproxyConfig.read()
        cert_path = str(resolve_mitmproxy_cert_path(self.config))
        return self._ok(
            state=self.helper_state,
            web_url=self.web_url,
            config=self.config.model_dump(),
            cert={"trusted": False, "can_install": Path(cert_path).exists(), "cert_path": cert_path, "message": ""},
        )

    def start(self) -> dict:
        """
        启动 mitmproxy helper。
        """
        logger.info("启动 mitmproxy")
        try:
            self.config = MitmproxyConfig.read()
            self._ensure_helper()
            if self.helper_state in {"starting", "running", "stopping"}:
                return self._fail(f"当前状态 {self.helper_state}，启动请求被忽略")

            self.helper_state = "starting"
            self._send_command("start", config=self.config.model_dump())
            self._push_state()
            return self._ok(state=self.helper_state)
        except Exception as e:
            self.helper_state = "stopped"
            self._push_state()
            logger.exception(f"启动 mitmproxy 失败: {e}")
            return self._fail(str(e))

    def stop(self) -> dict:
        """
        停止 mitmproxy（等待 helper 优雅退出，超时强制结束）。
        """
        logger.info("停止 mitmproxy")
        try:
            self._restart_after_stop = False
            self._restart_reason = ""
            if self.helper_state not in {"starting", "running", "stopping"}:
                self.helper_state = "stopped"
                self._push_state()
                return self._ok(state=self.helper_state)
            if self.helper_state in {"stopped", "stopping"}:
                return self._ok(state=self.helper_state)

            self.config = MitmproxyConfig.read()
            self._request_proxy_stop()
            return self._ok(state=self.helper_state)
        except Exception as e:
            logger.exception(f"停止 mitmproxy 失败: {e}")
            return self._fail(str(e))

    def continue_flow(self, flow_id: str, stage: str, payload: dict | None = None) -> dict:
        """
        放行指定流量断点，可携带请求/响应覆盖数据。
        """
        normalized_flow_id = str(flow_id or "").strip()
        normalized_stage = str(stage or "").strip().lower()
        if not self._is_helper_running() or self.helper_state not in {"starting", "running"}:
            return self._fail("mitmproxy 未运行，无法放行断点")
        if not normalized_flow_id or normalized_stage not in {"request", "response"}:
            return self._fail(f"参数无效 flow_id={normalized_flow_id}, stage={normalized_stage}")

        self._send_command(
            "continue_flow",
            flow_id=normalized_flow_id,
            stage=normalized_stage,
            payload=payload or {},
        )
        return self._ok()

    def save_config(self, data: dict) -> dict:
        """
        保存配置；运行中且修改了重启敏感字段时自动重启 helper。
        """
        try:
            old_config = self.config
            MitmproxyConfig.write(data)
            self.config = MitmproxyConfig.read()

            self._refresh_cert_status_async()
            if self._is_proxy_active():
                changed = [
                    display
                    for field, display in self.RESTART_SENSITIVE_FIELDS.items()
                    if getattr(old_config, field, None) != getattr(self.config, field, None)
                ]
                if changed:
                    self._restart_after_stop = True
                    self._restart_reason = "、".join(changed)
                    logger.info(f"mitmproxy 关键配置已变更，准备重启后应用：{self._restart_reason}")
                    self._request_proxy_stop()
                else:
                    self._send_command("update", config=self.config.model_dump())

            logger.info("mitmproxy 配置已保存")
            return self._ok(config=self.config.model_dump(), state=self.helper_state)
        except Exception as e:
            logger.exception(f"保存 mitmproxy 配置失败: {e}")
            return self._fail(str(e))

    def install_cert(self) -> dict:
        """
        为当前用户安装 mitmproxy CA 证书。
        """
        try:
            self.config = MitmproxyConfig.read()
            ok, message, _cert_path = install_mitmproxy_cert_for_current_user(self.config)
            self._refresh_cert_status_async()
            if ok:
                logger.info(message)
            else:
                logger.warning(message)
            return {"ok": ok, "message": message}
        except Exception as e:
            logger.exception(f"安装 mitmproxy 证书失败: {e}")
            return self._fail(str(e))

    def open_web(self) -> dict:
        """
        返回 mitmproxy Web 页面地址（Web 模式且已运行），前端自行打开浏览器。
        """
        self.config = MitmproxyConfig.read()
        if str(getattr(self.config, "startup_mode", "dump") or "dump").strip().lower() != "web":
            return self._fail("当前不是 Web 模式")
        if self.helper_state != "running":
            return self._fail("请先启动 mitmproxy，再打开 Web 页面")

        web_url = self.web_url.strip() or f"http://127.0.0.1:{self.config.web_port}/"
        logger.info(f"打开 mitmproxy Web 页面: {web_url}")
        return self._ok(web_url=web_url)

    def refresh_cert_status(self) -> dict:
        """
        主动刷新证书状态（后台线程执行，完成后推送 mitm_cert_status 事件）。
        """
        self._refresh_cert_status_async()
        return self._ok()

    def shutdown(self) -> None:
        """
        应用退出时停止 helper 并清理线程。
        """
        if self._shutting_down:
            return
        self._shutting_down = True
        self._monitor_stop.set()

        helper = self.helper
        if helper and self._is_helper_running():
            try:
                self._send_command("shutdown", timeout=5.0)
                try:
                    helper.wait(timeout=5.0)
                except subprocess.TimeoutExpired:
                    helper.terminate()
                    try:
                        helper.wait(timeout=2.0)
                    except subprocess.TimeoutExpired:
                        helper.kill()
                        helper.wait(timeout=2.0)
            except Exception as e:
                logger.exception(f"关闭 mitmproxy helper 失败: {e}")

        self._dispose_helper()

    # ===== 内部实现 =====

    def _start_monitor(self):
        """
        启动后台监控线程，替代原 QTimer：消费管道队列、检测进程退出。
        """
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop, name="mitm-monitor", daemon=True
        )
        self._monitor_thread.start()

    def _monitor_loop(self):
        while not self._monitor_stop.wait(_MONITOR_INTERVAL):
            try:
                self._drain_helper_stdout()
                self._drain_helper_stderr()
                if self.helper and not self._helper_finished_emitted:
                    exit_code = self.helper.poll()
                    if exit_code is not None:
                        self._helper_finished_emitted = True
                        exit_status = "NormalExit" if exit_code == 0 else "CrashExit"
                        self._on_helper_finished(exit_code, exit_status)
            except Exception as e:
                logger.exception(f"mitmproxy 监控线程异常: {e}")

    def _ensure_helper(self):
        if self._is_helper_running():
            return
        if self.helper:
            self._dispose_helper()

        program, arguments = self._resolve_helper_command()
        popen_kwargs = {
            "args": [program, *arguments],
            "cwd": str(Path(__file__).resolve().parents[2]),
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
            helper.stdout, self._helper_stdout_queue, "mitmproxy-helper-stdout"
        )
        self._helper_stderr_thread = _PipeReaderThread(
            helper.stderr, self._helper_stderr_queue, "mitmproxy-helper-stderr"
        )
        self._helper_stdout_thread.start()
        self._helper_stderr_thread.start()

    def _dispose_helper(self):
        stdout_thread = self._helper_stdout_thread
        stderr_thread = self._helper_stderr_thread
        if self.helper:
            for stream_name in ("stdin", "stdout", "stderr"):
                stream = getattr(self.helper, stream_name, None)
                if stream is None:
                    continue
                try:
                    stream.close()
                except Exception:
                    pass

        self.helper = None
        self.helper_state = "stopped"
        self._stdout_buffer = ""
        self._stderr_buffer = ""
        self._helper_finished_emitted = False
        for thread in (stdout_thread, stderr_thread):
            if thread and thread.is_alive():
                thread.join(timeout=2.0)
        self._helper_stdout_queue = queue.Queue()
        self._helper_stderr_queue = queue.Queue()
        self._helper_stdout_thread = None
        self._helper_stderr_thread = None

    def _is_helper_running(self) -> bool:
        return bool(self.helper and self.helper.poll() is None)

    def _request_proxy_stop(self):
        if self.helper_state not in {"starting", "running", "stopping"}:
            self.helper_state = "stopped"
            self._push_state()
            return
        self.helper_state = "stopping"
        self._send_command("stop", timeout=10.0)
        self._push_state()
        # 停止超时兜底：15 秒后仍处于 stopping 则强制结束进程。
        threading.Timer(15.0, self._force_stop_if_needed).start()

    def _force_stop_if_needed(self):
        if self._shutting_down or self.helper_state != "stopping":
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

    def _resolve_helper_command(self) -> tuple[str, list[str]]:
        if getattr(sys, "frozen", False):
            executable_dir = Path(sys.executable).resolve().parent
            for name in ("QTRClientNewMitmHelper.exe", "QTRMitmHelper.exe"):
                candidate = executable_dir / name
                if candidate.exists():
                    return str(candidate), []
            return str(sys.executable), ["--mitm-helper"]

        helper_main = Path(__file__).resolve().parents[2] / "mitm_helper_main.py"
        return str(Path(sys.executable)), ["-Xfrozen_modules=off", "-u", str(helper_main)]

    def _send_command(self, cmd: str, timeout: float = 5.0, **payload):
        del timeout  # 行协议为阻塞写，保留参数兼容原调用形态
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
                logger.warning(f"helper stdout 非协议消息: {line[:200]}")
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
                logger.warning(f"mitmproxy helper: {line[:300]}")

    def _handle_helper_message(self, message: dict):
        msg_type = message.get("type")

        if msg_type == "ready":
            return

        if msg_type == "state":
            self.web_url = str(message.get("web_url") or "")
            self.helper_state = message.get("state", "stopped")
            self._push_state()
            if (
                self.helper_state == "stopped"
                and self._restart_after_stop
                and not self._shutting_down
            ):
                restart_reason = self._restart_reason
                self._restart_after_stop = False
                self._restart_reason = ""
                if restart_reason:
                    logger.info(f"mitmproxy 已停止，开始重新启动以应用配置：{restart_reason}")
                threading.Thread(target=self.start, name="mitm-restart", daemon=True).start()
            return

        if msg_type == "flow_new":
            event_bus.push("mitm_flow_new", {"item": self._normalize_flow(message.get("item") or {})})
            return

        if msg_type == "flow_update":
            event_bus.push("mitm_flow_update", {"item": self._normalize_flow(message.get("item") or {})})
            return

        if msg_type == "result":
            if not message.get("ok", False):
                logger.warning(
                    f"helper 命令失败 cmd={message.get('cmd')}: {message.get('message')}"
                )
                if message.get("cmd") in {"start", "stop"}:
                    self.helper_state = "stopped"
                    self._push_state()
            elif message.get("cmd") == "continue_flow":
                logger.info(message.get("message", "断点已放行"))
            return

        if msg_type == "error":
            logger.error(message.get("message", "mitmproxy helper 发生未知错误"))
            if self.helper_state == "starting":
                self.helper_state = "stopped"
                self._push_state()

    def _normalize_flow(self, payload: dict) -> dict:
        """
        归一化流量数据：时间转字符串，供前端直接渲染表格与详情。
        """
        item = dict(payload)
        raw_time = item.get("time")
        try:
            parsed = datetime.fromisoformat(raw_time) if raw_time else datetime.now()
        except (TypeError, ValueError):
            parsed = datetime.now()
        item["time"] = parsed.strftime("%H:%M:%S.%f")[:-3]
        item["time_full"] = parsed.strftime("%Y-%m-%d %H:%M:%S")
        return item

    def _on_helper_finished(self, exit_code: int, exit_status: str):
        if not self._shutting_down:
            logger.warning(
                f"mitmproxy helper 已退出 exit_code={exit_code}, exit_status={exit_status}"
            )
        self._drain_helper_stdout()
        self._drain_helper_stderr()
        self.helper_state = "stopped"
        self._push_state()
        self._dispose_helper()

    def _push_state(self):
        event_bus.push(
            "mitm_state",
            {"state": self.helper_state, "web_url": self.web_url},
        )

    # ===== 证书状态 =====

    def _refresh_cert_status_async(self):
        cert_path = str(resolve_mitmproxy_cert_path(self.config))
        event_bus.push(
            "mitm_cert_status",
            {"message": "正在检查 mitmproxy CA...", "trusted": False, "can_install": False, "cert_path": cert_path},
        )

        thread = self._cert_thread
        if thread and thread.is_alive():
            self._cert_refresh_pending = True
            return

        self._cert_refresh_pending = False
        self._cert_thread = threading.Thread(
            target=self._cert_status_worker,
            args=(self.config.model_copy(deep=True),),
            name="mitm-cert-status",
            daemon=True,
        )
        self._cert_thread.start()
        # 超时兜底：超时后若检查线程仍在运行，推送“状态未确认”。
        threading.Timer(
            _CERT_CHECK_TIMEOUT,
            self._cert_status_timeout,
            args=(cert_path,),
        ).start()

    def _cert_status_worker(self, config):
        try:
            trusted, can_install, cert_path, message = describe_windows_cert_status(config)
        except Exception as e:
            cert_path = str(resolve_mitmproxy_cert_path(config))
            trusted, can_install, message = False, False, f"检查 mitmproxy 证书状态失败: {e}"
        self._cert_thread = None
        event_bus.push(
            "mitm_cert_status",
            {"trusted": trusted, "can_install": can_install, "cert_path": cert_path, "message": message},
        )
        if self._cert_refresh_pending:
            self._cert_refresh_pending = False
            self._refresh_cert_status_async()

    def _cert_status_timeout(self, cert_path: str):
        thread = self._cert_thread
        if thread is None or not thread.is_alive():
            return
        logger.warning("mitmproxy 证书状态检查超时")
        event_bus.push(
            "mitm_cert_status",
            {
                "message": "检查 mitmproxy CA 超时，状态暂未确认，可继续使用或稍后重试。",
                "trusted": False,
                "can_install": Path(cert_path).exists(),
                "cert_path": cert_path,
            },
        )

    # ===== 结果包装 =====

    @staticmethod
    def _ok(**data) -> dict:
        return {"ok": True, "message": "", **data}

    @staticmethod
    def _fail(message: str) -> dict:
        return {"ok": False, "message": message}
