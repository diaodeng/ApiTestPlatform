import os
from multiprocessing import freeze_support

import flet as ft

# from flet import Column, Row, Divider, Text, Page, MainAxisAlignment, TextAlign, VerticalDivider
from config import AppConfig
from navigationMenu import NavigationMenu
from utils.common import load_json, ensure_directory_exists, get_sys_info, get_memory_usage, get_process_by_name
from utils.logger import log
from utils.mytimers import add_timer_and_start

ensure_directory_exists("logs")


basepath = os.path.dirname(__file__)

async def main(page: ft.Page):

    app = AppConfig(page)
    config = load_json(app.tools_db)
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
    sys_show_view = ft.Text("正在获取信息...")

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
                    expand=True
                ),
                ft.Divider(height=1),
                ft.Row(
                    controls=[
                        sys_show_view,
                        ft.Text(
                            f"当前版本: {app.version}",
                            size=16,
                            text_align=ft.TextAlign.END
                        )
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
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

    def get_sys_info_view():

        try:
            info = get_sys_info()
            process_men = get_memory_usage()
            pos = get_process_by_name("CPOS-DF.exe")
            pos_mem = 0
            pos_dir = ""
            if pos:
                pos_dir = pos[0][1]
                pos_mem = get_memory_usage(int(pos[0][0]))
            sys_show_view.value = f"CPU:{info['cpu']}/内存:{info['mem']}/磁盘:{info['disk']}/进程:{process_men}/CPOS-DF:{pos_mem}/{pos_dir}"
        except Exception as e:
            log.error(f"获取系统信息异常:{e}")
            sys_show_view.value = f"获取系统信息异常:{e}"
        sys_show_view.update()

    add_timer_and_start(10, get_sys_info_view)
    page.on_error = lambda e: log.error(f"页面异常:{e}")
    page.update()


# ft.app(target=main, view=ft.WEB_BROWSER)
if __name__ == "__main__":
    freeze_support()
    log.info("app start")
    # multiprocessing.set_start_method("spawn")
    ft.app(target=main)
