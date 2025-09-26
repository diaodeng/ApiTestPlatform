import os.path

from pydantic import BaseModel


class SearchConfigModel(BaseModel):
    dir: list[str] = ["c:/"]
    file_pattern: str = "*.exe"
    dir_pattern: str = ""
    max_depth: str = "1"


class MitmProxyConfigModel(BaseModel):
    """mitmproxy 配置"""
    port: int = 8080
    web_port: int = 8081
    web_open_browser: bool = False
    cert_path: str = ""
    script_path: str = ""
    is_mock: bool = False
    mitmproxy_config_dir: str = os.path.join(os.path.expanduser("~"), ".mitmproxy")
    proxy_client: str = ""
    proxy_model: str = "local"
    proxy_model_value: str = "CPOS-DF.exe"

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


class PosParamsModel(BaseModel):
    posGroupNo: str = ""
    posType: str = ""
    orgNo: str = ""
    venderNo: str = ""


class PosChangeParamsModel(BaseModel):
    env: str = ""
    orgNo: str = ""  # 门店ID
    pos_group: int = 1  # 收银台组
    pos_ip: str = ""
    pos_mac: str = ""
    pos_no: str = ""  # POS编号
    pos_skin: str = ""  # POS皮肤
    pos_type:str = ""  # POS类型
    switchMode: str = "1"  # 切换模式，1mac，2posno
    venderId: str = ""  # 厂商ID


class PosConfigModel(BaseModel):
    """POS配置"""
    pos_path: str = ""
    payment_driver_back_up_path: str = ""
    payment_mock_driver_path: str = ""
    env_files: list[str] = []
    cache_files: list[str] = []
    pos_params: PosParamsModel = PosParamsModel()
    pos_start_params: PosParamsModel = PosParamsModel()
    running_pos_path: str = ""


class SetupConfigModel(BaseModel):
    """启动配置"""
    setup_mitmproxy: bool = False
    setup_pos: bool = False
