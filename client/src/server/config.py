import base64
import hashlib
import json
import os
from collections import defaultdict
from shutil import copytree, copyfile, rmtree
from typing import Optional

from loguru import logger
from mitmproxy.net.dns.domain_names import cache

from model.config import SearchConfigModel, MitmProxyConfigModel, PaymentMockConfigModel, StartConfigModel, \
    SetupConfigModel, PosParamsModel, PosConfigModel, PosChangeParamsModel, AgentConfigModel
from model.pos_network_model import PosInitRespStoreModel, PosInitRespEnvModel, PosInitRespModel
from utils.common import get_active_mac, get_local_ip
from utils.file_handle import IniFileHandel
from utils.pos_network import change_pos_from_network, pos_tool_init

if not os.path.exists("storage/data"):
    os.makedirs("storage/data")


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
        if not os.path.exists(cls.config_file):
            return []
        with open(cls.config_file, "r", encoding="utf-8") as f:
            try:
                return json.load(f).get("dir", [])
            except json.JSONDecodeError:
                logger.warning(f"读取工作目录文件失败:{cls.config_file}")
                return []

    @classmethod
    def save_work_dir(cls, dirs: list[str]):
        """
        保存工作目录
        """
        old_config = {}
        if os.path.exists(cls.config_file):
            with open(cls.config_file, "r", encoding="utf-8") as f:
                try:
                    old_config = json.load(f)
                except json.JSONDecodeError:
                    logger.warning(f"读取工作目录文件失败:{cls.config_file}")
                    return False

        old_config["dir"] = dirs or []

        with open(cls.config_file, "w", encoding="utf-8") as f:
            json.dump(old_config, f, ensure_ascii=False)
        return True

    @classmethod
    def add_work_dir(cls, dir: str):
        """
        新增工作目录
        """
        old_result = cls.read_work_dir()
        old_result.append(dir)
        cls.save_work_dir(old_result)

    @classmethod
    def remove_work_dir(cls, dir: str):
        """
        删除工作目录
        """
        old_result = cls.read_work_dir()
        old_result.remove(dir)
        cls.save_work_dir(old_result)

    @classmethod
    def save_search_result(cls, result: list[str]):
        """
        保存搜索结果
        """
        with open(cls.search_result_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False)

    @classmethod
    def read_search_result(cls) -> list[str]:
        if not os.path.exists(cls.search_result_file):
            return []
        with open(cls.search_result_file, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                logger.warning(f"读取搜索结果文件失败:{cls.search_result_file}")
                return []

    @classmethod
    def read(cls) -> SearchConfigModel:
        if not os.path.exists(cls.config_file):
            return SearchConfigModel()
        with open(cls.config_file) as f:
            config = json.load(f)
            return SearchConfigModel(**config)

    @classmethod
    def write(cls, data: dict | SearchConfigModel):
        if not isinstance(data, SearchConfigModel):
            data = SearchConfigModel.model_validate(data)
        data = data.model_dump()
        with open(cls.config_file, "w") as f:
            f.write(json.dumps(data, indent=4, ensure_ascii=False))


class MitmproxyConfig:
    config_file = "storage/data/config_mitmproxy.json"

    def __init__(self):
        pass

    @classmethod
    def read(cls) -> MitmProxyConfigModel:

        if not os.path.exists(cls.config_file):
            cls.write({})
            # return MitmProxyConfigModel()
        with open(cls.config_file) as f:
            config = json.load(f)
            return MitmProxyConfigModel(**config)

    @classmethod
    def write(cls, data: dict | MitmProxyConfigModel):
        if not isinstance(data, MitmProxyConfigModel):
            data = MitmProxyConfigModel.model_validate(data)
        data = data.model_dump()
        with open(cls.config_file, "w") as f:
            f.write(json.dumps(data, indent=4, ensure_ascii=False))


class PaymentMockConfig:
    config_file = "storage/data/config_payment_mock.json"

    def __init__(self):
        pass

    @classmethod
    def read(cls) -> PaymentMockConfigModel:
        if not os.path.exists(cls.config_file):
            return PaymentMockConfigModel()
        with open(cls.config_file) as f:
            config = json.load(f)
            return PaymentMockConfigModel(**config)

    @classmethod
    def write(cls, data: dict | PaymentMockConfigModel):
        if not isinstance(data, PaymentMockConfigModel):
            data = PaymentMockConfigModel.model_validate(data)
        data = data.model_dump()
        with open(cls.config_file, "w") as f:
            f.write(json.dumps(data, indent=4, ensure_ascii=False))

class StartConfig:
    config_file = "storage/data/config_pos_start.json"

    def __init__(self):
        pass

    @classmethod
    def read(cls) -> StartConfigModel:
        if not os.path.exists(cls.config_file):
            return StartConfigModel()
        with open(cls.config_file) as f:
            config = json.load(f)
            return StartConfigModel(**config)

    @classmethod
    def write(cls, data: dict | StartConfigModel):
        if not isinstance(data, StartConfigModel):
            data = StartConfigModel.model_validate(data)
        data = data.model_dump()
        with open(cls.config_file, "w") as f:
            f.write(json.dumps(data, indent=4, ensure_ascii=False))


class SetupConfig:
    config_file = "storage/data/config_pos_setup.json"

    def __init__(self):
        pass

    @classmethod
    def read(cls) -> SetupConfigModel:
        if not os.path.exists(cls.config_file):
            return SetupConfigModel()
        with open(cls.config_file) as f:
            config = json.load(f)
            return SetupConfigModel(**config)

    @classmethod
    def write(cls, data: dict | SetupConfigModel):
        if not isinstance(data, SetupConfigModel):
            data = SetupConfigModel.model_validate(data)
        data = data.model_dump()
        with open(cls.config_file, "w") as f:
            f.write(json.dumps(data, indent=4, ensure_ascii=False))
            logger.info(f"写入配置文件:{cls.config_file}")


class Config:
    search_config: SearchConfig = SearchConfig()
    start_config: StartConfig = StartConfig()
    setup_config: SetupConfig = SetupConfig()


class PosConfig:
    pos_path: str = "storage/data/config_pos.json"

    def __init__(self):
        pass

    @classmethod
    def read_pos_params(cls, pos_path: str) -> PosParamsModel | None:
        pos_dir = os.path.dirname(pos_path)
        params_file = os.path.join(pos_dir, "pos_params")
        if not os.path.exists(params_file):
            return None
        with open(params_file) as f:
            content = base64.b64decode(f.read().encode("utf-8")).decode("utf-8")
            content = eval(content)
            # content_str = json.dumps(content, indent=4, ensure_ascii=False)
            return PosParamsModel.model_validate(content)

    @classmethod
    def read_pos_config(cls) -> PosConfigModel:
        if not os.path.exists(cls.pos_path):
            data = PosConfigModel()
            with open(cls.pos_path, "w") as f:
                f.write(data.model_dump_json())
        else:
            with open(cls.pos_path, "r") as f:
                data = f.read()
                try:
                    data = json.loads(data)
                    data = PosConfigModel.model_validate(data)
                except Exception as e:
                    data = PosConfigModel()
        return data

        # if not os.path.exists(pos_path):
        #     return data
        # params = cls.read_pos_params(pos_path)
        # if params:
        #     data.pos_params = params
        # return data

    @classmethod
    def save_pos_config(cls, config: PosConfigModel):
        with open(cls.pos_path, "w") as f:
            f.write(config.model_dump_json())

    @classmethod
    def get_local_pos_env(cls, pos_file) -> str | None:
        """
        从本地pos.ini获取pos当前环境
        """
        if not os.path.exists(pos_file):
            logger.warning(f"POS文件不存在:{pos_file}")
            return None

        pos_dir = os.path.dirname(pos_file)
        pos_ini_file = os.path.join(pos_dir, "pos.ini")
        if not os.path.exists(pos_ini_file):
            logger.warning(f"pos.ini文件不存在:{pos_ini_file}")
            return None
        ini_file_handle = IniFileHandel(pos_ini_file)
        old_env = ini_file_handle.get_value("PosClient", "pos_env")
        return old_env

    @classmethod
    def change_pos_local_env(cls, pos_file, target_env_key: str) -> tuple[bool, str]:
        """
        要切换到对应环境的key：env_vendorId_store
        """

        if not os.path.exists(pos_file):
            logger.warning(f"POS文件不存在:{pos_file}")
            return False, "POS文件不存在"

        # 修改pos.ini
        pos_dir = os.path.dirname(pos_file)
        pos_ini_file = os.path.join(pos_dir, "pos.ini")
        if not os.path.exists(pos_ini_file):
            logger.warning(f"pos.ini文件不存在:{pos_ini_file}")
            return False, "pos.ini文件不存在"
        ini_file_handle = IniFileHandel(pos_ini_file)
        old_env = ini_file_handle.get_value("PosClient", "pos_env")
        if "test" in target_env_key.lower():
            env = "RTA_TEST"
        elif "uat" in target_env_key.lower():
            env = "RTA_UAT"
        else:
            env = "RTA"
        ini_file_handle.set_value("PosClient", "pos_env", env)
        ini_file_handle.write()

        pos_params = PosConfig.read_pos_params(pos_file)
        if pos_params is None:
            logger.warning(f"当前环境商家未知，将直接删除对应环境文件:{pos_file}")
            old_env = f"{old_env}"
        else:
            old_env = f"{old_env}_{pos_params.venderNo}_{pos_params.orgNo}"

        def copy_any_file(current_file, target_file):
            if os.path.exists(target_file):
                logger.warning(f"{target_file}文件已存在，将直接覆盖")

            if not os.path.exists(current_file):
                logger.warning(f"{current_file}文件不存在")
                return

            if os.path.isfile(current_file):
                copyfile(current_file, target_file)
                os.remove(current_file)
            else:
                copytree(current_file, target_file, dirs_exist_ok=True)
                rmtree(current_file)

        def backup_pos_env_file(pos_path: str, file_name: str, old_env_key: str, env_key: str):
            db_file = os.path.join(pos_path, file_name)
            # 备份当前数据
            db_old_env_file = os.path.join(pos_path, f"{file_name}_{old_env_key}")
            copy_any_file(db_file, db_old_env_file)
            # 恢复备份数据
            db_env_file = os.path.join(pos_path, f"{file_name}_{env_key}")
            copy_any_file(db_env_file, db_file)
        # 切换
        env_files = cls.read_pos_config().env_files
        for file in env_files:
            backup_pos_env_file(pos_dir, file, old_env, target_env_key)

        config_data = PosConfig.read_pos_config()
        # 更新当前备份过的环境key
        logger.info(f"{old_env}")
        logger.info(f"{target_env_key}")
        logger.info(f"{config_data.backup_envs.get(pos_file, [])}")
        if old_env not in config_data.backup_envs and old_env not in ["RTA_TEST", "RTA_UAT", "RTA"]:
            config_data.backup_envs[pos_file].append(old_env)
        if target_env_key not in ["RTA_TEST", "RTA_UAT", "RTA"]:
            config_data.backup_envs[pos_file].remove(target_env_key)
        PosConfig.save_pos_config(config_data)
        return True, "切换成功"

    @classmethod
    async def change_pos_on_network(cls, pos_path: str) -> tuple[bool, str]:
        env = PosConfig.get_local_pos_env(pos_path)
        if not env:
            logger.warning(f"获取pos环境失败:{pos_path}")
            return False, f"获取pos环境失败:{pos_path}"
        if env == "RTA_TEST":
            new_env = "rta-test"
        elif env == "RTA_UAT":
            new_env = "rta-uat"
        else:
            logger.warning(f"pos环境错误:{pos_path}")
            raise ValueError(f"pos环境错误:{env}")

        pos_info = cls.read_pos_params(pos_path)
        if not pos_info:
            logger.warning(f"获取pos_params参数失败:{pos_path}")
            return False, f"获取pos_params参数失败:{pos_path}"

        pos_group, account = cls.get_pos_group(pos_info.venderNo, env)
        if not pos_group:
            logger.warning(f"获取pos分组失败:{pos_path}")
            return False, f"获取pos分组失败:{pos_path}"
        mac = get_active_mac()
        ip = get_local_ip()
        data = PosChangeParamsModel()
        data.pos_mac = mac
        data.pos_ip = ip
        data.pos_type = pos_info.posType
        data.pos_group = int(pos_info.posGroupNo)
        data.venderId = pos_info.venderNo
        data.orgNo = pos_info.orgNo
        data.env = pos_group.lower()

        # data.pos_skin = pos_info.pos_skin
        # data.pos_no = pos_info.pos_no
        change_status, message_info = await change_pos_from_network(data)
        return change_status, message_info

    @classmethod
    def get_pos_group(cls, vendor_id: str, env: str) -> tuple[Optional[str], Optional[str]]:
        """
        根据商家和环境获取，环境分组和对应账号
        """
        pos_config = cls.read_pos_config()
        account = pos_config.vendor_account.get(int(vendor_id), None)
        if account and type(account) is list:
            account = account[0]
        if not account:
            account = ""
        if "test" in env.lower():
            return "rta-test", account
        for k, v in pos_config.env_group_vendor.items():
            if int(vendor_id) in v:
                return k, account
        return None, account

    @classmethod
    def clean_cache(cls, path) -> tuple[bool, str]:
        """
        清理缓存
        """
        if not os.path.exists(path):
            logger.info(f"pos文件不存在:{path}")
            return False, "pos文件不存在"

        cache_files = cls.read_pos_config().cache_files
        success = True
        msg = ""
        for cache_file in cache_files:
            cache_file = os.path.join(os.path.dirname(path), cache_file)
            if os.path.exists(cache_file):
                logger.info(f"清理缓存文件:{cache_file}")
                try:
                    os.remove(cache_file)
                except Exception as e:
                    logger.error(f"删除缓存文件失败:{cache_file}, 错误信息:{e}")
                    success = False
                    msg += f"删除缓存文件失败:{cache_file}, 错误信息:{e}\n"
        if success:
            msg = "清理缓存成功"
        return success, msg

    @classmethod
    def replace_mitm_cert(cls, pos_file) -> tuple[bool, str]:
        """
        替换mitm证书
        """
        file_dir = os.path.dirname(pos_file)

        # mitm_config = StartConfig.read()
        # if not mitm_config.replace_mitm_cert:
        #     return
        mitm_dir = MitmproxyConfig.read().mitmproxy_config_dir or os.path.join(os.path.expanduser("~"), ".mitmproxy")
        cert_file = mitm_dir + "/mitmproxy-ca-cert.pem"
        if not os.path.exists(cert_file):
            logger.error(f"mitmproxy-ca-cert.pem 不存在")
            return False, "mitmproxy-ca-cert.pem 不存在"
        with open(cert_file, "r", encoding="utf-8") as f:
            cert_content = f.read()
        with open(os.path.join(file_dir, "certifi/cacert.pem"), "r", encoding="utf-8") as f:
            old_content = f.read()
        if cert_content not in old_content:
            with open(os.path.join(file_dir, "certifi/cacert.pem"), "a+", encoding="utf-8") as f:
                f.write(f"\n\n# mitmproxy \n{cert_content}")
            return True, "替换mitm证书成功"
        return True, "mitm证书已存在，不用替换"

    @classmethod
    def backup_payment_driver(cls, pos_file):
        """
        备份支付驱动
        """
        pos_config = cls.read_pos_config()
        mock_dirver_dir = pos_config.payment_mock_driver_path
        if not os.path.exists(mock_dirver_dir):
            logger.error(f"支付mock驱动不存在:{mock_dirver_dir}，请设置支付mock驱动的目录")
            return
        backup_dir = pos_config.payment_mock_driver_backup_dir
        if not os.path.exists(backup_dir):
            pos_dir = os.path.dirname(pos_file)
            backup_dir = os.path.join(pos_dir, 'drive_backup')
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)

        for root, dirs, files in os.walk(mock_dirver_dir):
            for file in files:
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(os.path.dirname(file_path), mock_dirver_dir)
                backup_path = os.path.join(backup_dir, rel_path)
                old_payment_driver_dir = os.path.join(pos_dir, 'drive', rel_path)
                if not os.path.exists(backup_path):
                    os.makedirs(backup_path)
                # copytree(file_path, backup_path, dirs_exist_ok=True)
                old_driver_file = os.path.join(old_payment_driver_dir, file)
                if os.path.exists(old_driver_file):
                    copyfile(old_driver_file, os.path.join(backup_path, file))
                # os.makedirs(os.path.dirname(backup_path), exist_ok=True)
                # copytree(file_path, backup_path, dirs_exist_ok=True)

        # if not os.path.exists(cls.config_file):
        #     return
        # pos_key = hashlib.md5(pos_file.encode('utf-8')).hexdigest()

    @classmethod
    def restore_payment_driver(cls, pos_file):
        """
        恢复支付驱动
        """
        pos_dir = os.path.dirname(pos_file)
        backup_dir = os.path.join(pos_dir, 'drive_backup')
        if not os.path.exists(backup_dir):
            logger.warning(f"备份目录不存在:{backup_dir}")
            return
        copytree(backup_dir, os.path.join(pos_dir, 'drive'), dirs_exist_ok=True)

    @classmethod
    def cover_payment_driver(cls, pos_file):
        if not os.path.exists(pos_file):
            logger.warning(f"POS文件不存在:{pos_file}")
            return False, "POS文件不存在"
        drive_file = os.path.join(os.path.dirname(pos_file), 'drive')

        mock_file = os.path.abspath('drive')
        if not os.path.exists(mock_file):
            logger.warning(f"支付mock驱动不存在:{mock_file}")
            return False, "支付mock驱动不存在"
        logger.info(f"用mock驱动【{mock_file}】覆盖支付驱动:{drive_file}")
        # pos_key = hashlib.md5(pos_file.encode('utf-8')).hexdigest()
        copytree(mock_file, drive_file, dirs_exist_ok=True)
        return True, "覆盖支付驱动成功"

    @classmethod
    def clear_env(cls, pos_path: str):
        env_files = [
            "database",
            "log",
            "pos_params",
            "init_config.data",
            "charge_db"
        ]
        if not os.path.exists(pos_path):
            logger.warning(f"POS文件不存在:{pos_path}")
            return
        pos_dir = os.path.dirname(pos_path)
        for env_file in env_files:
            env_file = os.path.join(pos_dir, env_file)
            if os.path.exists(env_file):
                logger.info(f"清理缓存文件:{env_file}")
                try:
                    if os.path.isfile(env_file):
                        os.remove(env_file)
                    else:
                        rmtree(env_file)
                except Exception as e:
                    logger.error(f"删除缓存文件失败:{env_file}, 错误信息:{e}")


