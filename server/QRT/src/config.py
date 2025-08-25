import os

class AppConfig:
    """配置应用基本信息"""

    def __init__(self, ft, page):
        self.page = page
        self.page.title = "TestTools"
        self.version = "1.0.0.0"
        self.tools_db = "tools_config.json"
        self.page.theme_mode = ft.ThemeMode.LIGHT # 亮色主题
        self.page.theme = ft.Theme(color_scheme_seed=ft.Colors.GREEN)
        # 基础窗口配置
        # page.window.width = 800
        # page.window.height = 600
        # 禁用最大化窗口
        # page.window.maximizable = False

        # 不可调整窗口大小
        # page.window.resizable = False
        # 窗口启动时居中位置
        page.window.center()  # 自动居中
        page.update()


class _Config:
    def __init__(self):
        self.set_timer = 10

    @property
    def timer(self):
        """定时器间隔时间"""
        return self.set_timer


config = _Config()