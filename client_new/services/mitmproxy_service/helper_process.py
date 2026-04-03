import asyncio
import concurrent.futures
import json
import os
import sys
import threading
import traceback
from dataclasses import asdict
from pathlib import Path

from loguru import logger
from mitmproxy import addons as mitm_addons
from mitmproxy import master as mitm_master
from mitmproxy.options import Options
from mitmproxy.utils import asyncio_utils

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from model.config import MitmProxyConfigModel
from services.mitmproxy_service.mock_handle import MockHandle
from services.mitmproxy_service.runtime_config import RuntimeConfig


class HelperProtocol:
    def __init__(self):
        self._write_lock = threading.Lock()

    def send(self, message_type: str, **payload):
        message = {"type": message_type, **payload}
        line = json.dumps(message, ensure_ascii=False)
        with self._write_lock:
            sys.stdout.write(line + "\n")
            sys.stdout.flush()


class HelperRuntime:
    def __init__(self, protocol: HelperProtocol):
        self.protocol = protocol
        self._lock = threading.Lock()
        self._state = "stopped"
        self._loop_ready = threading.Event()
        self._loop_thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._master: mitm_master.Master | None = None
        self._session_future: concurrent.futures.Future | None = None
        self._config: MitmProxyConfigModel | None = None
        self._stop_requested = False
        self._start_loop_thread()

    @property
    def state(self) -> str:
        with self._lock:
            return self._state

    def start(self, config_data: dict) -> tuple[bool, str]:
        config = MitmProxyConfigModel.model_validate(config_data)
        RuntimeConfig.set(config)

        with self._lock:
            if self._state != "stopped":
                return False, f"mitmproxy 当前状态为 {self._state}"
            if not self._loop:
                raise RuntimeError("helper 事件循环未初始化")

            self._state = "starting"
            self._config = config
            self._stop_requested = False

        self.protocol.send("state", state="starting")
        future = asyncio.run_coroutine_threadsafe(self._run_session(config), self._loop)
        future.add_done_callback(self._on_session_finished)

        with self._lock:
            self._session_future = future

        return True, "mitmproxy 启动中"

    def stop(self, timeout: float = 10.0) -> tuple[bool, str]:
        with self._lock:
            if self._state == "stopped":
                return True, "mitmproxy 已停止"
            if self._state == "stopping":
                return True, "mitmproxy 停止中"

            self._state = "stopping"
            self._stop_requested = True
            loop = self._loop
            master = self._master

        self.protocol.send("state", state="stopping")

        if loop and master:
            try:
                loop.call_soon_threadsafe(self._request_session_shutdown, master)
            except RuntimeError:
                pass

        return True, "mitmproxy 停止请求已发送"

    def update_config(self, config_data: dict) -> tuple[bool, str]:
        config = MitmProxyConfigModel.model_validate(config_data)
        RuntimeConfig.set(config)
        with self._lock:
            self._config = config
        return True, "配置已更新"

    def shutdown(self, timeout: float = 5.0) -> tuple[bool, str]:
        ok, message = self.stop(timeout)

        loop = None
        thread = None
        future = None
        with self._lock:
            loop = self._loop
            thread = self._loop_thread
            future = self._session_future

        if future:
            try:
                future.result(timeout=timeout)
            except concurrent.futures.TimeoutError:
                ok = False
                message = "mitmproxy 关闭超时"
            except Exception as e:
                ok = False
                message = f"mitmproxy 关闭异常: {e}"

        if loop:
            loop.call_soon_threadsafe(loop.stop)
        if thread:
            thread.join(timeout=timeout)

        return ok, message

    def _start_loop_thread(self):
        self._loop_thread = threading.Thread(
            target=self._loop_thread_main,
            name="mitmproxy-helper-loop",
            daemon=True,
        )
        self._loop_thread.start()
        if not self._loop_ready.wait(timeout=5):
            raise RuntimeError("helper 事件循环线程启动超时")

    def _loop_thread_main(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        with self._lock:
            self._loop = loop

        self._loop_ready.set()

        try:
            loop.run_forever()
        finally:
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
                with self._lock:
                    self._loop = None
                loop.close()

    def _request_session_shutdown(self, master: mitm_master.Master):
        proxyserver = master.addons.get("proxyserver")
        if proxyserver:
            asyncio_utils.create_task(
                proxyserver.servers.update([]),
                name="stop servers",
                keep_ref=True,
            )
        master.shutdown()

    async def _run_session(self, config: MitmProxyConfigModel):
        mode = [config.proxy_model] if config.proxy_model else []
        if config.proxy_model == "local":
            mode = [f"{config.proxy_model}:{config.proxy_model_value}"]

        config_dir = config.mitmproxy_config_dir
        if config_dir and not os.path.exists(config_dir):
            os.makedirs(config_dir)

        opts = Options(
            listen_host="127.0.0.1",
            listen_port=config.port,
            ssl_insecure=True,
            mode=mode,
            confdir=config_dir or os.path.join(os.path.expanduser("~"), ".mitmproxy"),
        )

        master = mitm_master.Master(
            opts,
            event_loop=asyncio.get_running_loop(),
            with_termlog=False,
        )
        master.addons.add(*mitm_addons.default_addons())
        master.addons.add(MockHandle(flow_dispatcher=self._dispatch_flow))

        proxyserver = master.addons.get("proxyserver")
        with self._lock:
            self._master = master

        try:
            with (
                asyncio_utils.install_exception_handler(
                    master._asyncio_exception_handler
                ),
                asyncio_utils.set_eager_task_factory(),
            ):
                if proxyserver:
                    ok = await proxyserver.setup_servers()
                    if not ok:
                        raise RuntimeError("mitmproxy 服务器启动失败")

                await master.running()

                with self._lock:
                    self._state = "running"
                    should_stop = self._stop_requested

                self.protocol.send("state", state="running")

                if should_stop:
                    master.shutdown()

                await master.should_exit.wait()
        except Exception as e:
            self.protocol.send(
                "error",
                message=f"mitmproxy 运行异常: {e}",
                detail=traceback.format_exc(),
            )
        finally:
            if proxyserver:
                try:
                    await proxyserver.servers.update([])
                except Exception as e:
                    self.protocol.send(
                        "error",
                        message=f"mitmproxy 关闭代理实例失败: {e}",
                        detail=traceback.format_exc(),
                    )

            try:
                await master.done()
            except Exception as e:
                self.protocol.send(
                    "error",
                    message=f"mitmproxy 清理异常: {e}",
                    detail=traceback.format_exc(),
                )
            finally:
                with self._lock:
                    self._master = None
                    self._session_future = None
                    self._stop_requested = False
                    self._state = "stopped"

                self.protocol.send("state", state="stopped")

    def _on_session_finished(self, future: concurrent.futures.Future):
        try:
            future.result()
        except Exception as e:
            self.protocol.send(
                "error",
                message=f"mitmproxy 会话异常结束: {e}",
                detail=traceback.format_exc(),
            )

    def _dispatch_flow(self, event_type: str, item):
        payload = asdict(item)
        payload["time"] = item.time.isoformat()
        message_type = "flow_new" if event_type == "new" else "flow_update"
        self.protocol.send(message_type, item=payload)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True)
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(line_buffering=True)

    protocol = HelperProtocol()
    runtime = HelperRuntime(protocol)
    protocol.send("ready")

    try:
        for raw_line in sys.stdin:
            line = raw_line.lstrip("\ufeff").strip()
            if not line:
                continue

            try:
                command = json.loads(line)
            except json.JSONDecodeError as e:
                protocol.send("result", cmd="invalid", ok=False, message=str(e))
                continue

            cmd = command.get("cmd", "")

            try:
                if cmd == "start":
                    ok, message = runtime.start(command.get("config") or {})
                elif cmd == "stop":
                    ok, message = runtime.stop(float(command.get("timeout", 10.0)))
                elif cmd == "update":
                    ok, message = runtime.update_config(command.get("config") or {})
                elif cmd == "shutdown":
                    ok, message = runtime.shutdown(float(command.get("timeout", 10.0)))
                    protocol.send("result", cmd=cmd, ok=ok, message=message)
                    break
                elif cmd == "ping":
                    ok, message = True, "pong"
                else:
                    ok, message = False, f"未知命令: {cmd}"
            except Exception as e:
                protocol.send(
                    "result",
                    cmd=cmd or "unknown",
                    ok=False,
                    message=str(e),
                    detail=traceback.format_exc(),
                )
            else:
                protocol.send("result", cmd=cmd, ok=ok, message=message)
    finally:
        try:
            runtime.shutdown(5.0)
        except Exception:
            logger.exception("helper 退出前停止 mitmproxy 失败")


if __name__ == "__main__":
    main()
