from module_hrm.dao.job_log_dao import JobLogDao, JobLogPageQueryModel, JobLogModel, DeleteJobLogModel
from sqlalchemy.orm import Session
from module_admin.service.dict_service import Request, DictDataService
from module_hrm.entity.vo.common_vo import CrudResponseModel
from utils.common_util import export_list2excel


class JobLogService:
    """
    定时任务日志管理模块服务层
    """

    @classmethod
    def get_job_log_list_services(cls, query_db: Session, query_object: JobLogPageQueryModel, data_scope_sql:str, is_page: bool = False):
        """
        获取定时任务日志列表信息service
        :param query_db: orm对象
        :param query_object: 查询参数对象
        :param data_scope_sql: 数据权限依赖sql
        :param is_page: 是否开启分页
        :return: 定时任务日志列表信息对象
        """
        job_log_list_result = JobLogDao.get_job_log_list(query_db, query_object, data_scope_sql, is_page)

        return job_log_list_result

    @classmethod
    def add_job_log_services(cls, query_db: Session, page_object: JobLogModel):
        """
        新增定时任务日志信息service
        :param query_db: orm对象
        :param page_object: 新增定时任务日志对象
        :return: 新增定时任务日志校验结果
        """
        try:
            JobLogDao.add_job_log_dao(query_db, page_object)
            query_db.commit()
            result = dict(is_success=True, message='新增成功')
        except Exception as e:
            query_db.rollback()
            result = dict(is_success=False, message=str(e))

        return CrudResponseModel(**result)

    @classmethod
    def delete_job_log_services(cls, query_db: Session, page_object: DeleteJobLogModel):
        """
        删除定时任务日志信息service
        :param query_db: orm对象
        :param page_object: 删除定时任务日志对象
        :return: 删除定时任务日志校验结果
        """
        if page_object.job_log_ids.split(','):
            job_log_id_list = page_object.job_log_ids.split(',')
            try:
                for job_log_id in job_log_id_list:
                    JobLogDao.delete_job_log_dao(query_db, JobLogModel(jobLogId=job_log_id))
                query_db.commit()
                result = dict(is_success=True, message='删除成功')
            except Exception as e:
                query_db.rollback()
                raise e
        else:
            result = dict(is_success=False, message='传入定时任务日志id为空')
        return CrudResponseModel(**result)

    @classmethod
    def clear_job_log_services(cls, query_db: Session):
        """
        清除定时任务日志信息service
        :param query_db: orm对象
        :return: 清除定时任务日志校验结果
        """
        try:
            JobLogDao.clear_job_log_dao(query_db)
            query_db.commit()
            result = dict(is_success=True, message='清除成功')
        except Exception as e:
            query_db.rollback()
            raise e

        return CrudResponseModel(**result)

    @staticmethod
    async def export_job_log_list_services(request: Request, job_log_list: list):
        """
        导出定时任务日志信息service
        :param request: Request对象
        :param job_log_list: 定时任务日志信息列表
        :return: 定时任务日志信息对应excel的二进制数据
        """
        # 创建一个映射字典，将英文键映射到中文键
        mapping_dict = {
            "jobLogId": "任务日志编码",
            "jobName": "任务名称",
            "jobGroup": "任务组名",
            "jobExecutor": "任务执行器",
            "invokeTarget": "调用目标字符串",
            "jobArgs": "位置参数",
            "jobKwargs": "关键字参数",
            "jobTrigger": "任务触发器",
            "jobMessage": "日志信息",
            "status": "执行状态",
            "exceptionInfo": "异常信息",
            "createTime": "创建时间",
        }

        data = job_log_list
        job_group_list = await DictDataService.query_dict_data_list_from_cache_services(request.app.state.redis, dict_type='qtr_job_group')
        job_group_option = [dict(label=item.get('dictLabel'), value=item.get('dictValue')) for item in job_group_list]
        job_group_option_dict = {item.get('value'): item for item in job_group_option}
        job_executor_list = await DictDataService.query_dict_data_list_from_cache_services(request.app.state.redis, dict_type='qtr_job_executor')
        job_executor_option = [dict(label=item.get('dictLabel'), value=item.get('dictValue')) for item in job_executor_list]
        job_executor_option_dict = {item.get('value'): item for item in job_executor_option}

        for item in data:
            if item.get('status') == '0':
                item['status'] = '正常'
            else:
                item['status'] = '暂停'
            if str(item.get('jobGroup')) in job_group_option_dict.keys():
                item['jobGroup'] = job_group_option_dict.get(str(item.get('jobGroup'))).get('label')
            if str(item.get('jobExecutor')) in job_executor_option_dict.keys():
                item['jobExecutor'] = job_executor_option_dict.get(str(item.get('jobExecutor'))).get('label')
        new_data = [{mapping_dict.get(key): value for key, value in item.items() if mapping_dict.get(key)} for item in
                    data]
        binary_data = export_list2excel(new_data)

        return binary_data
