import os
from pathlib import Path

from loguru import logger


def get_static_dir() -> Path:
    """
    前端静态资源目录：源码运行时在包内 static/；打包（PyInstaller）时
    兼容 _MEIPASS 解压目录下的 ui_web_static。
    """
    import sys

    frozen_static = getattr(sys, "_MEIPASS", None)
    if frozen_static:
        candidate = Path(frozen_static) / "ui_web_static"
        if candidate.is_dir():
            return candidate
    return Path(__file__).resolve().parent / "static"


def run_app() -> int:
    """
    装配并运行 pywebview 窗口（阻塞直到窗口关闭）。

    启动内容：
    - 单实例判定（重复启动时激活旧窗口并退出）；
    - Bridge js_api（前端 window.pywebview.api.*）；
    - EventBus 绑定窗口用于事件推送；
    - 关闭时执行 Bridge.shutdown 清理后台任务（mitm helper、Agent 连接等）。

    :return: 进程退出码
    """
    import webview

    from ui_web.api.bridge import Bridge
    from ui_web.event_bus import event_bus
    from ui_web.utils.single_instance import SingleInstanceManager

    single_instance = SingleInstanceManager()
    if not single_instance.acquire():
        return 0

    static_dir = get_static_dir()
    entry = static_dir / "index.html"
    if not entry.exists():
        logger.error(f"前端入口不存在: {entry}")
        return 1

    bridge_holder = {"window": None, "bridge": None}

    def window_holder():
        return bridge_holder["window"]

    bridge = Bridge(window_holder)
    bridge_holder["bridge"] = bridge

    window = webview.create_window(
        "QTRClient",
        str(entry),
        js_api=bridge,
        width=1280,
        height=860,
        min_size=(1000, 640),
    )
    bridge_holder["window"] = window
    event_bus.bind(window)

    def _on_closed():
        logger.info("主窗口已关闭，执行清理")
        bridge.shutdown()
        event_bus.unbind()
        single_instance.release()

    window.events.closed += _on_closed

    # HTTP server 必须开启：ES module 脚本在 file:// 协议下会被 WebView 拦截，
    # 通过内置 HTTP 服务托管静态资源才能正常加载前端模块。
    debug = os.environ.get("QTRCLIENT_WEBVIEW_DEBUG") == "1"
    logger.info("启动 pywebview 主窗口")
    try:
        webview.start(debug=debug, http_server=True)
    except Exception as e:
        logger.exception(f"pywebview 运行异常: {e}")
        bridge.shutdown()
        return 1
    return 0
