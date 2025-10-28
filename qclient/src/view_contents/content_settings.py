import flet
from utils.logger import Logger

class Settings:
    """设置"""
    def __init__(self, ft, page, log):
        self.ft: flet = ft
        self.page = page
        self.log = log

        self.setup_ui()

    def settings(self):
        content = self.ft.Container(
                content=self.ft.Column([
                    self.ft.Text("设置>", size=24),
                    self.ft.Divider(),
                    flet.Row([
                        flet.Text("日志等级"),
                        flet.Dropdown(
                            options=[
                                flet.dropdown.Option("DEBUG"),
                                flet.dropdown.Option("INFO"),
                                flet.dropdown.Option("WARNING"),
                                flet.dropdown.Option("ERROR"),
                                flet.dropdown.Option("CRITICAL"),
                            ],
                            value="INFO",
                            on_change=self.change_log_level,
                        ),
                    ]),
                    flet.Row([
                        flet.Text("启动APP执行的操作"),
                        flet.Checkbox(
                            label="打开mitmproxy",
                            value=False,
                            on_change=lambda e:print(""),
                        ),
                        flet.Checkbox(
                            label="打开指定POS",
                            value=False,
                            on_change=lambda e:print(""),
                        ),
                    ]),
                    self.ft.FilledButton("示例按钮")
                ], alignment=self.ft.MainAxisAlignment.START),
                alignment=self.ft.alignment.center_left
            )
        return content

    def setup_ui(self):
        self.ft.Text()

    def change_log_level(self, e):
        Logger.change_log_level(e.control.value)
