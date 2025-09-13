import flet as ft
import asyncio
import threading
import time
# import paramiko
from watchfiles import watch
import re
from datetime import datetime
from loguru import logger
from watchfiles import awatch


class LogViewerApp:
    def __init__(self, page: ft.Page):
        self.page = page
        # self.page.title = "日志查看工具"
        # self.page.window.width = 1000
        # self.page.window.height = 700
        self.current_log_file_path = None
        self.current_thread = None
        self.stop_watch = False

        # 日志缓冲区
        self.log_buffer = []
        self.max_log_lines = 1000

        # SSH客户端
        self.ssh_client = None
        self.ssh_connected = False

        # 创建UI
        self.create_ui()

        # 启动内存日志记录
        self.start_memory_logger()

    def init_ui(self):
        self.tabs = ft.Container(
            content=ft.Tabs(
                selected_index=0,
                animation_duration=300,
                tabs=[
                    ft.Tab(
                        tab_content=ft.Container(content=ft.Row([ft.Icon(ft.Icons.SHELVES), ft.Text("SSH日志")])),
                        content=self.create_ssh_tab(),
                    ),
                    ft.Tab(
                        tab_content=ft.Container(content=ft.Row([ft.Icon(ft.Icons.FOLDER), ft.Text("本地日志")])),
                        content=self.create_local_tab(),
                    ),
                    ft.Tab(
                        tab_content=ft.Container(content=ft.Row([ft.Icon(ft.Icons.LIST), ft.Text("程序日志")])),
                        content=self.create_app_log_tab(),
                    ),
                ],
                expand=1,
            )
        )
        return self.tabs

    def create_ui(self):
        """创建用户界面"""
        # SSH连接控件
        self.host_input = ft.TextField(label="主机地址", width=200)
        self.port_input = ft.TextField(label="端口", value="22", width=100)
        self.username_input = ft.TextField(label="用户名", width=150)
        self.password_input = ft.TextField(
            label="密码", password=True, width=150)
        self.ssh_path_input = ft.TextField(
            label="日志路径",
            value="/var/log/syslog",
            width=300,
            tooltip="例如: /var/log/syslog 或 /var/log/auth.log")

        self.connect_button = ft.ElevatedButton(
            "连接SSH", on_click=self.toggle_ssh_connection)
        self.ssh_status = ft.Text("未连接", color="red")

        # 本地文件选择
        self.file_picker = ft.FilePicker(on_result=self.file_picked)
        self.page.overlay.append(self.file_picker)

        self.file_path_input = ft.TextField(
            label="本地日志路径", width=300, read_only=True)
        self.browse_button = ft.ElevatedButton(
            "浏览文件",
            on_click=lambda _: self.file_picker.pick_files(
                allow_multiple=False,
                allowed_extensions=["log", "txt"]))

        # 过滤设置
        self.filter_input = ft.TextField(
            label="过滤关键词",
            width=300,
            hint_text="支持正则表达式")
        self.filter_button = ft.ElevatedButton(
            "应用过滤", on_click=self.apply_filter)

        self.enable_watch_file_checkbox = ft.Checkbox(label="启用文件监控")

        self.search_file_log_input = ft.TextField(
            label="搜索文件日志",
            width=300,
            hint_text="支持正则表达式")

        self.file_max_lines_input = ft.TextField(
            label="最大显示行数",
            value="1000",
            on_change=self.file_max_lines_change,
            width=100)

        # 日志显示区域
        self.file_log_display = ft.Column(
            [ft.Text("日志内容将在这里显示...")],
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )

        self.is_auto_update = ft.Checkbox(label="自动滚动列表", value=True)

        # 日志显示区域
        self.ssh_log_display = ft.TextField(
            label="SSH日志",
            multiline=True,
            expand=True,
            col=12
        )

    def create_ssh_tab(self):
        """创建SSH日志标签页"""
        return ft.Container(
            content=ft.Column([
                ft.Row([
                    self.host_input,
                    self.port_input,
                    self.username_input,
                    self.password_input,
                ]),
                ft.Row([
                    self.ssh_path_input,
                    self.connect_button,
                    self.ssh_status
                ]),
                ft.Divider(),
                ft.Row([
                    self.filter_input,
                    self.filter_button
                ]),
                ft.Container(
                    content=self.ssh_log_display,
                    border=ft.border.all(1, ft.Colors.GREY_300),
                    border_radius=5,
                    padding=10,
                    expand=True
                )
            ], expand=True),
            padding=10,
            expand=True
        )

    def create_local_tab(self):
        """创建本地日志标签页"""
        return ft.Container(
            content=ft.Column([
                ft.Row([
                    self.file_path_input,
                    self.browse_button,
                    self.enable_watch_file_checkbox,
                    self.is_auto_update
                ]),
                ft.Divider(),
                ft.Row([
                    self.filter_input,
                    self.filter_button,
                    ft.Button("清空日志", on_click=self.clear_file_log),
                    self.search_file_log_input,
                    ft.Button("搜索日志", on_click=self.search_file_log),
                    self.file_max_lines_input,
                ]),
                ft.Container(
                    content=ft.Row([self.file_log_display]),
                    border=ft.border.all(1, ft.Colors.GREY_300),
                    border_radius=5,
                    padding=10,
                    expand=True
                )
            ], expand=True),
            padding=10,
            expand=True
        )

    def file_max_lines_change(self, e):
        """最大显示行数改变"""
        try:
            self.max_log_lines = int(self.file_max_lines_input.value)
        except ValueError:
            self.max_log_lines = 1000

    def create_app_log_tab(self):
        """创建程序日志标签页"""
        self.app_log_display = ft.Column(
            [ft.Text("程序运行日志将显示在这里...")],
            scroll=ft.ScrollMode.AUTO,
            expand=True
        )

        return ft.Container(
            content=ft.Column([
                ft.Container(
                    content=self.app_log_display,
                    border=ft.border.all(1, ft.Colors.GREY_300),
                    border_radius=5,
                    padding=10,
                    expand=True
                )
            ], expand=True),
            padding=10,
            expand=True
        )

    def toggle_ssh_connection(self, e):
        """切换SSH连接状态"""
        if not self.ssh_connected:
            # 连接SSH
            self.connect_ssh()
        else:
            # 断开SSH
            self.disconnect_ssh()

    def connect_ssh(self):
        """建立SSH连接"""
        pass
        # try:
        #     self.ssh_client = paramiko.SSHClient()
        #     self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        #
        #     # 在后台线程中执行SSH连接
        #     def ssh_connect():
        #         self.ssh_client.connect(
        #             hostname=self.host_input.value,
        #             port=int(self.port_input.value),
        #             username=self.username_input.value,
        #             password=self.password_input.value,
        #             timeout=10
        #         )
        #         self.ssh_connected = True
        #
        #         # 开始监控远程日志
        #         self.monitor_remote_log()
        #
        #     # 执行连接
        #     threading.Thread(target=ssh_connect, daemon=True).start()
        #
        #     # 更新UI状态
        #     self.connect_button.text = "断开SSH"
        #     self.ssh_status.value = "已连接"
        #     self.ssh_status.color = "green"
        #     self.page.update()
        #
        #     self.add_log("SSH连接成功")
        #
        # except Exception as e:
        #     self.add_log(f"SSH连接错误: {str(e)}")

    def disconnect_ssh(self):
        """断开SSH连接"""
        if self.ssh_client:
            self.ssh_client.close()
        self.ssh_connected = False

        self.connect_button.text = "连接SSH"
        self.ssh_status.value = "未连接"
        self.ssh_status.color = "red"
        self.page.update()

        self.add_log("SSH连接已断开")

    def monitor_remote_log(self):
        """监控远程日志文件"""
        if not self.ssh_connected:
            return

        try:
            # 执行tail -f命令实时获取日志
            command = f"tail -f {self.ssh_path_input.value}"
            stdin, stdout, stderr = self.ssh_client.exec_command(command)

            # 实时读取输出
            for line in iter(stdout.readline, ""):
                if line and self.ssh_connected:
                    self.add_log(line.strip())

        except Exception as e:
            self.add_log(f"监控远程日志错误: {str(e)}")

    async def file_picked(self, e: ft.FilePickerResultEvent):
        """处理文件选择结果"""
        if e.files:
            self.file_path_input.value = e.files[0].path
            self.page.update()

            # 开始监控选中的文件
            self.monitor_local_log()
            # 开始监控选中的文件
            # await self.log_watcher()

    async def log_watcher(self):
        file_path = self.file_path_input.value
        if not file_path:
            return
        self.add_log(f"watchfiles 开始监控文件: {file_path}")
        with open(file_path, "r", encoding="utf-8") as f:
            f.seek(0, 2)  # 移动到末尾
            async for changes in awatch(file_path):
                for change, path in changes:
                    if path == file_path:
                        for line in f:
                            self.add_log(line.strip())
                            # print("[watchfiles]", line.strip())

    def monitor_local_log(self):
        """监控本地日志文件"""
        self.file_path = self.file_path_input.value
        if not self.file_path:
            return
        if self.current_thread:
            self.stop_watch = True
            self.current_thread.join()
            self.current_thread = None
            self.stop_watch = False

        # 在后台线程中监控文件变化
        def watch_file():
            with open(self.file_path, "r", encoding="utf-8") as f:
                f.seek(0, 2)  # 移动到文件末尾
                while True:
                    if self.stop_watch:
                        break
                    line = f.readline()
                    if not line:
                        time.sleep(0.5)  # 没有新内容就等待
                        continue
                    # print("更新内容:", line.strip())
                    if self.enable_watch_file_checkbox.value:
                        self.add_log(line.strip())

        self.current_thread = threading.Thread(target=watch_file, daemon=True)
        self.current_thread.start()
        self.add_log(f"开始监控文件: {self.file_path}")

    async def apply_filter(self, e):
        """应用过滤条件"""
        filter_text = self.filter_input.value
        if not filter_text:
            self.add_log("请输入过滤条件")
            return
        # 过滤逻辑

        self.add_log(f"应用过滤: {filter_text}")
        # 在实际应用中，这里应该实现过滤逻辑

    def add_log(self, message):
        """添加日志到显示区域"""
        # 过滤逻辑
        filter_text = self.filter_input.value
        if filter_text:
            if filter_text.lower() not in message.lower():
                return

        log_entry = ft.Text(f"{message}")

        # 添加到缓冲区
        self.log_buffer.append(log_entry)
        self.file_log_display.controls.append(log_entry)

        # 限制日志行数
        if len(self.log_buffer) > self.max_log_lines:
            self.log_buffer.pop(0)
            self.file_log_display.controls.pop(0)

        # 更新显示
        # self.file_log_display.update()
        # 滚动到底部
        if self.file_log_display.page is not None:
            if self.is_auto_update.value:
                self.file_log_display.scroll_to(offset=-1, duration=100)
            else:
                self.file_log_display.update()

    def add_app_log(self, message):
        """添加日志到程序日志区域"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = ft.Text(f"[{timestamp}] {message}")

        # 更新程序日志显示
        if hasattr(self, 'app_log_display'):
            self.app_log_display.controls.append(log_entry)

            # 限制行数
            if len(self.app_log_display.controls) > self.max_log_lines:
                self.app_log_display.controls = self.app_log_display.controls[-self.max_log_lines:]

            # 滚动到底部
            if self.app_log_display.page is not None:
                self.app_log_display.scroll_to(offset=-1, duration=100)

    def start_memory_logger(self):
        """启动内存日志记录器"""

        def log_memory_usage():
            while True:
                import psutil
                process = psutil.Process()
                memory_usage = process.memory_info().rss / 1024 / 1024  # MB
                self.add_app_log(f"内存使用: {memory_usage:.2f} MB")
                time.sleep(60)

        threading.Thread(target=log_memory_usage, daemon=True).start()

    def clear_file_log(self, e):
        """清空文件日志显示"""
        self.log_buffer.clear()
        self.file_log_display.controls.clear()
        self.page.update(self.file_log_display)
        self.add_log("文件日志已清空")

    def search_file_log(self, e):
        """搜索文件日志"""
        search_text = self.search_file_log_input.value
        if not search_text:
            self.add_log("请输入搜索内容")
            return
        # 搜索逻辑

        self.add_log(f"搜索文件日志: {search_text}")
        # 在实际应用中，这里应该实现搜索逻辑


def main(page: ft.Page):
    app = LogViewerApp(page)


if __name__ == "__main__":
    ft.app(target=main)