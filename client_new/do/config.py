# 直接数据操作
import base64
import json
import os
from shutil import copyfile, copytree, rmtree
from typing import Optional

from loguru import logger

from common.excptions import ConfigFileException
from model.config import (
    AgentConfigModel,
    FtpConfigModel,
    MitmProxyConfigModel,
    PluginConfigModel,
    PosConfigModel,
    PosParamsModel,
    SearchConfigModel,
    SetupConfigModel,
    SqliteQueryConfigModel,
    StartConfigModel,
    ThemeConfigModel,
    VendorConfigModel,
)
from model.pos_network_model import PosInitRespModel
from utils.common import get_client_root_dir
from utils.file_handle import IniFileHandel

# 数据目录基准：打包态固定为 exe 所在目录，源码态为 client_new 项目根。
# 不能用 cwd：快捷方式起始位置、脚本/计划任务启动都会让 cwd 漂移，
# 相对路径会导致配置静默散落到其他目录（与插件链路 PluginsConfig 同源问题）。
_DATA_DIR = get_client_root_dir() / "storage" / "data"
if not os.path.exists(_DATA_DIR):
    os.makedirs(_DATA_DIR)


def _data_file(file_name: str) -> str:
    """
    返回 storage/data 下指定配置文件的绝对路径。
    :param file_name: 配置文件名（如 config_pos.json）
    :return: 绝对路径字符串
    """
    return str(_DATA_DIR / file_name)


def _read_config_file(file_path: str, model_cls):
    """
    读取 JSON 配置文件并构造模型实例，统一"缺失/损坏"语义：
    - 文件不存在：返回默认模型（首次运行正常路径）；
    - 文件存在但内容损坏（JSON 解析失败或模型校验失败）：
      抛 ConfigFileException，绝不静默回退默认值——静默回退会让用户配置
      （host、商家配置等）被悄悄清空，问题只在事后才暴露。
    :param file_path: 配置文件绝对路径
    :param model_cls: Pydantic 模型类
    :return: 模型实例
    :raises ConfigFileException: 文件损坏时
    """
    if not os.path.exists(file_path):
        return model_cls()
    try:
        with open(file_path, encoding="utf-8") as f:
            config = json.load(f)
        return model_cls.model_validate(config)
    except Exception as e:
        logger.error(f"配置文件异常:{file_path}, {e}")
        raise ConfigFileException(f"配置文件异常:{file_path}: {e}") from e


