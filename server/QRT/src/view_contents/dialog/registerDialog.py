from common.appState import userInfo
from utils.common import write_json

use_Info = userInfo
class RegisterDialog(object):
    def __init__(self, ft, page, log, **kwargs):
        self.ft = ft
        self.page = page
        self.log = log
        self.kwargs = kwargs
        self.setup_ui()

    def setup_ui(self):
        # 注册表单字段
        self.username = self.ft.TextField(label="用户名", autofocus=True)
        self.nickname = self.ft.TextField(label="用户昵称")

        # 创建对话框
        self.dlg = self.ft.AlertDialog(
            modal=True,
            title=self.ft.Text("用户注册"),
            content=self.ft.Column([
                self.username,
                self.nickname,
            ], tight=True),
            actions=[
                self.ft.TextButton("取消", on_click=lambda e: self.close_dlg()),
                self.ft.TextButton("注册", on_click=lambda e: self.register())
            ],
            actions_alignment=self.ft.MainAxisAlignment.END
        )
        self.page.update()

    def open_dlg(self, e=None):

        self.page.open(self.dlg)
        self.page.update()

    def close_dlg(self, e=None):
        self.page.close(self.dlg)
        self.page.update()

    def register(self, e=None):
        if not self.username.value:
            self.username.error_text = "请输入用户名"
            self.page.update()
            return
        if not self.nickname.value:
            self.nickname.error_text = "请输入昵称"
            self.page.update()
            return

        self.close_dlg()
        self.kwargs["UserInfo"]["username"] = self.username.value
        self.kwargs["UserInfo"]["nickname"] = self.nickname.value
        config_file_path = self.kwargs.pop("ToolsConfig")
        if write_json(config_file_path, self.kwargs):
            self.log.info(f"更新用户信息成功")
        else:
            self.log.error(f"更新用户信息失败")
        self.page.update()
        # self.page.add(self.ft.Text(f"注册陈功！用户名：{self.username.value}, 昵称：{self.nickname.value}"))

