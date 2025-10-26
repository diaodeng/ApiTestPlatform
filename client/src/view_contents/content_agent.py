import asyncio
import json
import os
import fnmatch
import os
from threading import Thread, Event

import flet as ft
from flet.core.alignment import bottom_right
from loguru import logger

from model.pos_network_model import PosLogoutModel
from server.agent_server import WebSocketClient
from server.config import SearchConfig, StartConfig, PaymentMockConfig, MitmproxyConfig, PosConfig, PosToolConfig
from utils import file_handle, pos_network
from utils.common import kill_process_by_name, get_active_mac
from common.ui_utils.ui_util import UiUtil


class AgentHandler:
    def __init__(self, ft, page: ft.Page):
        self.start_config = StartConfig.read()
        self.ft = ft
        self.page = page
        self.set_width = 400
        self.stop_event = Event()
        self.websocket_client = None

        self.uri = "ws://localhost:9099/qtr/agent/ws/1111111"
        self.connect_status = False
        self.show_log = True
        # self.setup_ui()
        self.request_data_view = ft.TextField(
                        label="请求参数",
                        tooltip="匹配指定规则的文件名",
                        hint_text="例如: *.txt 或 report*.docx",
                        # width=self.set_width,
                        value="111111",
                        multiline=True,
                        expand=True,
                        expand_loose=True,
                    )
        self.response_data_view = ft.TextField(
                        label="响应信息",
                        tooltip="匹配指定规则的文件名",
                        hint_text="例如: *.txt 或 report*.docx",
                        # width=self.set_width,
                        value="33333",
                        multiline=True,
                        expand=True
                    )

    def init_ui(self):

        content = self.ft.Container(
            content=self.ft.Column([
                self.ft.Text("Agent功能>", size=20),
                self.ft.Divider(),
                self.ft.Row([
                    ft.ElevatedButton(
                        "链接服务器",
                        tooltip="按规则索引工作目录中的文件",
                        on_click=self.start_connect,
                        disabled=self.connect_status,
                        key="connect_btn"
                    ),
                    ft.ElevatedButton(
                        "停止",
                        tooltip="按规则索引工作目录中的文件",
                        on_click=self.stop_connect,
                        disabled=not self.connect_status,
                        key="disconnect_btn"
                    ),
                    ft.Text(
                        get_active_mac(),
                        tooltip="客户端mac地址",
                        on_tap=self.copy_mac,
                        disabled=False
                    ),
                    ft.Checkbox(
                        "显示日志",
                        tooltip="客户端是否显示请求参数和响应",
                        on_change=self.change_show_log,
                        disabled=False
                    ),
                    ft.TextField(
                        label="地址",
                        value="ws://localhost:9099/qtr/agent/ws/1111111",
                        tooltip="服务端websocket地址",
                        on_change=self.change_server_url,
                        disabled=False,
                        key="websocket_url"
                    ),
                ]),
                ft.Row([
                    ft.Column([self.request_data_view], expand=True),
                    ft.Column([self.response_data_view], expand=True),
                ], expand=True, key="log_area")
            ], alignment=self.ft.MainAxisAlignment.START),
            alignment=self.ft.alignment.center_left
        )
        return content

    def before_request(self, data):
        if self.show_log:
            logger.info(f"请求数据： {json.dumps(data, ensure_ascii=True)}")
            self.request_data_view.value = json.dumps(data, ensure_ascii=True)
            self.response_data_view.value = ""
            self.request_data_view.update()
            self.response_data_view.update()

    def after_request(self, data):
        if self.show_log:
            logger.info(f"响应数据： {json.dumps(data, ensure_ascii=True)}")
            self.response_data_view.value = json.dumps(data, ensure_ascii=True)
            self.response_data_view.update()


    async def start_connect(self, e: ft.ControlEvent):
        self.connect_status = True
        for element in e.control.parent.controls:
            if element.key == "connect_btn":
                element.disabled = self.connect_status
            elif element.key == "disconnect_btn":
                element.disabled = not self.connect_status
            element.update()
        # self.page.update()
        try:
            if not self.websocket_client:
                self.websocket_client = WebSocketClient(self.uri, before_request_call=self.before_request, after_request_call=self.after_request)
            await self.websocket_client.connect(self.uri)
        except Exception as er:
            self.connect_status = False
            for element in e.control.parent.controls:
                if element.key == "connect_btn":
                    element.disabled = self.connect_status

                elif element.key == "disconnect_btn":
                    element.disabled = not self.connect_status
                element.update()
            # self.page.update()

    async def stop_connect(self, e: ft.ControlEvent):
        self.connect_status = False
        for element in e.control.parent.controls:
            if element.key == "connect_btn":
                element.disabled = self.connect_status
            elif element.key == "disconnect_btn":
                element.disabled = not self.connect_status
            element.update()
        try:
            await self.websocket_client.send_close()
        except Exception as e:
            pass
            # self.connect_status = True
            # for element in e.control.parent.controls:
            #     if element.key == "connect_btn":
            #         element.disabled = self.connect_status
            #     elif element.key == "disconnect_btn":
            #         element.disabled = not self.connect_status
            #     element.update()

    def copy_mac(self, e: ft.ControlEvent):
        local_mac = get_active_mac()
        pass

    def change_show_log(self, e: ft.ControlEvent):
        self.show_log = not self.show_log

    def change_server_url(self, e: ft.ControlEvent):
        self.uri = e.control.value


    def update_start_config(self, e):
        logger.info(f"更新启动配置")
        self.start_config.backup = self.before_start_back_view.value
        self.start_config.replace_mitm_cert = self.before_start_replace_mitm_cert_view.value
        self.start_config.change_env = self.before_start_change_env_view.value
        self.start_config.change_pos = self.before_start_change_pos_view.value
        self.start_config.account_logout = self.before_start_logout_view.value
        self.start_config.remove_cache = self.before_start_remove_cache_view.value
        self.start_config.cover_payment_driver = self.before_start_cover_payment_driver_view.value
        StartConfig.write(self.start_config)

    def start_search(self, e: ft.ControlEvent):
        path = e.control.data
        logger.info(f"清理缓存: {path}")



    def clean_cache(self, e: ft.ControlEvent):
        path = e.control.data
        logger.info(f"清理缓存: {path}")
        success, msg = PaymentMockConfig.clean_cache(path)
        if success:
            UiUtil.show_snackbar_success(self.page, msg)
        else:
            UiUtil.show_snackbar_error(self.page, msg)
        self.page.update()

    def update_ui(self, message, searching, progress=0):
        self.status_text.value = message
        self.progress_bar.value = progress
        self.search_btn.disabled = searching
        self.stop_btn.disabled = not searching
        self.page.update()
