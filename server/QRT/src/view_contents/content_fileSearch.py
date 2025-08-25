import os
import fnmatch
import flet as ft
import subprocess
import platform
from threading import Thread, Event


class FileSearcher:
    def __init__(self, ft, page: ft.Page):
        self.ft = ft
        self.page = page
        self.set_width = 400
        self.stop_event = Event()
        self.setup_ui()

    def fileSearcher(self):
        content = self.ft.Container(
            content=self.ft.Column([
                self.ft.Text("文件搜索>", size=20),
                self.ft.Divider(),
                self.ft.Row([
                    # 搜索参数输入区
                    self.dir_picker,
                    self.browse_btn
                ]),
                self.file_pattern,
                self.scan_deep,
                self.ft.Row([
                    # 控制按钮
                    self.search_btn,
                    self.stop_btn
                ]),
                # 进度显示
                self.progress_bar,
                self.status_text,
                self.ft.Divider(),
                # 结果展示
                self.results_view
            ], alignment=self.ft.MainAxisAlignment.START),
            alignment=self.ft.alignment.center_left
        )
        return content

    def setup_ui(self):
        self.page.vertical_alignment = ft.MainAxisAlignment.CENTER
        self.page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
        self.page.padding = 30

        # 搜索参数输入区
        self.dir_picker = ft.TextField(
            label="搜索目录",
            hint_text="输入或选择目录路径",
            width=self.set_width,
            on_change=self.validate_inputs
        )

        self.browse_btn = ft.ElevatedButton(
            "浏览",
            on_click=self.open_directory_dialog
        )

        self.file_pattern = ft.TextField(
            label="文件名模式",
            hint_text="例如: *.txt 或 report*.docx",
            width=self.set_width,
            on_change=self.validate_inputs
        )

        self.scan_deep = ft.TextField(
            label="递归深度",
            hint_text="1",
            width=self.set_width,
            # on_change=self.validate_inputs
        )

        # 控制按钮
        self.search_btn = ft.ElevatedButton(
            "开始搜索",
            on_click=self.start_search,
            disabled=True
        )
        self.stop_btn = ft.ElevatedButton(
            "停止",
            on_click=self.stop_search,
            disabled=True,
            # color="red"
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
            spacing=10
        )

        # # 布局组合
        # self.page.add(
        #     ft.Column([
        #         ft.Row([self.dir_picker, self.browse_btn]),
        #         self.file_pattern,
        #         ft.Row([self.search_btn, self.stop_btn]),
        #         self.progress_bar,
        #         self.status_text,
        #         ft.Divider(),
        #         ft.Text("搜索结果:", weight=ft.FontWeight.BOLD),
        #         ft.Container(
        #             self.results_view,
        #             height=300,
        #             border=ft.border.all(1),
        #             padding=10,
        #             border_radius=5
        #         )
        #     ])
        # )

    def validate_inputs(self, e):
        self.search_btn.disabled = not (self.dir_picker.value and self.file_pattern.value)
        self.page.update()

    def open_directory_dialog(self, e):
        def on_dialog_result(e: ft.FilePickerResultEvent):
            if e.path:
                self.dir_picker.value = e.path
                self.validate_inputs(None)

        directory_dialog = ft.FilePicker(on_result=on_dialog_result)
        self.page.overlay.append(directory_dialog)
        self.page.update()
        directory_dialog.get_directory_path()
        # directory_dialog.pick_files(allow_multiple=True)

    def start_search(self, e):
        if not self.dir_picker.value:
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

    def open_file(self, path):
        """打开文件"""
        try:
            if platform.system() == "Windows":
                os.startfile(path)
            elif platform.system() == "Darwin":
                subprocess.run(["open", path])
            else:  # Linux
                subprocess.run(["xdg-open", path])
        except Exception as e:
            self.status_text.value = f"打开文件失败: {str(e)}"
            self.page.update()

    def open_file_location(self, path):
        """打开文件所在目录"""
        try:
            dir_path = os.path.dirname(path)
            if platform.system() == "Windows":
                os.startfile(dir_path)
            elif platform.system() == "Darwin":
                subprocess.run(["open", dir_path])
            else:  # Linux
                subprocess.run(["xdg-open", dir_path])
        except Exception as e:
            self.status_text.value = f"打开目录失败: {str(e)}"
            self.page.update()

    def __find_files(self, directories: list[str], file_pattern=None, dir_pattern=None, max_depth=None):
        """在多个目录中递归查找文件，可指定匹配规则和递归深度"""
        result = []
        found_files = 0
        total_files = 0

        def scan_dir(path, depth, found_files, total_files):
            if max_depth is not None and depth > max_depth:
                return
            with os.scandir(path) as it:
                for entry in it:
                    if self.stop_event.is_set():
                        break
                    total_files += 1
                    if entry.is_file():
                        if file_pattern is None or fnmatch.fnmatch(entry.name.lower(), file_pattern.lower()):  # 可换成正则匹配
                            result.append(entry.path)
                            # 创建结果项
                            result_item = ft.Row(
                                controls=[
                                    ft.Text(entry.path, expand=True),
                                    ft.IconButton(
                                        icon=ft.Icons.FOLDER_OPEN,
                                        tooltip="打开所在目录",
                                        on_click=lambda e, path=entry.path: self.open_file_location(path)
                                    ),
                                    ft.IconButton(
                                        icon=ft.Icons.INSERT_DRIVE_FILE,
                                        tooltip="打开文件",
                                        on_click=lambda e, path=entry.path: self.open_file(path)
                                    )
                                ],
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                            )
                            found_files += 1

                            self.results_view.controls.append(result_item)


                    elif entry.is_dir() and (dir_pattern is None or fnmatch.fnmatch(entry.name.lower(), dir_pattern.lower())):
                        scan_dir(entry.path, depth + 1, found_files, total_files)

                    # progress = found_files / total_files
                    # self.update_ui(
                    #     f"已扫描 {found_files}/{total_files} 个",
                    #     True,
                    #     progress
                    # )

        for d in directories:
            scan_dir(d, depth=0, found_files=found_files, total_files=total_files)

        return result

    def search_files(self):
        directory = self.dir_picker.value
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
        total_files = 0
        for root, dirs, files in os.walk(directory):
            if self.stop_event.is_set():
                break
            total_files += len(files)

        if total_files == 0:
            self.update_ui("未找到可搜索的文件", False)
            return

        # 开始搜索
        found_files = 0
        processed = 0
        depth = 0

        self.__find_files([directory], file_pattern=pattern, max_depth=max_depth)

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
