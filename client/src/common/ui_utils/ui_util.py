from flet import SnackBar, Text, Colors, Page
import flet as ft
import json
from loguru import logger


from model.config import PosConfigModel
from server.config import PosConfig, PosToolConfig

from model.pos_network_model import PosInitRespModel
from utils.common import get_active_mac, get_local_ip
from utils.pos_network import pos_tool_init


class UiUtil:
    @staticmethod
    def show_snackbar(page, msg: str, action: str = "知道了"):
        page.open(SnackBar(
            content=Text(msg),
            action=action,
        ))
        page.update()

    @staticmethod
    def show_snackbar_error(page, msg: str, action: str = "知道了"):
        page.open(SnackBar(
            bgcolor=Colors.RED,
            content=Text(msg),
            action=action,
        ))
        page.update()

    @staticmethod
    def show_snackbar_success(page, msg: str, action: str = "知道了"):
        page.open(SnackBar(
            bgcolor=Colors.GREEN,
            content=Text(msg),
            action=action,
        ))
        page.update()


class StorageInMemory:
    def __init__(self, page:Page):
        self.data = {}
        self.page:Page = page

    def set(self, key: str, value: any):
        self.page.client_storage.set(key, value)

    def get(self, key: str) -> any:
        return self.page.client_storage.get(key)

    def get_pos_init_data(self) -> PosInitRespModel:
        pos_init_data = self.get("pos_init_data")
        if pos_init_data is None:
            pos_init_data = pos_tool_init()
            self.set("pos_init_data", pos_init_data.model_dump())
            return pos_init_data
        pos_init_data = PosInitRespModel(**pos_init_data)
        return pos_init_data



class PosSettingUi(ft.AlertDialog):
    def __init__(self, page: Page):
        super().__init__()
        self.page = page
        self.config_data: PosConfigModel = PosConfig.read_pos_config()
        self.modal = False
        self.title = ft.Text("POS设置")
        self.content = ft.Container(content=ft.Row(controls=[
            ft.Column(controls=[
                ft.TextField(value=self.config_data.payment_mock_driver_path, label="支付MOCK驱动目录", on_blur=self.update_config_data, data="payment_mock_driver_path"),
                ft.TextField(value=self.config_data.payment_driver_back_up_path, label="支付驱动备份目录", on_blur=self.update_config_data, data="payment_driver_back_up_path"),
                ft.TextField(value=json.dumps(self.config_data.env_files, indent=4, ensure_ascii=False), label="环境文件：", on_blur=self.update_config_data, data="env_files", multiline=True),
                ft.TextField(value=json.dumps(self.config_data.cache_files, indent=4, ensure_ascii=False), label="缓存文件:", on_blur=self.update_config_data, data="cache_files", multiline=True),
                ft.TextField(value=json.dumps(self.config_data.env_group_vendor, indent=4, ensure_ascii=False), label="商家分组:", on_blur=self.update_config_data, data="env_group_vendor", multiline=True),
                ft.TextField(value=json.dumps(self.config_data.vendor_account, indent=4, ensure_ascii=False), label="商家POS账号:", on_blur=self.update_config_data, data="vendor_account", multiline=True),
            ], expand=True)
        ], expand=True), expand=True, width=1000)
        self.actions = [
            ft.TextButton("关闭", on_click=self.close_dlg),
            ft.TextButton("保存", on_click=self.save_config),
        ]
        self.actions_alignment = ft.MainAxisAlignment.END
        self.scrollable = True
        self.open = True
        self.page.update()


    def close_dlg(self, event: ft.ControlEvent):
        self.open = False
        # event.control.page.overlay.remove(self)
        event.control.page.update()

    def save_config(self, event: ft.ControlEvent):
        try:
            PosConfig.save_pos_config(self.config_data)
            UiUtil.show_snackbar_success(self.page, "POS配置保存成功")
        except Exception as e:
            logger.exception(e)
            UiUtil.show_snackbar_error(self.page, f"POS配置保存失败：{str(e)}")

    def update_config_data(self, event: ft.ControlEvent):
        config_value = event.control.value
        config_key = event.control.data
        if config_key in ["payment_mock_driver_path", "payment_driver_back_up_path"]:
            setattr(self.config_data, config_key, config_value)
        else:
            setattr(self.config_data, config_key, json.loads(config_value))


