import asyncio
from multiprocessing import Process, Manager, freeze_support

import flet as ft
from loguru import logger

from server.config import MitmproxyConfig
from utils.mitmproxy_tool import ProxyCore, MockHandle as mockHandle
from utils.share_data import get_shared


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
        self.open_include = ft.Checkbox("启用包含", value=self.config.open_include)
        self.open_exclude = ft.Checkbox("启用排除", value=self.config.open_exclude)
        self.include_field = ft.TextField(label="包含", value=self.config.include, multiline=True)
        self.exclude_field = ft.TextField(label="排除", value=self.config.exclude, multiline=True)
        self.mock_server_field = ft.TextField(label="mock服务器", value=self.config.mock_server)
        self.add_headers_field = ft.TextField(label="添加headers", value=self.config.add_headers, multiline=True)
        self.add_body_field = ft.TextField(label="添加body", value=self.config.add_body, multiline=True)
        self.save_config_button = ft.ElevatedButton("保存配置",
                                                    on_click=self.save_config_by_button
                                                    )
        self.stest_button = ft.ElevatedButton("测试",
                                              on_click=self.test_proxy
                                              )

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
        self.page.snack_bar = ft.SnackBar(ft.Text("配置已保存"))
        self.page.snack_bar.open = True
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
                self.include_field,
                self.exclude_field,
                self.add_headers_field,
                self.add_body_field,
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
            self.proxy_core.run(int(self.port_field.value), int(self.web_port_field.value),
                                self.web_open_browser.value))
        # await self.proxy_core.run(int(self.port_field.value),int(self.web_port_field.value),self.web_open_browser.value)
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
        self.proxy = Process(target=ProxyCore().start_loop,
                             args=(int(self.port_field.value),
                                   int(self.web_port_field.value),
                                   self.web_open_browser.value,
                                   self.mitmproxy_config_dir.value,
                                   ),
                             name="mitmproxy-tool",
                             daemon=True
                             )
        self.proxy.start()
        self.status_text.value = f"代理已启动"
        self.page.update(self.status_text)

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
        self.status_text.value = "代理已停止"
        logger.info("mitmproxy 已停止")
        self.page.update(self.status_text)
