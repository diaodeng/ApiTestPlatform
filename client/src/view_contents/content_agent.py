import json

import flet as ft
import websockets
from loguru import logger

from common.ui_utils.ui_util import UiUtil
from server import agent_server
from server.agent_server import WebSocketClient
from server.config import AgentConfig
from utils.common import get_active_mac


class AgentHandler:
    def __init__(self, ft, page: ft.Page):
        self.ft = ft
        self.page = page
        self.set_width = 400
        self.websocket_client = None
        self.agent_config = AgentConfig.read_config()
        agent_server.MAX_MESSAGE_SIZE = self.agent_config.max_send_size

        self.local_mac = get_active_mac()
        self.connect_status = False
        self.show_log = self.agent_config.show_logs
        self.editing_server_url = None

        self.server_dropdown_ui: ft.Dropdown | None = None
        self.connect_btn: ft.ElevatedButton | None = None
        self.disconnect_btn: ft.ElevatedButton | None = None
        self.max_message_field: ft.TextField | None = None
        self.server_manage_btn: ft.ElevatedButton | None = None

        self.server_manager_dialog: ft.AlertDialog | None = None
        self.server_list_view = ft.ListView(expand=True, spacing=10, auto_scroll=False)
        self.server_form_title = ft.Text("新增服务", size=16, weight=ft.FontWeight.W_600)
        self.server_form_hint = ft.Text(size=12, color=ft.Colors.BLUE_GREY_500)
        self.server_name_field = ft.TextField(label="服务名称", hint_text="例如：UAT 环境")
        self.server_url_field = ft.TextField(label="服务地址", hint_text="例如：ws://127.0.0.1:9099/qtr/agent/ws")

        self.request_data_view = ft.TextField(
            label="请求参数",
            tooltip="客户端收到的请求内容",
            value="",
            multiline=True,
            min_lines=12,
            expand=True,
            expand_loose=True,
        )
        self.response_data_view = ft.TextField(
            label="响应信息",
            tooltip="客户端返回的响应内容",
            value="",
            multiline=True,
            min_lines=12,
            expand=True,
        )

    def init_ui(self):
        self.server_dropdown_ui = ft.Dropdown(
            label="地址",
            value=self.agent_config.current_server,
            on_change=self.change_server_url,
            options=[],
            disabled=self.connect_status,
            editable=True,
            width=360,
        )
        self.connect_btn = ft.ElevatedButton(
            "连接服务器",
            tooltip="连接当前选中的 Agent 服务端",
            on_click=self.start_connect,
            disabled=self.connect_status,
        )
        self.disconnect_btn = ft.ElevatedButton(
            "停止",
            tooltip="断开当前连接",
            on_click=self.stop_connect,
            disabled=not self.connect_status,
        )
        self.max_message_field = ft.TextField(
            label="发消息最大内容（KB）",
            value=self._format_message_kb(self.agent_config.max_send_size),
            on_blur=self._max_message_view_change,
            width=180,
        )
        self.server_manage_btn = ft.ElevatedButton("服务管理", on_click=self.open_server_edite_dialog)

        show_log_checkbox = ft.Checkbox(
            "显示日志",
            tooltip="客户端是否显示请求参数和响应",
            value=self.agent_config.show_logs,
            on_change=self.change_show_log,
            data="show_log",
        )
        retry_checkbox = ft.Checkbox(
            "是否重试",
            tooltip="连接异常后是否重试",
            value=self.agent_config.retry,
            on_change=self.change_show_log,
            data="retry",
        )
        retry_times_field = ft.TextField(
            label="重试次数",
            tooltip="最大重试次数",
            value=str(self.agent_config.retry_times),
            on_blur=self.change_show_log,
            data="retry_times",
            width=110,
        )
        retry_interval_field = ft.TextField(
            label="重试间隔S",
            tooltip="每次重试间隔（秒）",
            value=str(self.agent_config.retry_interval),
            on_blur=self.change_show_log,
            data="retry_interval",
            width=110,
        )

        self._refresh_server_dropdown()
        self._set_connection_state(self.connect_status)

        return ft.Container(
            expand=True,
            content=ft.Column(
                [
                    ft.Text("Agent功能>", size=20),
                    ft.Divider(),
                    ft.Row(
                        spacing=10,
                        run_spacing=10,
                        # tight=True,
                        # wrap=True,
                        # alignment=ft.MainAxisAlignment.START,
                        # run_alignment=ft.MainAxisAlignment.START,
                        # vertical_alignment=ft.CrossAxisAlignment.END,
                        controls=[
                            self.connect_btn,
                            self.disconnect_btn,
                            self.max_message_field,
                            show_log_checkbox,
                            retry_checkbox,
                            retry_times_field,
                            retry_interval_field,
                            self.server_dropdown_ui,
                            self.server_manage_btn,
                        ],
                    ),
                    ft.Row(
                        spacing=12,
                        vertical_alignment=ft.CrossAxisAlignment.STRETCH,
                        controls=[
                            ft.Container(content=self.request_data_view, expand=True),
                            ft.Container(content=self.response_data_view, expand=True),
                        ],
                        expand=True,
                    ),
                ],
                alignment=self.ft.MainAxisAlignment.START,
                expand=True,
            ),
            alignment=self.ft.alignment.center_left,
        )

    def _format_message_kb(self, value: int | float) -> str:
        kb_value = max(float(value) / 1024, 1)
        if kb_value.is_integer():
            return str(int(kb_value))
        return str(kb_value)

    def _safe_update(self, *controls):
        for control in controls:
            if control is None:
                continue
            try:
                control.update()
            except Exception:
                pass

    def _set_connection_state(self, connected: bool):
        self.connect_status = connected
        if self.connect_btn:
            self.connect_btn.disabled = connected
        if self.disconnect_btn:
            self.disconnect_btn.disabled = not connected
        if self.server_dropdown_ui:
            self.server_dropdown_ui.disabled = connected
        self._safe_update(self.connect_btn, self.disconnect_btn, self.server_dropdown_ui)

    def _build_server_label(self, url: str, name: str) -> str:
        server_name = (name or "").strip()
        return f"{server_name}[{url}]" if server_name else url

    def _refresh_server_dropdown(self):
        if self.server_dropdown_ui is None:
            return
        current_server = (self.agent_config.current_server or "").strip()
        dropdown_value = current_server or None
        if not current_server and self.agent_config.server_list:
            dropdown_value = next(iter(self.agent_config.server_list))
            self.agent_config.current_server = dropdown_value
            AgentConfig.save_config(self.agent_config)
        # Clear the previous selection first so Flet doesn't keep a stale option index
        # while the options list is being replaced.
        self.server_dropdown_ui.value = None
        self._safe_update(self.server_dropdown_ui)
        self.server_dropdown_ui.options = [
            ft.DropdownOption(url, self._build_server_label(url, name))
            for url, name in self.agent_config.server_list.items()
        ]
        self.server_dropdown_ui.value = dropdown_value
        self._safe_update(self.server_dropdown_ui)

    def _update_server_form_hint(self):
        current_server = self.agent_config.current_server or "未选择"
        server_count = len(self.agent_config.server_list)
        self.server_form_hint.value = f"当前服务：{current_server}，已保存 {server_count} 个服务"
        self._safe_update(self.server_form_hint)

    def _reset_server_form(self, _evt: ft.ControlEvent | None = None):
        self.editing_server_url = None
        self.server_form_title.value = "新增服务"
        self.server_name_field.value = ""
        self.server_url_field.value = ""
        self._safe_update(self.server_form_title, self.server_name_field, self.server_url_field)
        self._update_server_form_hint()

    def _start_edit_server(self, evt: ft.ControlEvent):
        server_url = evt.control.data
        if not server_url:
            return
        self.editing_server_url = server_url
        self.server_form_title.value = "编辑服务"
        self.server_name_field.value = self.agent_config.server_list.get(server_url, "")
        self.server_url_field.value = server_url
        self._safe_update(self.server_form_title, self.server_name_field, self.server_url_field)
        self._update_server_form_hint()

    def _render_server_rows(self):
        self.server_list_view.controls.clear()
        if not self.agent_config.server_list:
            self.server_list_view.controls.append(
                ft.Container(
                    padding=12,
                    border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
                    border_radius=12,
                    content=ft.Text("暂无服务，先在右侧填写名称和地址后保存。", color=ft.Colors.BLUE_GREY_500),
                )
            )
        else:
            for url, name in self.agent_config.server_list.items():
                current_badge = ft.Container(
                    padding=ft.padding.symmetric(horizontal=8, vertical=4),
                    border_radius=999,
                    bgcolor=ft.Colors.GREEN_50,
                    visible=self.agent_config.current_server == url,
                    content=ft.Text("当前", size=12, color=ft.Colors.GREEN_700),
                )
                self.server_list_view.controls.append(
                    ft.Container(
                        padding=12,
                        border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
                        border_radius=12,
                        content=ft.Row(
                            [
                                ft.Column(
                                    [
                                        ft.Text(name or "未命名服务", weight=ft.FontWeight.W_600),
                                        ft.Text(url, selectable=True, color=ft.Colors.BLUE_GREY_600),
                                    ],
                                    expand=True,
                                    spacing=4,
                                ),
                                current_badge,
                                ft.TextButton("编辑", data=url, on_click=self._start_edit_server),
                                ft.TextButton("删除", data=url, on_click=self._delete_server),
                            ],
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                    )
                )
        self._safe_update(self.server_list_view)
        self._update_server_form_hint()

    def _save_new_server(self, _evt: ft.ControlEvent):
        new_server_name = (self.server_name_field.value or "").strip()
        new_server_url = (self.server_url_field.value or "").strip()
        if not new_server_url:
            UiUtil.show_snackbar_error(self.page, "请填写服务地址")
            return
        if self.editing_server_url != new_server_url and new_server_url in self.agent_config.server_list:
            UiUtil.show_snackbar_error(self.page, "服务地址已存在，请直接编辑原记录")
            return

        if self.editing_server_url and self.editing_server_url != new_server_url:
            self.agent_config.server_list.pop(self.editing_server_url, None)

        self.agent_config.server_list[new_server_url] = new_server_name
        if not self.agent_config.current_server or self.agent_config.current_server == self.editing_server_url:
            self.agent_config.current_server = new_server_url

        AgentConfig.save_config(self.agent_config)
        self._refresh_server_dropdown()
        self._render_server_rows()
        self._reset_server_form()
        UiUtil.show_snackbar_success(self.page, "服务保存成功")

    def _delete_server(self, evt: ft.ControlEvent):
        server_url = evt.control.data
        if not server_url or server_url not in self.agent_config.server_list:
            return
        self.agent_config.server_list.pop(server_url, None)
        if self.agent_config.current_server == server_url:
            self.agent_config.current_server = next(iter(self.agent_config.server_list), "")
        if self.editing_server_url == server_url:
            self._reset_server_form()
        AgentConfig.save_config(self.agent_config)
        self._refresh_server_dropdown()
        self._render_server_rows()
        UiUtil.show_snackbar_success(self.page, "服务删除成功")

    def _ensure_server_manager_dialog(self):
        if self.server_manager_dialog is not None:
            return
        self.server_manager_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("服务管理"),
            content=ft.Container(
                width=880,
                height=420,
                content=ft.Row(
                    [
                        ft.Container(
                            expand=2,
                            padding=12,
                            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
                            border_radius=12,
                            content=ft.Column(
                                [
                                    ft.Text("已保存服务", weight=ft.FontWeight.W_600),
                                    ft.Text("点击“编辑”可将服务信息回填到右侧表单。", size=12, color=ft.Colors.BLUE_GREY_500),
                                    self.server_list_view,
                                ],
                                spacing=10,
                                expand=True,
                            ),
                        ),
                        ft.Container(
                            width=300,
                            padding=12,
                            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
                            border_radius=12,
                            content=ft.Column(
                                [
                                    self.server_form_title,
                                    self.server_form_hint,
                                    self.server_name_field,
                                    self.server_url_field,
                                    ft.Row(
                                        [
                                            ft.OutlinedButton("清空", on_click=self._reset_server_form),
                                            ft.ElevatedButton("保存", on_click=self._save_new_server),
                                        ],
                                        alignment=ft.MainAxisAlignment.END,
                                    ),
                                ],
                                spacing=12,
                            ),
                        ),
                    ],
                    spacing=16,
                    vertical_alignment=ft.CrossAxisAlignment.START,
                ),
            ),
            actions=[ft.TextButton("关闭", on_click=lambda e: self.page.close(self.server_manager_dialog))],
            actions_alignment=ft.MainAxisAlignment.END,
        )

    def _max_message_view_change(self, evt: ft.ControlEvent):
        raw_value = (evt.control.value or "1").strip()
        try:
            kb_value = max(int(float(raw_value)), 1)
        except ValueError:
            evt.control.value = self._format_message_kb(self.agent_config.max_send_size)
            self._safe_update(evt.control)
            UiUtil.show_snackbar_error(self.page, "发消息最大内容请输入数字")
            return

        data = kb_value * 1024
        self.agent_config.max_send_size = data
        agent_server.MAX_MESSAGE_SIZE = data
        evt.control.value = self._format_message_kb(data)
        self._safe_update(evt.control)
        AgentConfig.save_config(self.agent_config)
        UiUtil.show_snackbar_success(self.page, "消息大小配置已保存")

    def get_websocket_url(self):
        uri = (self.agent_config.current_server or "").strip()
        if not uri:
            return ""
        if uri.endswith("/"):
            uri = uri[:-1]
        return f"{uri}/{self.local_mac}"

    def before_request(self, data):
        if self.show_log:
            logger.info(f"请求数据： {json.dumps(data, ensure_ascii=False)}")
            self.request_data_view.value = json.dumps(data, ensure_ascii=False, indent=4)
            self.response_data_view.value = ""
            self.request_data_view.update()
            self._safe_update(self.response_data_view)

    def after_request(self, data):
        if self.show_log:
            logger.info(f"响应数据： {json.dumps(data, ensure_ascii=False)}")
            try:
                result_data = json.dumps(json.loads(data["text"]), ensure_ascii=False, indent=4)
            except Exception:
                result_data = data.get("text") or json.dumps(data, ensure_ascii=False, indent=4)
            self.response_data_view.value = result_data
            self._safe_update(self.response_data_view)

    async def start_connect(self, _evt: ft.ControlEvent):
        connect_url = self.get_websocket_url()
        if not connect_url:
            UiUtil.show_snackbar_error(self.page, "请先选择或填写服务地址")
            return
        logger.info(f"开始连接服务器： {connect_url}")
        UiUtil.show_snackbar_success(self.page, f"开始连接服务器：{connect_url}")
        self._set_connection_state(True)
        try:
            if not self.websocket_client:
                self.websocket_client = WebSocketClient(
                    connect_url,
                    before_request_call=self.before_request,
                    after_request_call=self.after_request,
                )
            await self.websocket_client.connect(
                connect_url,
                retry=self.agent_config.retry,
                retry_num=self.agent_config.retry_times,
                interval_time=self.agent_config.retry_interval,
            )
        except websockets.exceptions.ConnectionClosedError as e:
            logger.error(f"连接异常关闭：{e}")
            UiUtil.show_snackbar_error(self.page, f"连接异常关闭：{e}")
        except websockets.exceptions.ConnectionClosedOK:
            logger.info("连接关闭成功")
            UiUtil.show_snackbar_success(self.page, "连接关闭成功")
        except TimeoutError:
            logger.error(f"连接超时【{connect_url}】")
            UiUtil.show_snackbar_error(self.page, f"连接超时【{connect_url}】")
        except Exception as er:
            logger.error(f"服务器连接失败：{er}")
            UiUtil.show_snackbar_error(self.page, f"服务链接失败：【{type(er)}】{er}")
        finally:
            self._set_connection_state(False)

    async def open_server_edite_dialog(self, _evt: ft.ControlEvent):
        self._ensure_server_manager_dialog()
        self._render_server_rows()
        self._reset_server_form()
        self.page.open(self.server_manager_dialog)

    async def stop_connect(self, _evt: ft.ControlEvent):
        self._set_connection_state(False)
        if self.websocket_client is None:
            UiUtil.show_snackbar_error(self.page, "当前没有活动连接")
            return
        try:
            await self.websocket_client.send_close()
            UiUtil.show_snackbar_success(self.page, "成功断开连接")
        except Exception as e:
            UiUtil.show_snackbar_error(self.page, f"断开连接异常：{e}")

    def change_show_log(self, e: ft.ControlEvent):
        try:
            if e.control.data == "show_log":
                self.show_log = e.control.value
                self.agent_config.show_logs = e.control.value
            elif e.control.data == "retry":
                self.agent_config.retry = e.control.value
            elif e.control.data == "retry_times":
                self.agent_config.retry_times = int((e.control.value or "0").strip())
            elif e.control.data == "retry_interval":
                self.agent_config.retry_interval = float((e.control.value or "0").strip())
            AgentConfig.save_config(self.agent_config)
            UiUtil.show_snackbar_success(self.page, "配置保存成功")
        except Exception as ex:
            logger.error(f"配置保存失败：{ex}")
            logger.exception(ex)
            UiUtil.show_snackbar_error(self.page, f"配置保存失败：{ex}")

    def change_server_url(self, e: ft.ControlEvent):
        self.agent_config.current_server = (e.control.value or "").strip()
        AgentConfig.save_config(self.agent_config)
