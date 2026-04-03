import asyncio
import os

from loguru import logger

from managers.pos_manager import PosManager
from server.config import PosConfig, StartConfig
from server.pos_config_server import PosConfigServer
from services.pos.pos_start_service import PosStartService
from services.process_service import ProcessService
from utils.file_handle import start_file_independent
from utils.pos_network import change_pos_from_network


class PosService:
    def __init__(self):
        pass

    @classmethod
    def prepare_start(cls, dialog_pos, pos_path):
        try:
            ok, ctx = PosStartService.prepare_start(dialog_pos, pos_path)

            return ok, ctx
        except Exception as e:
            logger.exception(e)
            return False, None

    @staticmethod
    def execute_start(ctx):
        process_id = PosStartService.execute_start(ctx)

        # ===== 记录 =====
        PosManager.instance().set_running(ctx.path, process_id)

        return process_id

    @staticmethod
    def stop_current():
        current = PosManager.instance().get()
        if not current:
            return False

        ProcessService.kill_by_pid(current["pid"])
        PosManager.instance().clear()
        return True

    @staticmethod
    def stop_offline(process_names):
        return ProcessService.kill_by_name(process_names)

    @staticmethod
    def get_env_info(pos_path):
        env = PosConfig.get_local_pos_env(pos_path)
        params = PosConfig.read_pos_params(pos_path)
        return env, params

    @staticmethod
    def change_pos(request):
        return change_pos_from_network(request)
