import asyncio
from loguru import logger
from datetime import datetime
from common.PromoDataHandle import PromoDataHandle
from utils.feishu import Feishu


def job(*args, **kwargs):
    logger.info(args)
    logger.info(kwargs)
    logger.info(f"{datetime.now()}执行了")


def job_stop_promo(*args, **kwargs):
    handle = PromoDataHandle(**kwargs)
    pro_ids, user_pro_info = asyncio.run(handle.websocket_get_pro_ids())
    if pro_ids:
        asyncio.run(handle.websocket_stop_pro_ids(pro_ids))
    vender_id = kwargs.get('venderId')
    content = f"将强制结束商家：{vender_id}, 以下促销单(同步促销单不显示)，原因是包含了全部门店，且未设置资格码"
    sync_count = 0
    for k, v in user_pro_info.items():
        if k != "Sync Admin":
            content = content + '\r\n用户名：' + k + ' 促销单：' + str(v)
        else:
            sync_count = len(user_pro_info[k])
    content = content + f'\r\n本次任务共处理数据：{len(pro_ids)}条, 其中同步数据：{sync_count}条'
    robot_info = kwargs.get('feishu_robot', None)
    if robot_info:
        logger.info(content)
        feishu = Feishu(robot_info)
        feishu.sendTextmessage(content)
    else:
        logger.info(content)
        logger.info("未配置飞书通知")


