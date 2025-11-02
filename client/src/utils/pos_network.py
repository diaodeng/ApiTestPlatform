import json

import httpx
from loguru import logger

from model.config import PosChangeParamsModel
from model.pos_network_model import PosInitRespModel, PosInitModel, PosLogoutModel


def change_pos_from_network(data: PosChangeParamsModel):
    with httpx.Client(verify=False) as client:
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
            resp = client.post("https://uattoolserver.rta-os.com/tools/posChange", json=data)
        else:
            resp = client.post("https://testtoolserver.rta-os.com/tools/posChange", json=data)
        if resp.status_code != 200:
            logger.error(f"POS切换失败，状态码： {resp.status_code}")
            return False
        content = resp.json()
        logger.info(f"POS切换结果： {json.dumps(content, ensure_ascii=False)}")
        if content["code"] == 20000:
            return True
        return False


def pos_account_logout(data: PosLogoutModel):
    with httpx.Client(verify=False) as client:
        data = data.model_dump()
        logger.info(f"POS账号注销参数： {json.dumps(data)}")
        if "uat" in data["env"].lower():
            resp = client.post("https://uattoolserver.rta-os.com/tools/kickOut", json=data)
        else:
            resp = client.post("https://testtoolserver.rta-os.com/tools/kickOut", json=data)
        if resp.status_code != 200:
            logger.error(f"POS切换失败，状态码： {resp.status_code}")
            return False
        content = resp.json()
        logger.info(f"POS切换结果： {json.dumps(content, ensure_ascii=False)}")
        if content["code"] == 20000:
            return True
        return False


def pos_tool_init() -> PosInitRespModel | bool:
    with httpx.Client(verify=False) as client:

        resp = client.get("https://testtoolserver.rta-os.com/tools/init")
        if resp.status_code != 200:
            logger.error(f"POS初始化失败，状态码： {resp.status_code}")
            return False
        content = resp.json()
        logger.info(f"POS初始化结果： {json.dumps(content, ensure_ascii=False)}")
        if content["code"] == 20000:
            return PosInitRespModel(**content)
        return False


def reset_account_password(env_group:str, account:str|int):
    pass