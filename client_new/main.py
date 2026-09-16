import faulthandler
import os
import sys
import threading
from datetime import datetime
from multiprocessing import freeze_support

_FAULT_LOG_FILE = None


def _install_global_exception_handlers():
    from utils.logger import logger

    def _log_uncaught_exception(prefix, exc_type, exc_value, exc_traceback):
        if exc_type is None:
            return
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        if exc_value is None:
            exc_value = exc_type(prefix)
        logger.opt(exception=(exc_type, exc_value, exc_traceback)).critical(prefix)

    def _sys_excepthook(exc_type, exc_value, exc_traceback):
        _log_uncaught_exception("主线程未捕获异常", exc_type, exc_value, exc_traceback)

    def _thread_excepthook(args):
        thread_name = getattr(getattr(args, "thread", None), "name", "") or "unknown"
        _log_uncaught_exception(
            f"线程未捕获异常[{thread_name}]",
            getattr(args, "exc_type", None),
            getattr(args, "exc_value", None),
            getattr(args, "exc_traceback", None),
        )

    def _unraisablehook(unraisable):
        exc_value = getattr(unraisable, "exc_value", None)
        message = getattr(unraisable, "err_msg", None) or "存在未处理的不可抛出异常"
        obj = getattr(unraisable, "object", None)
        if obj is not None:
            message = f"{message}: {obj!r}"
        logger.opt(exception=exc_value).error(message)

    sys.excepthook = _sys_excepthook
    if hasattr(threading, "excepthook"):
        threading.excepthook = _thread_excepthook
    if hasattr(sys, "unraisablehook"):
        sys.unraisablehook = _unraisablehook

    global _FAULT_LOG_FILE
    try:
        os.makedirs("logs", exist_ok=True)
        _FAULT_LOG_FILE = open(
            os.path.join("logs", "fatal_error.log"),
            "a",
            encoding="utf-8",
            buffering=1,
        )
        _FAULT_LOG_FILE.write(
            f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] faulthandler enabled\n"
        )
        faulthandler.enable(file=_FAULT_LOG_FILE, all_threads=True)
    except Exception as e:
        logger.warning(f"启用 faulthandler 失败: {e}")


if __name__ == "__main__":
    if "--mitm-helper" in sys.argv:
        # helper 子进程同样需要先激活插件目录（mitmproxy 已拆为 proxy 插件）；
        # 打包态下插件根目录按 exe 所在目录解析，不受 cwd 影响
        try:
            from plugins.manager import plugin_manager

            plugin_manager.activate_installed()
        except Exception:
            pass
        from services.mitmproxy_service.helper_process import main as mitm_helper_main

        mitm_helper_main()
        sys.exit(0)

    from utils.logger import logger

    logger.info("应用开始启动（pywebview 界面）")
    freeze_support()
    # 在导入任何业务模块之前激活已安装插件目录，
    # 使 desktop_test_service / playwright 的守卫导入能命中插件包；
    # 激活失败只记录日志，不阻塞主功能启动。
    try:
        from plugins.manager import plugin_manager

        plugin_manager.activate_installed()
    except Exception as e:
        logger.warning(f"插件激活失败（不影响主功能）: {e}")
    _install_global_exception_handlers()
    if sys.platform.startswith("win"):
        try:
            import ctypes

            # 任务栏分组用 AppUserModelID，保持与旧版一致
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "api-test-platform.client.qtrclient"
            )
        except Exception:
            pass

    from ui_web.app import run_app

    exit_code = run_app()
    logger.info(f"应用退出 exit_code={exit_code}")
    sys.exit(exit_code)
