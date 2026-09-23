import json

import httpx
from loguru import logger

from common.excptions import PosHandleException
from do.config import PosConfig
from model.config import PosChangeParamsModel, PosConfigModel, PosParamsModel
from model.pos_network_model import (
    PosInitRespModel,
    PosLogoutModel,
    PosResetAccountRequestModel,
    PosUserInfoRespModel,
)
from utils.http_defaults import DEFAULT_HTTP_TIMEOUT
from utils.common import ExeVersionReader, get_active_mac, get_local_ip

# 模块导入时读取 POS 配置中的服务地址。
# config_pos.json 损坏时不能让 import 失败（否则整个应用无法启动）：
# 记录 critical 日志、host 置空降级，应用打开后 POS 页 bootstrap 会提示"配置文件异常"，
# 远程操作则走 _require_host 的未配置提示。
try:
    pos_config_data = PosConfig.read_pos_config()
except Exception as _e:
    import sys as _sys

    logger.critical(f"config_pos.json 读取失败，服务地址降级为空: {_e}")
    _sys.stderr.write(f"config_pos.json 读取失败: {_e}\n")
    pos_config_data = PosConfigModel()
uat_host = pos_config_data.pos_tool_uat_host
test_host = pos_config_data.pos_tool_test_host
pos_test_host = pos_config_data.pos_test_host
pos_uat_host = pos_config_data.pos_uat_host
pos_pro_host = pos_config_data.pos_pro_host


def update_network_host(data: PosConfigModel):
    # pos_config_data = PosConfig.read_pos_config()
    pos_config_data = data
    global uat_host
    global test_host
    global pos_test_host
    global pos_uat_host
    global pos_pro_host

    uat_host = pos_config_data.pos_tool_uat_host
    test_host = pos_config_data.pos_tool_test_host
    pos_test_host = pos_config_data.pos_test_host
    pos_uat_host = pos_config_data.pos_uat_host
    pos_pro_host = pos_config_data.pos_pro_host


def _require_host(host: str, name: str) -> str:
    """
    校验服务地址已配置，未配置时给出明确业务提示。

    host 为空时 httpx 会抛 InvalidURL 并被上层 except Exception 吞掉，
    用户只能看到笼统的"获取失败"，这里提前拦截并说明真实原因。
    :param host: 待使用的服务地址
    :param name: 服务名称（用于提示语）
    :return: 原样返回 host
    :raises PosHandleException: host 未配置时
    """
    if not str(host or "").strip():
        raise PosHandleException(
            f"{name}服务地址未配置，请在 POS 设置中填写服务地址或使用同步配置"
        )
    return host


def change_pos_from_network(data: PosChangeParamsModel) -> None:
    with httpx.Client(verify=False, timeout=DEFAULT_HTTP_TIMEOUT) as client:
        data_info = {
            "env": data.env,
            "venderId": data.venderId,
            "orgNo": data.orgNo,
            "pos_ip": data.pos_ip,
            "pos_mac": data.pos_mac,
            "pos_type": data.pos_type,
            "pos_group": data.pos_group,
            "pos_skin": data.pos_skin,
            "switchMode": data.switchMode,
            "pos_no": data.pos_no,
        }
        logger.info(f"c： {json.dumps(data_info)}")
        if "test" in data_info["env"].lower():
            resp = client.post(f"{_require_host(test_host, 'POS工具Test')}/tools/posChange", json=data_info)
        elif "uat" in data_info["env"].lower():
            resp = client.post(f"{_require_host(uat_host, 'POS工具UAT')}/tools/posChange", json=data_info)
        else:
            raise Exception("非测试及UAT环境，禁止切换POS")
        if resp.status_code != 200:
            logger.error(f"POS切换失败，状态码： {resp.status_code}")
            raise PosHandleException(f"POS切换失败，状态码： {resp.status_code}")
        content = resp.json()
        logger.info(f"POS切换结果： {json.dumps(content, ensure_ascii=False)}")
        if content["code"] != 20000:
            raise PosHandleException(f"POS切换失败: {content['message']}")


