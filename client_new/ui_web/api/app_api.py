import threading

from loguru import logger

from managers.pos_manager import PosManager
from plugins.manager import PLUGIN_DEFINITIONS, plugin_manager
from server.config import ThemeConfig
from ui_web.dialog_bridge import WebDialogService
from ui_web.event_bus import event_bus
from utils import VERSION


class AppApi:
    """
    全局应用层 API：主题、插件管理、文件对话框、全局状态、退出。

    对应原主窗口头部区域与插件管理对话框的后端逻辑。
    """

    def __init__(self, dialog_service: WebDialogService, window_holder):
        self._dialog_service = dialog_service
        # window_holder 为可调用对象，返回当前 pywebview 窗口（用于文件对话框）
        self._window_holder = window_holder
        self._installing_plugins: set[str] = set()
        self._lock = threading.Lock()

    # ===== 引导 =====

    def get_bootstrap(self) -> dict:
        """
        前端启动引导：主题模式、插件状态、当前 POS。
        导航项由前端按固定清单渲染，并按插件安装状态过滤 mitmproxy 入口。
        主题属于装饰性配置：文件损坏时降级为 auto 并提示，不让整个应用无法初始化。
        """
        try:
            theme = ThemeConfig.read_config().mode or "auto"
        except Exception as e:
            logger.error(f"theme_config.json 读取失败，主题降级为 auto: {e}")
            theme = "auto"
            event_bus.push(
                "ui_toast",
                {"level": "error", "message": f"主题配置异常: {e}"},
            )
        return {
            "ok": True,
            "version": VERSION,
            "theme": theme,
            "plugins": self._list_plugins(),
            "current_pos": PosManager.instance().get() or {},
        }

    # ===== 主题 =====

    def set_theme(self, mode: str) -> dict:
        """
        保存主题模式（auto/light/dark），前端据此切换 CSS 变量。
        """
        try:
            ThemeConfig.save_config({"mode": str(mode or "auto")})
            event_bus.push("theme_changed", {"mode": str(mode or "auto")})
            return {"ok": True}
        except Exception as e:
            logger.exception(f"保存主题配置失败: {e}")
            return {"ok": False, "message": str(e)}

    # ===== 全局状态 =====

    def get_global_status(self) -> dict:
        """
        底部状态栏数据：当前运行中的 POS。
        """
        current = PosManager.instance().get()
        if current:
            return {
                "ok": True,
                "running": True,
                "text": f"运行中 | 当前POS: {current.get('path') or '-'} | PID: {current.get('pid') or '-'}",
            }
        return {"ok": True, "running": False, "text": "就绪 | 当前运行POS: -"}

    # ===== 插件管理 =====

    def list_plugins(self) -> dict:
        return {"ok": True, "plugins": self._list_plugins()}

    def _list_plugins(self) -> list[dict]:
        plugins = []
        for name, definition in PLUGIN_DEFINITIONS.items():
            try:
                status = plugin_manager.get_status(name)
                status_text = plugin_manager.describe_status(name)
            except Exception as e:
                logger.warning(f"读取插件状态失败 name={name}: {e}")
                status, status_text = "missing", "未知"
            plugins.append(
                {
                    "name": name,
                    "title": getattr(definition, "title", name) or name,
                    "description": getattr(definition, "description", "") or "",
                    "status": status,
                    "status_text": status_text,
                    "busy": name in self._installing_plugins,
                }
            )
        return plugins

    def get_plugin_settings(self) -> dict:
        """
        插件管理配置：下载源、安装目录。
        """
        try:
            return {
                "ok": True,
                "download_base_url": plugin_manager.read_download_base_url(),
                "install_dir": str(plugin_manager.get_plugin_root()),
            }
        except Exception as e:
            logger.exception(f"读取插件配置失败: {e}")
            return {"ok": False, "message": str(e)}

    def save_plugin_download_url(self, base_url: str) -> dict:
        ok, message = plugin_manager.save_download_base_url(str(base_url or "").strip())
        return {"ok": bool(ok), "message": message}

    def save_plugin_install_dir(self, install_dir: str, migrate: bool = True) -> dict:
        ok, message = plugin_manager.set_install_dir(str(install_dir or "").strip(), bool(migrate))
        return {"ok": bool(ok), "message": message}

    def install_plugin_online(self, name: str) -> dict:
        """
        在线下载并安装插件（后台线程执行，完成推送 plugin_install_done）。
        """
        return self._run_plugin_task(name, "online", lambda: plugin_manager.download_and_install(name))

    def install_plugin_zip(self, name: str, zip_path: str) -> dict:
        """
        从本地 zip 安装插件。
        """
        if not zip_path:
            return {"ok": False, "message": "请先选择插件压缩包"}
        return self._run_plugin_task(
            name, "zip", lambda: plugin_manager.install_from_zip(name, zip_path)
        )

    def _run_plugin_task(self, name: str, mode: str, task) -> dict:
        with self._lock:
            if name in self._installing_plugins:
                return {"ok": False, "message": "该插件任务正在进行中"}
            self._installing_plugins.add(name)
        event_bus.push("plugin_status_changed", {"plugins": self._list_plugins()})

        def worker():
            try:
                ok, message = task()
            except Exception as e:
                logger.exception(f"插件任务失败 name={name}, mode={mode}: {e}")
                ok, message = False, str(e)
            self._installing_plugins.discard(name)
            logger.info(f"插件任务完成 name={name}, mode={mode}, ok={ok}: {message}")
            event_bus.push(
                "plugin_install_done",
                {"name": name, "ok": bool(ok), "message": message, "plugins": self._list_plugins()},
            )

        threading.Thread(target=worker, name=f"plugin-{mode}-{name}", daemon=True).start()
        return {"ok": True, "message": "任务已开始"}

    # ===== 文件/目录选择 =====

    def choose_file(self, title: str = "选择文件", file_types: str = "") -> dict:
        """
        弹出系统文件选择对话框，返回选中路径。

        :param file_types: 形如 "日志文件 (*.log;*.txt)|所有文件 (*.*)" 的过滤串
        """
        import webview

        window = self._window_holder()
        if window is None:
            return {"ok": False, "message": "窗口不可用"}
        # pywebview 要求 file_types 为字符串列表，形如 "描述 (*.a;*.b)"
        filters = self._parse_file_types(file_types) or ["所有文件 (*.*)"]
        result = window.create_file_dialog(
            dialog_type=webview.OPEN_DIALOG,
            file_types=filters,
        )
        # create_file_dialog 返回元组或列表
        path = ""
        if isinstance(result, (list, tuple)) and result:
            path = str(result[0] or "")
        elif isinstance(result, str):
            path = result
        return {"ok": bool(path), "path": path}

    def choose_dir(self, title: str = "选择目录") -> dict:
        """
        弹出系统目录选择对话框，返回选中目录。
        """
        import webview

        window = self._window_holder()
        if window is None:
            return {"ok": False, "message": "窗口不可用"}
        # FOLDER_DIALOG 已弃用，统一使用 FileDialog 枚举
        dialog_type = getattr(webview.FileDialog, "FOLDER", webview.FOLDER_DIALOG)
        result = window.create_file_dialog(dialog_type=dialog_type)
        path = ""
        if isinstance(result, (list, tuple)) and result:
            path = str(result[0] or "")
        elif isinstance(result, str):
            path = result
        return {"ok": bool(path), "path": path}

    @staticmethod
    def _parse_file_types(file_types: str) -> list[str]:
        """
        把 "描述 (*.a;*.b)|描述2 (*.c)" 解析为 pywebview 需要的
        ["描述 (*.a;*.b)", "描述2 (*.c)"] 字符串列表形式。

        注意：pywebview 内部用正则对每个过滤项做字符串匹配，
        传元组会抛 TypeError: expected string or bytes-like object。
        """
        if not file_types:
            return []
        filters = []
        for part in file_types.split("|"):
            part = part.strip()
            if not part:
                continue
            desc, _, pattern = part.partition("(")
            pattern = pattern.replace(")", "").strip() or "*.*"
            filters.append(f"{(desc.strip() or '文件')} ({pattern})")
        return filters

    # ===== 弹窗应答与退出 =====

    def log_js_error(self, kind: str, message: str, source: str = "", lineno: int = 0) -> dict:
        """
        接收前端运行时错误上报并写入日志（index.html 全局 error 钩子调用）。

        :param kind: js_error（同步错误）/ js_rejection（未处理的 Promise 拒绝）
        :param message: 错误消息
        :param source: 出错脚本地址
        :param lineno: 出错行号
        """
        logger.error(f"前端{kind}: {message} @ {source}:{lineno}")
        return {"ok": True}

    def resolve_dialog(self, req_id: str, value) -> dict:
        """
        前端模态框操作结果回传（confirm/choice）。
        """
        ok = self._dialog_service.resolve(str(req_id or ""), value)
        return {"ok": ok}

    def quit_app(self, confirm_text: str = "") -> dict:
        """
        前端发起退出应用（供“退出”菜单/更新完成流程使用）。
        """
        logger.info("前端请求退出应用")
        window = self._window_holder()
        if window is not None:
            try:
                window.destroy()
            except Exception as e:
                logger.warning(f"关闭窗口失败: {e}")
        return {"ok": True}
