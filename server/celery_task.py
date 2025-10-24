from config.get_db import get_db
from module_admin.entity.vo.user_vo import CurrentUserModel
from module_hrm.entity.vo.case_vo import CaseRunModel
from module_hrm.service.runner.runner_service import run_by_async
from app1 import app
import time
import asyncio


@app.task(name="run_test")
def process_task(data: dict):
    """
    一个示例的耗时任务
    """
    user_info = CurrentUserModel(**data['user_info'])
    run_info = CaseRunModel(**data['run_info'])
    # 模拟一些耗时操作，例如数据处理、发送邮件、生成报告等
    with get_db() as db:
        asyncio.create_task(run_by_async(db, run_info, user_info))
    # await run_by_async(query_db, run_info, current_user)
    time.sleep(5)
    result = f"Processed: {data['input']}"
    return {"result": result, "status": "success"}

# 你可以在这里定义更多任务
# @celery_app.task
# def another_task(...):