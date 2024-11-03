import asyncio
import inspect
import sys
import time
from datetime import datetime

from loguru import logger

from config.database import SessionLocal
from module_admin.entity.vo.user_vo import CurrentUserModel, UserInfoModel
from module_hrm.entity.vo.case_vo import CaseRunModel, FeishuRobotModel
from module_hrm.service.runner.runner_service import run_by_async


def job(*args, **kwargs):
    # logger.info(args)
    # logger.info(kwargs)
    time.sleep(1)
    logger.info(f"执行了测试方法: {args}  {kwargs}")

def test_error(*args, **kwargs):
    # logger.info(args)
    # logger.info(kwargs)
    try:
        raise TypeError("测试执行异常哈")
    except:

        logger.info(f"执行了异常测试方法: {args}  {kwargs}")


def test_error2(*args, **kwargs):
    # logger.info(args)
    # logger.info(kwargs)
    try:
        time.sleep(5)
        raise TypeError("测试执行异常哈2")
    except:

        logger.info(f"执行了异常测试方法2: {args}  {kwargs}")


def job_run_test(*args, **kwargs):
    """
    执行测试任务
    参数
     {
      "userName": "panda", # 用户名
      "userId": 4, # 用户ID
      "ids": [], # 数据id
      "runType": 1, # RunTypeEnum
      "reportName": "定时执行", # 报告名称，可选
      "repeatNum": 1, # 重复执行次数， 默认1
      "env": 20, # 环境ID。必填
      "concurrent": 1, # 并发数，默认1
      "feishuRobot": {
            "url": "51946e38-bf5d-40ee-9142-c97b55b67b1d",  # 飞书机器人token（url的最后一节）
            "keywords": [], # 关键字
            "secret": "openwrt-312209",
            "atUserId": [],
            "push": true # 是否推送，默认false
        }
    }
    """
    logger.debug(f"定时任务调用了测试方法：{__name__}.{inspect.currentframe().f_back.f_code.co_name}")
    try:
        logger.info("测试任务执行开始")
        in_data = kwargs

        user_info_module = UserInfoModel()
        user_info_module.user_name = in_data["userName"]
        user_info_module.user_id = in_data["userId"]
        user_module = CurrentUserModel(
            **{"permissions": [], "roles": [], "user": user_info_module.model_dump(by_alias=True)})

        data = CaseRunModel(env=1)
        data.ids = in_data.get("ids", [])
        data.run_type = in_data.get("runType", 1)
        data.report_name = in_data.get("reportName", datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"))
        data.repeat_num = in_data.get("repeatNum", 1)
        data.env = in_data["env"]
        data.concurrent = in_data.get("concurrent", 1)
        data.runner = in_data["userId"]
        data.push = in_data.get("push", True)

        if kwargs.get("feishuRobot"):
            feishu_bot_config = FeishuRobotModel(**kwargs.get("feishuRobot"))
            data.feishu_robot = feishu_bot_config

        logger.info(f"准备执行测试：{data.model_dump_json()}")
        new_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(new_loop)
        with SessionLocal() as db_session:
            task = asyncio.ensure_future(run_by_async(db_session, data, user_module))
            new_loop.run_until_complete(task)
            new_loop.stop()
            new_loop.close()
    except Exception as e:
        logger.exception(e)
    finally:
        logger.info("测试任务执行完成")
