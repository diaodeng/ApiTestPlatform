from sqlalchemy.orm import Session

from module_admin.entity.vo.common_vo import CrudResponseModel
from module_admin.entity.vo.job_vo import (
    ControlRunningTaskModel,
    DeleteJobModel,
    EditJobModel,
    JobModel,
    JobPageQueryModel,
    RunJobModel,
)
from module_task.celery_job_service import CeleryJobService


class JobService:
    """
    系统任务服务（owner_type=sys）。
    """

    OWNER_TYPE = "sys"
    SYS_QUEUE = "sys"

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
        page_object.queue_name = cls.SYS_QUEUE
        page_object.task_args = "[]"
        return CeleryJobService.add_job_services(query_db=query_db, owner_type=cls.OWNER_TYPE, page_object=page_object)

    @classmethod
    def edit_job_services(cls, query_db: Session, page_object: EditJobModel):
        """
        编辑系统任务。

        :param query_db: 数据库会话。
        :param page_object: 编辑模型。
        :return: CRUD 响应。
        """
        page_object.queue_name = cls.SYS_QUEUE
        page_object.task_args = "[]"
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

    @classmethod
    def list_running_jobs_services(cls, query_db: Session) -> list[dict]:
        """
        获取系统任务运行态快照。

        :param query_db: 数据库会话。
        :return: 运行态任务列表。
        """
        return CeleryJobService.list_running_job_tasks_services(
            query_db=query_db,
            owner_type=cls.OWNER_TYPE,
            data_scope_sql=True,
        )

    @classmethod
    def cancel_running_job_services(cls, query_db: Session, page_object: ControlRunningTaskModel) -> CrudResponseModel:
        """
        取消系统任务执行（撤销未执行任务）。

        :param query_db: 数据库会话。
        :param page_object: 控制任务请求模型。
        :return: CRUD 响应。
        """
        return CeleryJobService.revoke_running_job_services(
            query_db=query_db,
            owner_type=cls.OWNER_TYPE,
            page_object=page_object,
            terminate=False,
            data_scope_sql=True,
        )

    @classmethod
    def terminate_running_job_services(
        cls,
        query_db: Session,
        page_object: ControlRunningTaskModel,
    ) -> CrudResponseModel:
        """
        终止系统任务执行（尝试强制终止运行中任务）。

        :param query_db: 数据库会话。
        :param page_object: 控制任务请求模型。
        :return: CRUD 响应。
        """
        return CeleryJobService.revoke_running_job_services(
            query_db=query_db,
            owner_type=cls.OWNER_TYPE,
            page_object=page_object,
            terminate=True,
            data_scope_sql=True,
        )

    @staticmethod
    async def export_job_list_services(request, job_list: list):
        """
        导出系统任务列表。

        :param request: 请求对象（兼容原签名，当前未使用）。
        :param job_list: 任务列表。
        :return: Excel 二进制内容。
        """
        return await CeleryJobService.export_job_list_services(job_list)

    @staticmethod
    def list_registered_task_keys() -> list[str]:
        """
        获取任务注册键列表。

        :return: 任务注册键字符串列表。
        """
        return CeleryJobService.list_registered_task_keys()
