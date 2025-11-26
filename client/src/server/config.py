import asyncio
from shutil import rmtree
from typing import Optional

from do import config as do_config
from model.config import SearchConfigModel, MitmProxyConfigModel, StartConfigModel, \
    SetupConfigModel, PosParamsModel, PosConfigModel, AgentConfigModel, VendorConfigModel, FtpConfigModel
from model.pos_network_model import PosInitRespModel
from utils import pos_network


class SearchConfig:
    config_file = "storage/data/config_search.json"
    search_result_file = "storage/data/config_search_result.json"

    def __init__(self):
        pass

    @classmethod
    def read_work_dir(cls) -> list[str]:
        """
        读取工作目录
        """
        return do_config.SearchConfig.read_work_dir()

    @classmethod
    def save_work_dir(cls, dirs: list[str]):
        """
        保存工作目录
        """
        return do_config.SearchConfig.save_work_dir(dirs)

    @classmethod
    def add_work_dir(cls, dir: str):
        """
        新增工作目录
        """
        do_config.SearchConfig.add_work_dir(dir)

    @classmethod
    def remove_work_dir(cls, dir: str):
        """
        删除工作目录
        """
        do_config.SearchConfig.remove_work_dir(dir)

    @classmethod
    def save_search_result(cls, result: list[str]):
        """
        保存搜索结果
        """
        do_config.SearchConfig.save_search_result(result)

    @classmethod
    def read_search_result(cls) -> list[str]:
        return do_config.SearchConfig.read_search_result()

    @classmethod
    def read(cls) -> SearchConfigModel:
        return do_config.SearchConfig.read()

    @classmethod
    def write(cls, data: dict | SearchConfigModel):
        do_config.SearchConfig.write(data)


class MitmproxyConfig:
    def __init__(self):
        pass

    @classmethod
    def read(cls) -> MitmProxyConfigModel:
        return do_config.MitmproxyConfig.read()

    @classmethod
    def write(cls, data: dict | MitmProxyConfigModel):
        do_config.MitmproxyConfig.write(data)


class StartConfig:

    def __init__(self):
        pass

    @classmethod
    def read(cls) -> StartConfigModel:
        return do_config.StartConfig.read()

    @classmethod
    def write(cls, data: dict | StartConfigModel):
        do_config.StartConfig.write(data)


class SetupConfig:
    config_file = "storage/data/config_pos_setup.json"

    def __init__(self):
        pass

    @classmethod
    def read(cls) -> SetupConfigModel:
        return do_config.SetupConfig.read()

    @classmethod
    def write(cls, data: dict | SetupConfigModel):
        do_config.SetupConfig.write(data)


class Config:
    search_config: SearchConfig = SearchConfig()
    start_config: StartConfig = StartConfig()
    setup_config: SetupConfig = SetupConfig()


class PosConfig:
    def __init__(self):
        pass

    @classmethod
    def read_pos_params(cls, pos_path: str) -> PosParamsModel | None:
        local_params = do_config.PosConfig.read_pos_params(pos_path)
        if pos_path and not local_params:
            return pos_network.pos_init(pos_path)
        return local_params


    @classmethod
    def read_pos_config(cls) -> PosConfigModel:
        return do_config.PosConfig.read_pos_config()

    @classmethod
    def save_pos_config(cls, config: PosConfigModel):
        do_config.PosConfig.save_pos_config(config)

    @classmethod
    def get_vendor_config(cls, vendor_id) -> VendorConfigModel:
        return do_config.PosConfig.get_vendor_config(vendor_id)

    @classmethod
    def get_local_pos_env(cls, pos_file) -> str | None:
        """
        从本地pos.ini获取pos当前环境
        """
        return do_config.PosConfig.get_local_pos_env(pos_file)

    @classmethod
    def change_pos_local_env(cls, pos_file, target_env_key: str) -> tuple[bool, str]:
        """
        要切换到对应环境的key：env_vendorId_store
        """

        return do_config.PosConfig.change_pos_local_env(pos_file, target_env_key)

    @classmethod
    def get_pos_group(cls, vendor_id: str, env: str) -> tuple[Optional[str], Optional[str]]:
        """
        根据商家和环境获取，环境分组和对应账号
        """
        return do_config.PosConfig.get_pos_group(vendor_id, env)

    @classmethod
    def clean_cache(cls, path) -> tuple[bool, str]:
        """
        清理缓存
        """
        return do_config.PosConfig.clean_cache(path)

    @classmethod
    def replace_mitm_cert(cls, pos_file) -> tuple[bool, str]:
        """
        替换mitm证书
        """
        return do_config.PosConfig.replace_mitm_cert(pos_file)

    @classmethod
    def backup_payment_driver(cls, pos_file):
        """
        备份支付驱动
        """
        return do_config.PosConfig.backup_payment_driver(pos_file)

    @classmethod
    def restore_payment_driver(cls, pos_file):
        """
        恢复支付驱动
        """
        return do_config.PosConfig.restore_payment_driver(pos_file)

    @classmethod
    def cover_payment_driver(cls, pos_file):
        return do_config.PosConfig.cover_payment_driver(pos_file)

    @classmethod
    def clear_env(cls, pos_path: str):
        return do_config.PosConfig.clear_env(pos_path)


class PosToolConfig:
    @classmethod
    def read_local_pos_tool_config(cls) -> PosInitRespModel | None:
        return do_config.PosToolConfig.read_local_pos_tool_config()

    @classmethod
    def save_local_pos_tool_config(cls, data: PosInitRespModel) -> None:
        do_config.PosToolConfig.save_local_pos_tool_config(data)


class AgentConfig:
    @classmethod
    def read_config(cls) -> AgentConfigModel:
        return do_config.AgentConfig.read_config()

    @classmethod
    def save_config(cls, config_data: AgentConfigModel):
        do_config.AgentConfig.save_config(config_data)


class FtpConfig:
    @classmethod
    def read_config(cls) -> FtpConfigModel:
        return do_config.FtpConfig.read_config()

    @classmethod
    def save_config(cls, config_data: FtpConfigModel):
        do_config.FtpConfig.save_config(config_data)


if __name__ == "__main__":
    rmtree("C:\\myself\\tmp\\folder1\\111111.txt")
