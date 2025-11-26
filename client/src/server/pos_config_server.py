from loguru import logger

from common.excptions import PosHandleException
from utils import pos_network
from model.config import PosChangeParamsModel
from model.pos_network_model import PosLogoutModel
from server.config import PosConfig
from utils.common import get_active_mac, get_local_ip, kill_process_by_name
from utils.pos_network import change_pos_from_network


class PosConfigServer:
    @classmethod
    async def change_pos_on_network(cls, pos_path: str) -> None:
        env = PosConfig.get_local_pos_env(pos_path)
        if not env:
            logger.warning(f"获取pos环境失败:{pos_path}")
            raise PosHandleException(f"获取pos环境失败:{pos_path}")
        if env == "RTA_TEST":
            new_env = "rta-test"
        elif env == "RTA_UAT":
            new_env = "rta-uat"
        else:
            logger.warning(f"pos环境错误:{pos_path}")
            raise PosHandleException(f"pos环境错误:{env}")

        pos_info = PosConfig.read_pos_params(pos_path)
        if not pos_info:
            logger.warning(f"获取pos_params参数失败:{pos_path}")
            raise PosHandleException(f"获取pos_params参数失败:{pos_path}")

        pos_group, account = PosConfig.get_pos_group(pos_info.venderNo, env)
        if not pos_group:
            logger.warning(f"获取pos分组失败:{pos_path}")
            raise PosHandleException(f"获取pos分组失败:{pos_path}")
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
        await change_pos_from_network(data)

    @classmethod
    async def get_pos_init(cls):
        """
        获取POS init信息，优先从网络获取，网络获取失败从本地缓存读取
        """
        pass

    @classmethod
    async def logout_pos_account(self, pos_path) -> None:
        logger.info(f"开始退出账号：{pos_path}")
        pos_config = PosConfig.read_pos_params(pos_path)
        if not pos_config:
            raise PosHandleException(f"获取POS缓存失败， 无法注销POS账号: pos_config={pos_config}")
        pos_env = PosConfig.get_local_pos_env(pos_path)
        pos_group, account = PosConfig.get_pos_group(pos_config.venderNo, pos_env)
        if not pos_group or not account:
            raise PosHandleException(f"获取POS账号失败， 无法注销POS账号: pos_group={pos_group}, account={account}")
        logout_model = PosLogoutModel(
            env=pos_group,
            cashierNo=account
        )
        status, message_info = await pos_network.pos_account_logout(logout_model)
        if not status:
            raise PosHandleException(message_info)
