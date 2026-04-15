from datetime import datetime

from fastapi import APIRouter, Depends
from fastapi.requests import Request
from sqlalchemy.orm import Session

from config.get_db import get_db
from module_admin.annotation.log_annotation import log_decorator
from module_admin.aspect.data_scope import GetDataScope
from module_admin.aspect.interface_auth import CheckUserInterfaceAuth
from module_admin.service.login_service import CurrentUserModel, LoginService
from module_hrm.entity.vo.job_vo import (
    ControlRunningTaskModel,
    DeleteJobLogModel,
    DeleteJobModel,
    EditJobModel,
    JobLogPageQueryModel,
    JobModel,
    JobPageQueryModel,
)
from module_hrm.service.job_log_service import JobLogService
from module_hrm.service.job_service import JobService
from module_task.celery_job_models import CeleryPeriodicTask
from utils.common_util import bytes2file_response
from utils.log_util import logger
from utils.page_util import PageResponseModel
from utils.response_util import ResponseUtil

qtrJobController = APIRouter(prefix='/qtr', dependencies=[Depends(LoginService.get_current_user)])


@qtrJobController.get("/job/list", response_model=PageResponseModel,
                      dependencies=[Depends(CheckUserInterfaceAuth('qtr:job:list'))])
async def get_qtr_job_list(request: Request,
                           job_page_query: JobPageQueryModel = Depends(JobPageQueryModel.as_query),
                           query_db: Session = Depends(get_db),
                           data_scope_sql = Depends(
                               GetDataScope(CeleryPeriodicTask, user_alias='owner_user_id', dept_alias='owner_dept_id')
                           )
                           ):
    try:
        # 获取分页数据
        notice_page_query_result = JobService.get_job_list_services(query_db, job_page_query, data_scope_sql,
                                                                    is_page=True)
        logger.info('获取成功')
        return ResponseUtil.success(model_content=notice_page_query_result)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@qtrJobController.get("/job/schedulerList", response_model=PageResponseModel,
                      dependencies=[Depends(CheckUserInterfaceAuth('qtr:job:list'))])
async def get_scheduler_job_list(request: Request,
                                 job_page_query: JobPageQueryModel = Depends(JobPageQueryModel.as_query),
                                 query_db: Session = Depends(get_db),
                                 data_scope_sql = Depends(
                                     GetDataScope(
                                         CeleryPeriodicTask,
                                         user_alias='owner_user_id',
                                         dept_alias='owner_dept_id',
                                     )
                                 )):
    """
    获取当前启用的 Celery 定时任务快照列表。

    :param request: FastAPI 请求对象。
    :param job_page_query: 任务筛选参数，接口会强制查询启用状态任务。
    :param query_db: 数据库会话。
    :param data_scope_sql: 当前用户可见任务的数据权限表达式。
    :return: 任务调度快照数据，兼容前端展示所需字段。
    """
    try:
        job_page_query.enabled = True
        notice_page_query_result = JobService.get_job_list_services(
            query_db,
            job_page_query,
            data_scope_sql,
            is_page=False,
        )
        logger.info('获取成功')
        return ResponseUtil.success(
            data=[
                {
                    "id": i.get("taskId"),
                    "name": i.get("taskName"),
                    "func": i.get("taskKey"),
                    "args": i.get("taskArgs"),
                    "kwargs": i.get("taskKwargs"),
                    "queue": i.get("queueName"),
                    "next_run_time": None,
                    "trigger": i.get("scheduleType"),
                }
                for i in notice_page_query_result
            ]
        )
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@qtrJobController.get("/job/running", dependencies=[Depends(CheckUserInterfaceAuth("qtr:job:query"))])
async def get_running_qtr_job_list(
    request: Request,
    query_db: Session = Depends(get_db),
    data_scope_sql=Depends(
        GetDataScope(CeleryPeriodicTask, user_alias='owner_user_id', dept_alias='owner_dept_id')
    ),
):
    """
    获取 QTR 任务当前运行态快照（运行中/待执行/待调度）。

    :param request: FastAPI 请求对象。
    :param query_db: 数据库会话。
    :param data_scope_sql: 当前用户可见任务的数据权限表达式。
    :return: 运行态任务列表。
    """
    try:
        running_tasks = JobService.list_running_jobs_services(query_db, data_scope_sql)
        return ResponseUtil.success(data=running_tasks)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@qtrJobController.put("/job/running/cancel", dependencies=[Depends(CheckUserInterfaceAuth("qtr:job:run"))])
