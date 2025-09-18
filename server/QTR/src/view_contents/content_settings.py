
class Settings:
    """设置"""
    def __init__(self, ft, page, log):
        self.ft = ft
        self.page = page
        self.log = log

        self.setup_ui()

    def settings(self):
        content = self.ft.Container(
                content=self.ft.Column([
                    self.ft.Text("设置>", size=24),
                    self.ft.Divider(),
                    self.ft.FilledButton("示例按钮")
                ], alignment=self.ft.MainAxisAlignment.START),
                alignment=self.ft.alignment.center_left
            )
        return content

    def setup_ui(self):
        self.ft.Text()