import json

import httpx
from loguru import logger

from model.config import PosChangeParamsModel


def change_pos_from_network(data: PosChangeParamsModel):
    with httpx.Client() as client:
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
        if "uat" in data["env"]:
            resp = client.post("https://uattoolserver.rta-os.com/tools/posChange", json=data)
        else:
            resp = client.post("https://testtoolserver.rta-os.com/tools/posChange", json=data)
        if resp.status_code != 200:
            logger.error(f"POS切换失败，状态码： {resp.status_code}")
            return False
        content = resp.json()
        logger.info(f"POS切换结果： {json.dumps(content)}")
        if content["code"] == 20000:
            return True
        return False


def pos_account_logout(data: PosChangeParamsModel):
    with httpx.Client() as client:
        data = {"env":"rta-test","cashierNo":"00011111","userid":"","username":""}
        logger.info(f"POS账号注销参数： {json.dumps(data)}")
        if "uat" in data["env"]:
            resp = client.post("https://uattoolserver.rta-os.com/tools/kickOut", json=data)
        else:
            resp = client.post("https://testtoolserver.rta-os.com/tools/kickOut", json=data)
        if resp.status_code != 200:
            logger.error(f"POS切换失败，状态码： {resp.status_code}")
            return False
        content = resp.json()
        logger.info(f"POS切换结果： {json.dumps(content)}")
        if content["code"] == 20000:
            return True
        return False