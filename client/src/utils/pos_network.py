import json

import httpx
from loguru import logger

from model.config import PosChangeParamsModel
from server.config import PosConfig
from model.pos_network_model import PosInitRespModel, PosInitModel, PosLogoutModel, PosResetAccountRequestModel, \
    PosUserInfoRespModel

pos_config_data = PosConfig.read_pos_config()
uat_host = pos_config_data.pos_tool_uat_host
test_host = pos_config_data.pos_tool_test_host


async def change_pos_from_network(data: PosChangeParamsModel) -> tuple[bool, str]:
    async with httpx.AsyncClient(verify=False) as client:
        data = {"env": data.env,
                "venderId": data.venderId,
                "orgNo": data.orgNo,
                "pos_ip": data.pos_ip,
                "pos_mac": data.pos_mac,
                "pos_type": data.pos_type,
                "pos_group": data.pos_group,
                "pos_skin": data.pos_skin,
                "switchMode": data.switchMode,
                "pos_no": data.pos_no}
        logger.info(f"POS切换参数： {json.dumps(data)}")
        if "uat" in data["env"].lower():
            resp = await client.post(f"{uat_host}/tools/posChange", json=data)
        else:
            resp = await client.post(f"{test_host}/tools/posChange", json=data)
        if resp.status_code != 200:
            logger.error(f"POS切换失败，状态码： {resp.status_code}")
            return False, f"POS切换失败，状态码： {resp.status_code}"
        content = resp.json()
        logger.info(f"POS切换结果： {json.dumps(content, ensure_ascii=False)}")
        if content["code"] == 20000:
            return True, "切换成功"
        return False, f"POS切换失败: {content['message']}"


async def pos_account_logout(data: PosLogoutModel) -> tuple[bool, str]:
    async with httpx.AsyncClient(verify=False) as client:
        data = data.model_dump()
        logger.info(f"POS账号注销参数： {json.dumps(data)}")
        if "uat" in data["env"].lower():
            resp = await client.post(f"{uat_host}/tools/kickOut", json=data)
        else:
            resp = await client.post(f"{test_host}/tools/kickOut", json=data)
        if resp.status_code != 200:
            logger.error(f"POS切换失败，状态码： {resp.status_code}")
            return False, f"POS切换失败，状态码： {resp.status_code}"
        content = resp.json()
        logger.info(f"POS切换结果： {json.dumps(content, ensure_ascii=False)}")
        if content["code"] == 20000 or (content['code'] == 40000 and content["message"] == "账号未登录"):
            return True, "踢出账号成功"
        return False, content["message"]


def pos_tool_init() -> PosInitRespModel | bool:
    with httpx.Client(verify=False) as client:

        resp = client.get(f"{test_host}/tools/init")
        if resp.status_code != 200:
            logger.error(f"POS初始化失败，状态码： {resp.status_code}")
            return False
        content = resp.json()
        logger.info(f"POS初始化结果： {json.dumps(content, ensure_ascii=False)}")
        if content["code"] == 20000:
            return PosInitRespModel(**content)
        return False


async def get_user_info(data: PosResetAccountRequestModel) -> PosUserInfoRespModel|None:
    async with httpx.AsyncClient(verify=False) as client:
        data = data.model_dump()
        logger.info(f"查询POS账号信息： {json.dumps(data)}")
        if "uat" in data["env"].lower():
            resp = await client.post(f"{uat_host}/tools/getuserinfo", json=data)
        else:
            resp = await client.post(f"{test_host}/tools/getuserinfo", json=data)
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

    async with httpx.AsyncClient(verify=False) as client:
        data = data.model_dump()
        logger.info(f"重置POS账号密码： {json.dumps(data, ensure_ascii=False)}")
        if "uat" in data["env"].lower():
            resp = await client.post(f"{uat_host}/tools/resetpwd", json=data)
        else:
            resp = await client.post(f"{test_host}/tools/resetpwd", json=data)
        if resp.status_code != 200:
            logger.error(f"重置POS账号密码失败，状态码： {resp.status_code}")
            return False, f"重置密码失败: {resp.status_code}"
        content = resp.json()
        logger.info(f"重置POS账号密码结果： {json.dumps(content, ensure_ascii=False)}")
        if content["code"] == 20000:
            return True, "重置密码成功"
        return False, f"重置密码失败: {json.dumps(content, ensure_ascii=False)}"