def pos_account_logout(data: PosLogoutModel) -> tuple[bool, str]:
    with httpx.Client(verify=False, timeout=DEFAULT_HTTP_TIMEOUT) as client:
        data_info = data.model_dump()
        logger.info(f"POS账号注销参数： {json.dumps(data_info)}")
        if "uat" in data_info["env"].lower():
            resp = client.post(f"{_require_host(uat_host, 'POS工具UAT')}/tools/kickOut", json=data_info)
        else:
            resp = client.post(f"{_require_host(test_host, 'POS工具Test')}/tools/kickOut", json=data_info)
        if resp.status_code != 200:
            logger.error(f"POS切换失败，状态码： {resp.status_code}")
            return False, f"POS切换失败，状态码： {resp.status_code}"
        content = resp.json()
        logger.info(f"POS切换结果： {json.dumps(content, ensure_ascii=False)}")
        if content["code"] == 20000 or (
            content["code"] == 40000 and content["message"] == "账号未登录"
        ):
            return True, "踢出账号成功"
        return False, content["message"]


def pos_tool_init() -> PosInitRespModel | bool:
    with httpx.Client(verify=False, timeout=DEFAULT_HTTP_TIMEOUT) as client:
        resp = client.get(f"{_require_host(test_host, 'POS工具Test')}/tools/init")
        if resp.status_code != 200:
            logger.error(f"POS初始化失败，状态码： {resp.status_code}")
            return False
        content = resp.json()
        logger.info(f"POS初始化结果： {json.dumps(content, ensure_ascii=False)}")
        if content["code"] == 20000:
            return PosInitRespModel(**content)
        return False


async def get_user_info(
    data: PosResetAccountRequestModel,
) -> PosUserInfoRespModel | None:
    async with httpx.AsyncClient(
        verify=False,
        timeout=DEFAULT_HTTP_TIMEOUT,
    ) as client:
        data_info = data.model_dump()
        logger.info(f"查询POS账号信息： {json.dumps(data_info)}")
        if "uat" in data_info["env"].lower():
            resp = await client.post(f"{_require_host(uat_host, 'POS工具UAT')}/tools/getuserinfo", json=data_info)
        else:
            resp = await client.post(f"{_require_host(test_host, 'POS工具Test')}/tools/getuserinfo", json=data_info)
        if resp.status_code != 200:
            logger.error(f"查询POS账号信息失败，状态码： {resp.status_code}")
            return None
        content = resp.json()
        logger.info(f"查询POS账号信息结果： {json.dumps(content, ensure_ascii=False)}")
        if content["code"] == 20000:
            return PosUserInfoRespModel.model_validate(content["data"][0])
        return None


async def reset_account_password(data: PosResetAccountRequestModel) -> tuple[bool, str]:
    user_info = await get_user_info(data)
    if not user_info:
        return False, "获取用户信息失败"
    data.userid = user_info.user_id
    data.username = user_info.user_name

    async with httpx.AsyncClient(
        verify=False,
        timeout=DEFAULT_HTTP_TIMEOUT,
    ) as client:
        data_info = data.model_dump()
        logger.info(f"重置POS账号密码： {json.dumps(data_info, ensure_ascii=False)}")
        if "uat" in data_info["env"].lower():
            resp = await client.post(f"{_require_host(uat_host, 'POS工具UAT')}/tools/resetpwd", json=data_info)
        else:
            resp = await client.post(f"{_require_host(test_host, 'POS工具Test')}/tools/resetpwd", json=data_info)
        if resp.status_code != 200:
            logger.error(f"重置POS账号密码失败，状态码： {resp.status_code}")
            return False, f"重置密码失败: {resp.status_code}"
        content = resp.json()
        logger.info(f"重置POS账号密码结果： {json.dumps(content, ensure_ascii=False)}")
        if content["code"] == 20000:
            return True, "重置密码成功"
        return False, f"重置密码失败: {json.dumps(content, ensure_ascii=False)}"


