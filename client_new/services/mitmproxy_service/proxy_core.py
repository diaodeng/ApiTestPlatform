import asyncio
import os
import threading
from enum import Enum

from loguru import logger
from mitmproxy.options import Options
from mitmproxy.tools.dump import DumpMaster
import psutil

from model.config import MitmProxyConfigModel

from .mock_handle import MockHandle
from .runtime_config import RuntimeConfig


class ProxyState(str, Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"


class ProxyCore:
    def __init__(self):
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._master: DumpMaster | None = None
        self._state = ProxyState.STOPPED
        self._lock = threading.Lock()
        self._baseline_child_pids: set[int] = set()
        self._created_child_pids: set[int] = set()

    @property
    def state(self) -> ProxyState:
        with self._lock:
            return self._state

    def is_running(self) -> bool:
        return self.state in (ProxyState.STARTING, ProxyState.RUNNING, ProxyState.STOPPING)

    def start(self, config: MitmProxyConfigModel) -> bool:
        with self._lock:
            if self._state != ProxyState.STOPPED:
                logger.warning(f"mitmproxy 已在运行态: {self._state}")
                return False
            self._state = ProxyState.STARTING
            self._baseline_child_pids = self._collect_child_pids()
            self._created_child_pids = set()

        # local 模式启动前清理系统残留 redirector，避免 "Cannot spawn more than one local redirector"
        if config.proxy_model == "local":
            self._cleanup_global_redirector()

        RuntimeConfig.set(config)
        self._thread = threading.Thread(
            target=self._run_loop,
            args=(config,),
            name="mitmproxy-thread",
            daemon=True,
        )
        self._thread.start()
        return True

    def stop(self, timeout: float = 5.0) -> bool:
        thread = None
        with self._lock:
            if self._state == ProxyState.STOPPED:
                return True
            self._state = ProxyState.STOPPING
            if self._loop and self._master:
                self._loop.call_soon_threadsafe(self._master.shutdown)
            thread = self._thread

        if thread:
            thread.join(timeout=timeout)

        # local 模式在 Windows 可能残留系统拦截辅助进程，这里做定向清理
        self._cleanup_residual_children()
        self._cleanup_global_redirector()

        with self._lock:
            stopped = self._state == ProxyState.STOPPED
            if not stopped:
                logger.warning("mitmproxy 未在超时时间内完成停止")
            return stopped

    def update_config(self, config: MitmProxyConfigModel):
        RuntimeConfig.set(config)

    def _run_loop(self, config: MitmProxyConfigModel):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        with self._lock:
            self._loop = loop

        try:
            loop.run_until_complete(self._run_proxy(config))
        except Exception as e:
            logger.exception(f"mitmproxy 运行异常: {e}")
        finally:
            self._cleanup_loop(loop)

    async def _run_proxy(self, config: MitmProxyConfigModel):
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

        master = DumpMaster(opts)
        master.addons.add(MockHandle())

        with self._lock:
            self._master = master
            self._state = ProxyState.RUNNING

        await master.run()

    def _cleanup_loop(self, loop: asyncio.AbstractEventLoop):
        with self._lock:
            self._master = None
            self._loop = None
            self._thread = None
            self._state = ProxyState.STOPPED

        try:
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        except Exception:
            pass
        finally:
            loop.close()

    def _collect_child_pids(self) -> set[int]:
        try:
            p = psutil.Process(os.getpid())
            return {child.pid for child in p.children(recursive=True)}
        except Exception:
            return set()

    def _refresh_created_children(self):
        current_children = self._collect_child_pids()
        self._created_child_pids = current_children - self._baseline_child_pids

    def _cleanup_residual_children(self):
        self._refresh_created_children()
        if not self._created_child_pids:
            return

        for pid in list(self._created_child_pids):
            try:
                proc = psutil.Process(pid)
                name = (proc.name() or "").lower()
                exe = (proc.exe() or "").lower()
                cmdline = " ".join(proc.cmdline()).lower()
                text = f"{name} {exe} {cmdline}"

                # 仅清理与 mitm/local-capture 相关的残留进程
                if any(k in text for k in ("mitm", "redirector", "windivert", "npcap")):
                    logger.warning(f"清理残留子进程 pid={pid}, name={proc.name()}")
                    proc.terminate()
                    try:
                        proc.wait(timeout=2)
                    except psutil.TimeoutExpired:
                        proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
            except Exception as e:
                logger.warning(f"清理残留进程失败 pid={pid}: {e}")

    def _cleanup_global_redirector(self):
        current_pid = os.getpid()
        for proc in psutil.process_iter(["pid", "name", "exe", "cmdline"]):
            try:
                if proc.info["pid"] == current_pid:
                    continue
                name = (proc.info.get("name") or "").lower()
                exe = (proc.info.get("exe") or "").lower()
                cmdline = " ".join(proc.info.get("cmdline") or []).lower()
                text = f"{name} {exe} {cmdline}"
                if "windows-redirector" not in text and "redirector" not in text:
                    continue
                logger.warning(f"清理全局残留 redirector pid={proc.pid}, name={proc.name()}")
                proc.terminate()
                try:
                    proc.wait(timeout=2)
                except psutil.TimeoutExpired:
                    proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
            except Exception as e:
                logger.warning(f"清理全局 redirector 失败 pid={proc.info.get('pid')}: {e}")
