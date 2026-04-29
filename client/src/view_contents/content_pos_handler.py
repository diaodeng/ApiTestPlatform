import asyncio
import fnmatch
import os
from threading import Event, Thread

import flet as ft
from loguru import logger

from common import appState
from common.excptions import PosParamsException
from common.ui_utils.ui_util import ChangeLocalPosUi, ChangePosUi, PosAccountManagerUi, PosSettingUi, UiUtil
from model.config import PosParamsModel, ResolutionModel
from server.config import PosConfig, SearchConfig, StartConfig
from server.pos_config_server import PosConfigServer
from server.pos_tool_config_server import PosToolConfigServer
from utils import file_handle
from utils.common import ExeVersionReader, get_all_process, kill_process_by_id, kill_process_by_name
from view_contents.dialog.registerDialog import FeatureDialog


class PosHandler:
    def __init__(self, ft, page: ft.Page):
        self.start_config = StartConfig.read()
        self.ft = ft
        self.page = page
        self.set_width = 400
        self.all_p = []
        self.stop_event = Event()
        self.setup_ui()

    def _ensure_directory_picker(self):
        if getattr(self, "directory_picker", None) is None:
            self.directory_picker = ft.FilePicker(on_result=self._handle_directory_selected)
            self.page.overlay.append(self.directory_picker)
            self.page.update()

    def _handle_directory_selected(self, e: ft.FilePickerResultEvent):
        if not e.path:
            return
        work_dirs = SearchConfig.read_work_dir()
        if e.path in work_dirs:
            UiUtil.show_snackbar_error(self.page, "工作目录已存在")
            return
        SearchConfig.add_work_dir(e.path)
        self._render_work_dir_list()
        self.validate_inputs(None)
        UiUtil.show_snackbar_success(self.page, "工作目录添加成功")

    def _load_search_settings_to_fields(self):
        search_config = SearchConfig.read()
        self.file_pattern.value = search_config.file_pattern
        self.dir_pattern.value = search_config.dir_pattern
        self.scan_deep.value = search_config.max_depth
        for control in (self.file_pattern, self.dir_pattern, self.scan_deep):
            try:
                control.update()
            except Exception:
                pass

    def _render_work_dir_list(self):
        self.work_dir_list_view.controls.clear()
        work_dirs = SearchConfig.read_work_dir()
        if not work_dirs:
            self.work_dir_list_view.controls.append(
                ft.Container(
                    padding=12,
                    border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
                    border_radius=12,
                    content=ft.Text("暂无工作目录，请先添加。", color=ft.Colors.BLUE_GREY_500),
                )
            )
        else:
            for item in work_dirs:
                self.work_dir_list_view.controls.append(
                    ft.Container(
                        padding=10,
                        border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
                        border_radius=12,
                        content=ft.Row(
                            [
                                ft.Text(item, expand=True, selectable=True),
                                ft.TextButton("删除", on_click=lambda e, pos_path=item: self.remove_work_dir(e, pos_path)),
                            ]
                        ),
                    )
                )
        if self.search_settings_dialog is not None:
            try:
                self.work_dir_list_view.update()
            except Exception:
                pass

    def _ensure_search_settings_dialog(self):
        if self.search_settings_dialog is not None:
            return
        self.search_settings_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("索引设置"),
            content=ft.Container(
                width=960,
                height=460,
                content=ft.Row(
                    [
                        ft.Container(
                            expand=2,
                            padding=12,
                            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
                            border_radius=12,
                            content=ft.Column(
                                [
                                    ft.Row(
                                        [
                                            ft.Text("工作目录", weight=ft.FontWeight.W_600),
                                            ft.ElevatedButton("添加工作目录", on_click=self.open_directory_dialog),
                                        ],
                                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    ),
                                    ft.Text("索引时会递归搜索这些目录。", size=12, color=ft.Colors.BLUE_GREY_500),
                                    self.work_dir_list_view,
                                ],
                                spacing=10,
                                expand=True,
                            ),
                        ),
                        ft.Container(
                            width=320,
                            padding=12,
                            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
                            border_radius=12,
                            content=ft.Column(
                                [
                                    ft.Text("扫描规则", weight=ft.FontWeight.W_600),
                                    self.file_pattern,
                                    self.dir_pattern,
                                    self.scan_deep,
                                    ft.Row(
                                        [
                                            ft.OutlinedButton("重新载入", on_click=lambda e: self._load_search_settings_to_fields()),
                                            ft.ElevatedButton("保存", on_click=self.save_search_settings),
                                        ],
                                        alignment=ft.MainAxisAlignment.END,
                                    ),
                                ],
                                spacing=12,
                            ),
                        ),
                    ],
                    spacing=16,
                    vertical_alignment=ft.CrossAxisAlignment.START,
                ),
            ),
            actions=[ft.TextButton("关闭", on_click=lambda e: self.page.close(self.search_settings_dialog))],
            actions_alignment=ft.MainAxisAlignment.END,
        )

    def open_search_settings_dialog(self, _e):
        self._ensure_search_settings_dialog()
        self._load_search_settings_to_fields()
        self._render_work_dir_list()
        self.page.open(self.search_settings_dialog)

    def save_search_settings(self, _e: ft.ControlEvent):
        file_pattern = (self.file_pattern.value or "").strip()
        if not file_pattern:
            UiUtil.show_snackbar_error(self.page, "文件名模式不能为空")
            return
        dir_pattern = (self.dir_pattern.value or "*").strip() or "*"
        depth_value = (self.scan_deep.value or "1").strip()
        try:
            depth = max(int(depth_value), 1)
        except ValueError:
            UiUtil.show_snackbar_error(self.page, "递归深度必须是正整数")
            return

        SearchConfig.write(
            {
                "dir": SearchConfig.read_work_dir(),
                "file_pattern": file_pattern,
                "dir_pattern": dir_pattern,
                "max_depth": str(depth),
            }
        )
        self.scan_deep.value = str(depth)
        self.validate_inputs(None)
        self.page.close(self.search_settings_dialog)
        UiUtil.show_snackbar_success(self.page, "索引设置保存成功")

    def open_process_list_dialog(self, e):
        self.all_p = get_all_process()
        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("运行中的进程"),
            content=ft.Container(
                content=ft.Column(
                    [
                        ft.Row(
                            [
                                ft.TextField(data="filter_key"),
                                ft.ElevatedButton("查询", on_click=self.filter_process),
                                ft.ElevatedButton("更新", on_click=self.update_all_process),
                            ]
                        ),
                        ft.ListView(
                            [
                                ft.Row(
                                    [
                                        ft.Text(f"{item['name']}:{item['exe']}", expand=True),
                                        ft.Text(
                                            "子进程",
                                            color=ft.Colors.GREEN_100,
                                            visible=item.get("is_current_child", False),
                                        ),
                                        ft.ElevatedButton("停止", on_click=self.kill_p_by_id, data=item["pid"]),
                                    ],
                                    expand=True,
                                )
                                for item in self.all_p
                            ],
                            expand=True,
                            data="filter_result",
                        ),
                    ]
                ),
                expand=True,
                width=1000,
            ),
            actions=[
                ft.TextButton("取消", on_click=lambda e: e.page.close(dialog)),
                # ft.TextButton("添加", on_click=lambda e: dialog.dismiss()),
            ],
            alignment=ft.alignment.center,
        )
        dialog.open = True
        self.page.open(dialog)
        self.page.update()

    def filter_process(self, e: ft.ControlEvent):
        filter_data = ""
        for i in e.control.parent.controls:
            if i.data == "filter_key":
                filter_data = i.value
        filter_data = filter_data.lower()
        for item_view in e.control.parent.parent.controls:
            if item_view.data == "filter_result":
                item_view.controls.clear()
                item_view.update()
                for item in self.all_p:
                    if filter_data in item["name"].lower():
                        item_view.controls.append(
                            ft.Row(
                                [
                                    ft.Text(f"{item['name']}:{item['exe']}", expand=True),
                                    ft.Text(
                                        "子进程", color=ft.Colors.GREEN_100, visible=item.get("is_current_child", False)
                                    ),
                                    ft.ElevatedButton("停止", on_click=self.kill_p_by_id, data=item["pid"]),
                                ],
                                expand=True,
                            )
                        )
                        item_view.update()

    def update_all_process(self, e: ft.ControlEvent):
        self.all_p = get_all_process()

    def kill_p_by_id(self, e):
        k_id = e.control.data
        if k_id:
            kill_process_by_id(e.control.data)

        UiUtil.show_snackbar_success(self.page, "进程已停止")

    def remove_work_dir(self, e: ft.ControlEvent | None, item):
        work_dirs = SearchConfig.read_work_dir()
        if item not in work_dirs:
            return
        SearchConfig.remove_work_dir(item)
        self._render_work_dir_list()
        self.validate_inputs(None)
        if e is not None:
            UiUtil.show_snackbar_success(self.page, "工作目录已删除")

    def init_ui(self):

        content = self.ft.Container(
            content=self.ft.Column(
                controls = [
                    self.ft.Text("POS快捷功能>", size=20),
                    self.ft.Divider(),
                    ft.Row(
                        spacing=10,
                        run_spacing=10,
                        wrap=True,
                        controls=[
                            ft.ElevatedButton(
                                "索引设置",
                                tooltip="配置工作目录和扫描规则",
                                on_click=self.open_search_settings_dialog,
                            ),
                            self.search_btn,
                            self.stop_btn,
                            self.kill_pos_btn,
                            self.restart_offline_btn,
                            self.kill_offline_btn,
                            ft.Button("结束进程", tooltip="查看并结束进程", on_click=self.open_process_list_dialog),
                            ft.ElevatedButton(
                                "设置", tooltip="POS工具相关设置", on_click=lambda e: self.page.open(PosSettingUi())
                            ),
                            ft.ElevatedButton(
                                "切换POS", tooltip="调用接口切换POS", on_click=self.change_env_from_network
                            ),
                            ft.ElevatedButton(
                                "POS账号处理",
                                tooltip="调用接口踢出POS账号或重置密码",
                                on_click=lambda e: self.page.open(PosAccountManagerUi()),
                            ),
                        ],
                    ),
                    self.ft.Row(
                        [
                            ft.Text("启动POS前："),
                            self.before_start_back_view,
                            self.before_start_cover_payment_driver_view,
                            self.before_start_replace_mitm_cert_view,
                            self.before_start_change_pos_view,
                            self.before_start_logout_view,
                            self.before_start_remove_cache_view,
                            self.search_keyword_field,
                        ],
                        alignment=ft.MainAxisAlignment.START,
                    ),
                    self.status_text,
                    self.ft.Divider(),
                    self.results_view,
                ],
                alignment=self.ft.MainAxisAlignment.START,
                expand=True,
            ),
            alignment=self.ft.alignment.center_left,
            expand=True,
        )
        return content

    def setup_ui(self):
        search_config = SearchConfig.read()
        self.page.vertical_alignment = ft.MainAxisAlignment.START
        self.page.horizontal_alignment = ft.CrossAxisAlignment.STRETCH
        self.page.padding = 30

        self.directory_picker = None
        self.search_settings_dialog = None
        self.search_results_cache = []
        self.work_dir_list_view = ft.ListView(expand=True, spacing=10, auto_scroll=False)
        self.search_keyword_field = ft.TextField(label="查找结果", width=260, on_change=self.search_result)

        self.file_pattern = ft.TextField(
            label="文件名模式",
            tooltip="匹配指定规则的文件名",
            hint_text="例如: *.txt 或 report*.docx",
            width=280,
            value=search_config.file_pattern,
        )

        self.dir_pattern = ft.TextField(
            label="目录名模式",
            tooltip="只索引指定规则的目录名",
            hint_text="例如: * 或 report*.docx",
            width=280,
            value=search_config.dir_pattern,
        )

        self.scan_deep = ft.TextField(
            label="递归深度",
            hint_text="1",
            value=search_config.max_depth,
            width=120,
        )

        self.search_btn = ft.ElevatedButton(
            "开始索引",
            tooltip="按规则索引工作目录中的文件",
            on_click=self.start_search,
            disabled=not SearchConfig.read_work_dir() or not (search_config.file_pattern or "").strip(),
        )
        self.stop_btn = ft.ElevatedButton(
            "停止",
            tooltip="停止索引",
            on_click=self.stop_search,
            disabled=True,
        )

        self.kill_pos_btn = ft.ElevatedButton(
            "结束POS",
            on_click=lambda e: self.kill_pos_process(),
            color="red",
        )

        self.restart_offline_btn = ft.ElevatedButton(
            "重启POS",
            tooltip=appState.client_info.current_pos,
            on_click=self.restart_pos,
            color="red",
        )

        self.kill_offline_btn = ft.ElevatedButton(
            "结束离线",
            on_click=lambda e: self.kill_offline_process(),
            color="red",
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
            label="切换本地环境",
            tooltip="切换本地环境",
            value=self.start_config.change_env,
            on_change=self.update_start_config,
        )

        self.before_start_logout_view = ft.Checkbox(
            label="注销账号",
            tooltip="调用kickOut接口注销账号",
            value=self.start_config.account_logout,
            on_change=self.update_start_config,
        )

        self.before_start_remove_cache_view = ft.Checkbox(
            label="清除缓存",
            tooltip="清除POS缓存文件",
            value=self.start_config.remove_cache,
            on_change=self.update_start_config,
        )

        self.progress_bar = ft.ProgressBar(width=self.set_width, value=0, visible=False)
        self.status_text = ft.Text()
        self.results_view = ft.ListView(expand=True, spacing=10, auto_scroll=False)

        self.before_start_change_env_dialog_view = ft.AlertDialog(
            modal=True,
            title=ft.Text("切换环境"),
            content=ft.Container(
                content=ft.Column(
                    [
                        ft.Text("请选择环境"),
                        ft.RadioGroup(
                            content=ft.Column(
                                [
                                    ft.Radio(value="RTA_TEST", label="RTA_TEST"),
                                    ft.Radio(value="RTA_UAT", label="RTA_UAT"),
                                    ft.Radio(value="RTA_PROD", label="RTA_PROD"),
                                ]
                            ),
                        ),
                    ]
                )
            ),
            actions=[
                ft.TextButton("Yes", on_click=self.change_env),
                ft.TextButton("No", on_click=lambda e: e.control.close()),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
            on_dismiss=lambda e: print("Modal dialog dismissed!"),
        )
        self._set_search_results(SearchConfig.read_search_result())
        self.validate_inputs(None)

    def search_result(self, e):
        keyword = (e.control.value or "").strip()
        self.results_view.controls.clear()
        for i in self.search_results_cache:
            if (not keyword) or (keyword.lower() in i.lower()):
                self.results_view.controls.append(self.row_item(i))
        try:
            self.page.update(self.results_view)
        except Exception as e:
            logger.error(f"更新搜索结果失败: {e}")

    async def restart_pos(self, e: ft.ControlEvent):
        self.kill_pos_process()
        await self.open_pos_file(appState.client_info.current_pos)

    def kill_pos_process(self):
        kill_process_name = [
            "CPOS-DF.exe",
            "Launcher.exe",
            "df_sv.exe",
            "Pos.exe",
            "CPOS-KH.exe",
            "ONENOTE.exe",
            "ONENOTEM.exe",
        ]
        try:
            for process_name in kill_process_name:
                # logger.info(f"结束{process_name}进程")
                kill_process_by_name(process_name)
            logger.info("POS进程已结束")
            UiUtil.show_snackbar_success(self.page, "POS进程已结束")
            appState.client_info.current_pos = ""
        except Exception as e:
            logger.error(f"POS结束进程失败: {e}")
            UiUtil.show_snackbar_error(self.page, f"POS结束进程失败: {e}")

    def kill_offline_process(self):
        kill_process_name = ["java.exe"]
        try:
            for process_name in kill_process_name:
                # logger.info(f"结束{process_name}进程")
                kill_process_by_name(process_name)
            logger.info("离线（java.exe）进程已结束")
            UiUtil.show_snackbar_success(self.page, "离线（java.exe）进程已结束")
        except Exception as e:
            logger.error(f"离线（java.exe）结束进程失败: {e}")
            UiUtil.show_snackbar_error(self.page, f"离线（java.exe）结束进程失败: {e}")

    def validate_inputs(self, _e):
        search_config = SearchConfig.read()
        self.search_btn.disabled = not SearchConfig.read_work_dir() or not (search_config.file_pattern or "").strip()
        try:
            self.search_btn.update()
        except Exception:
            pass

    def _set_search_results(self, results: list[str], keyword: str = ""):
        self.search_results_cache = list(results)
        filtered_results = self.search_results_cache
        if keyword:
            keyword = keyword.lower()
            filtered_results = [item for item in self.search_results_cache if keyword in item.lower()]
        self.results_view.controls.clear()
        self.results_view.controls.extend(self.row_item(item) for item in filtered_results)

    def update_start_config(self, e):
        logger.info("更新启动配置")
        self.start_config.backup = self.before_start_back_view.value
        self.start_config.replace_mitm_cert = self.before_start_replace_mitm_cert_view.value
        self.start_config.change_env = self.before_start_change_env_view.value
        self.start_config.change_pos = self.before_start_change_pos_view.value
        self.start_config.account_logout = self.before_start_logout_view.value
        self.start_config.remove_cache = self.before_start_remove_cache_view.value
        self.start_config.cover_payment_driver = self.before_start_cover_payment_driver_view.value
        StartConfig.write(self.start_config)

    def open_directory_dialog(self, _e):
        self._ensure_directory_picker()
        self.directory_picker.get_directory_path()

    def start_search(self, e):
        try:
            search_config = SearchConfig.read()
            work_dirs = SearchConfig.read_work_dir()
            if not work_dirs:
                UiUtil.show_snackbar_error(self.page, "请先在索引设置中添加工作目录")
                return
            if not (search_config.file_pattern or "").strip():
                UiUtil.show_snackbar_error(self.page, "请先在索引设置中配置文件名模式")
                return

            self.stop_event.clear()
            self._set_search_results([])
            self.search_btn.disabled = True
            self.stop_btn.disabled = False
            self.progress_bar.visible = True
            self.progress_bar.value = 0
            self.page.update()

            Thread(target=self.search_files, daemon=True).start()
        except Exception as e:
            logger.exception(e)
            UiUtil.show_snackbar_error(self.page, f"搜索异常：{e}")

    def stop_search(self, e):
        self.stop_event.set()
        self.status_text.value = "正在停止搜索..."
        self.page.update()

    async def logout_pos_account_for_view(self, evt: ft.ControlEvent):
        path = evt.control.data
        try:
            await PosConfigServer.logout_pos_account(path)
            UiUtil.show_snackbar_success(self.page, "账号登出成功")
        except Exception as e:
            UiUtil.show_snackbar_error(self.page, f"账号登出失败：{e}")

    async def __confirm_dialog(self, title, content_data):
        return await FeatureDialog(
            page=self.page, tile=title, content=content_data, actions=[("取消", False), ("确定", True)]
        ).show()

    async def __choice_start_type_dialog(self, title, content_data):
        return await FeatureDialog(
            page=self.page, tile=title, content=content_data, actions=[("取消", 0), ("确定", 1), ("切换后启动", 2)]
        ).show()

    def _get_group(self, pos_file: str):
        """
        根据本地POS配置获取分组信息
        测试和pro不用判断
        UAT有多个分组，需要判断从哪个分组读取信息
        """
        env_info = PosConfig.get_local_pos_env(pos_file=pos_file)
        local_pos_params = PosConfig.read_pos_params(pos_file, 1)
        if env_info and "uat" in env_info.lower():
            if not local_pos_params:
                return None
                # raise Error("本地是UAT环境，但是没有本地配置信息（pos_params），无法判断分组，直接启动？")
            group, account = PosConfig.get_pos_group(local_pos_params.venderNo, env=env_info)
            return group

    async def open_pos_file(self, e: ft.ControlEvent | str):
        """打开文件"""
        cancel = False
        try:
            if isinstance(e, str):
                path = e
            else:
                path = e.control.data

            if not os.path.exists(path):
                logger.warning(f"没有POS文件：{path}")
                UiUtil.show_snackbar_error(self.page, "POS文件不存在：{path}，无法启动！！！")
                return

            logger.info(f"启动POS文件: {path}")
            logger.debug("启动前,检查CPOS-DF.exe进程是否存在，存在则杀死")
            kill_process_by_name("CPOS-DF.exe")
            UiUtil.show_snackbar_success(self.page, "启动前,检查CPOS-DF.exe进程是否存在，存在则杀死")
            await asyncio.sleep(2)

            appState.client_info.current_pos = path

            local_env_info = PosConfig.get_local_pos_env(pos_file=path)
            if local_env_info is None:
                UiUtil.show_snackbar_error(self.page, "没有获取到本地环境信息，无法启动！！！")
                return
            pos_file_version = ExeVersionReader(path).get_exe_file_version()
            is_uat = local_env_info and ("rta_uat" in local_env_info.lower() or "kh_test_s" in local_env_info.lower())

            local_pos_params = PosConfig.read_pos_params(path, 1)
            has_local = local_pos_params and isinstance(local_pos_params, PosParamsModel)
            has_group = None
            if has_local:
                group, account = PosConfig.get_pos_group(local_pos_params.venderNo, env=local_env_info)
                has_group = False if group is None else True

            remote_pos_params = PosConfig.read_pos_params(path, 2)
            remote_info = PosConfig.remote_pos_info(remote_pos_params)
            has_remote = remote_pos_params and isinstance(remote_pos_params, PosParamsModel)

            custum_headers = ""

            can_not_auto_change_text = ""
            if self.start_config.change_pos:
                can_not_auto_change_text = "无法自动切换POS,"

            if is_uat:
                if not has_local:
                    ok = await self.__confirm_dialog(
                        "POS启动提示",
                        f"本地是UAT环境，但是没有POS配置文件（pos_params），无法知道服务端机台信息，{can_not_auto_change_text}继续启动？",
                    )
                    logger.info(
                        f"本地是UAT环境，但是没有POS配置文件（pos_params），无法知道服务端机台信息，{can_not_auto_change_text}是否继续启动：{'是' if ok else '否'}"
                    )
                    if not ok:
                        return
                # elif not has_group or not pos_file_version:
                #     ok = await self.__confirm_dialog(
                #         "POS启动提示",
                #         "本地是UAT环境，但是没有获取到版本信息，无法知道服务端机台信息，继续启动？",
                #     )
                #     logger.info(
                #         f"本地是UAT环境，但是没有获取到版本信息，无法知道服务端机台信息，是否继续启动：{'是' if ok else '否'}"
                #     )
                #     if not ok:
                #         return
                elif not has_remote and not self.start_config.change_pos:
                    ok = await self.__confirm_dialog(
                        "POS启动提示",
                        f"本地是UAT环境，获取服务端POS信息失败，继续启动？{remote_info}",
                    )
                    logger.info(
                        f"本地是UAT环境，获取服务端POS信息失败，继续启动？：{'是' if ok else '否'} {remote_info}"
                    )
                    if not ok:
                        return

            else:
                if not has_local and not has_remote:
                    ok = await self.__confirm_dialog(
                        "POS启动提示",
                        f"本地没有POS配置文件（pos_params），{can_not_auto_change_text}且服务端没有当前机台信息，继续启动？{remote_pos_params}",
                    )
                    logger.info(
                        f"本地没有POS配置文件（pos_params），{can_not_auto_change_text}且服务端没有当前机台信息，是否继续启动：{'是' if ok else '否'}"
                    )
                    if not ok:
                        return

                elif not has_remote and not self.start_config.change_pos:
                    ok = await self.__confirm_dialog(
                        "POS启动提示", f"服务端没有当前机台信息，继续启动？{remote_pos_params}"
                    )
                    logger.info(f"服务端没有当前机台信息，继续启动？{'是' if ok else '否'}:{remote_pos_params}")
                    if not ok:
                        return

                elif not has_local:
                    ok = await self.__confirm_dialog(
                        "POS启动提示", f"本地配置为空，{can_not_auto_change_text}将启动服务端对应机台：\n{remote_info}"
                    )
                    if not ok:
                        return

            if self.start_config.change_pos and has_local:
                await PosConfigServer.change_pos_on_network(path)
            elif (
                has_local
                and has_remote
                and (
                    local_pos_params.venderNo != remote_pos_params.venderNo
                    or local_pos_params.orgNo != remote_pos_params.orgNo
                    or local_pos_params.posId != remote_pos_params.posId
                )
            ):
                open_type = await self.__choice_start_type_dialog(
                    "POS启动提示",
                    f"配置不一致，将启动服务端对应机台："
                    f"\n{remote_info}"
                    "；"
                    f"\n本地：商家：{local_pos_params.venderNo}，门店：{local_pos_params.orgNo}，POS：{local_pos_params.posId}；",
                )
                if open_type == 0:
                    return
                elif open_type == 2:
                    await PosConfigServer.change_pos_on_network(path)

            if self.start_config.account_logout:
                await PosConfigServer.logout_pos_account(path)

            if self.start_config.replace_mitm_cert:
                logger.info("替换mitm证书")
                success, msg = PosConfig.replace_mitm_cert(path)
                if not success:
                    UiUtil.show_snackbar_error(self.page, msg)
                    return
                else:
                    UiUtil.show_snackbar_success(self.page, msg)

            if self.start_config.backup:
                logger.info("备份支付驱动")
                try:
                    PosConfig.backup_payment_driver(path)
                except Exception as e:
                    UiUtil.show_snackbar_error(self.page, f"备份支付驱动失败: {e}")
                    return

            if self.start_config.cover_payment_driver:
                logger.info("覆盖支付驱动")
                try:
                    success, msg = PosConfig.cover_payment_driver(path)
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
                logger.info("清理缓存")
                try:
                    PosConfig.clean_cache(path)
                except Exception as e:
                    UiUtil.show_snackbar_error(self.page, f"清理缓存失败: {e}")
                    return

            UiUtil.show_snackbar_success(self.page, "正在启动POS。。。")
            # if not file_handle.open_file(path):
            vendor_id = None
            pos_params = PosConfig.read_pos_params(path, 2)
            if pos_params and isinstance(pos_params, PosParamsModel):
                vendor_id = pos_params.venderNo
                pos_resolution = PosConfig.get_vendor_config(vendor_id=vendor_id).resolution
                if str(pos_params.posType) == "2":
                    env_vars = pos_resolution.sco.model_dump()
                else:
                    env_vars = pos_resolution.pos.model_dump()
            else:
                env_vars = ResolutionModel().model_dump()
            if not file_handle.start_file_independent(path, env_vars):
                UiUtil.show_snackbar_error(self.page, f"打开文件:{path} 失败")
            else:
                UiUtil.show_snackbar_success(self.page, "启动POS成功")
        except Exception as e:
            logger.exception(e)
            UiUtil.show_snackbar_error(self.page, f"POS启动失败：{e}")

    def open_pos_file_location(self, e: ft.ControlEvent):
        """打开文件所在目录"""
        path = e.control.data
        if not file_handle.open_file_location(path):
            self.status_text.value = f"打开:{path} 所在目录失败"
            self.page.update()

    def change_env_from_network(self, e: ft.ControlEvent):
        pos_path = e.control.data
        self.page.open(ChangePosUi(pos_path))

    def change_env(self, e: ft.ControlEvent):
        path = e.control.data
        try:
            self.page.open(ChangeLocalPosUi(path))
        except Exception as e:
            UiUtil.show_snackbar_error(self.page, f"打开环境切换窗口失败：{e}")

        self.page.update()

    def clean_cache(self, e: ft.ControlEvent):
        path = e.control.data
        logger.info(f"清理缓存: {path}")
        success, msg = PosConfig.clean_cache(path)
        if success:
            UiUtil.show_snackbar_success(self.page, msg)
        else:
            UiUtil.show_snackbar_error(self.page, msg)
        self.page.update()

    def backup_payment_driver(self, e: ft.ControlEvent):
        path = e.control.data
        logger.info(f"备份支付驱动: {path}")
        PosConfig.backup_payment_driver(path)
        self.page.update()

    def cover_payment_driver(self, e: ft.ControlEvent):
        path = e.control.data
        logger.info(f"使用mock支付驱动: {path}")
        PosConfig.cover_payment_driver(path)
        self.page.update()

    def restore_payment_driver(self, e: ft.ControlEvent):
        path = e.control.data
        logger.info(f"恢复支付驱动: {path}")
        PosConfig.restore_payment_driver(path)
        self.page.update()

    def get_pos_env(self, e: ft.ControlEvent):
        e.control.disabled = True
        e.control.update()
        path = e.control.data
        logger.info(f"获取POS环境: {path}")
        try:
            if not os.path.exists(path):
                UiUtil.show_snackbar_error(self.page, f"文件路径不存在【{path}】")
                return
            pos_env = PosConfig.get_local_pos_env(path)
            e.control.text = pos_env
            # if pos_env == "RTA":
            #     UiUtil.show_snackbar_error(self.page, "生产环境【RTA】不支持获取POS环境")
            #     return

            pos_params, store_list, env_list = PosToolConfigServer.get_store_list(path)
            pos_params: PosParamsModel = pos_params
            is_local = "本地" if pos_params.is_local else "远端"
            pos_version = ExeVersionReader(path).get_exe_file_version()
            for child in e.control.parent.controls:
                if isinstance(child, ft.Text) and child.key == "store":
                    child.value = f" 门店:{pos_params.sapOrgNo}"
                    child.data = pos_params.sapOrgNo
                    child.update()
                if isinstance(child, ft.Text) and child.key == "vendor":
                    child.value = f"{is_local} 商家:{pos_params.venderNo}"
                    child.data = pos_params.venderNo
                    child.update()

                if isinstance(child, ft.Text) and child.key == "env":
                    child.value = f" 环境:{store_list[0].env if store_list else pos_env} 版本：{pos_version} posId:{pos_params.posId}"
                    child.data = store_list[0].env if store_list else pos_env
                    child.update()

            UiUtil.show_snackbar_success(self.page, "获取POS环境成功")
        except PosParamsException as pe:
            logger.error(f"获取POS配置失败: {pe}")
            UiUtil.show_snackbar_error(self.page, f"{pe}")
        except Exception as ex:
            logger.error(f"获取POS环境失败: {ex}")
            logger.exception(ex)
            UiUtil.show_snackbar_error(self.page, f"获取POS环境失败: {ex}")
        finally:
            e.control.disabled = False
            e.control.update()

    async def change_pos_env(self, e: ft.ControlEvent):
        path = e.control.data
        try:
            await PosConfigServer.change_pos_on_network(path)
            UiUtil.show_snackbar_success(self.page, "POS切换成功")
        except Exception as e:
            UiUtil.show_snackbar_error(self.page, f"POS切换失败：{e}")

    def clear_pos_env_file(self, e: ft.ControlEvent):
        path = e.control.data
        try:
            logger.info(f"清理POS环境文件: {path}")
            PosConfig.clear_env(path)
            e.page.open(
                ft.SnackBar(
                    content=ft.Text("清理成功"),
                    action="知道了",
                )
            )
            self.page.update()
        except Exception as e:
            UiUtil.show_snackbar_error(self.page, f"环境清理失败： {e}")

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
                    ft.Text(pos_path, expand=True, selectable=True),
                    ft.Text("商家", key="vendor", bgcolor=ft.Colors.YELLOW_50),
                    ft.Text("门店", key="store", bgcolor=ft.Colors.YELLOW_100),
                    ft.Text("环境", key="env", bgcolor=ft.Colors.YELLOW_200),
                    ft.ElevatedButton(
                        data=pos_path,
                        text="切换POS",
                        tooltip="调用接口切换对应环境的POS为当前POS",
                        on_click=self.change_pos_env,
                        on_long_press=self.change_env_from_network,
                    ),
                    ft.ElevatedButton(
                        data=pos_path,
                        width=120,
                        text="点击查看环境",
                        tooltip="查看POS当前环境",
                        on_click=self.get_pos_env,
                    ),
                    ft.IconButton(
                        data=pos_path,
                        icon=ft.Icons.FOLDER_OPEN,
                        tooltip="打开所在目录",
                        on_click=self.open_pos_file_location,
                    ),
                    ft.IconButton(
                        data=pos_path,
                        icon=ft.Icons.PLAY_CIRCLE,
                        tooltip="启动POS",
                        on_click=self.open_pos_file,
                    ),
                    ft.PopupMenuButton(
                        data=pos_path,
                        icon=ft.Icons.MORE_VERT,
                        tooltip="更多操作",
                        items=[
                            ft.PopupMenuItem(
                                text="切换本地环境",
                                data=pos_path,
                                tooltip="切换本地环境，修改pos.ini、切换database、logs、缓存等",
                                on_click=self.change_env,
                            ),
                            ft.PopupMenuItem(text="备份支付驱动", data=pos_path, on_click=self.backup_payment_driver),
                            ft.PopupMenuItem(text="恢复支付驱动", data=pos_path, on_click=self.restore_payment_driver),
                            ft.PopupMenuItem(
                                text="使用支付mock驱动", data=pos_path, on_click=self.cover_payment_driver
                            ),
                            ft.PopupMenuItem(text="清理缓存", data=pos_path, on_click=self.clean_cache),
                            ft.PopupMenuItem(text="清理当前环境文件", data=pos_path, on_click=self.clear_pos_env_file),
                            ft.PopupMenuItem(text="退出账号", data=pos_path, on_click=self.logout_pos_account_for_view),
                        ],
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                spacing=1,
                # auto_scroll=True,
            ),
        )
        return result_item

    def __find_files(self, directories: list[str], file_pattern=None, dir_pattern=None, max_depth=None):
        """在多个目录中递归查找文件，可指定匹配规则和递归深度"""
        logger.info(f"开始搜索: {directories}, 模式: {file_pattern}, 目录模式: {dir_pattern}, 递归深度: {max_depth}")

        data = {
            "dir": directories,
            "file_pattern": file_pattern,
            "dir_pattern": dir_pattern,
            "max_depth": str(max_depth),
        }
        SearchConfig.write(data)
        result = []
        depth = 0
        scan_state = {"count": 0, "last_report_count": 0}

        def scan_dir(path, depth):
            if max_depth is not None and depth >= max_depth:
                return
            try:
                with os.scandir(path) as it:
                    depth += 1
                    for entry in it:
                        logger.debug(f"当前目录: {path}, 深度: {depth}, 文件名: {entry.name}")
                        if self.stop_event.is_set():
                            break
                        scan_state["count"] += 1

                        if entry.is_file():
                            if file_pattern is None or fnmatch.fnmatch(
                                entry.name.lower(), file_pattern.lower()
                            ):  # 可换成正则匹配
                                result.append(entry.path)

                        elif entry.is_dir() and (
                            dir_pattern is None or fnmatch.fnmatch(entry.name.lower(), dir_pattern.lower())
                        ):
                            scan_dir(entry.path, depth)

                        if scan_state["count"] - scan_state["last_report_count"] >= 100:
                            scan_state["last_report_count"] = scan_state["count"]
                            self.update_ui(
                                f"已扫描 {scan_state['count']} 项，已找到 {len(result)} 个文件",
                                True,
                                0.5,
                            )
            except PermissionError:
                self.update_ui(f"权限错误: {path}", True)

        for d in directories:
            scan_dir(d, depth=depth)

        return result

    def search_files(self):
        search_config = SearchConfig.read()
        directory = SearchConfig.read_work_dir()
        pattern = search_config.file_pattern
        dir_pattern = search_config.dir_pattern
        max_depth = 1
        try:
            max_depth = int(search_config.max_depth)
            if max_depth < 1:
                max_depth = 1
        except Exception:
            pass

        result = self.__find_files(directory, file_pattern=pattern, dir_pattern=dir_pattern, max_depth=max_depth)
        SearchConfig.save_search_result(result)
        found_files = len(result)
        self._set_search_results(result, (self.search_keyword_field.value or "").strip())

        msg = "搜索已停止" if self.stop_event.is_set() else f"完成! 共找到 {found_files} 个文件"
        self.update_ui(msg, False)

    def update_ui(self, message, searching, progress=0):
        self.status_text.value = message
        self.progress_bar.value = progress
        self.progress_bar.visible = searching
        self.search_btn.disabled = searching
        self.stop_btn.disabled = not searching
        self.page.update()



