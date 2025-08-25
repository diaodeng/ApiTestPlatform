import os
from threading import Timer
from utils.mytimers import active_timers, add_timer, clear_all_timers

from utils.common import check_process, kill_process_by_name, check_offline_service_status, run_bat
from config import config
from view_contents.exitAlertDialog import ExitAlertDialog


class Shortcut(object):
    """快捷操作"""

    def __init__(self, ft, page, log):
        self.ft = ft
        self.log = log
        self.page = page

        # 初始化状态变量
        self.pos_process_name = "CPOS-DF.exe"
        self.pos_status = False
        self.offline_status = False

        self.pos_status_text = None
        self.offline_status_text = None

        # 启动时执行状态检查更新
        self.update_status()

        # 定时任务
        self.timer = None  # 用于保存定时器对象
        self.timer_status = False  # 定时器运行状态
        self.timer_status_text = self.ft.Text(
            f"{"已启动" if self.timer_status else "未启动"}",
            color=self.ft.Colors.GREEN if self.timer_status else self.ft.Colors.RED
        )
        self.timer_control_btn = self.ft.Button("启动定时刷新", on_click=self.toggle_timer)

        # 绑定页面加载完成
        self.page.on_load = self._on_page_loaded

        # 处理页面关闭事件,如果定时器运行中需要先清理资源
        def window_event(e):
            if e.data == "close":
                self.page.open(ExitAlertDialog(self.ft, self.page).confirm_dialog)
                self.page.update()

        self.page.window.prevent_close = True
        self.page.window.on_event = window_event

    def _on_page_loaded(self, e):
        """页面加载完成"""
        self.page.update()
        # 启动定时器更新状态
        self.start_auto_refresh()

    def toggle_timer(self, e):
        """切换定时器状态"""
        if self.timer_status:
            self.stop_auto_refresh()
        else:
            self.start_auto_refresh()

    def update_status(self, flag=0):
        """更新所有状态"""
        if flag == 1 or flag == 0:
            # POS 状态
            if not self.pos_status_text:
                self.pos_status_text = self.ft.Text(
                    f"{"已启动" if self.pos_status else "未启动"}",
                    color=self.ft.Colors.GREEN if self.pos_status else self.ft.Colors.RED
                )
            else:
                self.pos_status = check_process(self.pos_process_name, self.log)
                self.pos_status_text.value = f"{"已启动" if self.pos_status else "未启动"}"
                self.pos_status_text.color = self.ft.Colors.GREEN if self.pos_status else self.ft.Colors.RED
        if flag == 2 or flag == 0:
            # Offline Service 状态
            if not self.offline_status_text:
                self.offline_status_text = self.ft.Text(
                    f"{"已启动" if self.offline_status else "未启动"}",
                    color=self.ft.Colors.GREEN if self.offline_status else self.ft.Colors.RED
                )
            else:
                self.offline_status = check_offline_service_status(self.log)
                self.offline_status_text.value = f"{"已启动" if self.offline_status else "未启动"}"
                self.offline_status_text.color = self.ft.Colors.GREEN if self.offline_status else self.ft.Colors.RED

    def start_auto_refresh(self):
        """启动自动刷新定时器"""

        if self.timer is not None and self.timer.is_alive():
            self.timer.cancel()  # 取消已有定时器

        self.timer_status = True
        self.log.info(f"定时器间隔时间:{config.timer}S")
        self.timer_status_text.value = "已启动"
        self.timer_status_text.color = self.ft.Colors.GREEN
        self.timer_control_btn.text = "停止定时刷新"

        # 创建并启动新定时器
        self.timer = Timer(config.timer, self.refresh_status)
        add_timer(self.timer)
        self.timer.start()

        # 更新UI
        if self.timer_status_text:
            self.timer_status_text.update()
            self.timer_control_btn.update()

    def stop_auto_refresh(self):
        """停止自动刷新定时器"""
        if self.timer is not None:
            self.timer.cancel()
            self.timer = None

        self.timer_status = False
        self.timer_status_text.value = "未启动"
        self.timer_status_text.color = self.ft.Colors.RED
        self.timer_control_btn.text = "启动定时刷新"

        # 更新UI
        if self.timer_status_text:
            self.timer_status_text.update()
            self.timer_control_btn.update()
            self.log.info("定时刷新已停止")

    def refresh_status(self):
        """定时刷新状态"""
        try:
            # 更新状态
            self.update_status()

            # 刷新UI
            self.pos_status_text.update()
            self.offline_status_text.update()
            self.log.info(f"状态已自动刷新")

            # 如果定时器仍在运行状态，重新启动定时器
            if self.timer_status:
                self.log.debug("重新启动定时器...")
                self.start_auto_refresh()

        except Exception as e:
            self.log.error(f"自动刷新失败：{str(e)}")
            self.stop_auto_refresh()  # 出错时停止定时器

    def on_click_recheck(self, flag):
        """
        手动检查状态
        :param flag: 1-POS，2-离线服务
        :return:
        """
        self.update_status(flag)
        if flag == 1:
            self.pos_status_text.update()
        elif flag == 2:
            self.offline_status_text.update()
        self.log.info(f"手动检查状态：{'POS' if flag == 1 else '离线服务'} 完成")

    def on_click_kill(self, flag):
        """
        杀死应用进程并更新状态
        :param flag: : 1-POS，2-离线服务
        :return:
        """
        if flag == 1:
            kill_process_by_name(self.pos_process_name, self.log)
            self.log.info("已尝试终止POS进程")

            # 更新pos应用状态
            self.update_status()
            self.pos_status_text.update()

        elif flag == 2:
            base_path = os.path.dirname(__file__)
            bat_file_path = os.path.join(base_path, "shell\\stop.bat")
            self.log.info(f"脚本文件路径: {bat_file_path}")
            run_bat(bat_file_path, log=self.log)

            # 更新离线服务状态
            self.update_status()
            self.offline_status_text.update()

    def shortcut(self):
        content = self.ft.Container(
            content=self.ft.Column([
                self.ft.Text("快捷操作>", size=20),
                self.ft.Divider(),
                self.ft.Row([
                    self.ft.Text(f"定时任务状态:"),
                    self.timer_status_text,
                    self.timer_control_btn

                ]),
                self.ft.Row([
                    self.ft.Text(f"POS状态:"),
                    self.pos_status_text,
                    self.ft.Button("重新检查", on_click=lambda e: self.on_click_recheck(1)),
                    self.ft.Button("Kill POS", on_click=lambda e: self.on_click_kill(1)),
                ]),
                self.ft.Row([
                    self.ft.Text(f"离线服务状态:"),
                    self.offline_status_text,
                    self.ft.Button("重新检查", on_click=lambda e: self.on_click_recheck(2)),
                    self.ft.Button("Kill Offline-Service", on_click=lambda e: self.on_click_kill(2)),
                ]),
            ], alignment=self.ft.MainAxisAlignment.START),
            alignment=self.ft.alignment.center_left
        )
        return content
