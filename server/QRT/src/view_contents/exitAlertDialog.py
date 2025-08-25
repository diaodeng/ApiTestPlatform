from utils.mytimers import clear_all_timers

class ExitAlertDialog:
    def __init__(self, ft, page, **kwargs):
        self.ft = ft
        self.page = page
        self.kwargs = kwargs

        self.confirm_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Please confirm"),
            content=ft.Text("Do you really want to exit this app?"),
            actions=[
                ft.ElevatedButton("Yes", on_click=self.yes_click),
                ft.OutlinedButton("No", on_click=self.no_click),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.update()

    def yes_click(self, e):
        # 页面包含定时器，需要先关闭定时器，清理资源
        clear_all_timers()
        self.page.window.destroy()

    def no_click(self, e):
        self.page.close(self.confirm_dialog)
        self.page.update()
