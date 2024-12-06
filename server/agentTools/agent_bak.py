import asyncio
import configparser
import os
import subprocess
import sys
import time
from datetime import datetime
from tkinter import messagebox, simpledialog
from typing import Any

from loguru import logger
from ttkbootstrap import StringVar
import threading
import json
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from tkinter.scrolledtext import ScrolledText
from pathlib import Path
import pystray
from pystray import MenuItem, Menu
from PIL import Image
from ttkbootstrap.dialogs import Messagebox

# from common.db import Database
from common.AgentTools import AgentTools
from common.utils import bs64_to_text, decompress_text, get_mac_address
from common.RequestByInput import RequestByInput
from common.WebSocketClient import WebSocketClient
from view.CollapsingFrame import CollapsingFrame


class AgentToolsMain(ttk.Frame):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 读取配置文件
        self.config = configparser.ConfigParser()
        self.config.read('config.ini')
        config_setting = self.config['Settings']

        self.pack(fill=BOTH, expand=YES)
        # 实例化监听实例
        self.ag = AgentTools()
        # 用于启动服务监听
        self.server_thread = None
        # 避免重复启动服务
        self.server_status = False
        # 用于关闭启动监听服务的线程
        self.join_thread = None
        # 代理服务启动时间
        self.start_time = None
        # 代理服务启动时长计算
        self.timer_running = False
        self.agent_id = config_setting.get('agent_id') if config_setting.get('agent_id') else get_mac_address()
        self.client = WebSocketClient(config_setting['server_uri'] + '/' + self.agent_id, self.on_message_received)
        # self.websocket_client_thread = None
        # 初始化设置窗口标志
        self.settings_window_open = False

        image_files = {
            'properties-dark': 'icons8_settings_24px.png',
            'properties-light': 'icons8_settings_24px_2.png',
            'add-to-backup-dark': 'icons8_add_folder_24px.png',
            'add-to-backup-light': 'icons8_add_book_24px.png',
            'stop-backup-dark': 'icons8_cancel_24px.png',
            'stop-backup-light': 'icons8_cancel_24px_1.png',
            'play': 'icons8_play_24px_1.png',
            'refresh': 'icons8_refresh_24px_1.png',
            'stop-dark': 'icons8_stop_24px.png',
            'stop-light': 'icons8_stop_24px_1.png',
            'opened-folder': 'icons8_opened_folder_24px.png',
            'logo': 'backup.png',
            'sign-out-light': 'sign-out.png',
            'sign-out-dark': 'sign-out_1.png',
        }

        self.photoimages = []
        imgpath = Path(__file__).parent / 'assets'
        for key, val in image_files.items():
            _path = imgpath / val
            self.photoimages.append(ttk.PhotoImage(name=key, file=_path))

        # buttonbar
        buttonbar = ttk.Frame(self, style='primary.TFrame')
        buttonbar.pack(fill=X, pady=1, side=TOP)

        ## settings
        btn = ttk.Button(
            master=buttonbar,
            text='设置',
            image='properties-light',
            compound=LEFT,
            command=self.open_settings_window
        )
        btn.pack(side=LEFT, ipadx=5, ipady=5, padx=0, pady=1)

        ## restart
        btn = ttk.Button(
            master=buttonbar,
            text='重启',
            image='refresh',
            compound=LEFT,
            command=self._restart_app
        )
        btn.pack(side=LEFT, ipadx=5, ipady=5, padx=0, pady=1)

        ## Exit
        btn = ttk.Button(
            master=buttonbar,
            text='退出',
            image='sign-out-light',
            compound=LEFT,
            command=self.on_closing
        )
        btn.pack(side=LEFT, ipadx=5, ipady=5, padx=0, pady=1)

        # left panel
        left_panel = ttk.Frame(self, style='bg.TFrame', width=220)
        # left_panel.pack(side=LEFT, fill=Y)
        left_panel.pack(side='left', fill='y', expand=False)  # 禁止在水平方向扩展
        left_panel.propagate(False)  # 关闭自动调整大小

        ## Client Status (collapsible)
        bus_cf = CollapsingFrame(left_panel, width=220)
        bus_cf.pack(fill=X, pady=1)

        ## container
        bus_frm = ttk.Frame(bus_cf, padding=5, width=220)
        bus_frm.columnconfigure(1, weight=2)
        bus_cf.add(
            child=bus_frm,
            title='转发代理连接信息',
            bootstyle=SECONDARY)
        ## Start
        btn = ttk.Button(
            bus_frm,
            text='启动',
            image='play',
            compound=LEFT,
            command=self.start_websocket
        )
        btn.grid(row=0, column=0, sticky=W, padx=1, pady=2)

        ## Stop
        btn = ttk.Button(
            bus_frm,
            text='停止',
            image='stop-light',
            compound=LEFT,
            width=4,
            command=self.stop_websocket
        )
        btn.grid(row=0, column=1, sticky=W, padx=1, pady=2)

        ## Status
        lbl = ttk.Label(bus_frm, text='状态:')
        lbl.grid(row=2, column=0, sticky=W, pady=2)
        lbl = ttk.Label(bus_frm, textvariable='status')
        lbl.grid(row=2, column=1, sticky=EW, padx=5, pady=2)
        self.setvar('status', '未连接服务器')

        ## start time
        lbl = ttk.Label(bus_frm, text='开始时间:')
        lbl.grid(row=3, column=0, sticky=W, pady=2)
        lbl = ttk.Label(bus_frm, textvariable='StartTime')
        lbl.grid(row=3, column=1, sticky=EW, padx=5, pady=2)
        self.setvar('StartTime', '')

        ## connected time
        lbl = ttk.Label(bus_frm, text='持续时长:')
        lbl.grid(row=4, column=0, sticky=W, pady=2)
        lbl = ttk.Label(bus_frm, textvariable='ConnectedTime')
        lbl.grid(row=4, column=1, sticky=EW, padx=5, pady=2)
        self.setvar('ConnectedTime', '')

        ## section separator
        sep = ttk.Separator(bus_frm, bootstyle=SECONDARY)
        sep.grid(row=5, column=0, columnspan=2, pady=10, sticky=EW)

        lbl = ttk.Label(bus_frm, text='本机MAC:')
        lbl.grid(row=6, column=0, sticky=W, pady=2)
        self.loc_mac = StringVar()
        file_entry = ttk.Entry(bus_frm, textvariable=self.loc_mac, state="readonly", width=13)
        file_entry.grid(row=6, column=1, columnspan=1, sticky=W)
        self.loc_mac.set(get_mac_address())

        ## container
        # bus_frm = ttk.Frame(bus_cf, padding=5, width=220)
        # bus_frm.columnconfigure(1, weight=2)
        # bus_cf.add(
        #     child=bus_frm,
        #     title='本地代理连接信息',
        #     bootstyle=SECONDARY)

        # right panel
        right_panel = ttk.Frame(self, padding=(1, 1))
        right_panel.pack(side=RIGHT, fill=BOTH, expand=YES)

        ## Treeview
        # self.tv = ttk.Treeview(right_panel, show='headings', height=8)
        # self.tv.configure(columns=(
        #     'Id', 'Name', 'ListenAddress', 'ListenPort', 'ForwardBaseUrl', 'Remark'
        # ))
        # self.tv.column('Id', width=50, stretch=True)
        # self.tv.column('Name', width=120, stretch=True)
        # self.tv.column('ListenPort', width=120, stretch=True)
        #
        # for col in ['ListenAddress', 'ListenPort', 'ForwardBaseUrl']:
        #     self.tv.column(col, stretch=False)
        #
        # for col in self.tv['columns']:
        #     self.tv.heading(col, text=col.title(), anchor=W)
        #
        # self.tv.pack(fill=X, pady=1)
        #
        # db = Database('db/ag.db')
        # sql = "select * from ag_config"
        # res = db.query(sql)
        # num = 1
        # for row in res:
        #     item_id = row[0]
        #     self.tv.insert('', index=item_id, iid=item_id, values=(num, row[1], row[2], row[3], row[4], row[5]))
        #     num += 1

        # 为Treeview绑定双击事件
        # self.tv.bind('<Double-1>', self.on_double_click)

        ## scrolling text input
        scroll_cf_in = CollapsingFrame(right_panel)
        scroll_cf_in.pack(fill=BOTH, expand=YES)

        input_container = ttk.Frame(scroll_cf_in, padding=1)
        _value = 'Receive Data'
        self.setvar('input-message', _value)
        self.btn = ttk.Button(input_container, text="格式化", command=lambda: self._format_data("st_input"))
        self.btn.pack(side=TOP, fill=X)
        self.st_input = ScrolledText(input_container)
        self.st_input.tag_configure("sel", background="lightblue", foreground="blue")
        # 绑定全选事件到Ctrl+A
        self.st_input.bind("<Control-a>", lambda event: self._select_all_text("st_input", event))
        self.st_input.pack(fill=BOTH, expand=YES)
        scroll_cf_in.add(input_container, textvariable='input-message')

        ## scrolling text output
        scroll_cf = CollapsingFrame(right_panel)
        scroll_cf.pack(fill=BOTH, expand=YES)

        output_container = ttk.Frame(scroll_cf, padding=1)
        _value = 'Output Data'
        self.setvar('scroll-message', _value)
        self.btn = ttk.Button(output_container, text="格式化", command=lambda: self._format_data("st_output"))
        self.btn.pack(side=TOP, fill=X)
        self.st_output = ScrolledText(output_container)
        self.st_output.tag_configure("sel", background="lightblue", foreground="blue")
        # 绑定全选事件到Ctrl+A
        self.st_output.bind("<Control-a>", lambda event: self._select_all_text("st_output", event))
        self.st_output.pack(fill=BOTH, expand=YES)
        scroll_cf.add(output_container, textvariable='scroll-message')

    def _select_all_text(self, f_type, event):
        # ScrolledText事件绑定的函数
        if f_type == 'st_input':
            self.st_input.tag_add("sel", "1.0", "end-1c")  # 添加全选tag
            self.st_input.mark_set("insert", "1.0")  # 将光标移动到起始位置
            self.st_input.see("1.0")  # 滚动条滚动到起始位置
        elif f_type == 'st_output':
            self.st_output.tag_add("sel", "1.0", "end-1c")
            self.st_output.mark_set("insert", "1.0")
            self.st_output.see("1.0")
        return 'break'  # 阻止进一步处理事件

    def _format_data(self, f_type):
        try:
            if f_type == 'st_input':
                data = self.st_input.get(1.0, END)
                format_data = json.dumps(json.loads(data), indent=4, ensure_ascii=False)
                self.st_input.delete("1.0", END)
                self.st_input.insert(END, format_data)
            elif f_type == 'st_output':
                data = self.st_output.get(1.0, END)
                format_data = json.dumps(json.loads(data), indent=4, ensure_ascii=False)
                self.st_output.delete("1.0", END)
                self.st_output.insert(END, format_data)
        except json.decoder.JSONDecodeError as e:
            Messagebox.show_error(str(e), "格式化失败")


    def on_closing(self):
        """
        这个函数在用户点击关闭按钮时调用，弹出一个确认对话框。
        如果用户选择确认，则关闭程序。
        """
        if messagebox.askokcancel("退出", "确定要退出应用吗?"):
            self.master.destroy()

    # def on_double_click(self, event):
    #     item = self.tv.selection()  # 获取当前选中的项
    #     logger.info(f"Double clicked on item: {item}")
    #     # 根据ID查询服务配置信息
    #     db = Database('db/ag.db')
    #     sql = f"select * from ag_config where id={int(item[0])}"
    #     res = db.query(sql)
    #     if res:
    #         print(res)
    #         res = res[0]
    #         if self.server_status:
    #             self.stop_websocket()
    #
    #         # 配置信息
    #         CONFIG = {
    #             'listen_address': res[2],
    #             'listen_port': int(res[3]),
    #             'forward_base_url': res[4]
    #         }
    #         logger.info(f'CONFIG===========>{CONFIG}')
    #         # 创建一个线程来运行服务器
    #         server_thread = threading.Thread(target=self.ag.start_server, args=(CONFIG,))
    #         server_thread.start()

    def start_websocket(self):
        self.client.running = True
        if not self.client.websocket_client_thread or not self.client.websocket_client_thread.is_alive():
            self.client.websocket_client_thread = threading.Thread(target=self.client.run, daemon=True)
            self.client.websocket_client_thread.start()
            self.setvar('status', '已连接服务器')
            self.start_time = datetime.now()
            self.StartTime = self.start_time.strftime("%Y-%m-%d %H:%M:%S")
            self.setvar('StartTime', self.StartTime)

            self.timer_running = True
            self.update_timer()
        elif self.client.websocket_client_thread or self.client.websocket_client_thread.is_alive():
            self.setvar('status', '已连接服务器')
            self.start_time = datetime.now()
            self.StartTime = self.start_time.strftime("%Y-%m-%d %H:%M:%S")
            self.timer_running = True
            self.update_timer()
            self.setvar('StartTime', self.StartTime)

    def stop_websocket(self):
        self.client.running = False
        self.timer_running = False
        if self.client.websocket_client_thread:
            self.client.websocket_client_thread.join(timeout=3)
            try:
                asyncio.run(self.client.send_close())
            except RuntimeError as e:
                pass
        self.setvar('status', '连接已断开')

    async def on_message_received(self, data):
        self.st_input.delete("1.0", END)
        data = decompress_text(data)
        show_input_data = json.dumps(json.loads(bs64_to_text(data)), indent=4, ensure_ascii=False)
        self.st_input.insert(END, f'{show_input_data}\n')
        self.st_output.delete("1.0", END)
        res = await RequestByInput.forward_by_rules(data)
        show_output_data = json.dumps(json.loads(bs64_to_text(decompress_text(res))), indent=4, ensure_ascii=False)
        self.st_output.insert(END, f'{show_output_data}\n')
        return res

    def update_timer(self):
        if self.timer_running:
            current_time = datetime.now()
            elapsed_time = current_time - self.start_time
            # 使用 timedelta 格式化时间为天-时-分-秒
            days = elapsed_time.days
            hours, remainder = divmod(elapsed_time.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            formatted_time = f"{days:02}-{hours:02}-{minutes:02}-{seconds:02}"
            self.setvar('ConnectedTime', formatted_time)
            # 使用 after 方法每 1000 毫秒（1 秒）调用一次 update_timer
            self.after(1000, self.update_timer)

    def _restart_app(self):
        if messagebox.askokcancel("提示", "确定要重启应用吗？"):
            restart_app()

    def open_settings_window(self):
        # 检查设置窗口是否已经打开
        if self.settings_window_open:
            return  # 如果已经打开，则不做任何操作

        # 标记设置窗口为已打开
        self.settings_window_open = True
        # 创建自定义的Toplevel窗口
        settings_window = ttk.Toplevel(self)
        settings_window.title("设置SERVER_URI")
        settings_window.geometry("400x200")  # 设置窗口大小为400x200
        settings_window.resizable(False, False)

        # 创建输入框和标签
        ttk.Label(settings_window, text="请输入新的SERVER_URI").pack(pady=5)
        self.server_uri_entry = ttk.Entry(settings_window, width=50)
        self.server_uri_entry.pack(pady=5)
        self.server_uri_entry.insert(0, self.config['Settings']['server_uri'])
        self.server_uri_entry.focus()

        # 创建确认和取消按钮
        def confirm():
            new_server_uri = self.server_uri_entry.get()
            self.config.set('Settings', 'server_uri', new_server_uri)
            self.write_config()
            messagebox.showinfo("设置成功", "设置已更新，需要重启应用才能生效。")
            # 标记设置窗口为已关闭
            self.settings_window_open = False
            settings_window.destroy()
            self.ask_to_restart()

        def cancel():
            # 标记设置窗口为已关闭
            self.settings_window_open = False
            settings_window.destroy()

        ttk.Button(settings_window, text="取消", command=cancel).pack(side='right', padx=10)
        ttk.Button(settings_window, text="确认", command=confirm).pack(side='right', padx=10)

    def write_config(self):
        # 将配置写入文件
        with open('config.ini', 'w') as configfile:
            self.config.write(configfile)

    def ask_to_restart(self):
        # 提示重启生效
        restart_choice = messagebox.askyesno("重启应用", "是否立即重启应用以使设置生效？")
        if restart_choice:
            self.restart_app()

    def restart_app(self):
        restart_app()

class OperateWinProcess:

    def __init__(self, args: tuple, kwargs: dict[str, Any] = None) -> None:
        if kwargs is None:
            kwargs = {}
        # 获取当前脚本所在的目录
        base_path = os.path.dirname(__file__)
        self.args = args  # 必须传入app
        self.kwargs = kwargs
        menu = (
            MenuItem('显示', self.show_window, default=True),
            Menu.SEPARATOR,
            MenuItem('启动', self.start_service),
            MenuItem('停止', self.stop_service),
            Menu.SEPARATOR,
            MenuItem('重启', restart_app),
            Menu.SEPARATOR,
            MenuItem('退出', self.quit_window))
        # 拼接图标文件的路径
        icon_path = os.path.join(base_path, 'assets', 'main.ico')
        image = Image.open(icon_path)
        icon = pystray.Icon("icon", image, "AgentTools", menu)
        threading.Thread(target=icon.run, daemon=True).start()
        # 重新定义点击关闭按钮的处理
        self.args[0].protocol('WM_DELETE_WINDOW', self.on_exit)

    def quit_window(self, icon: pystray.Icon):
        icon.stop()
        self.args[0].destroy()

    def show_window(self):
        self.args[0].deiconify()

    def on_exit(self):
        self.args[0].withdraw()

    def stop_service(self):
        self.args[1].stop_websocket()

    def start_service(self):
        self.args[1].start_websocket()

def restart_app():
    # 使用 subprocess 来重新启动脚本
    try:
        # 获取当前执行的.exe文件的路径（假设它是通过命令行启动的）
        # 注意：这里应该是sys.argv，而不是sys.argv（它是一个列表）
        exe_path = os.path.abspath(sys.argv[0])

        # 检查是否是.exe文件（在Windows上）
        if exe_path.endswith(".exe"):
            # 使用subprocess.Popen来启动一个新的进程，并执行相同的.exe文件
            subprocess.Popen([exe_path])
        else:
            # 如果不是.exe文件（这种情况在打包后通常不会发生），则使用Python解释器来重新执行脚本
            python = sys.executable
            script_path = os.path.abspath(__file__)
            subprocess.Popen([python, script_path])
        time.sleep(3)
        # 使用sys.exit()退出当前程序
        sys.exit(0)
    except Exception as e:
        # 如果出现错误，显示一个错误消息
        messagebox.showerror("重启失败", str(e))

def check_and_create_config():
    """检查配置文件是否存在，不存在则创建"""
    config_file = 'config.ini'

    # 检查配置文件是否存在
    if not os.path.exists(config_file):
        # 创建配置文件
        config = configparser.ConfigParser()

        # 添加[Settings]节
        config['Settings'] = {}

        # 设置SERVER_URI的默认值为空
        config['Settings']['server_uri'] = ''

        # 写入配置文件
        with open(config_file, 'w') as f:
            config.write(f)
        logger.info(f"配置文件 {config_file} 已创建，并设置了默认值。")
    else:
        logger.info(f"配置文件 {config_file} 已存在。")

def main():
    # 检查/初始化配置文件
    check_and_create_config()
    app = ttk.Window(themename="vapor", title="AgentTools")
    app.geometry("1024x838")
    # app.resizable(False, False)
    am = AgentToolsMain(app)
    # 至少传入app
    OperateWinProcess((app, am))

    # 运行程序
    app.mainloop()


# 如果这是主程序，可以添加以下代码来运行GUI
if __name__ == "__main__":
    main()
