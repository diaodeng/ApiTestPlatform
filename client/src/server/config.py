import base64
import hashlib
import json
import os
from shutil import copytree, copyfile, rmtree
from loguru import logger
from mitmproxy.net.dns.domain_names import cache

from model.config import SearchConfigModel, MitmProxyConfigModel, PaymentMockConfigModel, StartConfigModel, \
    SetupConfigModel, PosParamsModel, PosConfigModel, PosChangeParamsModel
from utils.common import get_active_mac, get_local_ip
from utils.file_handle import IniFileHandel
from utils.pos_network import change_pos_from_network

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

    @classmethod
    def clean_cache(cls, path) -> tuple[bool, str]:
        """
        清理缓存
        """
        if not os.path.exists(path):
            logger.info(f"pos文件不存在:{path}")
            return False, "pos文件不存在"

        cache_files = ['pos_params', "init_config.data", "charge_db"]
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
        mock_dirver_dir = os.path.abspath('drive')
        if not os.path.exists(mock_dirver_dir):
            logger.error(f"支付mock驱动不存在:{mock_dirver_dir}")
            return

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
    def get_pos_env(cls, pos_file) -> str | None:
        if not os.path.exists(pos_file):
            logger.warning(f"POS文件不存在:{pos_file}")
            return None

        # 修改pos.ini
        pos_dir = os.path.dirname(pos_file)
        pos_ini_file = os.path.join(pos_dir, "pos.ini")
        if not os.path.exists(pos_ini_file):
            logger.warning(f"pos.ini文件不存在:{pos_ini_file}")
            return None
        ini_file_handle = IniFileHandel(pos_ini_file)
        old_env = ini_file_handle.get_value("PosClient", "pos_env")
        return old_env

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

    @classmethod
    def change_env(cls, pos_file, env: str) -> tuple[bool, str]:

        if not os.path.exists(pos_file):
            logger.warning(f"POS文件不存在:{pos_file}")
            return False, "POS文件不存在"
        if env not in ["RTA_TEST", "RTA_UAT", "RTA"]:
            logger.warning(f"环境参数错误:{env}")
            return False, "环境参数错误"

        # 修改pos.ini
        pos_dir = os.path.dirname(pos_file)
        pos_ini_file = os.path.join(pos_dir, "pos.ini")
        if not os.path.exists(pos_ini_file):
            logger.warning(f"pos.ini文件不存在:{pos_ini_file}")
            return False, "pos.ini文件不存在"
        ini_file_handle = IniFileHandel(pos_ini_file)
        old_env = ini_file_handle.get_value("PosClient", "pos_env")
        if old_env == env:
            logger.warning(f"原环境就是【{env}】不用切换: old_env: {old_env}")
            return False, "原环境就是【{env}】不用切换"
        ini_file_handle.set_value("PosClient", "pos_env", env)
        ini_file_handle.write()

        def change_dir_env(pos_path: str, file_name: str, old_env: str, env: str):
            db_file = os.path.join(pos_path, file_name)
            if not os.path.exists(db_file):
                logger.warning(f"{file_name}文件不存在:{db_file}")
            else:
                # 备份老环境
                db_old_env_file = os.path.join(pos_path, f"{file_name}_{old_env}")
                if os.path.exists(db_old_env_file):
                    logger.warning(f"{file_name}_env文件已存在，将直接覆盖:{db_old_env_file}")
                copytree(db_file, db_old_env_file, dirs_exist_ok=True)
                # 备份后删除
                rmtree(db_file)
            # 恢复备份数据
            db_env_file = os.path.join(pos_path, f"{file_name}_{env}")
            if not os.path.exists(db_env_file):
                logger.warning(f"{file_name}_env文件不存在:{db_env_file}")
            else:
                copytree(db_env_file, db_file, dirs_exist_ok=True)

        def change_file_env(pos_path: str, file_name: str, old_env: str, env: str):
            db_file = os.path.join(pos_path, file_name)
            if not os.path.exists(db_file):
                logger.warning(f"{file_name}文件不存在:{db_file}")
            else:
                # 备份老环境
                db_old_env_file = os.path.join(pos_path, f"{file_name}_{old_env}")
                if os.path.exists(db_old_env_file):
                    logger.warning(f"{file_name}_{old_env}文件已存在，将直接覆盖:{db_old_env_file}")
                copyfile(db_file, db_old_env_file)
                # 备份后删除
                os.remove(db_file)
            # 恢复备份数据
            db_env_file = os.path.join(pos_path, f"{file_name}_{env}")
            if not os.path.exists(db_env_file):
                logger.warning(f"{file_name}_env文件不存在:{db_env_file}")
            else:
                copyfile(db_env_file, db_file)

        # 切换database
        change_dir_env(pos_dir, "database", old_env, env)

        # 切换log
        change_dir_env(pos_dir, "log", old_env, env)

        # 切换缓存
        cache_files = ['pos_params', "init_config.data", "charge_db"]
        for file in cache_files:
            change_file_env(pos_dir, file, old_env, env)
        return True, "切换成功"

    @classmethod
    def restore(cls, pos_file):
        if not os.path.exists(cls.config_file):
            return
        with open(cls.config_file) as f:
            config = json.load(f)
            if "back_data" not in config:
                return
            if pos_file not in config["back_data"]:
                return
            config = config["back_data"][pos_file]
            with open(cls.config_file, "w") as f:
                f.write(json.dumps(config, indent=4, ensure_ascii=False))


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
    def read_pos_config(cls, pos_path: str) -> PosConfigModel:
        data = PosConfigModel()
        if not os.path.exists(pos_path):
            return data
        params = cls.read_pos_params(pos_path)
        if params:
            data.pos_params = params

    @classmethod
    def change_pos(cls, pos_path: str) -> bool:
        env = PaymentMockConfig.get_pos_env(pos_path)
        if not env:
            logger.warning(f"获取pos环境失败:{pos_path}")
            return False
        if env == "RTA_TEST":
            new_env = "rta-test"
        elif env == "RTA_UAT":
            new_env = "rta-uat"
        else:
            logger.warning(f"pos环境错误:{pos_path}")
            return False

        pos_info = cls.read_pos_params(pos_path)
        if not pos_info:
            logger.warning(f"获取pos_params参数失败:{pos_path}")
            return False

        pos_group = cls.get_pos_group(pos_info.venderNo, env)
        if not pos_group:
            logger.warning(f"获取pos分组失败:{pos_path}")
            return False
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
        return change_pos_from_network(data)

    @classmethod
    def get_pos_group(cls, vender_id: str, env: str) -> str|None:
        data = {
            "RTA_UAT": {
                "stable": [7, 9],
                "gray02": [11],
                "gray03": [3,50],
                "gray06": [12,58949,58959,58984,58969,58989,58964],
                "gray07": [],
                "gray08": [5, 10, 58938],
            },
            "RTA_TEST": {
                "stable": [1],
            }
        }
        if env == "RTA_TEST":
            return "rta-test"
        for k, v in data[env].items():
            if int(vender_id) in v:
                return f"rta-uat-{k}"
        return None


if __name__ == "__main__":
    PosConfig.read_pos_params("C:\\CPOS-DF-SM-1.0.0.0\\pos_params")
