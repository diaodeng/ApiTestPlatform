from flet import SnackBar, Text, Colors, Page

from model.pos_network_model import PosInitRespModel
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
