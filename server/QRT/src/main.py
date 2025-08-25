import os
import flet as ft
from config import AppConfig
from navigationMenu import NavigationMenu
from utils.logger import log
from utils.common import load_json

basepath = os.path.dirname(__file__)

def main(page: ft.Page):
    app = AppConfig(ft, page)
    config = load_json(app.tools_db)
    config["ToolsConfig"] = os.path.join(basepath, app.tools_db)

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
                        ft.Text(
                            value=f"用户：{config['UserInfo']['username']}-{config['UserInfo']['nickname']}",
                            size=16
                        ),
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


# ft.app(target=main, view=ft.WEB_BROWSER)
ft.app(target=main)
