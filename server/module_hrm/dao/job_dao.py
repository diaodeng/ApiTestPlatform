from sqlalchemy.orm import Session
from sqlalchemy.sql import or_, func # 不能把删掉，数据权限sql依赖

from module_admin.entity.do.dept_do import SysDept # 不能把删掉，数据权限sql依赖
from module_admin.entity.do.role_do import SysRoleDept # 不能把删掉，数据权限sql依赖
from module_hrm.entity.do.job_do import QtrJob
from module_hrm.entity.vo.job_vo import *
from utils.page_util import PageUtil


class JobDao:
    """
    定时任务管理模块数据库操作层
    """

    @classmethod
    def get_job_detail_by_id(cls, db: Session, job_id: int):
        """
        根据定时任务id获取定时任务详细信息
        :param db: orm对象
        :param job_id: 定时任务id
        :return: 定时任务信息对象
        """
        job_info = db.query(QtrJob) \
            .filter(QtrJob.job_id == job_id) \
            .first()

        return job_info

    @classmethod
    def get_job_detail_by_info(cls, db: Session, job: JobModel):
        """
        根据定时任务参数获取定时任务信息
        :param db: orm对象
        :param job: 定时任务参数对象
        :return: 定时任务信息对象
        """
        job_info = db.query(QtrJob) \
            .filter(QtrJob.job_name == job.job_name if job.job_name else True,
                    QtrJob.job_group == job.job_group if job.job_group else True,
                    QtrJob.invoke_target == job.invoke_target if job.invoke_target else True,
                    QtrJob.cron_expression == job.cron_expression if job.cron_expression else True) \
            .first()

        return job_info

    @classmethod
    def get_job_list(cls, db: Session, query_object: JobPageQueryModel, data_scope_sql: str,  is_page: bool = False):
        """
        根据查询参数获取定时任务列表信息
        :param db: orm对象
        :param query_object: 查询参数对象
        :param data_scope_sql: 数据权限依赖sql
        :param is_page: 是否开启分页
        :return: 定时任务列表信息对象
        """
        query = db.query(QtrJob) \
            .filter(QtrJob.job_name.like(f'%{query_object.job_name}%') if query_object.job_name else True,
                    QtrJob.job_group == query_object.job_group if query_object.job_group else True,
                    QtrJob.status == query_object.status if query_object.status else True,
                    eval(data_scope_sql)
                    ) \
            .order_by(QtrJob.create_time.desc(), QtrJob.update_time.desc()).distinct()
        job_list = PageUtil.paginate(query, query_object.page_num, query_object.page_size, is_page)

        return job_list

    @classmethod
    def get_job_list_for_scheduler(cls, db: Session):
        """
        获取定时任务列表信息
        :param db: orm对象
        :return: 定时任务列表信息对象
        """
        job_list = db.query(QtrJob) \
            .filter(QtrJob.status == '0') \
            .distinct().all()

        return job_list

    @classmethod
    def add_job_dao(cls, db: Session, job: JobModel):
        """
        新增定时任务数据库操作
        :param db: orm对象
        :param job: 定时任务对象
        :return:
        """
        model_data = job.model_dump(exclude_unset=True)
        db_job = QtrJob(**model_data)
        db.add(db_job)
        db.flush()

        return db_job

    @classmethod
    def edit_job_dao(cls, db: Session, job: dict):
        """
        编辑定时任务数据库操作
        :param db: orm对象
        :param job: 需要更新的定时任务字典
        :return:
        """
        db.query(QtrJob) \
            .filter(QtrJob.job_id == job.get('job_id')) \
            .update(job)

    @classmethod
    def delete_job_dao(cls, db: Session, job: JobModel):
        """
        删除定时任务数据库操作
        :param db: orm对象
        :param job: 定时任务对象
        :return:
        """
        db.query(QtrJob) \
            .filter(QtrJob.job_id == job.job_id) \
            .delete()