class SearchConfig:
    config_file = _data_file("config_search.json")
    search_result_file = _data_file("config_search_result.json")
    def __init__(self):
        pass

    @classmethod
    def read_work_dir(cls) -> list[str]:
        """
        读取工作目录
        """
        if not os.path.exists(cls.config_file):
            return []
        with open(cls.config_file, encoding="utf-8") as f:
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
            with open(cls.config_file, encoding="utf-8") as f:
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
        with open(cls.search_result_file, encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                logger.warning(f"读取搜索结果文件失败:{cls.search_result_file}")
                return []

    @classmethod
    def read(cls) -> SearchConfigModel:
        return _read_config_file(cls.config_file, SearchConfigModel)

    @classmethod
    def write(cls, data: dict | SearchConfigModel):
        if not isinstance(data, SearchConfigModel):
            data = SearchConfigModel.model_validate(data)
        data = data.model_dump()
        with open(cls.config_file, "w") as f:
            f.write(json.dumps(data, indent=4, ensure_ascii=False))


class MitmproxyConfig:
    config_file = _data_file("config_mitmproxy.json")

    def __init__(self):
        pass

    @classmethod
    def read(cls) -> MitmProxyConfigModel:
        if not os.path.exists(cls.config_file):
            cls.write({})
        return _read_config_file(cls.config_file, MitmProxyConfigModel)

    @classmethod
    def write(cls, data: dict | MitmProxyConfigModel):
        if not isinstance(data, MitmProxyConfigModel):
            data = MitmProxyConfigModel.model_validate(data)
        data = data.model_dump()
        with open(cls.config_file, "w") as f:
            f.write(json.dumps(data, indent=4, ensure_ascii=False))


class PluginsConfig:
    @classmethod
    def _config_file(cls) -> str:
        """
        配置文件路径：统一锚定到应用根目录（打包态为 exe 目录）的 storage/data。
        早期用 cwd 相对路径，helper 子进程 cwd 可能是临时解压目录导致读不到配置，
        现由 _DATA_DIR 统一保证，开发/打包行为一致。
        :return: 配置文件路径
        """
        return _data_file("config_plugins.json")

    def __init__(self):
        pass

    @classmethod
    def read(cls) -> PluginConfigModel:
        """
        读取插件管理配置，文件不存在时用默认值初始化。
        :return: 插件配置模型
        """
        config_file = cls._config_file()
        if not os.path.exists(config_file):
            return PluginConfigModel()
        try:
            with open(config_file, encoding="utf-8") as f:
                config = json.load(f)
                return PluginConfigModel(**config)
        except Exception as e:
            logger.warning(f"读取插件配置失败:{config_file}, {e}")
            return PluginConfigModel()

    @classmethod
    def write(cls, data: dict | PluginConfigModel):
        """
        写入插件管理配置。
        :param data: 配置数据
        """
        if not isinstance(data, PluginConfigModel):
            data = PluginConfigModel.model_validate(data)
        data = data.model_dump()
        config_file = cls._config_file()
        os.makedirs(os.path.dirname(config_file), exist_ok=True)
        with open(config_file, "w", encoding="utf-8") as f:
            f.write(json.dumps(data, indent=4, ensure_ascii=False))


class StartConfig:
    config_file = _data_file("config_pos_start.json")

    def __init__(self):
        pass

    @classmethod
    def read(cls) -> StartConfigModel:
        return _read_config_file(cls.config_file, StartConfigModel)

    @classmethod
    def write(cls, data: dict | StartConfigModel):
        if not isinstance(data, StartConfigModel):
            data = StartConfigModel.model_validate(data)
        data = data.model_dump()
        with open(cls.config_file, "w") as f:
            f.write(json.dumps(data, indent=4, ensure_ascii=False))


class SetupConfig:
    config_file = _data_file("config_pos_setup.json")

    def __init__(self):
        pass

    @classmethod
    def read(cls) -> SetupConfigModel:
        return _read_config_file(cls.config_file, SetupConfigModel)

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
    pos_path: str = _data_file("config_pos.json")

    def __init__(self):
        self.pos_config = self.read_pos_config()

    @classmethod
    def read_pos_params(cls, pos_path: str) -> PosParamsModel | None:
        if not pos_path:
            return None
        if not os.path.exists(pos_path):
            return None
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
            return data
        # 文件损坏时不允许静默回退默认值：那会悄悄清掉用户的 host/商家配置，
        # 必须抛 ConfigFileException 让用户感知并修复
        return _read_config_file(cls.pos_path, PosConfigModel)

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
    def get_vendor_config(cls, vendor_id) -> VendorConfigModel:
        if not vendor_id:
            return VendorConfigModel()
        for i in cls.read_pos_config().vendor_config:
            if str(i.vendor_id) == str(vendor_id):
                return i
        return VendorConfigModel()

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

        pos_params = PosConfig.read_pos_params(pos_file)
        if pos_params is None:
            logger.warning(f"当前环境商家未知，将直接删除对应环境文件:{pos_dir}")
            old_env = f"{old_env}"
        else:
            old_env = f"{old_env}_{pos_params.venderNo}_{pos_params.orgNo}"

        def copy_any_file(current_file, target_file):
            if not os.path.exists(os.path.dirname(target_file)):
                os.makedirs(os.path.dirname(target_file))
            if os.path.exists(target_file):
                logger.warning(f"{target_file}文件已存在，将直接删除")
                if os.path.isfile(target_file):
                    # copyfile(current_file, target_file)
                    os.remove(target_file)
                else:
                    # copytree(current_file, target_file, dirs_exist_ok=True)
                    rmtree(target_file)
            if not os.path.exists(os.path.dirname(current_file)):
                os.makedirs(os.path.dirname(current_file))
                logger.warning(f"{current_file}文件不存在")
                return
            if not os.path.exists(current_file):
                logger.warning(f"{current_file}文件不存在")
                return

            os.rename(current_file, target_file)

        def backup_pos_env_file(pos_path: str, file_name: str, old_env_key: str):
            db_file = os.path.join(pos_path, file_name)
            # 备份当前数据
            db_old_env_file = os.path.join(pos_path, "pos_env_back", f"{old_env_key}", f"{file_name}")
            copy_any_file(db_file, db_old_env_file)

        def restore_pos_env_file(pos_path: str, file_name: str, env_key: str):
            db_file = os.path.join(pos_path, file_name)
            # 恢复备份数据
            db_env_file = os.path.join(pos_path, "pos_env_back", f"{env_key}", f"{file_name}")
            copy_any_file(db_env_file, db_file)

        # 切换
        env_files = cls.read_pos_config().env_files

        pos_config_data = cls.read_pos_config()
        if len(old_env.split("_")) <= 2:
            pos_config_data.backup_status = 2
            logger.info(f"环境位置不备份：{old_env}")
        logger.info(f"当前备份状态：{pos_config_data.backup_status}")
        if pos_config_data.backup_status != 2:
            logger.info("开始备份文件")
            pos_config_data.backup_status = 1
            cls.save_pos_config(pos_config_data)
            for file in env_files:
                backup_pos_env_file(pos_dir, file, old_env)

            pos_config_data.backup_status = 2
            cls.save_pos_config(pos_config_data)

        if pos_config_data.backup_status == 2:
            logger.info("开始恢复原备份文件")
            for file in env_files:
                restore_pos_env_file(pos_dir, file, target_env_key)

            pos_config_data.backup_status = 3
            cls.save_pos_config(pos_config_data)

        # 更新pos.ini
        logger.info("修改pos.ini")
        if "test" in target_env_key.lower():
            env = "RTA_TEST"
        elif "uat" in target_env_key.lower():
            env = "RTA_UAT"
        else:
            env = "RTA"
        ini_file_handle.set_value("PosClient", "pos_env", env)
        ini_file_handle.write()

        config_data = PosConfig.read_pos_config()
        # 更新当前备份过的环境key
        logger.info(f"{old_env}")
        logger.info(f"{target_env_key}")
        # logger.info(f"{config_data.backup_envs.get(pos_file, [])}")
        # if old_env not in config_data.backup_envs and old_env not in ["RTA_TEST", "RTA_UAT", "RTA"]:
        #     if pos_file not in config_data.backup_envs:
        #         config_data.backup_envs[pos_file] = []
        #     config_data.backup_envs[pos_file].append(old_env)
        # if target_env_key not in ["RTA_TEST", "RTA_UAT", "RTA"]:
        #     config_data.backup_envs[pos_file].remove(target_env_key)
        PosConfig.save_pos_config(config_data)
        return True, "切换成功"

    @classmethod
    def get_pos_group(cls, vendor_id: str, env: str) -> tuple[Optional[str], Optional[str]]:
        """
        根据商家和环境获取，环境分组和对应账号
        """
        pos_config = cls.read_pos_config()
        account = ""
        for i in pos_config.vendor_config:
            if vendor_id and str(i.vendor_id) == str(vendor_id):
                account = i.account
                break

        if account and type(account) is list:
            account = account[0]
        if not account:
            account = ""
        if env.lower() in ("rta_test", "kh_test_s"):
            return "rta-test", account
        elif env.lower() in ("rta_uat", "kh_test"):
            for k, v in pos_config.env_group_vendor.items():
                if vendor_id and int(vendor_id) in v:
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
            logger.error("mitmproxy-ca-cert.pem 不存在")
            return False, "mitmproxy-ca-cert.pem 不存在"
        with open(cert_file, encoding="utf-8") as f:
            cert_content = f.read()
        with open(os.path.join(file_dir, "certifi/cacert.pem"), encoding="utf-8") as f:
            old_content = f.read()
        if cert_content not in old_content:
            with open(os.path.join(file_dir, "certifi/cacert.pem"), "a+", encoding="utf-8") as f:
                f.write(f"\n\n# mitmproxy \n{cert_content}")
            return True, "替换mitm证书成功"
        return True, "mitm证书已存在，不用替换"

    @classmethod
    def _get_mock_package_dir(cls, pos_config: PosConfigModel) -> str | None:
        """
        解析支付 mock 包根目录（包内应包含 drive/ 和 mock/ 两个子目录）。

        取值优先级：配置 payment_mock_driver_path -> 应用根目录 payment_mock。
        不做旧语义兼容：源目录必须是包根，缺失或不存在返回 None（调用方报错）。
        :param pos_config: 当前 POS 配置
        :return: 包根目录绝对路径；未配置或目录不存在时返回 None
        """
        configured_dir = pos_config.payment_mock_driver_path
        if not configured_dir:
            configured_dir = str(get_client_root_dir() / "payment_mock")
        if not os.path.isdir(configured_dir):
            logger.warning(f"支付mock包目录不存在:{configured_dir}")
            return None
        return configured_dir

    @classmethod
    def backup_payment_driver(cls, pos_file):
        """
        备份支付驱动：把 POS 目录 drive 下与 mock 包 drive/ 内同名的文件备份出来。

        注意：备份/恢复只覆盖 drive 内文件，不涉及 mock 包 mock/ 映射到 POS 根目录的文件。

        目录取值：
        - mock 包根：配置 payment_mock_driver_path（内含 drive/、mock/），
          未配置时回退应用根目录 payment_mock；
        - 备份目录：配置 payment_driver_back_up_path，未配置（或目录不存在）时
          回退 POS 目录下 drive_backup。
        """
        pos_dir = os.path.dirname(pos_file)
        pos_config = cls.read_pos_config()

        mock_package_dir = cls._get_mock_package_dir(pos_config)
        if not mock_package_dir:
            logger.error("支付mock包目录未配置或不存在，无法备份支付驱动")
            return
        mock_drive_dir = os.path.join(mock_package_dir, "drive")

        # 备份目录：配置优先，目录不存在则回退 POS 目录下 drive_backup
        backup_dir = pos_config.payment_driver_back_up_path
        if not backup_dir or not os.path.exists(backup_dir):
            if backup_dir:
                logger.warning(f"配置的支付驱动备份目录不存在，回退POS目录drive_backup: {backup_dir}")
            backup_dir = os.path.join(pos_dir, "drive_backup")
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)
        logger.info(f"备份支付驱动: mock包drive={mock_drive_dir}, 备份目录={backup_dir}")

        for root, dirs, files in os.walk(mock_drive_dir):
            for file in files:
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(os.path.dirname(file_path), mock_drive_dir)
                backup_path = os.path.join(backup_dir, rel_path)
                old_payment_driver_dir = os.path.join(pos_dir, "drive", rel_path)
                if not os.path.exists(backup_path):
                    os.makedirs(backup_path)
                old_driver_file = os.path.join(old_payment_driver_dir, file)
                if os.path.exists(old_driver_file):
                    copyfile(old_driver_file, os.path.join(backup_path, file))

    @classmethod
    def restore_payment_driver(cls, pos_file):
        """
        恢复支付驱动
        """
        pos_dir = os.path.dirname(pos_file)
        backup_dir = os.path.join(pos_dir, "drive_backup")
        if not os.path.exists(backup_dir):
            logger.warning(f"备份目录不存在:{backup_dir}")
            return
        copytree(backup_dir, os.path.join(pos_dir, "drive"), dirs_exist_ok=True)

    @classmethod
    def cover_payment_driver(cls, pos_file) -> tuple[bool, str]:
        """
        用支付 mock 包覆盖 POS 驱动。

        mock 包结构（配置项填包根目录）：
        - drive/：整体内容复制到 POS 目录下 drive/，同名覆盖、原有其他文件保留；
        - mock/：整体内容复制到 POS 安装根目录，同名覆盖、原有其他文件保留。

        未配置 payment_mock_driver_path 时使用应用根目录下的 payment_mock 包。
        """
        if not os.path.exists(pos_file):
            logger.warning(f"POS文件不存在:{pos_file}")
            return False, "POS文件不存在"
        pos_dir = os.path.dirname(pos_file)

        mock_package_dir = cls._get_mock_package_dir(cls.read_pos_config())
        if not mock_package_dir:
            msg = (
                "支付mock包目录未配置或不存在，请在 POS 设置中配置"
                "（目录内应包含 drive 和 mock 两个子目录）"
            )
            logger.warning(msg)
            return False, msg

        mock_drive_dir = os.path.join(mock_package_dir, "drive")
        mock_root_dir = os.path.join(mock_package_dir, "mock")
        if not os.path.isdir(mock_drive_dir) and not os.path.isdir(mock_root_dir):
            msg = f"支付mock包结构不正确:{mock_package_dir}（缺少 drive 或 mock 子目录）"
            logger.warning(msg)
            return False, msg

        # drive/ -> POS/drive：同名覆盖、无则新增、原有其他文件保留
        if os.path.isdir(mock_drive_dir):
            drive_target = os.path.join(pos_dir, "drive")
            logger.info(f"用mock包drive【{mock_drive_dir}】覆盖支付驱动:{drive_target}")
            copytree(mock_drive_dir, drive_target, dirs_exist_ok=True)

        # mock/ -> POS 安装根目录：同名覆盖、无则新增、原有其他文件保留
        if os.path.isdir(mock_root_dir):
            logger.info(f"用mock包mock【{mock_root_dir}】覆盖POS根目录:{pos_dir}")
            copytree(mock_root_dir, pos_dir, dirs_exist_ok=True)

        return True, "覆盖支付驱动成功"

    @classmethod
    def clear_env(cls, pos_path: str):
        env_files = ["database", "log", "pos_params", "init_config.data", "charge_db"]
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
    config_file = _data_file("pos_tool_ini_data.json")

    @classmethod
    def read_local_pos_tool_config(cls) -> PosInitRespModel | None:
        if not os.path.exists(cls.config_file):
            return None
        with open(cls.config_file, encoding="utf-8") as f:
            data = f.read()
        if not data:
            return None
        try:
            return PosInitRespModel.model_validate(json.loads(data))
        except Exception as e:
            logger.error(f"配置文件异常:{cls.config_file}, {e}")
            raise ConfigFileException(f"配置文件异常:{cls.config_file}: {e}") from e

    @classmethod
    def save_local_pos_tool_config(cls, data: PosInitRespModel) -> None:
        with open(cls.config_file, "w", encoding="utf-8") as f:
            f.write(json.dumps(data.model_dump(), indent=4, ensure_ascii=False))

    @classmethod
    def clear_local_pos_tool_config(cls) -> None:
        if os.path.exists(cls.config_file):
            os.remove(cls.config_file)


