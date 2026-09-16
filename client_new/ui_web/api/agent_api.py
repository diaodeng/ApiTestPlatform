import threading
from datetime import datetime

from loguru import logger

from model.config import AgentBrowserConfigModel, AgentConfigModel
from server.config import AgentConfig
from server.remote_config_server import RemoteConfigServer
from services.agent_client_service import AgentClientService
from services.playwright_browser_runtime import (
    add_install_event_listener,
    install_playwright_browser_sync,
    remove_install_event_listener,
)
from ui_web.event_bus import event_bus
from utils.common import get_active_mac


class AgentApi:
    """
    Agent 页面后端桥（替代原 Qt AgentController）。

    保留原状态机：stopped → starting（准备：MAC 解析 + 配置读取）→
    running（AgentClientService 回调 connected）→ stopping → stopped。
    原 QThread/QTimer/Signal 全部替换为 threading.Thread + EventBus：
    - agent_state / agent_status / agent_error：连接状态与提示推送；
    - agent_request / agent_response：请求/响应日志推送；
    - agent_install_log：Playwright 浏览器下载日志推送。
    """

    def __init__(self):
        self.config = AgentConfig.read_config()
        self.local_mac = ""
        self.connection_state = "stopped"
        self.service = AgentClientService()
        self._lock = threading.Lock()
        self._config_syncing = False
        self._browser_installing = False
        self._bind_service()
        self._register_install_listener()
        self._refresh_local_mac_async()

    # ===== 前端调用的接口 =====

    def get_state(self) -> dict:
        """
        返回配置、连接状态与本机 MAC，前端进入页面时调用。
        """
        self.config = AgentConfig.read_config()
        return {
            "ok": True,
            "config": self.config.model_dump(),
            "state": self.connection_state,
            "local_mac": self.local_mac,
        }

    def start(self) -> dict:
        """
        启动 Agent 连接：先做连接准备（MAC/配置），完成后真正建连。
        """
        with self._lock:
            if self.connection_state in {"starting", "running", "stopping"}:
                logger.warning(f"Agent 启动请求被忽略，当前状态: {self.connection_state}")
                return {"ok": False, "message": f"当前状态 {self.connection_state}"}

        logger.info("Agent 开始连接准备（MAC 解析与配置读取）")
        self.connection_state = "starting"
        self._push_status("正在准备连接...")
        self._push_state()

        # 连接准备存在磁盘与网络枚举开销，放后台线程执行。
        thread = threading.Thread(target=self._connect_prepare_worker, name="agent-connect-prepare", daemon=True)
        thread.start()
        return {"ok": True, "message": "Agent 连接中"}

    def stop(self) -> dict:
        """
        停止 Agent 连接；连接准备阶段直接取消启动。
        """
        if self.connection_state == "starting" and not self.service.is_running():
            logger.info("Agent 处于连接准备阶段，直接取消启动")
            self.connection_state = "stopped"
            self._push_status("已取消连接")
            self._push_state()
            return {"ok": True, "message": "已取消连接"}

        if self.connection_state in {"stopped", "stopping"}:
            return {"ok": True, "message": "Agent 未在运行"}

        logger.info("停止 Agent 连接")
        self.connection_state = "stopping"
        self._push_state()
        ok, message = self.service.stop()
        if not ok:
            self.connection_state = "stopped"
            self._push_status(message)
            self._push_state()
        return {"ok": ok, "message": message}

    def save_config(self, data: dict) -> dict:
        """
        保存 Agent 配置；配置拉取地址变更时重置同步标记。
        """
        try:
            config = AgentConfigModel.model_validate(data)
        except Exception as e:
            logger.exception(f"保存 Agent 配置失败: {e}")
            return {"ok": False, "message": f"配置无效: {e}"}

        previous_sync_url = (self.config.config_sync_url or "").strip()
        current_sync_url = (config.config_sync_url or "").strip()
        if current_sync_url != previous_sync_url:
            config.config_sync_initialized = False
            config.config_sync_last_sync_at = ""

        AgentConfig.save_config(config)
        self.config = AgentConfig.read_config()
        self.service.update_runtime_config(self.config)
        self._push_state()
        logger.info("Agent 配置已保存")
        return {"ok": True, "config": self.config.model_dump(), "message": "配置已保存"}

    def save_server(self, name: str, url: str, old_url: str = "") -> dict:
        """
        新增/修改服务器（服务器管理弹窗使用）。

        server_list 结构与旧版一致：{服务地址: 服务名称}，current_server 存地址。

        :param name: 服务名称
        :param url: 服务地址
        :param old_url: 修改前的服务地址，为空表示新增
        """
        name = str(name or "").strip()
        url = str(url or "").strip()
        old_url = str(old_url or "").strip()
        if not name or not url:
            return {"ok": False, "message": "名称与地址不能为空"}

        config = AgentConfig.read_config()
        if old_url and old_url != url:
            if url in config.server_list:
                return {"ok": False, "message": f"服务地址已存在: {url}"}
            config.server_list.pop(old_url, None)
            if config.current_server == old_url:
                config.current_server = url
        config.server_list[url] = name
        AgentConfig.save_config(config)
        self.config = AgentConfig.read_config()
        logger.info(f"Agent 服务器已保存: {name} -> {url}")
        return {"ok": True, "config": self.config.model_dump()}

    def delete_server(self, url: str) -> dict:
        """
        删除指定服务地址（server_list 按 {地址: 名称} 组织）。
        """
        url = str(url or "").strip()
        config = AgentConfig.read_config()
        if url not in config.server_list:
            return {"ok": False, "message": f"服务器不存在: {url}"}
        config.server_list.pop(url, None)
        if config.current_server == url:
            config.current_server = next(iter(config.server_list), "")
        AgentConfig.save_config(config)
        self.config = AgentConfig.read_config()
        logger.info(f"Agent 服务器已删除: {url}")
        return {"ok": True, "config": self.config.model_dump()}

    def sync_config(self) -> dict:
        """
        触发远程配置同步（后台线程执行，完成后推送 agent_status）。
        """
        with self._lock:
            if self._config_syncing:
                return {"ok": False, "message": "配置同步正在进行中"}
            self._config_syncing = True

        config = AgentConfig.read_config()
        config_url = (config.config_sync_url or "").strip()
        if not config_url:
            self._config_syncing = False
            return {"ok": False, "message": "请先在服务器管理中填写配置拉取地址"}

        self._push_status("正在更新 Agent 配置...")
        event_bus.push("agent_config_syncing", {"syncing": True})
        thread = threading.Thread(
            target=self._config_sync_worker, args=(config_url,), name="agent-config-sync", daemon=True
        )
        thread.start()
        return {"ok": True, "message": "配置同步已开始"}

    def manual_download_browser(self, browser_name: str, browser_payload: dict) -> dict:
        """
        按当前配置手动下载指定 Playwright 浏览器（后台线程执行）。
        """
        with self._lock:
            if self._browser_installing:
                event_bus.push("agent_manual_downloading", {"downloading": True, "message": "已有下载任务进行中"})
                return {"ok": False, "message": "已有浏览器下载任务在进行中"}
            self._browser_installing = True

        try:
            browser_config = AgentBrowserConfigModel.model_validate(browser_payload or {})
        except Exception as exc:
            self._browser_installing = False
            return {"ok": False, "message": f"浏览器配置无效: {exc}"}

        self.config = AgentConfig.read_config()
        self.config.browser = browser_config
        AgentConfig.save_config(self.config)
        self.config = AgentConfig.read_config()
        self.service.update_runtime_config(self.config)

        target_browser = str(browser_name or "chromium").strip().lower() or "chromium"
        self._push_status(f"开始手动下载浏览器: {target_browser}")
        event_bus.push(
            "agent_manual_downloading",
            {"downloading": True, "message": f"正在下载 {target_browser} ..."},
        )
        thread = threading.Thread(
            target=self._browser_install_worker,
            args=(target_browser, self.config.browser.model_dump()),
            name="agent-browser-install",
            daemon=True,
        )
        thread.start()
        return {"ok": True, "message": f"开始下载 {target_browser}"}

    def shutdown(self) -> None:
        """
        应用退出时关闭连接服务并注销监听。
        """
        try:
            self.service.shutdown()
        except Exception as e:
            logger.exception(f"关闭 Agent 服务失败: {e}")
        self._unregister_install_listener()

    # ===== 后台任务 =====

    def _connect_prepare_worker(self):
        """
        连接准备：MAC 解析与配置读取，完成后真正启动连接。
        """
        try:
            mac = get_active_mac() or ""
        except Exception as e:
            logger.exception(f"连接前获取本机 MAC 失败: {e}")
            mac = ""
        try:
            config = AgentConfig.read_config()
        except Exception as e:
            logger.exception(f"连接前读取 Agent 配置失败: {e}")
            config = None

        if config is not None:
            self.config = config
        if mac:
            self.local_mac = mac
            event_bus.push("agent_mac", {"mac": self.local_mac})

        if self.connection_state != "starting":
            logger.info(f"Agent 连接准备完成但状态已变为 {self.connection_state}，放弃启动")
            return

        server = (self.config.current_server or "").strip()
        if not server:
            self.connection_state = "stopped"
            self._push_status("请先选择服务器")
            self._push_state()
            return

        connect_url = self._build_connect_url(server)
        logger.info(f"启动 Agent 连接: {connect_url}")
        ok, message = self.service.start(self.config, connect_url)
        if not ok:
            self.connection_state = "stopped"
            self._push_state()
            self._push_status(message)

    def _config_sync_worker(self, config_url: str):
        try:
            result = RemoteConfigServer.sync_agent_config(config_url)
            self.config = AgentConfig.read_config()
            self.service.update_runtime_config(self.config)
            updated_at = str((result or {}).get("updated_at") or "").strip() if isinstance(result, dict) else ""
            message = "Agent 配置已更新"
            if updated_at:
                message = f"{message}，服务端更新时间：{updated_at}"
            self._push_status(message)
            event_bus.push("agent_config_sync_result", {"ok": True, "message": message})
            event_bus.push("agent_config_syncing", {"syncing": False})
        except Exception as e:
            logger.exception(e)
            error_message = f"更新 Agent 配置失败: {e}"
            self._push_status(error_message)
            event_bus.push("agent_config_sync_result", {"ok": False, "message": error_message})
            event_bus.push("agent_config_syncing", {"syncing": False})
        finally:
            self._config_syncing = False

    def _browser_install_worker(self, browser_name: str, browser_config_payload: dict):
        """
        后台执行手动浏览器下载，完成后推送结束事件。
        """
        try:
            browser_config = AgentBrowserConfigModel.model_validate(browser_config_payload)
            request_options = {
                "browserInstallDir": browser_config.install_dir,
                "playwrightDownloadHost": browser_config.playwright_download_host,
                "playwrightDownloadProxy": browser_config.playwright_download_proxy,
            }
            install_playwright_browser_sync(browser_name, request_options=request_options)
            status_text = f"浏览器下载完成: {browser_name} 下载完成"
            event_bus.push(
                "agent_manual_downloading",
                {"downloading": False, "message": status_text, "ok": True},
            )
        except Exception as exc:
            logger.exception(f"手动下载浏览器失败: {exc}")
            status_text = f"浏览器下载失败: {exc}"
            event_bus.push(
                "agent_manual_downloading",
                {"downloading": False, "message": status_text, "ok": False},
            )
        self._push_status(status_text)
        self._browser_installing = False

    def _refresh_local_mac_async(self):
        def worker():
            try:
                mac = get_active_mac() or ""
            except Exception as e:
                logger.exception(f"获取本机 MAC 失败: {e}")
                mac = ""
            if mac and mac != self.local_mac:
                self.local_mac = mac
                event_bus.push("agent_mac", {"mac": self.local_mac})

        threading.Thread(target=worker, name="agent-local-mac", daemon=True).start()

    # ===== 事件转发 =====

    def _build_connect_url(self, server: str) -> str:
        base = (server or "").strip().rstrip("/")
        if not self.local_mac:
            return base
        return f"{base}/{self.local_mac}"

    def _bind_service(self):
        """
        订阅 AgentClientService 事件并转发到前端。
        """
        self.service.add_listener("state_changed", self._on_service_state_changed)
        self.service.add_listener("status_message", lambda msg: self._push_status(msg))
        self.service.add_listener(
            "request_message",
            lambda msg: self.config.show_logs and event_bus.push("agent_request", {"text": msg}),
        )
        self.service.add_listener(
            "response_message",
            lambda msg: self.config.show_logs and event_bus.push("agent_response", {"text": msg}),
        )
        self.service.add_listener("error_message", self._on_service_error)

    def _on_service_state_changed(self, state: str):
        self.connection_state = state or "stopped"
        self._push_state()

    def _on_service_error(self, message: str):
        logger.error(message)
        event_bus.push("agent_error", {"message": message})
        self._push_status(message)

    def _register_install_listener(self):
        add_install_event_listener(self._forward_install_log)

    def _unregister_install_listener(self):
        try:
            remove_install_event_listener(self._forward_install_log)
        except Exception as e:
            logger.debug(f"移除浏览器安装日志监听失败: {e}")

    def _forward_install_log(self, message: str):
        text = str(message or "").strip()
        if not text:
            return
        self._push_status(text)
        timestamp = datetime.now().strftime("%H:%M:%S")
        event_bus.push("agent_install_log", {"text": f"[{timestamp}] [浏览器下载] {text}"})

    def _push_state(self):
        event_bus.push(
            "agent_state",
            {
                "state": self.connection_state,
                "running": self.connection_state in {"starting", "running", "stopping"},
            },
        )

    def _push_status(self, message: str):
        event_bus.push("agent_status", {"message": str(message or "")})
