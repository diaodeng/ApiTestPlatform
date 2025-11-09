from flet import SnackBar, Text, Colors, Page
import flet as ft
import json

from loguru import logger


from model.config import PosConfigModel, PosParamsModel, PosChangeParamsModel, VendorConfigModel
from server.config import PosConfig, PosToolConfig
from server.pos_tool_config_server import PosToolConfigServer

from model.pos_network_model import PosInitRespModel, PosResetAccountRequestModel, PosLogoutModel
from utils.common import get_active_mac, get_local_ip
from utils.pos_network import pos_tool_init, reset_account_password, pos_account_logout, change_pos_from_network


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
    def __init__(self):
        super().__init__()
        self.config_data: PosConfigModel = PosConfig.read_pos_config()
        self.modal = False
        self.title = ft.Text("POS设置")
        self.content = ft.Container(content=ft.Row(controls=[
            ft.Column(controls=[
                ft.TextField(value=self.config_data.pos_tool_test_host, label="Tbox测试环境host(修改后需要重启工具)", on_blur=self.update_config_data, data="pos_tool_test_host"),
                ft.TextField(value=self.config_data.pos_tool_uat_host, label="Tbox UAT host(修改后需要重启工具)", on_blur=self.update_config_data, data="pos_tool_uat_host"),
                ft.TextField(value=self.config_data.payment_mock_driver_path, label="支付MOCK驱动目录", on_blur=self.update_config_data, data="payment_mock_driver_path"),
                ft.TextField(value=self.config_data.payment_driver_back_up_path, label="支付驱动备份目录", on_blur=self.update_config_data, data="payment_driver_back_up_path"),
                ft.TextField(value=json.dumps(self.config_data.env_files, indent=4, ensure_ascii=False), label="环境文件：", on_blur=self.update_config_data, data="env_files", multiline=True),
                ft.TextField(value=json.dumps(self.config_data.cache_files, indent=4, ensure_ascii=False), label="缓存文件:", on_blur=self.update_config_data, data="cache_files", multiline=True),
                ft.TextField(value=json.dumps(self.config_data.env_group_vendor, indent=4, ensure_ascii=False), label="商家分组:", on_blur=self.update_config_data, data="env_group_vendor", multiline=True),
                ft.TextField(value=json.dumps([i.model_dump() for i in self.config_data.vendor_config], indent=4, ensure_ascii=False), label="商家POS账号:", on_blur=self.update_config_data, data="vendor_config", multiline=True),
            ], expand=True)
        ], expand=True), expand=True, width=1000)
        self.actions = [
            ft.TextButton("关闭", on_click=self.close_dlg),
            ft.TextButton("保存", on_click=self.save_config),
        ]
        self.actions_alignment = ft.MainAxisAlignment.END
        self.scrollable = True
        self.open = True


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
        if config_key in ["payment_mock_driver_path", "payment_driver_back_up_path", "pos_tool_test_host", "pos_tool_uat_host"]:
            setattr(self.config_data, config_key, config_value)
        elif config_key == "vendor_account":
            if not config_value:
                self.config_data.vendor_config = []
                return
            setattr(self.config_data, config_key, [VendorConfigModel.model_validate(j) for j in json.loads(config_value)])
        else:
            setattr(self.config_data, config_key, json.loads(config_value))