class AgentConfig:
    config_path = _data_file("agent_config.json")

    @classmethod
    def read_config(cls) -> AgentConfigModel:
        if not os.path.exists(cls.config_path):
            config = AgentConfigModel()
            with open(cls.config_path, "w", encoding="utf-8") as f:
                f.write(json.dumps(config.model_dump(), ensure_ascii=False))
            return config

        with open(cls.config_path, encoding="utf-8") as f:
            data = f.read()
        if not data:
            config = AgentConfigModel()
            with open(cls.config_path, "w", encoding="utf-8") as f:
                f.write(json.dumps(config.model_dump(), ensure_ascii=False))
            return config

        try:
            return AgentConfigModel.model_validate(json.loads(data))
        except Exception as e:
            logger.error(f"配置文件异常:{cls.config_path}, {e}")
            raise ConfigFileException(f"配置文件异常:{cls.config_path}: {e}") from e

    @classmethod
    def save_config(cls, config_data: AgentConfigModel):
        with open(cls.config_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(config_data.model_dump(), ensure_ascii=False))


class SqliteQueryConfig:
    config_path = _data_file("sqlite_query_config.json")

    @classmethod
    def read_config(cls) -> SqliteQueryConfigModel:
        if not os.path.exists(cls.config_path):
            config = SqliteQueryConfigModel()
            with open(cls.config_path, "w", encoding="utf-8") as f:
                f.write(json.dumps(config.model_dump(), ensure_ascii=False))
            return config

        with open(cls.config_path, encoding="utf-8") as f:
            data = f.read()
        if not data:
            config = SqliteQueryConfigModel()
            with open(cls.config_path, "w", encoding="utf-8") as f:
                f.write(json.dumps(config.model_dump(), ensure_ascii=False))
            return config

        try:
            return SqliteQueryConfigModel.model_validate(json.loads(data))
        except Exception as e:
            logger.error(f"配置文件异常:{cls.config_path}, {e}")
            raise ConfigFileException(f"配置文件异常:{cls.config_path}: {e}") from e

    @classmethod
    def save_config(cls, config_data: SqliteQueryConfigModel):
        with open(cls.config_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(config_data.model_dump(), ensure_ascii=False))


