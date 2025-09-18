from view_contents.dialog.registerDialog import RegisterDialog


class Home(object):
    """关于"""

    def __init__(self, ft, page, log, **kwargs):
        self.ft = ft
        self.page = page
        self.log = log
        self.registerDialog = RegisterDialog(ft, page, log, **kwargs)
        self.setup_ui()


    def setup_ui(self):
        self.identity_code = self.ft.TextField(
            label="身份码",
            hint_text="请输入身份码",
            width=300
        )

        self.btn_confirm = self.ft.ElevatedButton(
            text="验证",

            on_click=None
        )

        self.btn_register = self.ft.ElevatedButton(
            text="注册",
            on_click=lambda _:self.registerDialog.open_dlg(self.identity_code)
        )


    def home(self):
        content = self.ft.Container(
            content=self.ft.Column([
                self.ft.Text("首页>", size=20),
                self.ft.Divider(),
                self.ft.Row([
                    self.identity_code,
                    self.btn_confirm,
                    self.btn_register
                ]),

                self.ft.Row([
                    # self.ft.Text("POS状态"),
                    #
                    # self.ft.Button("Kill POS")
                ]),
                # self.ft.Text("离线服务状态"),
                # self.ft.FilledButton("示例按钮")
            ], alignment=self.ft.MainAxisAlignment.START),
            alignment=self.ft.alignment.center_left
        )
        return content