def pos_init(pos_path: str, version: str = "", group: str = "") -> PosParamsModel:
    ip = get_local_ip()
    mac = get_active_mac()
    pos_vender_config = ""
    pos_version = ExeVersionReader(pos_path).get_exe_file_version()
    local_params = PosConfig.read_pos_params(pos_path)
    if local_params:
        pos_vender_config = PosConfig.get_vendor_config(local_params.venderNo)
    headers = {}
    if pos_vender_config:
        ch = pos_vender_config.custum_headers
        if ch:
            headers = ch

    with httpx.Client(verify=False, timeout=DEFAULT_HTTP_TIMEOUT) as client:
        data = {
            "configTypeList": [],
            "extParams": {"picType": "base64"},
            "posIP": [ip],
            "posMacList": [mac],
            "versionType": "1",
        }

        if pos_version:
            data["posVersion"] = pos_version
        env = PosConfig.get_local_pos_env(pos_path)
        if not env:
            env = "test"

        logger.info(f"pos/init参数： {json.dumps(data, ensure_ascii=False)}")
        if "uat" in env.lower() or "kh_test_s" in env.lower():
            resp = client.post(f"{_require_host(pos_uat_host, 'POS UAT')}/pos/init", json=data, headers=headers)
        elif "test" in env.lower() or "kh_test" in env.lower():
            resp = client.post(f"{_require_host(pos_test_host, 'POS Test')}/pos/init", json=data, headers=headers)
        else:
            resp = client.post(f"{_require_host(pos_pro_host, 'POS 生产')}/pos/init", json=data, headers=headers)
        if resp.status_code != 200:
            logger.error(
                f"获取pos初始配置（pos/init）失败，状态码： {resp.status_code}"
            )
            raise ConnectionError(
                f"获取pos初始配置（pos/init）失败: {resp.status_code}"
            )
        content = resp.json()
        _log_pos_init_result(content, len(resp.content))
        if content["code"] != "0000":
            raise PosHandleException(
                f"从网络获取pos/init失败: {_build_pos_init_result_summary(content, len(resp.content))}"
            )
        res_data = content.get("data", {})
        res_model = PosParamsModel.model_validate(res_data)
        res_model.is_local = False
        return res_model


def _log_pos_init_result(content: dict, response_size: int) -> None:
    """
    记录 POS 初始化接口的安全摘要，避免超大配置和敏感字段进入客户端日志。

    :param content: pos/init 接口解析后的响应数据。
    :param response_size: 原始 HTTP 响应字节数，用于判断响应规模。
    """
    logger.info(
        f"获取pos初始配置（pos/init）结果摘要: {_build_pos_init_result_summary(content, response_size)}"
    )


def _build_pos_init_result_summary(content: dict, response_size: int) -> str:
    """
    构造不包含配置正文和敏感字段的 POS 初始化结果摘要。

    :param content: pos/init 接口解析后的响应数据。
    :param response_size: 原始 HTTP 响应字节数，用于判断响应规模。
    :return: 可安全记录或作为异常消息返回的结果摘要。
    """
    data = content.get("data") if isinstance(content, dict) else None
    data = data if isinstance(data, dict) else {}
    code = content.get("code") if isinstance(content, dict) else "-"
    success = content.get("success") if isinstance(content, dict) else "-"
    return (
        f"code={code}, success={success}, venderNo={data.get('venderNo', '-')}, "
        f"orgNo={data.get('orgNo', '-')}, posId={data.get('posId', '-')}, "
        f"posType={data.get('posType', '-')}, responseBytes={response_size}"
    )


if __name__ == "__main__":
    ip = get_local_ip()
    mac = get_active_mac()
    version = ""
    with httpx.Client(verify=False, timeout=DEFAULT_HTTP_TIMEOUT) as client:
        data = {
            "configTypeList": [],
            "extParams": {"picType": "base64"},
            "posIP": [ip],
            "posMacList": [mac],
            "versionType": "1",
        }
        headers = {"Vendorid": 111, "version": version}
        if version:
            data["posVersion"] = version
        env = "RTA_UAT"

        logger.info(f"pos/init参数： {json.dumps(data, ensure_ascii=False)}")
        if "uat" in env.lower() or "kh_test_s" in env.lower():
            resp = client.post(f"{pos_uat_host}/pos/init", json=data)
        elif "test" in env.lower() or "kh_test" in env.lower():
            resp = client.post(f"{pos_test_host}/pos/init", json=data)
        else:
            resp = client.post(f"{pos_pro_host}/pos/init", json=data)
        if resp.status_code != 200:
            logger.error(
                f"获取pos初始配置（pos/init）失败，状态码： {resp.status_code}"
            )
            raise ConnectionError(
                f"获取pos初始配置（pos/init）失败: {resp.status_code}"
            )
        content = resp.json()
        _log_pos_init_result(content, len(resp.content))
        if content["code"] != "0000":
            raise PosHandleException(
                f"从网络获取pos/init失败: {_build_pos_init_result_summary(content, len(resp.content))}"
            )
        res_data = content.get("data", {})
        res_model = PosParamsModel.model_validate(res_data)
        res_model.is_local = False
        logger.info(res_data)
