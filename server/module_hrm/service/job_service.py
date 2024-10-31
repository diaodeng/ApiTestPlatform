from module_hrm.dao.job_dao import *
from module_admin.service.dict_service import Request, DictDataService
from module_hrm.entity.vo.common_vo import CrudResponseModel
from utils.common_util import export_list2excel, CamelCaseUtil
from config.get_qtr_scheduler import qtr_scheduler_util as QtrSchedulerUtil


class JobService:
    """
    定时任务管理模块服务层
    """

    @classmethod
    def get_job_list_services(cls, query_db: Session, query_object: JobPageQueryModel, is_page: bool = False):
        """
        获取定时任务列表信息service
        :param query_db: orm对象
        :param query_object: 查询参数对象
        :param is_page: 是否开启分页
        :return: 定时任务列表信息对象
        """
        job_list_result = JobDao.get_job_list(query_db, query_object, is_page)

        return job_list_result

    @classmethod
    def add_job_services(cls, query_db: Session, page_object: JobModel):
        """
        新增定时任务信息service
        :param query_db: orm对象
        :param page_object: 新增定时任务对象
        :return: 新增定时任务校验结果
        """
        job = JobDao.get_job_detail_by_info(query_db, page_object)
        if job:
            result = dict(is_success=False, message='定时任务已存在')
        else:
            try:
                JobDao.add_job_dao(query_db, page_object)
                job_info = JobDao.get_job_detail_by_info(query_db, page_object)
                if job_info.status == '0':
                    QtrSchedulerUtil.add_scheduler_job(job_info=job_info)
                query_db.commit()
                result = dict(is_success=True, message='新增成功')
            except Exception as e:
                query_db.rollback()
                raise e

        return CrudResponseModel(**result)

    @classmethod
    def edit_job_services(cls, query_db: Session, page_object: EditJobModel):
        """
        编辑定时任务信息service
        :param query_db: orm对象
        :param page_object: 编辑定时任务对象
        :return: 编辑定时任务校验结果
        """
        edit_job = page_object.model_dump(exclude_unset=True)
        job_info = cls.job_detail_services(query_db, edit_job.get('job_id'))
        if job_info:
            try:
                JobDao.edit_job_dao(query_db, edit_job)
                query_job = QtrSchedulerUtil.get_scheduler_job(job_id=edit_job.get('job_id'))
                if query_job:
                    QtrSchedulerUtil.remove_scheduler_job(job_id=edit_job.get('job_id'))
                if edit_job.get('status') == '0':
                    job_info = cls.job_detail_services(query_db, edit_job.get('job_id'))
                    QtrSchedulerUtil.add_scheduler_job(job_info=job_info)
                query_db.commit()
                result = dict(is_success=True, message='更新成功')
            except Exception as e:
                query_db.rollback()
                raise e
        else:
            result = dict(is_success=False, message='定时任务不存在')

        return CrudResponseModel(**result)

    @classmethod
    def execute_job_once_services(cls, query_db: Session, page_object: JobModel):
        """
        执行一次定时任务service
        :param query_db: orm对象
        :param page_object: 定时任务对象
        :return: 执行一次定时任务结果
        """
        once_job_id = f"{page_object.job_id}1"
        query_job = QtrSchedulerUtil.get_scheduler_job(job_id=once_job_id)
        if query_job:
            QtrSchedulerUtil.remove_scheduler_job(job_id=once_job_id)
        job_info = cls.job_detail_services(query_db, page_object.job_id)
        if job_info:
            job_info.job_id = once_job_id
            QtrSchedulerUtil.execute_scheduler_job_once(job_info=job_info)
            result = dict(is_success=True, message='执行成功')
        else:
            result = dict(is_success=False, message='定时任务不存在')

        return CrudResponseModel(**result)

    @classmethod
    def delete_job_services(cls, query_db: Session, page_object: DeleteJobModel):
        """
        删除定时任务信息service
        :param query_db: orm对象
        :param page_object: 删除定时任务对象
        :return: 删除定时任务校验结果
        """
        if page_object.job_ids.split(','):
            job_id_list = page_object.job_ids.split(',')
            try:
                for job_id in job_id_list:
                    QtrSchedulerUtil.remove_scheduler_job(job_id)
                    JobDao.delete_job_dao(query_db, JobModel(jobId=job_id))
                query_db.commit()
                result = dict(is_success=True, message='删除成功')
            except Exception as e:
                query_db.rollback()
                raise e
        else:
            result = dict(is_success=False, message='传入定时任务id为空')
        return CrudResponseModel(**result)

    @classmethod
    def job_detail_services(cls, query_db: Session, job_id: int):
        """
        获取定时任务详细信息service
        :param query_db: orm对象
        :param job_id: 定时任务id
        :return: 定时任务id对应的信息
        """
        job = JobDao.get_job_detail_by_id(query_db, job_id=job_id)
        result = JobModel(**CamelCaseUtil.transform_result(job))

        return result

    @staticmethod
    async def export_job_list_services(request: Request, job_list: List):
        """
        导出定时任务信息service
        :param request: Request对象
        :param job_list: 定时任务信息列表
        :return: 定时任务信息对应excel的二进制数据
        """
        # 创建一个映射字典，将英文键映射到中文键
        mapping_dict = {
            "jobId": "任务编码",
            "jobName": "任务名称",
            "jobGroup": "任务组名",
            "jobExecutor": "任务执行器",
            "invokeTarget": "调用目标字符串",
            "jobArgs": "位置参数",
            "jobKwargs": "关键字参数",
            "cronExpression": "cron执行表达式",
            "misfirePolicy": "计划执行错误策略",
            "concurrent": "是否并发执行",
            "status": "状态",
            "createBy": "创建者",
            "createTime": "创建时间",
            "updateBy": "更新者",
            "updateTime": "更新时间",
            "remark": "备注",
        }

        data = job_list
        job_group_list = await DictDataService.query_dict_data_list_from_cache_services(request.app.state.redis,
                                                                                        dict_type='qtr_job_group')
        job_group_option = [dict(label=item.get('dictLabel'), value=item.get('dictValue')) for item in job_group_list]
        job_group_option_dict = {item.get('value'): item for item in job_group_option}
        job_executor_list = await DictDataService.query_dict_data_list_from_cache_services(request.app.state.redis,
                                                                                           dict_type='qtr_job_executor')
        job_executor_option = [dict(label=item.get('dictLabel'), value=item.get('dictValue')) for item in
                               job_executor_list]
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
            if item.get('misfirePolicy') == '1':
                item['misfirePolicy'] = '立即执行'
            elif item.get('misfirePolicy') == '2':
                item['misfirePolicy'] = '执行一次'
            else:
                item['misfirePolicy'] = '放弃执行'
            if item.get('concurrent') == '0':
                item['concurrent'] = '允许'
            else:
                item['concurrent'] = '禁止'
        new_data = [{mapping_dict.get(key): value for key, value in item.items() if mapping_dict.get(key)} for item in
                    data]
        binary_data = export_list2excel(new_data)

        return binary_data