class ChangePosUi(ft.AlertDialog):
    def __init__(self, page: Page, env_group=None, vendor=None, store=None):
        super().__init__()
        self.pos_tool_config_data = PosToolConfig.read_pos_tool_config()
        mac = get_active_mac()
        ip = get_local_ip()
        self.page = page
        # self.config_data: PosConfigModel = PosConfig.read_pos_config()
        self.modal = True
        self.title = ft.Text("在线切换POS")
        self.content = ft.Container(content=ft.Row(controls=[
            ft.Column(controls=[
                ft.Dropdown(label="环境",
                            value=env_group,
                            options=[ft.DropdownOption(item.env_code, item.env_name) for item in self.pos_tool_config_data.data.env_list],
                            editable=True,
                            on_change=self.change_env,
                            key="env",
                            expand=True
                            ),
                ft.Dropdown(label="商家",
                            value=vendor,
                            options=[],
                            editable=True,
                            on_change=self.change_vendor,
                            key="venderId",
                            expand=True
                            ),
                ft.Dropdown(label="门店",
                            value=store,
                            options=[],
                            editable=True,
                            on_change=self.change_store,
                            key="orgNo",
                            expand=True
                            ),
                ft.Dropdown(label="POS类型",
                            value=None,
                            options=[],
                            editable=True,
                            # on_change=self.change_store,
                            key="pos_type",
                            expand=True
                            ),
                ft.Dropdown(label="POS机台组",
                            value=None,
                            options=[],
                            editable=True,
                            # on_change=self.change_store,
                            key="pos_group",
                            expand=True
                            ),
                ft.TextField(value=ip, label="ip", key="pos_ip", on_change=lambda e:print(e)),
                ft.TextField(value=mac, label="mac", key="pos_mac", on_change=lambda e:print(e)),
            ], expand=True)
        ], expand=True), expand=True, width=1000)
        self.actions = [
            ft.TextButton("关闭", on_click=self.close_dlg),
            ft.TextButton("切换", on_click=self.change_pos_on_network),
        ]
        self.actions_alignment = ft.MainAxisAlignment.END
        self.scrollable = True
        self.open = True
        self.page.update()


    def close_dlg(self, event: ft.ControlEvent):
        self.open = False
        # event.control.page.overlay.remove(self)
        event.control.page.update()

    def change_pos_on_network(self, event: ft.ControlEvent):
        try:
            data = {}
            for item in event.control.parent.content.content.controls[0].controls:
                data[item.key] = item.value
            logger.info(f"切换POS请求参数：{json.dumps(data)}")

            UiUtil.show_snackbar_success(self.page, "POS切换成功")
        except Exception as e:
            logger.exception(e)
            UiUtil.show_snackbar_error(self.page, f"POS配置保存失败：{str(e)}")

    def update_config_data(self, event: ft.ControlEvent):
        config_value = event.control.value
        config_key = event.control.data
        if config_key in ["payment_mock_driver_path", "payment_driver_back_up_path"]:
            setattr(self.config_data, config_key, config_value)
        else:
            setattr(self.config_data, config_key, json.loads(config_value))

    def change_env(self, event: ft.ControlEvent):
        env_group = event.control.value
        for cont in event.control.parent.controls:
            if cont.key == "orgNo":
                cont.options.clear()
                cont.value = None
                cont.update()
            if cont.key == "venderId":
                cont.options.clear()
                cont.value = None
                cont.update()
                added_vendor = []
                for vendor_item in self.pos_tool_config_data.data.store_list:
                    if env_group == vendor_item.env and not vendor_item.vender_id in added_vendor:
                        added_vendor.append(vendor_item.vender_id)
                        cont.options.append(ft.DropdownOption(vendor_item.vender_id, vendor_item.vender_name))
                cont.options = sorted(cont.options, key=lambda x:x.key)
                # cont.value = cont.options[0].key if cont.options else None
                cont.update()


    def change_vendor(self, event: ft.ControlEvent):
        current_env = ""
        for cont in event.control.parent.controls:
            if cont.key == "env":
                current_env = cont.value
        current_vendor = event.control.value
        for cont in event.control.parent.controls:
            if cont.key == "orgNo":
                cont.options.clear()
                cont.value = None
                cont.update()
                for vendor_item in self.pos_tool_config_data.data.store_list:
                    if current_vendor == vendor_item.vender_id and vendor_item.env == current_env:
                        cont.options.append(ft.DropdownOption(vendor_item.store_id, vendor_item.store_name))
                # cont.value = cont.options[0].key if cont.options else None
                cont.update()

    def change_store(self, event: ft.ControlEvent):
        pass