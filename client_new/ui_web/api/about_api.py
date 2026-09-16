import asyncio
import threading

from loguru import logger

from ui_web.event_bus import event_bus
from utils import VERSION, get_build_label
from utils.common import (
    check_app_has_new,
    get_client_update_runtime_profile,
    perform_update_with_powershell,
)


class AboutApi:
    """
    关于页面后端桥（替代原 Qt 页面的检查/执行更新线程）。

    - check_update：后台线程检查新版本，直接返回结果；
    - perform_update：后台线程执行 PowerShell 自更新，进度经
      "update_progress" 事件推送，完成后返回结果（成功后前端关闭应用）。
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._updating = False

    def get_info(self) -> dict:
        """
        返回版本与运行形态信息。
        """
        profile = get_client_update_runtime_profile()
        return {
            "ok": True,
            "version": VERSION,
            # 构建信息标签（模式/tag/commit/时间），未走构建脚本时为空串
            "build_label": get_build_label(),
            "package_mode_label": profile.get("package_mode_label", ""),
            "preferred_asset_label": profile.get("preferred_asset_label", ""),
        }

    def check_update(self) -> dict:
        """
        检查是否有新版本，返回提示与 release 信息（Markdown 文本）。
        """
        try:
            has_new, info = asyncio.run(check_app_has_new())
            if has_new:
                message = f"当前版本: {VERSION}  新版本: {has_new}"
            else:
                message = f"当前版本: {VERSION}，已经是最新版本"
            return {"ok": True, "has_new": bool(has_new), "message": message, "info": info or ""}
        except Exception as e:
            logger.exception(e)
            return {"ok": False, "has_new": False, "message": f"检查更新失败: {e}", "info": ""}

    def perform_update(self, force_update: bool = False) -> dict:
        """
        执行自更新（PowerShell 脚本）。

        :param force_update: 是否跳过“有新版本”检查强制更新
        """
        with self._lock:
            if self._updating:
                return {"ok": False, "message": "更新任务正在进行中"}
            self._updating = True

        def worker():
            try:
                if not force_update:
                    has_new, _ = asyncio.run(check_app_has_new())
                    if not has_new:
                        event_bus.push("update_done", {"ok": False, "message": f"当前版本 {VERSION} 已是最新"})
                        return

                def _on_progress(text: str):
                    event_bus.push("update_progress", {"text": str(text or "")})

                success, message = asyncio.run(
                    perform_update_with_powershell(_on_progress, force=force_update)
                )
                event_bus.push("update_done", {"ok": bool(success), "message": message})
            except Exception as e:
                logger.exception(e)
                event_bus.push("update_done", {"ok": False, "message": f"更新失败: {e}"})
            finally:
                self._updating = False

        threading.Thread(target=worker, name="app-update", daemon=True).start()
        return {"ok": True, "message": "更新任务已开始"}
