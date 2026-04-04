import flet as ft

from flet import Page
from utils.mytimers import clear_all_timers


class ExitAlertDialog:
    def __init__(self, page, **kwargs):
        self.page: Page = page
        self.kwargs = kwargs

        self.confirm_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Do you really want to exit this app?"),
            # content=ft.Text("Do you really want to exit this app?"),
            actions=[
                ft.ElevatedButton("Yes", on_click=self.yes_click),
                ft.OutlinedButton("No", on_click=self.no_click),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

    def yes_click(self, e):
        self.page.window.prevent_close = False
        self.page.close(self.confirm_dialog)
        # 页面包含定时器，需要先关闭定时器，清理资源
        clear_all_timers()
        if hasattr(self.page.window, "close"):
            self.page.window.close()
        else:
            self.page.window.destroy()
        # sys.exit(0)  # 直接退出进程

    def no_click(self, e):
        self.page.close(self.confirm_dialog)
        self.page.update()
