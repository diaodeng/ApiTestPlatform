# main.py
from fastapi import FastAPI, HTTPException, APIRouter, Depends
from celery.result import AsyncResult
from app1 import app  # 导入Celery实例
from celery_task import process_task  # 导入任务函数
from pydantic import BaseModel
from sqlalchemy.orm import Session

from config.get_db import get_db
from module_admin.entity.vo.user_vo import CurrentUserModel
from module_admin.service.login_service import LoginService
from module_hrm.entity.vo.case_vo import CaseRunModel
from module_hrm.service.runner.runner_service import run_by_async

celeryController = APIRouter(prefix='/hrm/celery')


class TaskData(BaseModel):
    input: str


@celeryController.get("/tasks", response_model=dict)
async def create_task():
    """
    提交新任务到Celery
    """
    # 将任务发送到Celery队列
    task = process_task.delay({"user_info":{}, 'run_info':{}})
    return {"task_id": task.id, "status": "Task submitted"}


@celeryController.get("/tasks/{task_id}", response_model=dict)
async def get_task_status(task_id: str):
    """
    根据task_id查询任务状态和结果
    """
    task_result = AsyncResult(task_id, app=app)

    if task_result.state == 'PENDING':
        response = {"status": task_result.state, "result": None}
    elif task_result.state != 'FAILURE':
        response = {
            "status": task_result.state,
            "result": task_result.result
        }
    else:
        # 任务执行失败
        response = {
            "status": task_result.state,
            "result": str(task_result.info)  # 异常信息
        }

    return response