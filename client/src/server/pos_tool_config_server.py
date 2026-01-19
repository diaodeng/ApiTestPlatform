import json
import os

from model.config import PosParamsModel
from model.pos_network_model import PosInitRespModel, PosInitRespStoreModel, PosInitRespEnvModel
from server.config import PosConfig
from utils.pos_network import pos_tool_init
from server.config import PosToolConfig


class PosToolConfigServer:
    @classmethod
    def read_pos_tool_config(cls) -> PosInitRespModel:
        local_data = PosToolConfig.read_local_pos_tool_config()
        if local_data:
            return local_data
        data = pos_tool_init()
        PosToolConfig.save_local_pos_tool_config(data)
        return data

    @classmethod
    def get_store_list(cls, pos_path: str) -> (PosParamsModel, list[PosInitRespStoreModel], list[PosInitRespEnvModel]):
        res_data = [None, [], []]
        if not os.path.exists(pos_path):
            return res_data

        data = cls.read_pos_tool_config()
        if data:
            res_data[2] = data.data.env_list

        params = PosConfig.read_pos_params(pos_path)
        if params:
            res_data[0] = params

        # 只获取当前环境的store_list
        store_list = []
        env = PosConfig.get_local_pos_env(pos_path)
        group, account = PosConfig.get_pos_group(params.venderNo, env)
        if group:
            for store in data.data.store_list:
                if store.env == group and store.vender_id == params.venderNo:
                    store_list.append(store)
        res_data[1] = store_list
        return res_data