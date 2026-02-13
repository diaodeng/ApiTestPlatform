import asyncio
import inspect
import time
from datetime import datetime

from module_admin.entity.vo.user_vo import CurrentUserModel, UserInfoModel
from module_hrm.entity.vo.case_vo import CaseRunModel
from module_hrm.entity.vo.push_vo import FeishuRobotModel
from module_hrm.service.runner.runner_service import run_by_async
from module_hrm.utils.util import get_system_stats
from utils.log_util import logger

from .task_register import register_job


@register_job("module_task.scheduler_qtr.job_sys_info")
def job_sys_info(*args, **kwargs):
    get_system_stats()

@register_job("module_task.scheduler_qtr.job")
def job(*args, **kwargs):
    # logger.info(args)
    # logger.info(kwargs)
    time.sleep(1)
    logger.info(f"执行了测试方法: {args}  {kwargs}")

@register_job("module_task.scheduler_qtr.test_error")
def test_error(*args, **kwargs):
    # logger.info(args)
    # logger.info(kwargs)
    try:
        raise TypeError("测试执行异常哈")
    except Exception:

        logger.info(f"执行了异常测试方法: {args}  {kwargs}")

@register_job("module_task.scheduler_qtr.test_error2")
def test_error2(*args, **kwargs):
    # logger.info(args)
    # logger.info(kwargs)
    try:
        time.sleep(5)
        raise TypeError("测试执行异常哈2")
    except Exception:

        logger.info(f"执行了异常测试方法2: {args}  {kwargs}")

@register_job("module_task.scheduler_qtr.job_run_test")
def job_run_test(*args, **kwargs):
    """
    执行测试任务
    参数CaseRunModel
    """
    logger.debug(f"定时任务调用了测试方法：{__name__}.{inspect.currentframe().f_back.f_code.co_name}")
    logger.debug(f"任务执行参数: {args}  {kwargs}")
    try:
        logger.info("测试任务执行开始")
        data = CaseRunModel(**kwargs)
        new_data_format = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        user_info_module = UserInfoModel()
        user_info_module.user_name = data.user_name
        user_info_module.user_id = data.runner
        user_info_module.dept_id = data.dept_id
        user_info = user_info_module.model_dump(by_alias=True)
        logger.info(f"用户信息：{user_info}")
        user_module = CurrentUserModel(
            **{"permissions": [], "roles": [], "user": user_info})

        data.report_name = f'{data.report_name}{new_data_format}'

        if kwargs.get("feishuRobot"):
            feishu_bot_config = FeishuRobotModel(**kwargs.get("feishuRobot"))
            data.feishu_robot = feishu_bot_config

        logger.info(f"准备执行测试：{data.model_dump_json()}")
        # asyncio.create_task(run_test_in_background(data, user_module))

        new_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(new_loop)
        task = asyncio.ensure_future(run_by_async(data, user_module))
        new_loop.run_until_complete(task)
        new_loop.stop()
        new_loop.close()
        logger.info(f"测试任务执行完成：{data.report_name}-{data.report_id}")
    except Exception as e:
        logger.error(f"执行测试任务失败：{e}")
        logger.exception(e)

