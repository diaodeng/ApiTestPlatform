import os
import sys
from multiprocessing import freeze_support

import flet as ft

from config import AppConfig
from navigationMenu import NavigationMenu
from utils.common import load_json, ensure_directory_exists
from utils.logger import log
from view_contents.alertDialog.exitAlertDialog import ExitApplicationDialog

ensure_directory_exists("logs")
basepath = os.path.dirname(__file__)



async def main(page: ft.Page):
    app = AppConfig(page)
    config = load_json(app.tools_db)
    config["ToolsConfig"] = os.path.join(basepath, app.tools_db)
    sys_show_view = ft.Text("正在获取信息...")

    def window_event(e):
        if e.data == "close":
            page.open(ExitApplicationDialog(ft.AlertDialog))
            page.update()

    # 自定义title_bar
    title_bar = ft.WindowDragArea(
        ft.Container(
            ft.Text(
                # "Drag this area to move, maximize and restore application window.",
                height=35
            ),
            # bgcolor=ft.Colors.AMBER_300,
            padding=0,
            margin=0
        ),
        expand=True,
        height=35
    )

    page.window.prevent_close = True
    page.window.on_event = window_event

    # 加载菜单及应用资源
    nav_menu = NavigationMenu(ft, page, log, **config)
    # 主布局
    page.add(
        ft.Row([
            title_bar,
            ft.IconButton(ft.Icons.EXIT_TO_APP_ROUNDED, tooltip="退出", on_click=lambda _: page.window.close()),
        ]),
        ft.Column(
            [
                ft.Row(
                    [
                        nav_menu.nav_rail_menu(),
                        ft.VerticalDivider(width=1),
                        nav_menu.ref_content_area(),
                    ],
                    expand=True
                ),
                ft.Divider(height=1),
                ft.Row(
                    controls=[
                        sys_show_view,
                        ft.Text(
                            f"当前版本: {app.version}",
                            size=12,
                            text_align=ft.TextAlign.END
                        )
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
            ],
            expand=True,
            # spacing=0  # 垂直分割线与水平分割线是否相接
        )
    )
    page.update()

if __name__ == "__main__":
    freeze_support()
    log.info("app start")
    ft.app(target=main)
