import sys

import flet as ft
from loguru import logger

from common.ui_utils.ui_util import UiUtil
from utils import VERSION
from utils.common import check_app_has_new, perform_update_with_powershell


class About(object):
    """关于"""
    def __init__(self):
        self.download_progress_view = ft.Text(key="upload_process")

    def about(self):
        content = ft.Container(
                content=ft.Column([
                    ft.Text("关于>", size=20),
                    ft.Divider(),
                    ft.Column([
                        ft.Row([
                            ft.Text("更新过程中不要离开当前tab！！！", color=ft.Colors.RED),
                            ft.Text("exe是更新包，更新包替换原来的exe；zip是全量包，zip解压使用。", color=ft.Colors.RED)
                        ]),
                        ft.Row([
                            ft.Text("QTRClient客户端"),
                            ft.ElevatedButton("检查更新", on_click=self.check_new_version),
                            ft.ElevatedButton("更新", on_click=self.get_sys_info_view),
                            self.download_progress_view,
                            ft.Text(key="version_tip")
                            # ft.Button("Kill POS")
                        ]),
                        ft.Row([
                            ft.Markdown(key="update_info", selectable=True, auto_follow_links=True),
                        ],key="update_info")
                    ]),
                    # ft.Text("离线服务状态"),
                    # ft.FilledButton("示例按钮")
                ], alignment=ft.MainAxisAlignment.START),
                alignment=ft.alignment.center_left
            )
        return content

    async def check_new_version(self, e:ft.ControlEvent):
        e.control.disabled = True
        e.control.update()
        check_info = ""
        new_info = ""
        try:
            has_new, new_info = await check_app_has_new()
            logger.info(f"has_new: {has_new}")
            if has_new:
                check_info = f"当前版本：{VERSION}  新版本：{has_new}"
        except Exception as ex:
            logger.exception(ex)
            check_info = f"检查新版本异常：{str(ex)}"

        for i in e.control.parent.controls:
            if i.key == "version_tip":
                i.value = check_info
                i.update()
                break

        for i in e.control.parent.parent.controls:
            if i.key == "update_info":
                for j in i.controls:
                    if j.key == "update_info":
                        j.value = new_info
                        j.update()
                        break

        e.control.disabled = False
        e.control.update()

    async def get_sys_info_view(self, e:ft.ControlEvent):
        e.control.disabled = True
        e.control.update()
        try:
            has_new, new_info = await check_app_has_new()
            if not has_new:
                UiUtil.show_snackbar_success(e.control.page, f"当前版本{VERSION}已经是最新版本")
                return

            await perform_update_with_powershell(self.show_load_process)
            e.control.page.window.prevent_close = False
            e.control.page.window.close()
            # sys.exit(0)
        except Exception as ex:
            logger.exception(ex)
            UiUtil.show_snackbar_error(e.control.page, f"更新异常：{str(ex)}")
        finally:
            e.control.disabled = False
            e.control.update()



    def show_load_process(self, content: str):
        self.download_progress_view.value = content
        self.download_progress_view.update()

        