class PosToolConfig:
    config_file = "storage/data/pos_tool_ini_data.json"
    @classmethod
    def read_pos_tool_config(cls) -> PosInitRespModel:
        if os.path.exists(cls.config_file):
            with open(cls.config_file, "r", encoding="utf-8") as f:
                data = f.read()
                return PosInitRespModel.model_validate(json.loads(data))
        data = pos_tool_init()
        return data

    @classmethod
    def get_store_list(cls, pos_path: str) -> (str, str, list[PosInitRespStoreModel], list[PosInitRespEnvModel]):
        res_data = ["", "", [], []]
        if not os.path.exists(pos_path):
            return res_data

        data = cls.read_pos_tool_config()
        if data:
            res_data[3] = data.data.env_list

        params = PosConfig.read_pos_params(pos_path)
        if params:
            res_data[0] = params.venderNo
            res_data[1] = params.orgNo

        # 只获取当前环境的store_list
        store_list = []
        env = PosConfig.get_local_pos_env(pos_path)
        group, account = PosConfig.get_pos_group(params.venderNo, env)
        if group:
            for store in data.data.store_list:
                if store.env == group and store.vender_id == params.venderNo:
                    store_list.append(store)
        res_data[2] = store_list
        return res_data


class AgentConfig:
    config_path = "storage/data/agent_config.json"

    @classmethod
    def read_config(cls) -> AgentConfigModel:
        if not os.path.exists(cls.config_path):
            config = AgentConfigModel()
            with open(cls.config_path, "w", encoding="utf-8") as f:
                f.write(json.dumps(config.model_dump(), ensure_ascii=False))
            return config

        with open(cls.config_path, "r", encoding="utf-8") as f:
            data = f.read()
            if not data:
                config = AgentConfigModel()
                with open(cls.config_path, "w", encoding="utf-8") as f:
                    f.write(json.dumps(config.model_dump(), ensure_ascii=False))
                return config

            return AgentConfigModel.model_validate(json.loads(data))

    @classmethod
    def save_config(cls, config_data: AgentConfigModel):
        with open(cls.config_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(config_data.model_dump(), ensure_ascii=False))






if __name__ == "__main__":
    rmtree("C:\\myself\\tmp\\folder1\\111111.txt")