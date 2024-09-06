import asyncio
from loguru import logger
from datetime import datetime
from common.PromoDataHandle import PromoDataHandle


def job(*args, **kwargs):
    logger.info(args)
    logger.info(kwargs)
    logger.info(f"{datetime.now()}执行了")


def job_stop_promo(*args, **kwargs):
    handle = PromoDataHandle(**kwargs)
    pro_ids, user_pro_info = asyncio.run(handle.websocket_get_pro_ids())
    vender_id = 11
    content = f"即将强制结束商家：{vender_id}, 以下用户创建的促销单，原因是包含了全部门店，且未设置资格码"
    for k, v in user_pro_info.items():
        content = content + '\r\n用户名：' + k + ' 促销单：' + str(v)
    content = content + f'\r\n本次任务共处理数据：{len(pro_ids)}条'
    # Feishu().sendTextmessage(content)
    # asyncio.run(websocket_stop_pro_ids(token, 11, tuple(pro_ids)))
    print(content)

