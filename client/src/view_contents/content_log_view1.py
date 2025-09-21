import flet as ft
import logging
from loguru import logger
import threading
import queue
import time
from datetime import datetime
from watchfiles import watch
from utils.share_data import get_local_log_queue


class FletLogHandler:
    """自定义 Loguru sink，将日志发送到 Flet 界面"""

    def __init__(self, log_queue):
        self.log_queue = log_queue
        self.enabled = False

    def write(self, message):
        if self.enabled:
            # 将日志消息放入队列，供 Flet UI 消费
            self.log_queue.put(message)

    def flush(self):
        pass  # 不需要实现


class LogViewerApp:
    def __init__(self, page: ft.Page):
        self.page: ft.Page = page

        # 创建线程安全的日志队列
        self.log_queue = get_local_log_queue()

        # 设置 Loguru 日志器
        self.setup_logging()

        # 创建UI
        self.create_ui()

        # 启动日志消费者
        self.start_log_consumer()

    def init_ui(self):
        self.container = ft.Container(content=ft.Column([
            ft.Row([
                # self.console_toggle,
                self.flet_toggle,
                self.test_button,
                self.clear_button
            ]),
            ft.Container(
                content=self.log_display,
                border=ft.border.all(1, ft.Colors.GREY_300),
                border_radius=5,
                padding=10,
                expand=True
            )
        ])
        )
        return self.container

    def setup_logging(self):
        # 添加 Flet 界面处理器
        self.flet_handler = FletLogHandler(self.log_queue)
        logger.add(
            self.flet_handler.write,
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
            level="DEBUG"
        )

    def create_ui(self):
        """创建用户界面"""

        # Flet 日志显示开关
        self.flet_output_enabled = False
        self.flet_toggle = ft.Switch(
            label="界面日志显示",
            value=self.flet_output_enabled,
            on_change=self.toggle_flet_output
        )

        # 日志显示区域
        self.log_display = ft.ListView(
            expand=True,
            spacing=1,
            auto_scroll=True,
            padding=0,
        )

        # 测试按钮
        self.test_button = ft.ElevatedButton(
            "生成测试日志",
            on_click=self.generate_test_logs
        )

        # 清空日志按钮
        self.clear_button = ft.ElevatedButton(
            "清空日志",
            on_click=self.clear_logs
        )

        # 布局
        # self.page.add(
        #
        # )

    async def toggle_flet_output(self, e):
        """切换 Flet 界面日志显示"""
        self.flet_output_enabled = self.flet_toggle.value
        self.flet_handler.enabled = self.flet_output_enabled
        logger.info(f"界面日志显示: {'启用' if self.flet_output_enabled else '禁用'}")

    async def generate_test_logs(self, e):
        """生成测试日志"""
        logger.debug("这是一条调试日志")
        logger.info("这是一条信息日志")
        logger.warning("这是一条警告日志")
        logger.error("这是一条错误日志")

        # 模拟一些工作日志
        for i in range(3):
            logger.info(f"正在处理任务 {i + 1}/3")
            time.sleep(0.5)

        logger.info("所有任务已完成")

    async def clear_logs(self, e):
        """清空日志显示"""
        self.log_display.controls.clear()
        self.page.update(self.log_display)
        logger.info("日志已清空")

    def start_log_consumer(self):
        """启动日志消费者，从队列中获取日志并显示到UI"""

        def consume_logs():
            while True:
                try:
                    # 从队列中获取日志消息
                    log_message = self.log_queue.get(timeout=1.0)

                    # 在UI线程中更新显示
                    self.page.run_task(
                        self.add_log_to_display,
                        log_message
                    )
                except queue.Empty:
                    continue
                except Exception as e:
                    print(f"日志消费错误: {e}")

        # 在后台线程中运行日志消费者
        threading.Thread(target=consume_logs, daemon=True).start()

    async def add_log_to_display(self, log_message):
        """将日志添加到显示区域"""
        # 根据日志级别设置不同的颜色
        color = ft.Colors.WHITE
        if "DEBUG" in log_message:
            color = ft.Colors.BLUE
        elif "INFO" in log_message:
            color = ft.Colors.GREEN
        elif "WARNING" in log_message:
            color = ft.Colors.YELLOW
        elif "ERROR" in log_message:
            color = ft.Colors.RED

        # 创建日志文本控件
        log_text = ft.Text(log_message, color=color, selectable=True)

        # 添加到显示区域
        self.log_display.controls.append(log_text)

        # 更新界面
        self.page.update(self.log_display)

