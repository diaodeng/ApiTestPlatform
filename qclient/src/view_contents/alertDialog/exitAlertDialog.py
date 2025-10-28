
import flet as ft

class ExitApplicationDialog(ft.AlertDialog):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.title = ft.Text("确认退出?")
        self.actions = [ft.Column(alignment=ft.MainAxisAlignment.CENTER,
                                  spacing=10,
                                  controls=[ft.Column(alignment=ft.MainAxisAlignment.CENTER,
                                                      spacing=5,
                                                      controls=[ft.Text("确认退出系统？")]),
                                            ft.Row(alignment=ft.MainAxisAlignment.END,
                                                   controls=[ft.OutlinedButton("No", on_click=self.no_click),
                                                             ft.ElevatedButton("Yes", on_click=self.yes_click)
                                                             ])])]
        self.actions_alignment = ft.MainAxisAlignment.END
        self.actions_padding = 15

    def yes_click(self, e):
        self.page.window.prevent_close = False
        self.page.window.close()

    def no_click(self, e):
        self.open = False
        self.page.update()