class ChangePosUi(ft.AlertDialog):
    def __init__(self, pos_path = None):
        logger.info(f"打开切换POS页面：{pos_path}")
        super().__init__()
        self.pos_tool_config_data = PosToolConfigServer.read_pos_tool_config()
        mac = get_active_mac()
        ip = get_local_ip()
        # self.config_data: PosConfigModel = PosConfig.read_pos_config()
        self.modal = True
        self.title = ft.Text("在线切换POS")

        self.vender_potions = {}
        self.store_potions = {}

        env_group , vendor_id, store, pos_group, pos_type = None, None, None, None, None
        try:
            if pos_path:
                pos_params: PosParamsModel = PosConfig.read_pos_params(pos_path)
                pos_env = PosConfig.get_local_pos_env(pos_path)
                if pos_params:
                    vendor_id = pos_params.venderNo
                    store = pos_params.orgNo
                    pos_group = pos_params.posGroupNo
                    pos_type = pos_params.posType

                    env_group, account = PosConfig.get_pos_group(vendor_id, pos_env)

                    for store_potion in self.pos_tool_config_data.data.store_list:
                        if env_group and env_group == store_potion.env:
                            self.vender_potions[store_potion.vender_id] =store_potion.vender_name
                            if vendor_id and store_potion.vender_id == vendor_id:
                                self.store_potions[store_potion.store_id] = store_potion.store_name
        except Exception as e:
            logger.error(e)
            pass

        self.content = ft.Container(content=ft.Row(controls=[
            ft.Column(controls=[
                ft.Dropdown(label="环境",
                            value=env_group,
                            options=[ft.DropdownOption(item.env_code, item.env_name) for item in self.pos_tool_config_data.data.env_list],
                            # editable=True,
                            on_change=self.change_env,
                            data="env",
                            expand=True
                            ),
                ft.Dropdown(label="商家",
                            value=vendor_id,
                            options=[ft.DropdownOption(key, name) for key,name in self.vender_potions.items()],
                            # editable=True,
                            on_change=self.change_vendor,
                            data="venderId",
                            expand=True
                            ),
                ft.Dropdown(label="门店",
                            value=store,
                            options=[ft.DropdownOption(key, name) for key,name in self.store_potions.items()],
                            # editable=True,
                            on_change=self.change_store,
                            data="orgNo",
                            expand=True
                            ),
                ft.Dropdown(label="切换模式",
                            value="1",
                            options=[ft.DropdownOption("1", "指定MAC"),
                                     ft.DropdownOption("2", "指定POS_ID")],
                            # editable=True,
                            on_change=self.change_switch_model,
                            data="switchMode",
                            expand=True
                            ),
                ft.TextField(value=mac, label="mac", data="pos_mac", visible=True, on_blur=lambda e: print(e)),
                ft.TextField(value="", label="pos_id", data="pos_no", visible=False),
                ft.TextField(value=ip, label="ip", data="pos_ip"),
                ft.Dropdown(label="POS类型",
                            value=pos_type or "1",
                            options=[ft.DropdownOption("1", "人工收银"),
                                     ft.DropdownOption("2", "SCO"),
                                     ft.DropdownOption("4", "Combined")],
                            # editable=True,
                            # on_change=self.change_store,
                            data="pos_type",
                            expand=True
                            ),
                ft.Dropdown(label="POS机台组",
                            value=pos_group,
                            options=[],
                            # editable=True,
                            # on_change=self.change_store,
                            data="pos_group",
                            expand=True
                            ),

            ], expand=True)
        ], expand=True), expand=True, width=1000)
        self.actions = [
            ft.TextButton("关闭", on_click=self.close_dlg),
            ft.TextButton("切换", on_click=self.change_pos_on_network),
        ]
        self.actions_alignment = ft.MainAxisAlignment.END
        self.scrollable = True
        self.open = True


    def close_dlg(self, event: ft.ControlEvent):
        self.open = False
        # event.control.page.overlay.remove(self)
        event.control.page.update()

    async def change_pos_on_network(self, event: ft.ControlEvent):
        event.control.disabled = True
        event.control.update()
        try:
            data = {}
            for item in event.control.parent.content.content.controls[0].controls:
                data[item.data] = item.value
            logger.info(f"切换POS请求参数：{json.dumps(data)}")
            request_data = PosChangeParamsModel.model_validate(data)
            change_status, message_info = await change_pos_from_network(request_data)
            if not change_status:
                UiUtil.show_snackbar_error(self.page, message_info)
                return

            UiUtil.show_snackbar_success(self.page, "POS切换成功")
        except Exception as e:
            logger.exception(e)
            UiUtil.show_snackbar_error(self.page, f"POS配置保存失败：{str(e)}")
        finally:
            event.control.disabled = False
            event.control.update()

    def change_env(self, event: ft.ControlEvent):
        env_group = event.control.value
        for cont in event.control.parent.controls:
            if cont.data == "orgNo":
                cont.options.clear()
                cont.value = None
                cont.update()
            if cont.data == "venderId":
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
            if cont.data == "env":
                current_env = cont.value
        current_vendor = event.control.value
        for cont in event.control.parent.controls:
            if cont.data == "orgNo":
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

    def change_switch_model(self, event: ft.ControlEvent):
        """
        改变切换门店的模式
        """
        switch_model = event.control.value
        for cont in event.control.parent.controls:
            if cont.data == "pos_mac":
                cont.visible = switch_model == "1"  # 按mac切换
                cont.update()
            elif cont.data == "pos_no":
                cont.visible = switch_model != "1"  # 按posId切换
                cont.update()


