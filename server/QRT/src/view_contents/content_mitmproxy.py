import flet as ft
import threading
import asyncio
from mitmproxy.options import Options
from mitmproxy.tools.web.master import WebMaster

from src.utils.mitmproxy_tool import ProxyCore


class MitmHandel:
    def __init__(self, page: ft.Page):
        self.page = page
        self.proxy = ProxyCore()
        self.port_field = ft.TextField(label="代理端口", value="8080")
        self.web_port_field = ft.TextField(label="Web端口", value="8081")
        self.snack_bar = ft.SnackBar(ft.Text("代理未启动"), open=True)
        
    def init(self):
        content = ft.Container(
            content=ft.Column([
                self.snack_bar,
                self.port_field,
                self.web_port_field,
                ft.Row([
                    ft.ElevatedButton("启动代理", on_click=self.start_proxy),
                    ft.ElevatedButton("停止代理", on_click=self.stop_proxy),
                ])
            ], alignment=ft.MainAxisAlignment.START),
            alignment=ft.alignment.center_left
        )
        return content

    def start_proxy(self, e):
        self.proxy.start(int(self.port_field.value), int(self.web_port_field.value))
        self.snack_bar = ft.SnackBar(ft.Text("代理已启动"), open=True)
        self.page.update()

    def stop_proxy(self, e):
        self.proxy.stop()
        self.snack_bar = ft.SnackBar(ft.Text("代理已停止"), open=True)
        self.page.update()
