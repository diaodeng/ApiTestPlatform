from loguru import logger

from model.config import PosChangeParamsModel
from server.config import PosConfig
from utils.common import get_active_mac, get_local_ip
from utils.pos_network import change_pos_from_network


class PosConfigServer:
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

        pos_info = PosConfig.read_pos_params(pos_path)
        if not pos_info:
            logger.warning(f"获取pos_params参数失败:{pos_path}")
            return False, f"获取pos_params参数失败:{pos_path}"

        pos_group, account = PosConfig.get_pos_group(pos_info.venderNo, env)
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