class PosAccountManagerUi(ft.AlertDialog):
    def __init__(self, pos_path=None):
        super().__init__()
        self.pos_tool_config_data = PosToolConfigServer.read_pos_tool_config()
        # self.config_data: PosConfigModel = PosConfig.read_pos_config()
        env_group, account = None, None
        try:
            pos_params: PosParamsModel = PosConfig.read_pos_params(pos_path)
            vendor_id = None
            if pos_params:
                vendor_id = pos_params.venderNo
            pos_env = PosConfig.get_local_pos_env(pos_path)
            env_group, account = PosConfig.get_pos_group(vendor_id, pos_env)
        except Exception as e:
            logger.error(e)
            pass
        self.modal = False
        self.title = ft.Text("POS账号管理")
        self.content = ft.Container(content=ft.Row(controls=[
            ft.Column(controls=[
                ft.Dropdown(label="环境",
                            value=env_group,
                            options=[ft.DropdownOption(item.env_code, item.env_name) for item in self.pos_tool_config_data.data.env_list],
                            editable=True,
                            on_change=self.change_env,
                            data="env",
                            expand=True
                            ),
                ft.TextField(value=account, label="收银员账号", data="cashierNo", on_change=lambda e: print(e),visible=True),
                ft.Row(controls=[
                    ft.ElevatedButton("踢出登录", on_click=self.tick_out),
                    ft.ElevatedButton("重置密码", on_click=self.reset_password)
                ])

            ], expand=True)
        ], expand=True), expand=True, width=1000)
        self.actions = [
            ft.TextButton("关闭", on_click=self.close_dlg),
        ]
        self.actions_alignment = ft.MainAxisAlignment.END
        self.scrollable = True
        self.open = True


    def close_dlg(self, event: ft.ControlEvent):
        self.open = False
        event.control.page.update()

    async def tick_out(self, event: ft.ControlEvent):
        event.control.disabled = True
        event.control.update()
        try:
            env_group = ""
            account = ""
            for cont in event.control.parent.parent.controls:
                if cont.data == "cashierNo":
                    if not cont.value:
                        UiUtil.show_snackbar_error(self.page, "参数异常")
                        return
                    account = cont.value
                elif cont.data == "env":
                    if not cont.value:
                        UiUtil.show_snackbar_error(self.page, "参数异常")
                        return
                    env_group = cont.value
            data = PosLogoutModel(env=env_group, cashierNo=account)
            status, message_info = await pos_account_logout(data)
            if not status:
                UiUtil.show_snackbar_error(self.page, message_info)
            else:
                UiUtil.show_snackbar_success(self.page, message_info)
        except Exception as e:
            UiUtil.show_snackbar_error(self.page, f"重置密码失败：{str(e)}")
        finally:
            event.control.disabled = False
            event.control.update()

    async def reset_password(self, event: ft.ControlEvent):
        event.control.disabled = True
        event.control.update()
        try:
            data = PosResetAccountRequestModel()
            for cont in event.control.parent.parent.controls:
                if cont.data == "cashierNo":
                    if not cont.value:
                        UiUtil.show_snackbar_error(self.page, "参数异常")
                        return
                    data.cashierNo = cont.value
                elif cont.data == "env":
                    if not cont.value:
                        UiUtil.show_snackbar_error(self.page, "参数异常")
                        return
                    data.env = cont.value
            reset_status, message_info = await reset_account_password(data)
            if not reset_status:
                UiUtil.show_snackbar_error(self.page, message_info)
            else:
                UiUtil.show_snackbar_success(self.page, "重置成功")
        except Exception as e:
            UiUtil.show_snackbar_error(self.page, f"重置密码失败：{str(e)}")
        finally:
            event.control.disabled = False
            event.control.update()

    def change_env(self, event: ft.ControlEvent):
        env_group = event.control.value
        for cont in event.control.parent.controls:
            if cont.data == "orgNo":
                cont.options.clear()
                cont.value = None
                cont.update()
            if cont.data == "venderId":
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


