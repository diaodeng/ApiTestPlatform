from sqlalchemy.orm import Session

from module_admin.entity.vo.common_vo import CrudResponseModel
from module_admin.entity.vo.job_vo import DeleteJobModel, EditJobModel, JobModel, JobPageQueryModel, RunJobModel
from module_task.celery_job_service import CeleryJobService


class JobService:
    """
    系统任务服务（owner_type=sys）。
    """

    OWNER_TYPE = "sys"

    @classmethod
    def get_job_list_services(cls, query_db: Session, query_object: JobPageQueryModel, is_page: bool = False):
        """
        获取系统任务列表。

        :param query_db: 数据库会话。
        :param query_object: 查询模型。
        :param is_page: 是否分页。
        :return: 分页结果或列表结果。
        """
        return CeleryJobService.get_job_list_services(
            query_db=query_db,
            owner_type=cls.OWNER_TYPE,
            query_object=query_object,
            data_scope_sql=True,
            is_page=is_page,
        )

    @classmethod
    def add_job_services(cls, query_db: Session, page_object: JobModel):
        """
        新增系统任务。

        :param query_db: 数据库会话。
        :param page_object: 新增模型。
        :return: CRUD 响应。
        """
        return CeleryJobService.add_job_services(query_db=query_db, owner_type=cls.OWNER_TYPE, page_object=page_object)

    @classmethod
    def edit_job_services(cls, query_db: Session, page_object: EditJobModel):
        """
        编辑系统任务。

        :param query_db: 数据库会话。
        :param page_object: 编辑模型。
        :return: CRUD 响应。
        """
        return CeleryJobService.edit_job_services(query_db=query_db, owner_type=cls.OWNER_TYPE, page_object=page_object)

    @classmethod
    def change_status(cls, query_db: Session, task_id: int, enabled: bool, update_by: str = ""):
        """
        修改系统任务启停状态。

        :param query_db: 数据库会话。
        :param task_id: 任务ID。
        :param enabled: 是否启用。
        :param update_by: 更新人。
        :return: CRUD 响应。
        """
        return CeleryJobService.change_status_services(
            query_db=query_db,
            owner_type=cls.OWNER_TYPE,
            task_id=task_id,
            enabled=enabled,
            update_by=update_by,
        )

    @classmethod
    def execute_job_once_services(cls, query_db: Session, page_object: JobModel):
        """
        手动执行一次系统任务。

        :param query_db: 数据库会话。
        :param page_object: 任务模型（仅需 task_id）。
        :return: CRUD 响应。
        """
        if not page_object.task_id:
            return CrudResponseModel(is_success=False, message="task_id 不能为空")
        run_model = RunJobModel(taskId=page_object.task_id)
        return CeleryJobService.execute_job_once_services(
            query_db=query_db,
            owner_type=cls.OWNER_TYPE,
            page_object=run_model,
        )

    @classmethod
    def delete_job_services(cls, query_db: Session, page_object: DeleteJobModel):
        """
        删除系统任务。

        :param query_db: 数据库会话。
        :param page_object: 删除模型。
        :return: CRUD 响应。
        """
        return CeleryJobService.delete_job_services(
            query_db=query_db,
            owner_type=cls.OWNER_TYPE,
            page_object=page_object,
        )

    @classmethod
    def job_detail_services(cls, query_db: Session, task_id: int):
        """
        查询系统任务详情。

        :param query_db: 数据库会话。
        :param task_id: 任务ID。
        :return: 任务详情。
        """
        return CeleryJobService.job_detail_services(query_db=query_db, owner_type=cls.OWNER_TYPE, task_id=task_id)

    @staticmethod
    async def export_job_list_services(request, job_list: list):
        """
        导出系统任务列表。

        :param request: 请求对象（兼容原签名，当前未使用）。
        :param job_list: 任务列表。
        :return: Excel 二进制内容。
        """
        return await CeleryJobService.export_job_list_services(job_list)
