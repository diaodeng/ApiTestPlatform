import asyncio
from multiprocessing import Process, Manager, freeze_support

import flet as ft
from flet.core.control_event import ControlEvent
from loguru import logger

from server.config import MitmproxyConfig
from utils.mitmproxy_tool import ProxyCore, MockHandle as mockHandle
from utils.share_data import get_shared
from common.ui_utils.ui_util import UiUtil


class MitmHandel:
    def __init__(self, page: ft.Page):
        self.config = MitmproxyConfig.read()
        self.page = page
        self.proxy: Process = None
        self.proxy_core: ProxyCore = None
        self.proxy_global_config: dict = None
        self.loop = None
        self.task = None
        self.port_field = ft.TextField(label="代理端口", value=str(self.config.port))
        self.web_port_field = ft.TextField(label="Web端口", value=str(self.config.web_port))
        self.proxy_model_view = ft.Dropdown(
            value=self.config.proxy_model,
            editable=True,
            label="model",
            options=self.get_options(),
            on_change=self.dropdown_changed,
        )
        self.proxy_model_value_view = ft.TextField(label="需要代理的应用名，多个用逗号分隔", value=str(self.config.proxy_model_value), visible=self.config.proxy_model == "local")
        self.proxy_application_view = ft.TextField(label="代理应用", value=self.config.proxy_model)
        self.web_open_browser = ft.Checkbox("打开浏览器", value=self.config.web_open_browser)
        self.mitmproxy_config_dir = ft.TextField(label="mitmproxy配置目录", value=self.config.mitmproxy_config_dir)
        self.status_text = ft.Text("代理未启动")
        self.proxy_running = False
        self.start_button = ft.ElevatedButton("启动代理", on_click=self.start_proxy, disabled=self.proxy_running)
        self.stop_button = ft.ElevatedButton("停止代理",
                                             on_click=self.stop_proxy,
                                             disabled=not self.proxy_running
                                             )
        self.is_mock = ft.Checkbox("启用mock", value=self.config.is_mock)
        self.open_include = ft.Checkbox("启用包含", value=self.config.open_include, on_change=self.use_include_change)
        self.open_exclude = ft.Checkbox("启用排除", value=self.config.open_exclude, on_change=self.use_exclude_change)
        self.include_field = ft.TextField(label="启用mock的请求路径，多个用逗号分割", value=self.config.include, multiline=True, visible=self.config.open_include)
        self.exclude_field = ft.TextField(label="禁用mock的请求路径，多个用逗号分割", value=self.config.exclude, multiline=True, visible=self.config.open_exclude)
        self.mock_server_field = ft.TextField(label="mock服务器", value=self.config.mock_server)
        self.add_headers_field = ft.TextField(label="mock请求添加headers，一行一条记录", value=self.config.add_headers, multiline=True)
        self.add_body_field = ft.TextField(label="添加body", value=self.config.add_body, multiline=True)
        self.save_config_button = ft.ElevatedButton("保存配置",
                                                    on_click=self.save_config_by_button
                                                    )
        self.stest_button = ft.ElevatedButton("测试",
                                              on_click=self.test_proxy
                                              )

    def use_include_change(self, e:ControlEvent):
        self.include_field.visible = e.control.value
        self.page.update()

    def use_exclude_change(self, e:ControlEvent):
        self.exclude_field.visible = e.control.value
        self.page.update()

    def get_options(self):
        options = ["local", "regular", "wireguard", "socks5", "dns"]

        return [ft.DropdownOption(
            key=model,
            content=ft.Text(
                value=model
            ),
        ) for model in options]

    def dropdown_changed(self, e):
        self.config.proxy_model = e.control.value
        self.proxy_model_value_view.visible = self.config.proxy_model == "local"
        self.page.update()

    def test_proxy(self, e):
        ProxyCore.find_mitm_children()
        # children, threads = ProxyCore.find_mitm_children()
        # logger.info(f"mitmproxy children: {children}")
        # logger.info(f"mitmproxy threads: {threads}")

    async def save_config_by_button(self, e):
        await self.save_config()

    async def save_config(self):
        self.config.port = int(self.port_field.value)
        self.config.web_port = int(self.web_port_field.value)
        self.config.web_open_browser = self.web_open_browser.value
        self.config.proxy_model = self.proxy_model_view.value
        self.config.proxy_model_value = self.proxy_model_value_view.value
        self.config.mitmproxy_config_dir = self.mitmproxy_config_dir.value
        self.config.is_mock = self.is_mock.value
        self.config.open_include = self.open_include.value
        self.config.open_exclude = self.open_exclude.value
        self.config.include = self.include_field.value
        self.config.exclude = self.exclude_field.value
        self.config.mock_server = self.mock_server_field.value
        self.config.add_headers = self.add_headers_field.value
        self.config.add_body = self.add_body_field.value
        MitmproxyConfig.write(self.config)
        # UiUtil.show_snackbar_success(self.page, "配置已保存")
        await ProxyCore.update_config()
        logger.info("代理配置已保存")
        logger.info(f"mitmproxy config: {self.config}")
        self.page.update()

    def init(self):
        content = ft.Container(
            content=ft.Column([
                self.mock_server_field,
                ft.Row([
                    self.status_text,
                    self.is_mock,
                    self.open_include,
                    self.open_exclude,
                    self.web_open_browser,
                ]),
                ft.Row([
                    self.port_field,
                    self.web_port_field,
                    self.mitmproxy_config_dir
                ]),
                # ft.Row([
                #     self.proxy_model_view,
                #     self.proxy_model_value_view,
                # ]),
                self.include_field,
                self.exclude_field,
                self.add_headers_field,
                # self.add_body_field,
                ft.Row([
                    self.start_button,
                    self.stop_button,
                    self.save_config_button,
                    self.stest_button
                ])
            ], alignment=ft.MainAxisAlignment.START),
            alignment=ft.alignment.center_left
        )
        return content

    async def start_proxy_by_async(self, e):
        if self.proxy_running:
            return
        await self.save_config()
        self.start_button.disabled = True
        self.stop_button.disabled = False
        self.proxy_running = True
        self.page.update()
        self.proxy_core = ProxyCore()
        self.loop = asyncio.get_running_loop()
        self.task = self.loop.create_task(
            self.proxy_core.run(self.config))
        # await self.proxy_core.run(int(self.port_field.value),int(self.web_port_field.value),self.web_open_browser.value)
        UiUtil.show_snackbar_success(self.page, "mitmproxy 已启动")
        self.page.update()

    async def stop_proxy_by_async(self, e):
        self.start_button.disabled = False
        self.stop_button.disabled = True
        self.proxy_running = False

        """停止 mitmproxy"""
        if not self.proxy_core:
            logger.debug("mitmproxy 未启动")
            return

        logger.debug("正在停止 mitmproxy...")
        self.proxy_core.master.shutdown()
        await self.proxy_core.master.done()

        if self.task:
            logger.debug("正在停止 task...")
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass

        self.master = None
        self.task = None
        logger.info("mitmproxy 已停止")

        self.proxy_core = None
        UiUtil.show_snackbar_success(self.page, "mitmproxy 已停止")
        self.page.update()

    async def start_proxy(self, e):
        if self.proxy_running:
            logger.info("mitmproxy 已启动")
            return
        self.start_button.disabled = True
        self.stop_button.disabled = False
        self.proxy_running = True
        self.page.update(self.start_button, self.stop_button)
        await self.save_config()

        freeze_support()
        # share_data = get_shared()
        # share_data.update(self.config.model_dump())
        try:
            self.proxy = Process(target=ProxyCore().start_loop,
                                 args=(self.config,),
                                 name="mitmproxy-tool",
                                 daemon=True
                                 )
            self.proxy.start()
        except Exception as e:
            UiUtil.show_snackbar_error(self.page, f"mitmproxy启动失败:{e}")
            return
        UiUtil.show_snackbar_success(self.page, "mitmproxy 已启动")

    def stop_proxy(self, e):
        if not self.proxy_running:
            return

        self.start_button.disabled = False
        self.stop_button.disabled = True
        self.page.update(self.start_button, self.stop_button)
        self.proxy_running = False
        if self.proxy:
            self.proxy.terminate()
            self.proxy.join()
            self.proxy = None
        logger.info("mitmproxy 已停止")
        UiUtil.show_snackbar_success(self.page, "mitmproxy 已停止")
