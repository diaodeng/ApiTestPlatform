import asyncio
import concurrent.futures
import errno
import json
import os
import sys
import threading
import traceback
from dataclasses import asdict
from pathlib import Path

import tornado.httpserver
import tornado.ioloop
from loguru import logger
from mitmproxy import master as mitm_master
from mitmproxy.options import Options
from mitmproxy.tools.dump import DumpMaster
from mitmproxy.tools.web.master import WebMaster
from mitmproxy.utils import asyncio_utils

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from model.config import MitmProxyConfigModel
from services.mitmproxy_service.mock_handle import MockHandle
from services.mitmproxy_service.runtime_config import RuntimeConfig
from services.mitmproxy_service.windows_redirector_util import (
    ensure_windows_redirector_gui_subsystem,
)


class ManagedWebMaster(WebMaster):
    def __init__(self, opts: Options, with_termlog: bool = True):
        super().__init__(opts, with_termlog=with_termlog)
        self._http_server: tornado.httpserver.HTTPServer | None = None

    async def running(self):
        tornado.ioloop.IOLoop.current()

        if self._http_server is None:
            self._http_server = tornado.httpserver.HTTPServer(
                self.app,
                max_buffer_size=2**32,
            )

        try:
            self._http_server.listen(self.options.web_port, self.options.web_host)
        except OSError as e:
            message = (
                f"Web server failed to listen on {self.options.web_host or '*'}:"
                f"{self.options.web_port} with {e}"
            )
            if e.errno == errno.EADDRINUSE:
                message += (
                    "\nTry specifying a different port by using "
                    f"`--set web_port={self.options.web_port + 2}`."
                )
            raise OSError(e.errno, message, e.filename) from e

        logger.info(f"Web server listening at {self.web_url}")
        return await mitm_master.Master.running(self)

    async def done(self) -> None:
        if self._http_server is not None:
            try:
                self._http_server.stop()
                await self._http_server.close_all_connections()
            except Exception:
                logger.exception("关闭 mitmweb 服务失败")
            finally:
                self._http_server = None
        await super().done()


class HelperProtocol:
    def __init__(self):
        self._write_lock = threading.Lock()
        self._stdout = getattr(sys, "__stdout__", None) or sys.stdout

    def send(self, message_type: str, **payload):
        message = {"type": message_type, **payload}
        line = json.dumps(message, ensure_ascii=False)
        with self._write_lock:
            self._stdout.write(line + "\n")
            self._stdout.flush()


