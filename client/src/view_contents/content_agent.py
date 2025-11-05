import asyncio
import json
import os
import fnmatch
import os
from threading import Thread, Event

import flet as ft
import websockets
from flet.core.alignment import bottom_right
from loguru import logger

from model.pos_network_model import PosLogoutModel
from server.agent_server import WebSocketClient
from server.config import SearchConfig, StartConfig, PaymentMockConfig, MitmproxyConfig, PosConfig, PosToolConfig, \
    AgentConfig
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
        self.agent_config = AgentConfig.read_config()

        self.local_mac = get_active_mac()
        self.connect_status = False
        self.show_log = True
        # self.setup_ui()
        self.request_data_view = ft.TextField(
                        label="请求参数",
                        tooltip="匹配指定规则的文件名",
                        hint_text="",
                        # width=self.set_width,
                        value="",
                        multiline=True,
                        expand=True,
                        expand_loose=True,
                    )
        self.response_data_view = ft.TextField(
                        label="响应信息",
                        tooltip="匹配指定规则的文件名",
                        hint_text="",
                        # width=self.set_width,
                        value="",
                        multiline=True,
                        expand=True
                    )

    def init_ui(self):
        self.server_dropdown_ui = ft.Dropdown(
                        label="地址",
                        value=self.agent_config.current_server,
                        on_change=self.change_server_url,
                        options=[ft.DropdownOption(key, f"{name}[{key}]") for key, name in self.agent_config.server_list.items()],
                        disabled=self.connect_status,
                        editable=True
                    )

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
                        data="connect_btn"
                    ),
                    ft.ElevatedButton(
                        "停止",
                        tooltip="按规则索引工作目录中的文件",
                        on_click=self.stop_connect,
                        disabled=not self.connect_status,
                        data="disconnect_btn"
                    ),
                    ft.Text(
                        self.local_mac,
                        tooltip="客户端mac地址",
                        on_tap=self.copy_mac,
                        disabled=False,
                        selectable=True
                    ),
                    ft.Checkbox(
                        "显示日志",
                        tooltip="客户端是否显示请求参数和响应",
                        value=self.agent_config.show_logs,
                        on_change=self.change_show_log,
                        disabled=False
                    ),
                    self.server_dropdown_ui,
                    ft.ElevatedButton("新增服务端地址", on_click=self.open_server_edite_dialog)
                ]),
                ft.Row([
                    ft.Column([self.request_data_view], expand=True),
                    ft.Column([self.response_data_view], expand=True),
                ], expand=True, data="log_area")
            ], alignment=self.ft.MainAxisAlignment.START),
            alignment=self.ft.alignment.center_left
        )
        return content

    def get_websocket_url(self):
        uri = self.agent_config.current_server
        if uri.endswith("/"):
            uri = uri[:-1]
        return f"{uri}/{self.local_mac}"

    def before_request(self, data):
        if self.show_log:
            logger.info(f"请求数据： {json.dumps(data, ensure_ascii=False)}")
            self.request_data_view.value = json.dumps(data, ensure_ascii=False, indent=4)
            self.response_data_view.value = ""
            self.request_data_view.update()
            self.response_data_view.update()

    def after_request(self, data):
        if self.show_log:
            logger.info(f"响应数据： {json.dumps(data, ensure_ascii=False)}")
            try:
                result_data = json.dumps(json.loads(data["text"]), ensure_ascii=False, indent=4)
            except Exception as e:
                result_data = data.get("text") or json.dumps(data, ensure_ascii=False, indent=4)

            self.response_data_view.value = result_data
            self.response_data_view.update()


    async def start_connect(self, evt: ft.ControlEvent):
        connect_url = self.get_websocket_url()
        logger.info(f"开始连接服务器： {connect_url}")
        UiUtil.show_snackbar_success(self.page, f"开始连接服务器：{connect_url}")
        self.connect_status = True
        for element in evt.control.parent.controls:
            if element.data == "connect_btn":
                element.disabled = self.connect_status
            elif element.data == "disconnect_btn":
                element.disabled = not self.connect_status
            element.update()
        self.server_dropdown_ui.disabled = self.connect_status
        self.server_dropdown_ui.update()
        try:
            if not self.websocket_client:
                self.websocket_client = WebSocketClient(connect_url, before_request_call=self.before_request, after_request_call=self.after_request)
            await self.websocket_client.connect(connect_url)
        except websockets.exceptions.ConnectionClosedError as e:
            logger.error(f"连接异常关闭：{e}")
            UiUtil.show_snackbar_error(self.page, f"连接异常关闭：{e}")
        except websockets.exceptions.ConnectionClosedOK as e:
            logger.info(f"连接关闭成功")
            UiUtil.show_snackbar_success(self.page, f"连接关闭成功")
        except TimeoutError as e:
            logger.error(f"连接超时【{connect_url}】")
            UiUtil.show_snackbar_error(self.page, f"连接超时【{connect_url}】")
        except Exception as er:
            logger.error(f"服务器连接失败：{er}")
            UiUtil.show_snackbar_error(self.page, f"服务链接失败：【{type(er)}】{er}")
        finally:
            self.connect_status = False
            for element in evt.control.parent.controls:
                if element.data == "connect_btn":
                    element.disabled = self.connect_status

                elif element.data == "disconnect_btn":
                    element.disabled = not self.connect_status
                element.update()
            # self.page.update()

    def _save_new_server(self, evt: ft.ControlEvent):
        new_server_name = ""
        new_server_url = ""
        for item in evt.control.parent.content.controls:
            if item.data == "name":
                new_server_name = item.value
            elif item.data == "url":
                new_server_url = item.value
        if new_server_url:
            self.agent_config.server_list[new_server_url] = new_server_name
            AgentConfig.save_config(self.agent_config)
            self.server_dropdown_ui.options.clear()
            self.server_dropdown_ui.options = [ft.DropdownOption(key, f"{name}[{key}]") for key, name in self.agent_config.server_list.items()]
            self.server_dropdown_ui.update()
            UiUtil.show_snackbar_success(self.page, "新增成功")
        else:
            UiUtil.show_snackbar_error(self.page, "请添加url")

    async def open_server_edite_dialog(self, evt: ft.ControlEvent):
        dialog = ft.AlertDialog(content=ft.Column(controls=[
            ft.TextField(label="服务名称", data="name"),
            ft.TextField(label="服务地址", data="url"),
        ]), actions=[
            ft.ElevatedButton("关闭", on_click=lambda e: self.page.close(dialog)),
            ft.ElevatedButton("保存", on_click=self._save_new_server)
        ])
        self.page.open(dialog)


    async def stop_connect(self, e: ft.ControlEvent):
        self.connect_status = False
        for element in e.control.parent.controls:
            if element.data == "connect_btn":
                element.disabled = self.connect_status
            elif element.data == "disconnect_btn":
                element.disabled = not self.connect_status
            element.update()
        self.server_dropdown_ui.disabled = self.connect_status
        self.server_dropdown_ui.update()
        try:
            await self.websocket_client.send_close()
            UiUtil.show_snackbar_success(self.page, f"成功断开连接")
        except Exception as e:
            UiUtil.show_snackbar_error(self.page, f"断开连接异常：{e}")
            # self.connect_status = True
            # for element in e.control.parent.controls:
            #     if element.data == "connect_btn":
            #         element.disabled = self.connect_status
            #     elif element.data == "disconnect_btn":
            #         element.disabled = not self.connect_status
            #     element.update()

    def copy_mac(self, e: ft.ControlEvent):
        local_mac = get_active_mac()
        pass

    def change_show_log(self, e: ft.ControlEvent):
        self.agent_config.show_logs = not self.agent_config.show_logs
        AgentConfig.save_config(self.agent_config)

    def change_server_url(self, e: ft.ControlEvent):
        self.agent_config.current_server = e.control.value
        AgentConfig.save_config(self.agent_config)


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
        success, msg = PosConfig.clean_cache(path)
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
