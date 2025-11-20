import json
from threading import Event
from multiprocessing import Process, freeze_support

import flet as ft
import websockets
from loguru import logger

from common.ui_utils.ui_util import UiUtil
from server.config import StartConfig, FtpConfig
from utils.common import get_active_mac
from server.sftp_server import create_ftp_server, run_server


class FtpHandler:
    def __init__(self, page: ft.Page):
        self.page = page
        self.set_width = 400
        self.stop_event = Event()
        self.websocket_client = None
        self.current_config = FtpConfig.read_config()

        self.local_mac = get_active_mac()
        self.server_running = False
        self.show_log = True
        self.ftp_server = None
        self.root_dir_view = ft.TextField(label="根目录",
                                     value=f"{self.current_config.ftp_root}",
                                     on_change=self.update_config,
                                     data="ftp_root"
                                     )
        self.start_server_button_view = ft.ElevatedButton(
            "启动ftp服务",
            tooltip="启动ftp服务",
            on_click=self.start_connect,
            disabled=self.server_running,
            data="connect_btn"
        )
        self.stop_server_button_view = ft.ElevatedButton(
            "停止",
            tooltip="按规则索引工作目录中的文件",
            on_click=self.stop_connect,
            disabled=not self.server_running,
            data="disconnect_btn"
        )

    def server_list_ui(self, evt: ft.ControlEvent):
        dialog = ft.AlertDialog(
            title="服务列表",
            content=ft.Container(ft.ListView(controls=[
                ft.Row(controls=[
                    ft.Text("服务名", data="地址", expand=True),
                    ft.IconButton(ft.Icons.PENDING, icon_color=ft.Colors.BLUE),
                    ft.IconButton(ft.Icons.DELETE, icon_color=ft.Colors.RED)
                ], expand=True),
            ],
                expand=True
            ),
                expand=True, width=1000),
            actions=[
                ft.ElevatedButton("关闭", on_click=lambda e: self.page.close(dialog)),
                ft.ElevatedButton("新增")
            ],
            scrollable=True
        )
        self.page.open(dialog)

    def pick_files_result(self, e: ft.FilePickerResultEvent):
        if e.path:
            self.current_config.ftp_root = e.path
            FtpConfig.save_config(self.current_config)
            self.root_dir_view.value = self.current_config.ftp_root
            self.root_dir_view.update()

    def pick_file_ui(self, evt: ft.ControlEvent):
        pick_files_dialog = ft.FilePicker(on_result=self.pick_files_result)
        self.page.add(pick_files_dialog)
        pick_files_dialog.get_directory_path()

    def manager_server_ui(self, evt: ft.ControlEvent):
        dialog = ft.AlertDialog(
            title="服务信息",
            content=ft.Container(ft.ListView(controls=[
                ft.Column(controls=[
                    ft.Row(controls=[
                        self.root_dir_view,
                        ft.ElevatedButton(
                            "Pick files",
                            icon=ft.Icons.UPLOAD_FILE,
                            on_click=self.pick_file_ui,
                        )
                    ]),
                    ft.TextField(label="地址",
                                 value=f"{self.current_config.host}",
                                 on_change=self.update_config,
                                 data="host"
                                 ),
                    ft.TextField(label="端口",
                                 value=f"{self.current_config.port}",
                                 on_change=self.update_config,
                                 data="port"
                                 ),
                    ft.TextField(label="用户",
                                 value=f"{self.current_config.username}",
                                 on_change=self.update_config,
                                 data="user"
                                 ),
                    ft.TextField(
                        label="密码",
                        tooltip="密码",
                        value=f"{self.current_config.password}",
                        on_change=self.update_config,
                        data="password",
                        disabled=False
                    ),
                    ft.Checkbox(
                        "匿名访问",
                        tooltip="匿名访问",
                        value=self.current_config.enable_anonymous,
                        on_change=self.update_config,
                        data="enable_anonymous",
                        disabled=False
                    )
                ], expand=True)
            ], expand=True), width=500),
            actions=[
                ft.ElevatedButton("关闭", on_click=lambda e: self.page.close(dialog)),
                # ft.ElevatedButton("新增")
            ],
            scrollable=True
        )
        self.page.open(dialog)

    def init_ui(self):
        self.server_dropdown_ui = ft.Dropdown(
            label="地址",
            # value=self.agent_config.current_server,
            # on_change=self.change_server_url,
            # options=[ft.DropdownOption(key, f"{name}[{key}]") for key, name in self.agent_config.server_list.items()],
            disabled=self.server_running,
            editable=True
        )

        content = ft.Container(
            content=ft.Column([
                ft.Text("FTP功能>", size=20),
                ft.Divider(),
                ft.Row([
                    self.start_server_button_view,
                    self.stop_server_button_view,
                    # self.server_dropdown_ui,
                    ft.ElevatedButton("服务配置", on_click=self.manager_server_ui)
                ]),
            ], alignment=ft.MainAxisAlignment.START),
            alignment=ft.alignment.center_left
        )
        return content

    async def update_config(self, evt: ft.ControlEvent):
        try:
            data = evt.control.data
            if data == "user":
                self.current_config.username = evt.control.value
            elif data == "password":
                self.current_config.password = evt.control.value
            elif data == "enable_anonymous":
                self.current_config.enable_anonymous = evt.control.value
            elif data == "host":
                self.current_config.host = evt.control.value
            elif data == "port":
                self.current_config.port = evt.control.value
            elif data == "ftp_root":
                self.current_config.ftp_root = evt.control.value

            FtpConfig.save_config(self.current_config)
            UiUtil.show_snackbar_success(self.page, f"配置更新成功")
        except Exception as e:
            logger.exception(e)
            UiUtil.show_snackbar_error(self.page, f"配置更新失败：{e}")

    async def start_connect(self, evt: ft.ControlEvent):
        try:
            evt.control.disabled = True
            evt.control.update()
            self.stop_server_button_view.disabled = False
            self.stop_server_button_view.update()
            freeze_support()
            self.ftp_server = Process(target=run_server,
                                      args=(
                                          self.current_config.host,
                                          self.current_config.port,
                                          self.current_config.username,
                                          self.current_config.password,
                                          self.current_config.ftp_root
                                      ), daemon=True)
            self.ftp_server.start()
        except Exception as e:
            evt.control.disabled = False
            evt.control.update()
            self.stop_server_button_view.disabled = True
            self.stop_server_button_view.update()
            logger.exception(e)
            UiUtil.show_snackbar_error(self.page, f"服务启动失败： {e}")

    async def open_server_edite_dialog(self, evt: ft.ControlEvent):
        dialog = ft.AlertDialog(content=ft.Column(controls=[
            ft.TextField(label="服务名称", data="name"),
            ft.TextField(label="服务地址", data="url"),
        ]), actions=[
            ft.ElevatedButton("关闭", on_click=lambda e: self.page.close(dialog)),
            ft.ElevatedButton("保存")
        ])
        self.page.open(dialog)

    async def stop_connect(self, e: ft.ControlEvent):
        if not self.ftp_server:
            return

        self.stop_server_button_view.disabled = True
        self.stop_server_button_view.update()
        self.start_server_button_view.disabled = False
        self.start_server_button_view.update()
        self.server_running = False
        if self.ftp_server:
            self.ftp_server.terminate()
            self.ftp_server.join()
            self.ftp_server = None
        logger.info("ftp 已停止")
        UiUtil.show_snackbar_success(self.page, "ftp 已停止")
