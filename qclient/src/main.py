import os
from multiprocessing import freeze_support
import flet as ft
from config import AppConfig
from navigationMenu import NavigationMenu
from utils.common import load_json, ensure_directory_exists
from utils.logger import log
from utils.common import get_mac_address
from view_contents.alertDialog.exitAlertDialog import ExitApplicationDialog

ensure_directory_exists("logs")
basepath = os.path.dirname(__file__)

async def main(page: ft.Page):
    app = AppConfig(page)
    config = load_json(app.tools_db)
    config["ToolsConfig"] = os.path.join(basepath, app.tools_db)
    sys_show_view = ft.Text("正在获取信息...")
    log.info(f"testmac:{get_mac_address()}")
    def minimize_window(e):
        page.window.minimized = True
        page.update()

    def toggle_maximize(e):
        page.window.maximized = not page.window.maximized
        page.update()

    def window_event(e):
        if e.data == "maximized":
            pass

        if e.data == "close":
            page.open(ExitApplicationDialog(ft.AlertDialog))
            page.update()

    # 自定义header_bar
    header_bar = ft.WindowDragArea(
        ft.Container(
            ft.Column(
                [
                    # 第一行：居中的标题文本
                    ft.Container(
                        # content=ft.Text("Qclient", text_align=ft.TextAlign.CENTER, size=16, weight=ft.FontWeight.BOLD),
                        alignment=ft.alignment.center,
                        height=40
                    ),
                    # 第二行：靠右的按钮组
                    ft.Container(
                        content=ft.Row(
                            [
                                ft.IconButton(ft.Icons.REMOVE, tooltip="最小化", on_click=minimize_window),
                                ft.IconButton(ft.Icons.CROP_SQUARE, tooltip="最大化", on_click=toggle_maximize),
                                ft.IconButton(ft.Icons.CLOSE, tooltip="退出", on_click=lambda _: page.window.close())
                            ],
                            alignment=ft.MainAxisAlignment.END,
                            spacing=1
                        ),
                        alignment=ft.alignment.center_right,
                        height=40
                    )
                ],
                spacing=0,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER
            ),
            height=80,
            padding=ft.padding.only(left=5, right=5)
        ),
        expand=True
    )

    # 自定义foot_bar
    foot_bar = ft.WindowDragArea(
        ft.Container(
            ft.Row(
                [
                    sys_show_view,
                    ft.Text(
                        f"当前版本: {app.version}",
                        text_align=ft.TextAlign.END
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN
            ),
            height=35,
            margin=1,
            expand = True
        ),
        height=35
    )

    # 绑定窗口事件
    page.window.prevent_close = True
    page.window.on_event = window_event

    # 加载菜单及应用资源
    nav_menu = NavigationMenu(ft, page, log, **config)

    # 主布局
    page.add(
        ft.Row([
            header_bar
        ]),
        ft.Divider(height=1),
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
                ft.Divider(height=1)
            ],
            expand=True,
            # spacing=0  # 垂直分割线与水平分割线是否相接
        ),
        foot_bar
    )
    page.update()

if __name__ == "__main__":
    freeze_support()
    log.info("app start")
    ft.app(target=main)
