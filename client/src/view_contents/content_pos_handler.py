import asyncio
import os
import fnmatch
import os
from threading import Thread, Event

import flet as ft
from loguru import logger

from server.config import SearchConfig, StartConfig, PaymentMockConfig, MitmproxyConfig, PosConfig
from utils import file_handle
from utils.common import kill_process_by_name
from common.ui_utils.ui_util import UiUtil


class PosHandler:
    def __init__(self, ft, page: ft.Page):
        self.start_config = StartConfig.read()
        self.ft = ft
        self.page = page
        self.set_width = 400
        self.stop_event = Event()
        self.setup_ui()

    def open_work_dir_list_dialog(self, e):
        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("已添加工作目录"),
            content=ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Text(item, expand=True),
                        ft.ElevatedButton("删除", on_click=lambda e, pos_path=item: self.remove_work_dir(e, pos_path))
                    ]) for item in SearchConfig.read_work_dir()
                ], expand=True),
                expand=True,
            ),
            actions=[
                ft.TextButton("取消", on_click=lambda e: e.page.close(dialog)),
                # ft.TextButton("添加", on_click=lambda e: dialog.dismiss()),
            ],
        )
        dialog.open = True
        self.page.open(dialog)
        self.page.update()

    def remove_work_dir(self, e: ft.ControlEvent, item):
        SearchConfig.remove_work_dir(item)
        e.control.parent.parent.controls.remove(e.control.parent)
        # self.open_work_dir_list_dialog(None)
        self.page.update()

    def init_ui(self):

        content = self.ft.Container(
            content=self.ft.Column([
                self.ft.Text("POS快捷功能>", size=20),
                self.ft.Divider(),
                self.ft.Row([
                    # 搜索参数输入区
                    ft.ElevatedButton(
                        "添加工作目录",
                        tooltip="添加工作目录，索引时会递归搜索",
                        on_click=self.open_directory_dialog
                    ),
                    ft.Button("查看工作目录", tooltip="查看已经添加的工作目录", on_click=lambda e: self.open_work_dir_list_dialog(e)),
                    self.search_btn,
                    self.stop_btn,
                    self.kill_process_btn,
                ]),
                ft.Row([
                    self.file_pattern,
                    self.dir_pattern,
                    self.scan_deep,
                ]),
                self.ft.Row([
                    # 控制按钮
                    ft.Text("启动POS前："),
                    self.before_start_back_view,
                    self.before_start_cover_payment_driver_view,
                    self.before_start_replace_mitm_cert_view,
                    self.before_start_change_pos_view,
                    self.before_start_change_env_view,
                    self.before_start_remove_cache_view,
                    ft.TextField(label="查找结果", on_change=lambda e: self.search_result(e))
                ],
                    # expand=True,
                    alignment=ft.MainAxisAlignment.START,
                ),
                # 进度显示
                # self.progress_bar,
                self.status_text,
                self.ft.Divider(),
                # 结果展示
                self.results_view
            ], alignment=self.ft.MainAxisAlignment.START),
            alignment=self.ft.alignment.center_left
        )
        return content

    def setup_ui(self):
        search_config = SearchConfig.read()
        self.page.vertical_alignment = ft.MainAxisAlignment.CENTER
        self.page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
        self.page.padding = 30

        self.file_pattern = ft.TextField(
            label="文件名模式",
            tooltip="匹配指定规则的文件名",
            hint_text="例如: *.txt 或 report*.docx",
            width=self.set_width,
            value=search_config.file_pattern,
            on_change=self.validate_inputs
        )

        self.dir_pattern = ft.TextField(
            label="目录名模式",
            tooltip="只索引指定规则的目录名",
            hint_text="例如: * 或 report*.docx",
            width=self.set_width,
            value=search_config.dir_pattern,
            on_change=self.validate_inputs
        )

        self.scan_deep = ft.TextField(
            label="递归深度",
            hint_text="1",
            value=search_config.max_depth,
            width=100,
            # on_change=self.validate_inputs
        )

        # 控制按钮
        self.search_btn = ft.ElevatedButton(
            "开始索引",
            tooltip="按规则索引工作目录中的文件",
            on_click=self.start_search,
            disabled=not search_config.dir
        )
        self.stop_btn = ft.ElevatedButton(
            "停止",
            tooltip="停止索引",
            on_click=self.stop_search,
            disabled=True,
            # color="red"
        )

        self.kill_process_btn = ft.ElevatedButton(
            "结束POS",
            on_click=lambda e: self.kill_pos_process(),
            # disabled=True,
            # color="red"
        )

        self.before_start_back_view = ft.Checkbox(
            label="备份支付驱动",
            tooltip="备份支付驱动，备份在POS根目录下的drive_backup",
            value=self.start_config.backup,
            on_change=self.update_start_config,
        )

        self.before_start_change_pos_view = ft.Checkbox(
            label="切换POS",
            tooltip="调用posChange接口切换POS",
            value=self.start_config.change_pos,
            on_change=self.update_start_config,
        )

        self.before_start_cover_payment_driver_view = ft.Checkbox(
            label="覆盖支付驱动",
            tooltip="使用mock驱动覆盖现有支付驱动",
            value=self.start_config.cover_payment_driver,
            on_change=self.update_start_config,
        )

        self.before_start_replace_mitm_cert_view = ft.Checkbox(
            label="替换mitm证书",
            tooltip="在POS证书中添加mitmproxy证书，避免接口代理失败",
            value=self.start_config.replace_mitm_cert,
            on_change=self.update_start_config,
        )

        self.before_start_change_env_view = ft.Checkbox(
            label="切换环境",
            tooltip="切换本地环境，修改pos.ini、切换database、logs、缓存等",
            value=self.start_config.change_env,
            on_change=self.update_start_config,
        )

        self.before_start_remove_cache_view = ft.Checkbox(
            label="清除缓存",
            tooltip="清除POS缓存文件",
            value=self.start_config.remove_cache,
            on_change=self.update_start_config,
        )

        # 进度显示
        self.progress_bar = ft.ProgressBar(
            width=self.set_width,
            value=0,
            visible=False
        )
        self.status_text = ft.Text()

        # 结果展示
        self.results_view = ft.ListView(
            expand=True,
            spacing=10,
            auto_scroll=False
        )

        self.before_start_change_env_dialog_view = ft.AlertDialog(
            modal=True,
            title=ft.Text("切换环境"),
            content=ft.Container(content=ft.Column([
                ft.Text("请选择环境"),
                ft.RadioGroup(
                    content=ft.Column([
                        ft.Radio(value="RTA_TEST", label="RTA_TEST"),
                        ft.Radio(value="RTA_UAT", label="RTA_UAT"),
                        ft.Radio(value="RTA_PROD", label="RTA_PROD"),
                    ]),
                ),
            ])),
            actions=[
                ft.TextButton("Yes", on_click=lambda e: self.change_env(e, "RTA_TEST")),
                ft.TextButton("No", on_click=lambda e: e.control.close()),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
            on_dismiss=lambda e: print("Modal dialog dismissed!"),
        )
        for i in SearchConfig.read_search_result():
            self.results_view.controls.append(self.row_item(i))


    def search_result(self, e):
        keyword = (e.control.value or "").strip()
        self.results_view.controls.clear()
        for i in SearchConfig.read_search_result():
            if (not keyword) or (keyword.lower() in i.lower()):
                self.results_view.controls.append(self.row_item(i))
        try:
            self.page.update(self.results_view)
        except Exception as e:
            logger.error(f"更新搜索结果失败: {e}")

    def kill_pos_process(self):
        kill_process_name = ["CPOS-DF.exe", "Launcher.exe", "df_sv.exe", "Pos.exe", "CPOS-KH.exe", "ONENOTE.exe",
                             "ONENOTEM.exe"]
        try:
            for process_name in kill_process_name:
                # logger.info(f"结束{process_name}进程")
                kill_process_by_name(process_name)
            logger.info(f"POS进程已结束")
            UiUtil.show_snackbar_success(self.page, "POS进程已结束")
        except Exception as e:
            logger.error(f"结束进程失败: {e}")
            UiUtil.show_snackbar_error(self.page, f"结束进程失败: {e}")

    def validate_inputs(self, e):
        self.search_btn.disabled = not self.file_pattern.value
        self.page.update()

    def update_start_config(self, e):
        logger.info(f"更新启动配置")
        self.start_config.backup = self.before_start_back_view.value
        self.start_config.replace_mitm_cert = self.before_start_replace_mitm_cert_view.value
        self.start_config.change_env = self.before_start_change_env_view.value
        self.start_config.remove_cache = self.before_start_remove_cache_view.value
        self.start_config.cover_payment_driver = self.before_start_cover_payment_driver_view.value
        StartConfig.write(self.start_config)

    def open_directory_dialog(self, e):
        def on_dialog_result(e: ft.FilePickerResultEvent):
            # for i in e.files:
            #     logger.info(f"选择文件: {i.name} path :{i.path}")
            # logger.info(f"选择目录: {e.path}")
            if e.path:
                SearchConfig.add_work_dir(e.path)
                self.validate_inputs(None)

        directory_dialog = ft.FilePicker(on_result=on_dialog_result)

        self.page.overlay.append(directory_dialog)
        self.page.update()
        directory_dialog.get_directory_path()
        # directory_dialog.pick_files(allow_multiple=True)

    def start_search(self, e):
        work_dirs = SearchConfig.read_work_dir()
        if not work_dirs:
            logger.info("请先添加工作目录")
            return

        # 重置状态
        self.stop_event.clear()
        self.results_view.controls.clear()
        self.search_btn.disabled = True
        self.stop_btn.disabled = False
        self.progress_bar.visible = True
        self.progress_bar.value = 0
        self.page.update()

        # 启动搜索线程
        Thread(
            target=self.search_files,
            daemon=True
        ).start()

    def stop_search(self, e):
        self.stop_event.set()
        self.status_text.value = "正在停止搜索..."
        self.page.update()

    def open_pos_file(self,e:ft.ControlEvent, path):
        """打开文件"""
        logger.info(f"启动POS文件: {path}")
        logger.debug(f"启动前,检查CPOS-DF.exe进程是否存在，存在则杀死")
        kill_process_by_name("CPOS-DF.exe")
        UiUtil.show_snackbar_success(self.page, "启动前,检查CPOS-DF.exe进程是否存在，存在则杀死")

        if self.start_config.change_pos:
            logger.info(f"切换环境")
            if PosConfig.change_pos(path):
                UiUtil.show_snackbar_success(self.page, "切换POS成功")
            else:
                UiUtil.show_snackbar_error(self.page, "切换POS失败")
                return

        if self.start_config.replace_mitm_cert:
            logger.info(f"替换mitm证书")
            success, msg = PaymentMockConfig.replace_mitm_cert(path)
            if not success:
                UiUtil.show_snackbar_error(self.page, msg)
                return
            else:
                UiUtil.show_snackbar_success(self.page, msg)

        if self.start_config.backup:
            logger.info(f"备份支付驱动")
            try:
                PaymentMockConfig.backup_payment_driver(path)
            except Exception as e:
                UiUtil.show_snackbar_error(self.page, f"备份支付驱动失败: {e}")
                return

        if self.start_config.cover_payment_driver:
            logger.info(f"覆盖支付驱动")
            try:
                success, msg = PaymentMockConfig.cover_payment_driver(path)
                if not success:
                    UiUtil.show_snackbar_error(self.page, msg)
                    return
                else:
                    UiUtil.show_snackbar_success(self.page, msg)
            except Exception as e:
                logger.error(f"覆盖支付驱动失败: {e}")
                UiUtil.show_snackbar_error(self.page, f"覆盖支付驱动失败: {e}")
                return

        if self.start_config.remove_cache:
            logger.info(f"清理缓存")
            try:
                PaymentMockConfig.clean_cache(path)
            except Exception as e:
                UiUtil.show_snackbar_error(self.page, f"清理缓存失败: {e}")
                return

        UiUtil.show_snackbar_success(self.page, "正在启动POS。。。")
        if not file_handle.open_file(path):
            UiUtil.show_snackbar_error(self.page, f"打开文件:{path} 失败")
        else:
            UiUtil.show_snackbar_success(self.page, "启动POS成功")

    def open_pos_file_location(self, path):
        """打开文件所在目录"""
        if not file_handle.open_file_location(path):
            self.status_text.value = f"打开:{path} 所在目录失败"
            self.page.update()

    def change_env(self, path, env):
        logger.info(f"切换环境: {path}, {env}")
        success, msg = PaymentMockConfig.change_env(path, env)
        if success:
            UiUtil.show_snackbar_success(self.page, msg)
        else:
            UiUtil.show_snackbar_error(self.page, msg)
        self.page.update()

    def clean_cache(self, path):
        logger.info(f"清理缓存: {path}")
        success, msg = PaymentMockConfig.clean_cache(path)
        if success:
            UiUtil.show_snackbar_success(self.page, msg)
        else:
            UiUtil.show_snackbar_error(self.page, msg)
        self.page.update()

    def backup_payment_driver(self, path):
        logger.info(f"备份支付驱动: {path}")
        PaymentMockConfig.backup_payment_driver(path)
        self.page.update()

    def cover_payment_driver(self, path):
        logger.info(f"使用mock支付驱动: {path}")
        PaymentMockConfig.cover_payment_driver(path)
        self.page.update()

    def restore_payment_driver(self, path):
        logger.info(f"恢复支付驱动: {path}")
        PaymentMockConfig.restore_payment_driver(path)
        self.page.update()

    def get_pos_env(self, e: ft.ControlEvent, path):
        logger.info(f"获取POS环境: {path}")
        pos_env = PaymentMockConfig.get_pos_env(path)
        e.control.text = pos_env
        UiUtil.show_snackbar_success(self.page, "获取POS环境成功")
        # self.page.update()

    def change_pos_env(self, e: ft.ControlEvent, path):
        try:
            logger.info(f"切换POS环境: {path}")
            if PosConfig.change_pos(path):
                UiUtil.show_snackbar_success(self.page, "切换POS环境成功")
            else:
                UiUtil.show_snackbar_error(self.page, "切换POS环境失败")
        except Exception as e:
            logger.error(f"切换POS环境失败: {e}")
            UiUtil.show_snackbar_error(self.page, f"切换POS环境失败: {e}")
        # self.page.update()

    def clear_pos_env_file(self, e: ft.ControlEvent, path):
        logger.info(f"清理POS环境文件: {path}")
        PaymentMockConfig.clear_env(path)
        e.page.open(ft.SnackBar(
            content=ft.Text("清理成功"),
            action="知道了",
        ))
        self.page.update()


    def row_item(self, pos_path):
        result_item = ft.Container(
            border_radius=15,
            # opacity=0.5,
            # on_hover=lambda e: e.control.bgcolor=ft.Colors.WHITE70,
            # on_unhover=lambda _: result_item.opacity(0.5),
            padding=0,
            bgcolor=ft.Colors.WHITE,
            content=ft.Row(
                controls=[
                    ft.Text(pos_path, expand=True),
                    ft.ElevatedButton(
                        text="切换POS",
                        tooltip="调用接口切换对应环境的POS未当前POS",
                        on_click=lambda e, path=pos_path: self.change_pos_env(e, path),
                    ),
                    ft.ElevatedButton(
                        text="点击查看环境",
                        tooltip="查看POS当前环境",
                        on_click=lambda e, path=pos_path: self.get_pos_env(e, path),
                    ),
                    ft.IconButton(
                        icon=ft.Icons.FOLDER_OPEN,
                        tooltip="打开所在目录",
                        on_click=lambda e, path=pos_path: self.open_pos_file_location(path),
                    ),
                    ft.IconButton(
                        icon=ft.Icons.PLAY_CIRCLE,
                        tooltip="启动POS",
                        on_click=lambda e, path=pos_path: self.open_pos_file(e, path),
                    ),
                    ft.PopupMenuButton(
                        icon=ft.Icons.MORE_VERT,
                        tooltip="更多操作",
                        items=[
                            ft.PopupMenuItem(text="切换环境",
                                             content=ft.PopupMenuButton(
                                                 tooltip="切换本地环境，修改pos.ini、切换database、logs、缓存等",
                                                 padding=0,
                                                 content=ft.Row([ft.Text("切换本地环境")]),
                                                 items=[
                                                     ft.PopupMenuItem(text="RTA_TEST", on_click=lambda e,
                                                                                                       path=pos_path: self.change_env(
                                                         path, "RTA_TEST")),
                                                     ft.PopupMenuItem(text="RTA_UAT", on_click=lambda e,
                                                                                                      path=pos_path: self.change_env(
                                                         path, "RTA_UAT")),
                                                     ft.PopupMenuItem(text="RTA", on_click=lambda e,
                                                                                                  path=pos_path: self.change_env(
                                                         path, "RTA")),
                                                 ]
                                             )
                                             ),
                            ft.PopupMenuItem(text="备份支付驱动",
                                             on_click=lambda e, path=pos_path: self.backup_payment_driver(path)),
                            ft.PopupMenuItem(text="恢复支付驱动",
                                             on_click=lambda e, path=pos_path: self.restore_payment_driver(path)),
                            ft.PopupMenuItem(text="使用支付mock驱动",
                                             on_click=lambda e, path=pos_path: self.cover_payment_driver(path)),
                            ft.PopupMenuItem(text="清理缓存",
                                             on_click=lambda e, path=pos_path: self.clean_cache(path)),
                            ft.PopupMenuItem(text="清理当前环境文件",
                                             on_click=lambda e, path=pos_path: self.clear_pos_env_file(e, path)),
                        ]
                    )

                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                spacing=1,
                # auto_scroll=True,
            )
        )
        return result_item

    def __find_files(self, directories: list[str], file_pattern=None, dir_pattern=None, max_depth=None):
        """在多个目录中递归查找文件，可指定匹配规则和递归深度"""
        logger.info(f"开始搜索: {directories}, 模式: {file_pattern}, 目录模式: {dir_pattern}, 递归深度: {max_depth}")

        data = {"dir": directories, "file_pattern": file_pattern, "dir_pattern": dir_pattern,
                "max_depth": str(max_depth)}
        SearchConfig.write(data)
        result = []
        found_files = 0
        total_files = 0
        depth = 0

        def scan_dir(path, depth, found_files, total_files):
            if max_depth is not None and depth >= max_depth:
                return
            try:
                with os.scandir(path) as it:
                    depth += 1
                    for entry in it:
                        logger.debug(f"当前目录: {path}, 深度: {depth}, 文件名: {entry.name}")
                        if self.stop_event.is_set():
                            break
                        total_files += 1

                        if entry.is_file():
                            if file_pattern is None or fnmatch.fnmatch(entry.name.lower(),
                                                                       file_pattern.lower()):  # 可换成正则匹配
                                result.append(entry.path)
                                # 创建结果项
                                found_files += 1

                                self.results_view.controls.append(self.row_item(entry.path))


                        elif entry.is_dir() and (
                                dir_pattern is None or fnmatch.fnmatch(entry.name.lower(), dir_pattern.lower())):
                            scan_dir(entry.path, depth, found_files, total_files)

                        # progress = found_files / total_files
                        self.update_ui(
                            f"已扫描 {entry.path} 个",
                            True,
                            0.5
                        )
            except PermissionError as e:
                self.update_ui(f"权限错误: {path}", True)

        for d in directories:
            scan_dir(d, depth=depth, found_files=found_files, total_files=total_files)

        return result

    def search_files(self):
        directory = SearchConfig.read_work_dir()
        pattern = self.file_pattern.value
        max_depth = 1
        try:

            max_depth = int(self.scan_deep.value)
            if max_depth < 1:
                max_depth = 1
        except Exception as e:
            pass

        depth = 0
        # 预计算文件总数
        # total_files = 0
        # for root, dirs, files in os.walk(directory):
        #     if self.stop_event.is_set():
        #         break
        #     total_files += len(files)
        #
        # if total_files == 0:
        #     self.update_ui("未找到可搜索的文件", False)
        #     return

        # 开始搜索
        found_files = 0
        processed = 0
        depth = 0

        result = self.__find_files(directory, file_pattern=pattern, dir_pattern=self.dir_pattern.value,
                                   max_depth=max_depth)
        SearchConfig.save_search_result(result)
        found_files = len(result)

        # for root, dirs, files in os.walk(directory):
        #     if self.stop_event.is_set():
        #         break
        #
        #     for filename in files:
        #         if fnmatch.fnmatch(filename.lower(), pattern.lower()):
        #             full_path = os.path.join(root, filename)
        #
        #             # 创建结果项
        #             result_item = ft.Row(
        #                 controls=[
        #                     ft.Text(full_path, expand=True),
        #                     ft.IconButton(
        #                         icon=ft.Icons.FOLDER_OPEN,
        #                         tooltip="打开所在目录",
        #                         on_click=lambda e, path=full_path: self.open_file_location(path)
        #                     ),
        #                     ft.IconButton(
        #                         icon=ft.Icons.INSERT_DRIVE_FILE,
        #                         tooltip="打开文件",
        #                         on_click=lambda e, path=full_path: self.open_file(path)
        #                     )
        #                 ],
        #                 alignment=ft.MainAxisAlignment.SPACE_BETWEEN
        #             )
        #
        #             self.results_view.controls.append(result_item)
        #             found_files += 1
        #
        #         processed += 1
        #         progress = processed / total_files
        #         self.update_ui(
        #             f"已扫描 {processed}/{total_files} | 找到 {found_files} 个",
        #             True,
        #             progress
        #         )

        # 搜索完成
        msg = "搜索已停止" if self.stop_event.is_set() else f"完成! 共找到 {found_files} 个文件"
        self.update_ui(msg, False)

    def update_ui(self, message, searching, progress=0):
        self.status_text.value = message
        self.progress_bar.value = progress
        self.search_btn.disabled = searching
        self.stop_btn.disabled = not searching
        self.page.update()
