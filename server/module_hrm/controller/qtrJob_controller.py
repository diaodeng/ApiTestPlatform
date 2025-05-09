import json
from datetime import datetime

from fastapi import APIRouter
from fastapi import Depends
from fastapi.requests import Request
from sqlalchemy.orm import Session

from config.get_db import get_db
from config.get_qtr_scheduler import qtr_scheduler_util
from module_admin.annotation.log_annotation import log_decorator
from module_admin.aspect.data_scope import GetDataScope
from module_admin.aspect.interface_auth import CheckUserInterfaceAuth
from module_admin.service.login_service import LoginService, CurrentUserModel
from module_hrm.entity.vo.job_vo import JobModel, JobPageQueryModel, EditJobModel, DeleteJobModel, JobLogPageQueryModel, \
    DeleteJobLogModel
from module_hrm.service.job_log_service import JobLogService
from module_hrm.service.job_service import JobService
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
                           data_scope_sql: str = Depends(GetDataScope('QtrJob', user_alias='manager'))
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
                                 query_db: Session = Depends(get_db)):
    try:
        # 获取分页数据,scheduler加载的任务
        notice_page_query_result = qtr_scheduler_util.get_job_list()
        logger.info('获取成功')
        return ResponseUtil.success(data=[{"id": i.id,
                                           "name": i.name,
                                           "func": i.func,
                                           "args": i.args,
                                           "kwargs": i.kwargs,
                                           "executor": i.executor,
                                           "next_run_time": i.next_run_time,
                                           "trigger": i.trigger
                                           } for i in notice_page_query_result])
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
        add_job.dept_id = current_user.user.dept_id
        add_job.manager = current_user.user.user_id

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
async def edit_qtr_job(request: Request, edit_job: EditJobModel, query_db: Session = Depends(get_db),
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


@qtrJobController.put("/job/changeStatus", dependencies=[Depends(CheckUserInterfaceAuth('qtr:job:changeStatus'))])
@log_decorator(title='定时任务管理', business_type=2)
async def change_status_qtr_job(request: Request, edit_job: EditJobModel, query_db: Session = Depends(get_db),
                                current_user: CurrentUserModel = Depends(LoginService.get_current_user)):
    try:

        job_info = EditJobModel()
        job_info.status = edit_job.status
        job_info.job_id = edit_job.job_id
        job_info.update_by = current_user.user.user_name
        job_info.update_time = datetime.now()
        edit_job_result = JobService.edit_job_services(query_db, job_info, current_user)
        if edit_job_result.is_success:
            logger.info(edit_job_result.message)
            return ResponseUtil.success(msg=edit_job_result.message)
        else:
            logger.warning(edit_job_result.message)
            return ResponseUtil.failure(msg=edit_job_result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@qtrJobController.put("/job/run", dependencies=[Depends(CheckUserInterfaceAuth('qtr:job:changeStatus'))])
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
    try:
        add_job.create_by = current_user.user.user_name
        add_job.update_by = current_user.user.user_name
        qtr_scheduler_util.remove_scheduler_job(add_job.job_id)

        return ResponseUtil.success(msg=f"停止任务{add_job.job_id}异常")
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
                              data_scope_sql: str = Depends(GetDataScope('QtrJob', user_alias='manager'))
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


@qtrJobController.get("/jobLog/list", response_model=PageResponseModel,
                      dependencies=[Depends(CheckUserInterfaceAuth('qtr:job:list'))])
async def get_qtr_job_log_list(request: Request,
                               job_log_page_query: JobLogPageQueryModel = Depends(JobLogPageQueryModel.as_query),
                               query_db: Session = Depends(get_db),
                               data_scope_sql: str = Depends(GetDataScope(''))
                               ):
    try:
        # 获取分页数据
        job_log_page_query_result = JobLogService.get_job_log_list_services(query_db, job_log_page_query,
                                                                            data_scope_sql, is_page=True)
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
async def clear_qtr_job_log(request: Request, query_db: Session = Depends(get_db)):
    try:
        clear_job_log_result = JobLogService.clear_job_log_services(query_db)
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
                                  data_scope_sql: str = Depends(GetDataScope('QtrJobLog', user_alias='manager'))
                                  ):
    try:
        # 获取全量数据
        job_log_query_result = JobLogService.get_job_log_list_services(query_db, job_log_page_query, data_scope_sql, is_page=False)
        job_log_export_result = await JobLogService.export_job_log_list_services(request, job_log_query_result)
        logger.info('导出成功')
        return ResponseUtil.streaming(data=bytes2file_response(job_log_export_result))
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))
