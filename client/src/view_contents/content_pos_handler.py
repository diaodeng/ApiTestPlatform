import asyncio
import os
import fnmatch
import os
from threading import Thread, Event

import flet as ft
from flet.core.alignment import bottom_right
from loguru import logger

from model.pos_network_model import PosLogoutModel
from server.config import SearchConfig, StartConfig, PaymentMockConfig, MitmproxyConfig, PosConfig, PosToolConfig
from utils import file_handle, pos_network
from utils.common import kill_process_by_name, get_all_process, kill_process_by_id, ExeVersionReader
from common.ui_utils.ui_util import UiUtil, PosSettingUi, ChangePosUi, PosAccountManagerUi, ChangeLocalPosUi


class PosHandler:
    def __init__(self, ft, page: ft.Page):
        self.start_config = StartConfig.read()
        self.ft = ft
        self.page = page
        self.set_width = 400
        self.all_p = []
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

    def open_process_list_dialog(self, e):
        self.all_p = get_all_process()
        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("运行中的进程"),
            content=ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.TextField(data="filter_key"),
                        ft.ElevatedButton("查询", on_click=self.filter_process),
                        ft.ElevatedButton("更新", on_click=self.update_all_process),
                    ]),
                    ft.ListView([
                        ft.Row([
                            ft.Text(f"{item['name']}:{item['exe']}", expand=True),
                            ft.Text("子进程", color=ft.Colors.GREEN_100, visible=item.get('is_current_child', False)),
                            ft.ElevatedButton("停止", on_click=self.kill_p_by_id, data=item['pid']),
                        ], expand=True) for item in self.all_p
                    ], expand=True, data="filter_result"),
                ]),

                expand=True,
                width=1000
            ),
            actions=[
                ft.TextButton("取消", on_click=lambda e: e.page.close(dialog)),
                # ft.TextButton("添加", on_click=lambda e: dialog.dismiss()),
            ],
            alignment=ft.alignment.center
        )
        dialog.open = True
        self.page.open(dialog)
        self.page.update()

    def filter_process(self, e:ft.ControlEvent):
        filter_data = ""
        for i  in e.control.parent.controls:
            if i.data == "filter_key":
                filter_data = i.value
        filter_data = filter_data.lower()
        for item_view in e.control.parent.parent.controls:
            if item_view.data == "filter_result":
                item_view.controls.clear()
                item_view.update()
                for item in self.all_p:
                    if filter_data in item['name'].lower():
                        item_view.controls.append(
                            ft.Row([
                                ft.Text(f"{item['name']}:{item['exe']}", expand=True),
                                ft.Text("子进程", color=ft.Colors.GREEN_100,
                                        visible=item.get('is_current_child', False)),
                                ft.ElevatedButton("停止", on_click=self.kill_p_by_id, data=item['pid']),
                            ], expand=True)
                        )
                        item_view.update()

    def update_all_process(self, e:ft.ControlEvent):
        self.all_p = get_all_process()

    def kill_p_by_id(self, e):
        k_id = e.control.data
        if k_id:
            kill_process_by_id(e.control.data)

        UiUtil.show_snackbar_success(self.page, f"进程已停止")

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
                    self.kill_pos_btn,
                    self.kill_offline_btn,
                    ft.Button("结束进程", tooltip="查看并结束进程", on_click=self.open_process_list_dialog),
                    ft.ElevatedButton("设置", tooltip="POS工具相关设置",on_click=lambda e:self.page.open(PosSettingUi())),
                    ft.ElevatedButton("切换POS", tooltip="调用接口切换POS",on_click=self.change_env_from_network),
                    ft.ElevatedButton("POS账号处理", tooltip="调用接口踢出POS账号或重置密码",on_click=lambda e:self.page.open(PosAccountManagerUi()))
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
                    # self.before_start_change_env_view,
                    self.before_start_logout_view,
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

        self.kill_pos_btn = ft.ElevatedButton(
            "结束POS",
            on_click=lambda e: self.kill_pos_process(),
            # disabled=True,
            color="red"
        )

        self.kill_offline_btn = ft.ElevatedButton(
            "结束离线",
            on_click=lambda e: self.kill_offline_process(),
            # disabled=True,
            color="red"
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
                ft.TextButton("Yes", on_click=self.change_env),
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
            logger.error(f"POS结束进程失败: {e}")
            UiUtil.show_snackbar_error(self.page, f"POS结束进程失败: {e}")

    def kill_offline_process(self):
        kill_process_name = ["java.exe"]
        try:
            for process_name in kill_process_name:
                # logger.info(f"结束{process_name}进程")
                kill_process_by_name(process_name)
            logger.info(f"离线（java.exe）进程已结束")
            UiUtil.show_snackbar_success(self.page, "离线（java.exe）进程已结束")
        except Exception as e:
            logger.error(f"离线（java.exe）结束进程失败: {e}")
            UiUtil.show_snackbar_error(self.page, f"离线（java.exe）结束进程失败: {e}")

    def validate_inputs(self, e):
        self.search_btn.disabled = not self.file_pattern.value
        self.page.update()

    def update_start_config(self, e):
        logger.info(f"更新启动配置")
        self.start_config.backup = self.before_start_back_view.value
        self.start_config.replace_mitm_cert = self.before_start_replace_mitm_cert_view.value
        self.start_config.change_env = self.before_start_change_env_view.value
        self.start_config.change_pos = self.before_start_change_pos_view.value
        self.start_config.account_logout = self.before_start_logout_view.value
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

    async def logout_pos_account_for_view(self, evt: ft.ControlEvent):
        path = evt.control.data
        await self._logout_pos_account(path)

    async def _logout_pos_account(self, pos_path) -> bool:
        logger.info(f"开始退出账号：{pos_path}")
        pos_config = PosConfig.read_pos_params(pos_path)
        if not pos_config:
            UiUtil.show_snackbar_error(self.page, f"获取POS缓存失败， 无法注销POS账号: pos_config={pos_config}")
            return False
        pos_env = PosConfig.get_local_pos_env(pos_path)
        pos_group, account = PosConfig.get_pos_group(pos_config.venderNo, pos_env)
        if not pos_group or not account:
            UiUtil.show_snackbar_error(self.page,
                                       f"获取POS账号失败， 无法注销POS账号: pos_group={pos_group}, account={account}")
            return False
        logout_model = PosLogoutModel(
            env=pos_group,
            cashierNo=account
        )
        try:
            status, message_info = await pos_network.pos_account_logout(logout_model)
            if not status:
                UiUtil.show_snackbar_error(self.page, message_info)
                return False
            else:
                UiUtil.show_snackbar_success(self.page, message_info)
                return True
        except Exception as e:
            UiUtil.show_snackbar_error(self.page, f"注销POS账号失败: {e}")
            return False




    async def open_pos_file(self,e:ft.ControlEvent):
        """打开文件"""
        path = e.control.data
        logger.info(f"启动POS文件: {path}")
        logger.debug(f"启动前,检查CPOS-DF.exe进程是否存在，存在则杀死")
        kill_process_by_name("CPOS-DF.exe")
        UiUtil.show_snackbar_success(self.page, "启动前,检查CPOS-DF.exe进程是否存在，存在则杀死")
        await asyncio.sleep(2)

        if self.start_config.change_pos:
            change_result = await self._change_pos(path)
            if not change_result:
                return

        if self.start_config.account_logout:
            logout_result = await self._logout_pos_account(path)
            if not logout_result:
                return

        if self.start_config.replace_mitm_cert:
            logger.info(f"替换mitm证书")
            success, msg = PosConfig.replace_mitm_cert(path)
            if not success:
                UiUtil.show_snackbar_error(self.page, msg)
                return
            else:
                UiUtil.show_snackbar_success(self.page, msg)

        if self.start_config.backup:
            logger.info(f"备份支付驱动")
            try:
                PosConfig.backup_payment_driver(path)
            except Exception as e:
                UiUtil.show_snackbar_error(self.page, f"备份支付驱动失败: {e}")
                return

        if self.start_config.cover_payment_driver:
            logger.info(f"覆盖支付驱动")
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
            logger.info(f"清理缓存")
            try:
                PosConfig.clean_cache(path)
            except Exception as e:
                UiUtil.show_snackbar_error(self.page, f"清理缓存失败: {e}")
                return

        UiUtil.show_snackbar_success(self.page, "正在启动POS。。。")
        # if not file_handle.open_file(path):
        envs = {
            "width": "1366",
            "height": "768",
            "c_width": "1024",
            "c_height": "768",
        }
        if not file_handle.start_file_independent(path, envs):
            UiUtil.show_snackbar_error(self.page, f"打开文件:{path} 失败")
        else:
            UiUtil.show_snackbar_success(self.page, "启动POS成功")

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
        self.page.open(ChangeLocalPosUi(path))


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

            vender_id, org_no, store_list, env_list = PosToolConfig.get_store_list(path)
            pos_version = ExeVersionReader(path).get_exe_file_version()
            for child in e.control.parent.controls:
                if isinstance(child, ft.Text) and child.key == "store":
                    child.value = f" 门店:{org_no}"
                    child.data = org_no
                    child.update()
                if isinstance(child, ft.Text) and child.key == "vendor":
                    child.value = f"商家:{vender_id}"
                    child.data = vender_id
                    child.update()

                if isinstance(child, ft.Text) and child.key == "env":
                    child.value = f" 环境:{store_list[0].env if store_list else pos_env} 版本：{pos_version}"
                    child.data = store_list[0].env if store_list else pos_env
                    child.update()

            UiUtil.show_snackbar_success(self.page, "获取POS环境成功")
        except Exception as ex:
            logger.error(f"获取POS环境失败: {ex}")
            logger.exception(ex)
            UiUtil.show_snackbar_error(self.page, f"获取POS环境失败: {ex}")
        finally:
            e.control.disabled = False
            e.control.update()

    async def _change_pos(self, pos_path:str) -> bool:
        try:
            logger.info(f"切换POS环境: {pos_path}")
            change_status, message_info = await PosConfig.change_pos_on_network(pos_path)
            if change_status:
                UiUtil.show_snackbar_success(self.page, "切换POS环境成功")
                return True
            else:
                UiUtil.show_snackbar_error(self.page, f"切换POS环境失败：{message_info}")
                return False
        except Exception as e:
            logger.error(f"切换POS环境失败: {e}")
            UiUtil.show_snackbar_error(self.page, f"切换POS环境失败: {e}")
            return False


    async def change_pos_env(self, e: ft.ControlEvent):
        path = e.control.data
        await self._change_pos(path)

    def clear_pos_env_file(self, e: ft.ControlEvent):
        path = e.control.data
        logger.info(f"清理POS环境文件: {path}")
        PosConfig.clear_env(path)
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
                    ft.Text("商家", key="vendor", bgcolor=ft.Colors.YELLOW_50),
                    ft.Text("门店", key="store", bgcolor=ft.Colors.YELLOW_100),
                    ft.Text("环境", key="env", bgcolor=ft.Colors.YELLOW_200),
                    # ft.Dropdown(
                    #     editable=True,
                    #     label="门店",
                    #     key="store",
                    #     options=[
                    #         ft.dropdown.Option(i) for i in ["111", "222", "333"]
                    #     ],
                    #     padding=0,
                    #     border_width=1,
                    #     border_color=ft.Colors.GREY_300,
                    # ),
                    # ft.Dropdown(
                    #     editable=True,
                    #     label="环境",
                    #     key="env",
                    #     options=[
                    #         ft.dropdown.Option("")
                    #     ],
                    #     padding=0,
                    #     border_width=1,
                    #     border_color=ft.Colors.GREY_300,
                    # ),
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

                            ft.PopupMenuItem(text="切换本地环境",
                                             data=pos_path,
                                             tooltip="切换本地环境，修改pos.ini、切换database、logs、缓存等",
                                             on_click=self.change_env,
                                             ),
                            ft.PopupMenuItem(text="备份支付驱动",
                                             data=pos_path,
                                             on_click=self.backup_payment_driver),
                            ft.PopupMenuItem(text="恢复支付驱动",
                                             data=pos_path,
                                             on_click=self.restore_payment_driver),
                            ft.PopupMenuItem(text="使用支付mock驱动",
                                             data=pos_path,
                                             on_click=self.cover_payment_driver),
                            ft.PopupMenuItem(text="清理缓存",
                                             data=pos_path,
                                             on_click=self.clean_cache),
                            ft.PopupMenuItem(text="清理当前环境文件",
                                             data=pos_path,
                                             on_click=self.clear_pos_env_file),
                            ft.PopupMenuItem(text="退出账号",
                                             data=pos_path,
                                             on_click=self.logout_pos_account_for_view),
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