@log_decorator(title='定时任务管理', business_type=2)
async def cancel_running_qtr_job(
    request: Request,
    page_object: ControlRunningTaskModel,
    query_db: Session = Depends(get_db),
    data_scope_sql=Depends(
        GetDataScope(CeleryPeriodicTask, user_alias='owner_user_id', dept_alias='owner_dept_id')
    ),
):
    """
    取消 QTR 运行态任务（撤销尚未执行的任务）。

    :param request: FastAPI 请求对象。
    :param page_object: 任务控制请求体（celery_task_id）。
    :param query_db: 数据库会话。
    :param data_scope_sql: 当前用户可见任务的数据权限表达式。
    :return: 控制结果。
    """
    try:
        cancel_result = JobService.cancel_running_job_services(query_db, page_object, data_scope_sql)
        if cancel_result.is_success:
            return ResponseUtil.success(msg=cancel_result.message)
        return ResponseUtil.failure(msg=cancel_result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@qtrJobController.put("/job/running/terminate", dependencies=[Depends(CheckUserInterfaceAuth("qtr:job:run"))])
@log_decorator(title='定时任务管理', business_type=2)
async def terminate_running_qtr_job(
    request: Request,
    page_object: ControlRunningTaskModel,
    query_db: Session = Depends(get_db),
    data_scope_sql=Depends(
        GetDataScope(CeleryPeriodicTask, user_alias='owner_user_id', dept_alias='owner_dept_id')
    ),
):
    """
    终止 QTR 运行态任务（尝试中断运行中任务）。

    :param request: FastAPI 请求对象。
    :param page_object: 任务控制请求体（celery_task_id）。
    :param query_db: 数据库会话。
    :param data_scope_sql: 当前用户可见任务的数据权限表达式。
    :return: 控制结果。
    """
    try:
        terminate_result = JobService.terminate_running_job_services(query_db, page_object, data_scope_sql)
        if terminate_result.is_success:
            return ResponseUtil.success(msg=terminate_result.message)
        return ResponseUtil.failure(msg=terminate_result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@qtrJobController.post("/job", dependencies=[Depends(CheckUserInterfaceAuth('qtr:job:add'))])
@log_decorator(title='定时任务管理', business_type=1)
async def add_qtr_job(request: Request, add_job: JobModel, query_db: Session = Depends(get_db),
                      current_user: CurrentUserModel = Depends(LoginService.get_current_user)):
    try:
        add_job.create_by = current_user.user.user_name
        add_job.update_by = current_user.user.user_name
        add_job.owner_dept_id = current_user.user.dept_id
        add_job.owner_user_id = current_user.user.user_id

        add_job_result = JobService.add_job_services(query_db, add_job, current_user)
        if add_job_result.is_success:
            logger.info(add_job_result.message)
            return ResponseUtil.success(msg=add_job_result.message)
        else:
            logger.warning(add_job_result.message)
            return ResponseUtil.failure(msg=add_job_result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@qtrJobController.put("/job", dependencies=[Depends(CheckUserInterfaceAuth('qtr:job:edit'))])
@log_decorator(title='定时任务管理', business_type=2)
async def edit_qtr_job(request: Request,
                       edit_job: EditJobModel,
                       query_db: Session = Depends(get_db),
                       current_user: CurrentUserModel = Depends(LoginService.get_current_user)):
    try:
        edit_job.update_by = current_user.user.user_name
        edit_job.update_time = datetime.now()
        edit_job_result = JobService.edit_job_services(query_db, edit_job, current_user)
        if edit_job_result.is_success:
            logger.info(edit_job_result.message)
            return ResponseUtil.success(msg=edit_job_result.message)
        else:
            logger.warning(edit_job_result.message)
            return ResponseUtil.failure(msg=edit_job_result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@qtrJobController.put("/job/changeStatus", dependencies=[Depends(CheckUserInterfaceAuth('qtr:job:edit'))])
@log_decorator(title='定时任务管理', business_type=2)
async def change_status_qtr_job(request: Request, edit_job: EditJobModel, query_db: Session = Depends(get_db),
                                current_user: CurrentUserModel = Depends(LoginService.get_current_user)):
    try:
        change_result = JobService.change_status(
            query_db=query_db,
            task_id=edit_job.task_id,
            enabled=bool(edit_job.enabled),
            update_by=current_user.user.user_name,
        )
        if change_result.is_success:
            return ResponseUtil.success(msg=change_result.message)
        return ResponseUtil.failure(msg=change_result.message)

    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@qtrJobController.put("/job/run", dependencies=[Depends(CheckUserInterfaceAuth('qtr:job:run'))])
@log_decorator(title='定时任务管理', business_type=2)
async def execute_qtr_job(request: Request, execute_job: JobModel, query_db: Session = Depends(get_db)):
    try:
        execute_job_result = JobService.execute_job_once_services(query_db, execute_job)
        if execute_job_result.is_success:
            logger.info(execute_job_result.message)
            return ResponseUtil.success(msg=execute_job_result.message)
        else:
            logger.warning(execute_job_result.message)
            return ResponseUtil.failure(msg=execute_job_result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@qtrJobController.delete("/job/{job_ids}", dependencies=[Depends(CheckUserInterfaceAuth('qtr:job:remove'))])
@log_decorator(title='定时任务管理', business_type=3)
async def delete_qtr_job(request: Request, job_ids: str, query_db: Session = Depends(get_db)):
    try:
        delete_job = DeleteJobModel(jobIds=job_ids)
        delete_job_result = JobService.delete_job_services(query_db, delete_job)
        if delete_job_result.is_success:
            logger.info(delete_job_result.message)
            return ResponseUtil.success(msg=delete_job_result.message)
        else:
            logger.warning(delete_job_result.message)
            return ResponseUtil.failure(msg=delete_job_result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@qtrJobController.post("/job/stop", dependencies=[Depends(CheckUserInterfaceAuth('qtr:job:add'))])
@log_decorator(title='定时任务管理', business_type=1)
async def stop_job(request: Request, add_job: JobModel, query_db: Session = Depends(get_db),
                   current_user: CurrentUserModel = Depends(LoginService.get_current_user)):
    """
    手动停止指定 QTR 任务（将状态更新为暂停）。

    :param request: FastAPI 请求对象。
    :param add_job: 任务请求体，仅使用 task_id 字段。
    :param query_db: 数据库会话。
    :param current_user: 当前登录用户，用于审计字段。
    :return: 停止结果响应。
    """
    try:
        change_result = JobService.change_status(
            query_db=query_db,
            task_id=add_job.task_id,
            enabled=False,
            update_by=current_user.user.user_name,
        )
        if change_result.is_success:
            return ResponseUtil.success(msg=f"停止任务{add_job.task_id}成功")
        return ResponseUtil.failure(msg=change_result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@qtrJobController.get("/job/{job_id}", response_model=JobModel,
                      dependencies=[Depends(CheckUserInterfaceAuth('qtr:job:query'))])
async def query_detail_qtr_job(request: Request, job_id: int, query_db: Session = Depends(get_db)):
    try:
        job_detail_result = JobService.job_detail_services(query_db, job_id)
        logger.info(f'获取job_id为{job_id}的信息成功')
        return ResponseUtil.success(data=job_detail_result)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@qtrJobController.post("/job/export", dependencies=[Depends(CheckUserInterfaceAuth('qtr:job:export'))])
@log_decorator(title='定时任务管理', business_type=5)
async def export_qtr_job_list(request: Request,
                              job_page_query: JobPageQueryModel = Depends(JobPageQueryModel.as_form),
                              query_db: Session = Depends(get_db),
                              data_scope_sql = Depends(
                                  GetDataScope(
                                      CeleryPeriodicTask,
                                      user_alias='owner_user_id',
                                      dept_alias='owner_dept_id',
                                  )
                              )
                              ):
    try:
        # 获取全量数据
        job_query_result = JobService.get_job_list_services(query_db, job_page_query, data_scope_sql, is_page=False)
        job_export_result = await JobService.export_job_list_services(request, job_query_result)
        logger.info('导出成功')
        return ResponseUtil.streaming(data=bytes2file_response(job_export_result))
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@qtrJobController.get("/jobLog/list",
                      response_model=PageResponseModel,
                      dependencies=[Depends(CheckUserInterfaceAuth('qtr:job:list'))])
async def get_qtr_job_log_list(request: Request,
                               job_log_page_query: JobLogPageQueryModel = Depends(JobLogPageQueryModel.as_query),
                               query_db: Session = Depends(get_db),
                               data_scope_sql = Depends(
                                   GetDataScope(
                                       CeleryPeriodicTask,
                                       user_alias='owner_user_id',
                                       dept_alias='owner_dept_id',
                                   )
                               )
                               ):
    try:
        # 获取分页数据
        job_log_page_query_result = JobLogService.get_job_log_list_services(
            query_db, job_log_page_query, data_scope_sql, is_page=True
        )
        logger.info('获取成功')
        return ResponseUtil.success(model_content=job_log_page_query_result)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@qtrJobController.delete("/jobLog/{job_log_ids}", dependencies=[Depends(CheckUserInterfaceAuth('qtr:job:remove'))])
@log_decorator(title='定时任务日志管理', business_type=3)
async def delete_qtr_job_log(request: Request, job_log_ids: str, query_db: Session = Depends(get_db)):
    try:
        delete_job_log = DeleteJobLogModel(jobLogIds=job_log_ids)
        delete_job_log_result = JobLogService.delete_job_log_services(query_db, delete_job_log)
        if delete_job_log_result.is_success:
            logger.info(delete_job_log_result.message)
            return ResponseUtil.success(msg=delete_job_log_result.message)
        else:
            logger.warning(delete_job_log_result.message)
            return ResponseUtil.failure(msg=delete_job_log_result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@qtrJobController.post("/jobLog/clean", dependencies=[Depends(CheckUserInterfaceAuth('qtr:job:remove'))])
@log_decorator(title='定时任务日志管理', business_type=9)
async def clear_qtr_job_log(
    request: Request,
    query_db: Session = Depends(get_db),
    data_scope_sql = Depends(
        GetDataScope(CeleryPeriodicTask, user_alias='owner_user_id', dept_alias='owner_dept_id')
    ),
):
    try:
        clear_job_log_result = JobLogService.clear_job_log_services(query_db, data_scope_sql)
        if clear_job_log_result.is_success:
            logger.info(clear_job_log_result.message)
            return ResponseUtil.success(msg=clear_job_log_result.message)
        else:
            logger.warning(clear_job_log_result.message)
            return ResponseUtil.failure(msg=clear_job_log_result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@qtrJobController.post("/jobLog/export", dependencies=[Depends(CheckUserInterfaceAuth('qtr:job:export'))])
@log_decorator(title='定时任务日志管理', business_type=5)
async def export_qtr_job_log_list(request: Request,
                                  job_log_page_query: JobLogPageQueryModel = Depends(JobLogPageQueryModel.as_form),
                                  query_db: Session = Depends(get_db),
                                  data_scope_sql = Depends(
                                      GetDataScope(
                                          CeleryPeriodicTask,
                                          user_alias='owner_user_id',
                                          dept_alias='owner_dept_id',
                                      )
                                  )
                                  ):
    try:
        # 获取全量数据
        job_log_query_result = JobLogService.get_job_log_list_services(query_db,
                                                                       job_log_page_query,
                                                                       data_scope_sql,
                                                                       is_page=False)
        job_log_export_result = await JobLogService.export_job_log_list_services(request, job_log_query_result)
        logger.info('导出成功')
        return ResponseUtil.streaming(data=bytes2file_response(job_log_export_result))
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))
