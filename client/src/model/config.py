import os.path
from collections import defaultdict
from typing import Optional

from pydantic import BaseModel


class SearchConfigModel(BaseModel):
    dir: list[str] = ["c:/"]
    file_pattern: str = "cpos-df.exe"
    dir_pattern: str = "*"
    max_depth: str = "1"

class ProxyDelayConfigModel(BaseModel):
    enabled: bool = False
    delay: float = 0.0
    delay_path: list[str] = []

class MitmProxyConfigModel(BaseModel):
    """mitmproxy 配置"""
    port: int = 9080
    web_port: int = 9081
    web_open_browser: bool = False
    cert_path: str = ""
    script_path: str = ""
    is_mock: bool = False
    mitmproxy_config_dir: str = os.path.join(os.path.expanduser("~"), ".mitmproxy")
    proxy_client: str = ""
    proxy_model: str = "local"
    proxy_model_value: str = "CPOS-DF.exe"

    request_delay: ProxyDelayConfigModel = ProxyDelayConfigModel()
    response_delay: ProxyDelayConfigModel = ProxyDelayConfigModel()

    add_headers: str = ""
    add_body: str = ""
    exclude: str = ""
    include: str = ""
    open_include: bool = False
    open_exclude: bool = False
    mock_server: str = "https://testautoapi.rta-os.com/hrm/mock"

    model_config = {
        "extra": "allow"  # 允许未知字段
    }


class PaymentMockConfigModel(BaseModel):
    mock_files: str = ""
    back_dir: str = ""
    back_data: dict = dict()


class StartConfigModel(BaseModel):
    """POS启动配置"""
    backup: bool = False  # 备份支付配置
    replace_mitm_cert: bool = False  # 替换mitm证书
    change_env: bool = False  # 切换POS本地环境
    change_pos: bool = False  # 调用接口切换云端POS
    remove_cache: bool = False  # 清除缓存
    cover_payment_driver: bool = False  # 覆盖支付驱动
    account_logout: bool = False  # 退出登录


class PosParamsModel(BaseModel):
    posGroupNo: str = ""
    posType: str = ""
    orgNo: str = ""
    venderNo: str = ""


class PosChangeParamsModel(BaseModel):
    env: str = ""
    orgNo: str = ""  # 门店ID
    pos_group: Optional[str] = ""  # 收银台组
    pos_ip: str = ""
    pos_mac: str = ""
    pos_no: str = ""  # POS编号
    pos_skin: str = ""  # POS皮肤
    pos_type:str = ""  # POS类型:1POS,2SCO,4Combined
    switchMode: str = "1"  # 切换模式，1mac，2posno
    venderId: str = ""  # 厂商ID


class ResolutionModel(BaseModel):
    width: int = 1366
    height: int = 768
    c_width: int = 1366
    c_height: int = 768
    c_x: int = 1366


class PosResolutionModel(BaseModel):
    pos: ResolutionModel = ResolutionModel()
    sco: ResolutionModel = ResolutionModel()
    scan: ResolutionModel = ResolutionModel()


class VendorConfigModel(BaseModel):
    vendor_id: int|str = ""
    account: str|int = ""
    resolution: PosResolutionModel = PosResolutionModel()


class PosConfigModel(BaseModel):
    """POS配置"""
    pos_path: str = ""
    payment_driver_back_up_path: str = ""
    payment_mock_driver_path: str = ""
    env_files: list[str] = [
            "database",
            "log",
            "pos_params",
            "init_config.data",
            "charge_db"
        ]
    cache_files: list[str] = ['pos_params', "init_config.data", "charge_db"]
    env_group_vendor: dict[str, list] = {
                "rta-uat": [7, 9, 11],
                "rta-uat-gray03": [3, 50],
                "rta-uat-gray06": [12, 58949, 58959, 58984, 58969, 58989, 58964],
                "rta-uat-gray07": [],
                "rta-uat-gray08": [5, 10, 58938],
                "rta-test": [1],
            }
    vendor_config: list[VendorConfigModel] = [
                VendorConfigModel(vendor_id=3),
                VendorConfigModel(vendor_id=5),
                VendorConfigModel(vendor_id=7),
                VendorConfigModel(vendor_id=8),
                VendorConfigModel(vendor_id=9),
                VendorConfigModel(vendor_id=10),
                VendorConfigModel(vendor_id=11),
                VendorConfigModel(vendor_id=12),
                VendorConfigModel(vendor_id=13),
                VendorConfigModel(vendor_id=50),
                VendorConfigModel(vendor_id=58949),
                VendorConfigModel(vendor_id=58959),
                VendorConfigModel(vendor_id=58984),
                VendorConfigModel(vendor_id=58969),
                VendorConfigModel(vendor_id=58989),
                VendorConfigModel(vendor_id=58964),
                VendorConfigModel(vendor_id=58938),
                VendorConfigModel(vendor_id=1)
            ]
    pos_params: PosParamsModel = PosParamsModel()
    pos_start_params: PosParamsModel = PosParamsModel()
    running_pos_path: str = ""
    change_pos_params: PosChangeParamsModel = PosChangeParamsModel()
    account_logout_params: str = ""
    backup_envs: dict[str, list[str]] = defaultdict(list)  # 备份过的环境


class SetupConfigModel(BaseModel):
    """启动配置"""
    setup_mitmproxy: bool = False
    setup_pos: bool = False


class AgentConfigModel(BaseModel):
    current_server: str = ""
    server_list: dict[str, str] = {}
    show_logs: bool = False
    max_send_size: int = 1024