class ChangeLocalPosUi(ft.AlertDialog):
    def __init__(self, pos_path=None):
        logger.info(f"打开本地POS切换页面：{pos_path}")
        super().__init__()
        # self.pos_tool_config_data = PosToolConfig.read_pos_tool_config()
        self.modal = True
        self.title = ft.Text("在线切换POS")
        self.target_env = None

        env_group , vendor_id, store, pos_group, pos_type = None, None, None, None, None
        self.pos_path = pos_path

        self.content = ft.Container(content=ft.Row(controls=[
            ft.Column(controls=[
                ft.TextField(value=self.get_current_env_info(), label="当前环境", data="current_env"),
                ft.Dropdown(label="已备份环境",
                            value=None,
                            options=[ft.DropdownOption(key, name) for key, name in self.get_backed_env().items()],
                            # editable=True,
                            on_change=self.change_target_env,
                            data="backed_env",
                            expand=True
                            )

            ], expand=True)
        ], expand=True), expand=True, width=1000)
        self.actions = [
            ft.TextButton("关闭", on_click=self.close_dlg),
            ft.TextButton("切换", on_click=self.change_local_pos, data=pos_path),
        ]
        self.actions_alignment = ft.MainAxisAlignment.END
        self.scrollable = True
        self.open = True


    def close_dlg(self, event: ft.ControlEvent):
        self.open = False
        # event.control.page.overlay.remove(self)
        event.control.page.update()

    def get_current_env_info(self):
        local_pos_env = PosConfig.get_local_pos_env(self.pos_path)
        pos_params: PosParamsModel = PosConfig.read_pos_params(self.pos_path)
        if pos_params:
            env_group, account = PosConfig.get_pos_group(pos_params.venderNo, local_pos_env)
            pos_tool_config_data = PosToolConfigServer.read_pos_tool_config()
            for store_info in pos_tool_config_data.data.store_list:
                if store_info.vender_id == pos_params.venderNo and store_info.env == env_group and store_info.store_id == pos_params.orgNo:
                    return f"{local_pos_env} --> {store_info.vender_name} --> {store_info.store_name}"
            return f"环境：{local_pos_env}，商家：{pos_params.venderNo}，门店：{pos_params.orgNo}"
        else:
            return f"环境：{local_pos_env}，商家：无，门店：无"

    def get_backed_env(self) -> dict[str,str]:
        config_data: PosConfigModel = PosConfig.read_pos_config()
        backed_env = ["RTA_TEST", "RTA_UAT", "RTA"]
        backed_env.extend(config_data.backup_envs.get(self.pos_path, []))
        backed_env = {e:e for e in backed_env}

        local_pos_env = PosConfig.get_local_pos_env(self.pos_path)
        if not local_pos_env:
            return backed_env
        pos_tool_config_data = PosToolConfigServer.read_pos_tool_config()

        current_backed_env = {}
        for local_backed_env, _ in backed_env.items():
            backed_env_info = local_backed_env.split("_")
            if len(backed_env_info) >2:
                current_env = '_'.join(backed_env_info[:-2])
                vender_id = backed_env_info[2]
                store = backed_env_info[3]
                env_group, account = PosConfig.get_pos_group(vender_id, current_env)
                for store_info in pos_tool_config_data.data.store_list:
                    if store_info.vender_id == vender_id and store_info.env == env_group and store_info.store_id == store:
                        current_backed_env[local_backed_env] = f"{local_backed_env} --> {store_info.vender_name} --> {store_info.store_name}"
        backed_env.update(current_backed_env)
        return backed_env


        # pos_params: PosParamsModel = PosConfig.read_pos_params(self.pos_path)



        return backed_env

    async def change_local_pos(self, event: ft.ControlEvent):
        event.control.disabled = True
        event.control.update()
        pos_path = event.control.data
        try:
            target_env = None
            for item in event.control.parent.content.content.controls[0].controls:
                if item.data == "backed_env":
                    target_env = item.value
            logger.info(f"切换本地POS：{target_env} --> {pos_path}")

            success, msg = PosConfig.change_pos_local_env(pos_path, target_env)
            if not success:
                UiUtil.show_snackbar_error(self.page, f"本地POS切换: {msg}")
            else:
                for item in event.control.parent.content.content.controls[0].controls:
                    if item.data == "backed_env":
                        item.options.clear()
                        item.options = [ft.DropdownOption(key, name) for key, name in self.get_backed_env().items()]
                        item.value = None
                        item.update()
                    elif item.data == "current_env":
                        item.value = self.get_current_env_info()
                        item.update()
                UiUtil.show_snackbar_success(self.page, "POS切换成功")

        except Exception as e:
            logger.exception(e)
            UiUtil.show_snackbar_error(self.page, f"本地POS切换失败：{str(e)}")
        finally:
            event.control.disabled = False
            event.control.update()

    def change_target_env(self, event: ft.ControlEvent):
        self.target_env = event.control.value

