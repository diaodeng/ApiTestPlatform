
class About(object):
    """关于"""
    def __init__(self, ft):
        self.ft = ft

    def about(self):
        content = self.ft.Container(
                content=self.ft.Column([
                    self.ft.Text("关于>", size=20),
                    self.ft.Divider(),
                    self.ft.Row([
                        self.ft.Text("hi 我是yoyo~~"),
                        # self.ft.Button("Kill POS")
                    ]),
                    # self.ft.Text("离线服务状态"),
                    # self.ft.FilledButton("示例按钮")
                ], alignment=self.ft.MainAxisAlignment.START),
                alignment=self.ft.alignment.center_left
            )
        return content