class FtpConfig:
    config_path = _data_file("ftp_config.json")

    @classmethod
    def read_config(cls) -> FtpConfigModel:
        if not os.path.exists(cls.config_path):
            config = FtpConfigModel()
            with open(cls.config_path, "w", encoding="utf-8") as f:
                f.write(json.dumps(config.model_dump(), ensure_ascii=False))
            return config

        with open(cls.config_path, encoding="utf-8") as f:
            data = f.read()
        if not data:
            config = FtpConfigModel()
            with open(cls.config_path, "w", encoding="utf-8") as f:
                f.write(json.dumps(config.model_dump(), ensure_ascii=False))
            return config

        try:
            return FtpConfigModel.model_validate(json.loads(data))
        except Exception as e:
            logger.error(f"配置文件异常:{cls.config_path}, {e}")
            raise ConfigFileException(f"配置文件异常:{cls.config_path}: {e}") from e

    @classmethod
    def save_config(cls, config_data: FtpConfigModel):
        with open(cls.config_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(config_data.model_dump(), ensure_ascii=False))


class ThemeConfig:
    config_path = _data_file("theme_config.json")

    @classmethod
    def read_config(cls) -> ThemeConfigModel:
        if not os.path.exists(cls.config_path):
            config = ThemeConfigModel()
            with open(cls.config_path, "w", encoding="utf-8") as f:
                f.write(json.dumps(config.model_dump(), ensure_ascii=False))
            return config

        with open(cls.config_path, encoding="utf-8") as f:
            data = f.read()
        if not data:
            config = ThemeConfigModel()
            with open(cls.config_path, "w", encoding="utf-8") as f:
                f.write(json.dumps(config.model_dump(), ensure_ascii=False))
            return config

        try:
            return ThemeConfigModel.model_validate(json.loads(data))
        except Exception as e:
            logger.error(f"配置文件异常:{cls.config_path}, {e}")
            raise ConfigFileException(f"配置文件异常:{cls.config_path}: {e}") from e

    @classmethod
    def save_config(cls, config_data: ThemeConfigModel):
        with open(cls.config_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(config_data.model_dump(), ensure_ascii=False))


if __name__ == "__main__":
    rmtree("C:\\myself\\tmp\\folder1\\111111.txt")