class BreakpointManager:
    def __init__(self):
        self._waiters: dict[tuple[str, str], asyncio.Future] = {}

    async def wait_for_continue(self, flow_id: str, stage: str) -> dict:
        """
        在事件循环线程中等待指定流量断点放行。
        :param flow_id: 流量id
        :param stage: 断点阶段（request/response）
        :return: 放行时携带的覆盖数据
        """
        loop = asyncio.get_running_loop()
        key = (flow_id, stage)
        future = loop.create_future()
        old_future = self._waiters.get(key)
        if old_future and not old_future.done():
            old_future.set_result({})
        self._waiters[key] = future
        try:
            result = await future
            return result if isinstance(result, dict) else {}
        finally:
            self._waiters.pop(key, None)

    def continue_flow(
        self,
        flow_id: str,
        stage: str,
        payload: dict | None = None,
    ) -> tuple[bool, str]:
        """
        放行指定流量断点。
        :param flow_id: 流量id
        :param stage: 断点阶段（request/response）
        :param payload: 覆盖请求/响应数据
        :return: 放行结果
        """
        key = (flow_id, stage)
        future = self._waiters.get(key)
        resolved_stage = stage
        if not future:
            for (wait_flow_id, wait_stage), wait_future in self._waiters.items():
                if wait_flow_id == flow_id and not wait_future.done():
                    future = wait_future
                    resolved_stage = wait_stage
                    break
        if not future:
            return False, "未找到可放行的断点，可能已被处理"
        if future.done():
            return False, "断点已放行"
        future.set_result(payload or {})
        return True, f"已放行 stage={resolved_stage}"

    def release_all(self, payload: dict | None = None):
        """
        释放全部等待中的断点，通常用于停止代理时兜底。
        :param payload: 释放时传递给等待方的数据
        :return:
        """
        data = payload or {}
        for key, future in list(self._waiters.items()):
            if not future.done():
                future.set_result(data)
            self._waiters.pop(key, None)


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
        self._breakpoint_manager = BreakpointManager()
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

        self.protocol.send(
            "state", state="starting", **self._runtime_state_payload(config=config)
        )
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

        self.protocol.send(
            "state",
            state="stopping",
            **self._runtime_state_payload(master=master),
        )

        if loop and master:
            try:
                loop.call_soon_threadsafe(self._request_session_shutdown, master)
            except RuntimeError:
                pass

        return True, "mitmproxy 停止请求已发送"

    def update_config(self, config_data: dict) -> tuple[bool, str]:
        config = MitmProxyConfigModel.model_validate(config_data)
        RuntimeConfig.set(config)
        state = None
        master = None
        with self._lock:
            self._config = config
            state = self._state
            master = self._master
        self.protocol.send(
            "state",
            state=state or "stopped",
            **self._runtime_state_payload(config=config, master=master),
        )
        return True, "配置已更新"

    def continue_flow(
        self,
        flow_id: str,
        stage: str,
        payload: dict | None = None,
    ) -> tuple[bool, str]:
        """
        放行处于断点暂停状态的请求或响应。
        :param flow_id: 流量id
        :param stage: 断点阶段（request/response）
        :param payload: 覆盖请求/响应数据
        :return: 放行结果
        """
        normalized_flow_id = str(flow_id or "").strip()
        normalized_stage = str(stage or "").strip().lower()
        if not normalized_flow_id:
            return False, "flow_id 不能为空"
        if normalized_stage not in {"request", "response"}:
            return False, "stage 仅支持 request 或 response"

        with self._lock:
            loop = self._loop
            state = self._state

        if not loop or state == "stopped":
            return False, "mitmproxy 未运行"

        result_future: concurrent.futures.Future = concurrent.futures.Future()

        def _resume():
            try:
                ok, message = self._breakpoint_manager.continue_flow(
                    normalized_flow_id,
                    normalized_stage,
                    payload if isinstance(payload, dict) else {},
                )
                result_future.set_result((ok, message))
            except Exception as e:
                result_future.set_result((False, f"放行失败: {e}"))

        loop.call_soon_threadsafe(_resume)
        try:
            return result_future.result(timeout=2.0)
        except concurrent.futures.TimeoutError:
            return False, "放行超时"

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
        self._breakpoint_manager.release_all({"release_reason": "shutdown"})
        proxyserver = master.addons.get("proxyserver")
        if proxyserver:
            asyncio_utils.create_task(
                proxyserver.servers.update([]),
                name="stop servers",
                keep_ref=True,
            )
        master.shutdown()

    def _normalize_startup_mode(self, startup_mode: str | None) -> str:
        mode = str(startup_mode or "dump").strip().lower()
        return mode if mode in {"dump", "web"} else "dump"

    def _should_emit_app_flows(self, config: MitmProxyConfigModel | None) -> bool:
        if not config:
            return True
        if (
            self._normalize_startup_mode(getattr(config, "startup_mode", "dump"))
            != "web"
        ):
            return True
        return bool(getattr(config, "web_show_in_app", True))

    def _runtime_state_payload(
        self,
        *,
        config: MitmProxyConfigModel | None = None,
        master: mitm_master.Master | None = None,
    ) -> dict:
        active_config = config
        active_master = master
        with self._lock:
            if active_config is None:
                active_config = self._config
            if active_master is None:
                active_master = self._master

        startup_mode = self._normalize_startup_mode(
            getattr(active_config, "startup_mode", "dump")
        )
        web_url = ""
        if startup_mode == "web" and isinstance(active_master, WebMaster):
            web_url = getattr(active_master, "web_url", "") or ""

        return {
            "startup_mode": startup_mode,
            "web_show_in_app": self._should_emit_app_flows(active_config),
            "web_url": web_url,
        }

    def _build_master(
        self,
        *,
        config: MitmProxyConfigModel,
        loop: asyncio.AbstractEventLoop,
    ) -> mitm_master.Master:
        if config.proxy_model == "local":
            logger.info("before ensure redirector")
            ok, message = ensure_windows_redirector_gui_subsystem()
            logger.info("after ensure redirector")
            if ok:
                logger.info(message)
            else:
                logger.warning(message)

        mode = [config.proxy_model] if config.proxy_model else []
        if config.proxy_model == "local":
            mode = [f"{config.proxy_model}:{config.proxy_model_value}"]

        config_dir = config.mitmproxy_config_dir
        if config_dir and not os.path.exists(config_dir):
            os.makedirs(config_dir)

        opts = Options(
            listen_host="127.0.0.1",
            listen_port=config.port,
            ssl_insecure=bool(config.ssl_insecure),
            mode=mode,
            confdir=config_dir or os.path.join(os.path.expanduser("~"), ".mitmproxy"),
        )

        startup_mode = self._normalize_startup_mode(config.startup_mode)
        if startup_mode == "web":
            master = ManagedWebMaster(opts, with_termlog=False)
            master.options.update(
                web_host="127.0.0.1",
                web_port=config.web_port,
                web_open_browser=bool(config.web_open_browser),
            )
        else:
            master = DumpMaster(
                opts,
                loop=loop,
                with_termlog=False,
                with_dumper=False,
            )

        master.addons.add(
            MockHandle(
                flow_dispatcher=self._dispatch_flow,
                breakpoint_manager=self._breakpoint_manager,
            )
        )
        return master

    async def _run_session(self, config: MitmProxyConfigModel):
        master = self._build_master(
            config=config,
            loop=asyncio.get_running_loop(),
        )

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
                    logger.info("before setup_servers")
                    ok = await proxyserver.setup_servers()
                    logger.info("after setup_servers")
                    if not ok:
                        raise RuntimeError("mitmproxy 服务器启动失败")

                await master.running()

                with self._lock:
                    self._state = "running"
                    should_stop = self._stop_requested

                self.protocol.send(
                    "state",
                    state="running",
                    **self._runtime_state_payload(config=config, master=master),
                )

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

                self.protocol.send(
                    "state",
                    state="stopped",
                    startup_mode=self._normalize_startup_mode(config.startup_mode),
                    web_show_in_app=self._should_emit_app_flows(config),
                    web_url="",
                )

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
        config = RuntimeConfig.get()
        if not self._should_emit_app_flows(config):
            return
        payload = asdict(item)
        payload["time"] = item.time.isoformat()
        message_type = "flow_new" if event_type == "new" else "flow_update"
        self.protocol.send(message_type, item=payload)


def main():
    protocol_stdout = getattr(sys, "__stdout__", None) or sys.stdout
    protocol_stderr = getattr(sys, "__stderr__", None) or sys.stderr
    if hasattr(protocol_stdout, "reconfigure"):
        protocol_stdout.reconfigure(line_buffering=True)
    if hasattr(protocol_stderr, "reconfigure"):
        protocol_stderr.reconfigure(line_buffering=True)

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
                elif cmd == "continue_flow":
                    ok, message = runtime.continue_flow(
                        command.get("flow_id", ""),
                        command.get("stage", ""),
                        command.get("payload") or {},
                    )
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
