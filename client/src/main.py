import os
from multiprocessing import freeze_support

import flet as ft

from common import appState
from config import AppConfig
from navigationMenu import NavigationMenu
from utils import VERSION
from utils.common import (
    ensure_directory_exists,
    get_sys_info_view as refresh_sys_info_cache,
    load_json,
)
from utils.logger import log
from utils.mytimers import ThreadPool
from view_contents.exitAlertDialog import ExitAlertDialog

ensure_directory_exists("logs")

basepath = os.path.dirname(__file__)


async def main(page: ft.Page):
    page.window.prevent_close = True
    exit_dialog = ExitAlertDialog(page)
    page.window.on_event = lambda e: page.open(exit_dialog.confirm_dialog) if e.data == "close" else None
    app = AppConfig(page)
    config = load_json(app.tools_db) or {}
    config["ToolsConfig"] = os.path.join(basepath, app.tools_db)

    # page.appbar = ft.AppBar(
    #     leading=ft.Container(padding=5, content=ft.Image(src=f"logo.svg")),
    #     leading_width=40,
    #     title=ft.Text("QTRClient"),
    #     center_title=True,
    #     bgcolor=ft.Colors.INVERSE_PRIMARY,
    #     actions=[
    #         ft.Container(
    #             padding=10, content=ft.Text(f"Flet version: {flet.version.version}")
    #         )
    #     ],
    # )
    sys_show_view = ft.Text("正在获取信息...", selectable=True)

    # 加载菜单及应用资源
    nav_menu = NavigationMenu(ft, page, log, **config)
    # 主布局
    page.add(
        ft.Column(
            [
                ft.Row(
                    [
                        nav_menu.nav_rail_menu(),
                        ft.VerticalDivider(width=1),
                        nav_menu.ref_content_area(),
                    ],
                    expand=True,
                ),
                ft.Divider(height=1),
                ft.Row(
                    controls=[
                        sys_show_view,
                        ft.Text(f"当前版本: {VERSION}", size=16, text_align=ft.TextAlign.END),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
            ],
            expand=True,
            # spacing=0  # 垂直分割线与水平分割线是否相接
        )
    )

    def close_dlg(e):
        dlg_modal.open = False
        e.control.page.update()

    dlg_modal = ft.AlertDialog(
        modal=True,
        title=ft.Text("异常了"),
        content=ft.Text("请联系管理员"),
        actions=[
            ft.TextButton("确定", on_click=close_dlg),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
        # on_dismiss=lambda e: print("Modal dialog dismissed!"),
    )

    def open_dlg(e):
        dlg_modal.content = ft.Text(e.data)
        e.control.page.overlay.append(dlg_modal)
        dlg_modal.open = True
        e.control.page.update()

    def sync_sys_info_view():
        toolbar_info = appState.client_info.toolbar_info or "正在获取信息..."
        if sys_show_view.value == toolbar_info:
            return
        sys_show_view.value = toolbar_info
        try:
            sys_show_view.update()
        except Exception as ex:
            log.debug(f"系统信息视图更新失败: {ex}")

    ThreadPool.add_task(refresh_sys_info_cache, 10)
    ThreadPool.add_task(sync_sys_info_view, 1)
    page.on_error = lambda e: log.error(f"页面异常:{e}")
    # page.on_window_event = lambda e: open_dlg(e) if e.data == "close" else None

    page.update()


# ft.app(target=main, view=ft.WEB_BROWSER)
if __name__ == "__main__":
    freeze_support()
    log.info("app start")
    # multiprocessing.set_start_method("spawn")
    ft.app(target=main)
