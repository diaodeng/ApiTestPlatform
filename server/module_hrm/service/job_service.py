import json

from sqlalchemy.orm import Session

from module_admin.entity.vo.common_vo import DataScopeExpr
from module_admin.entity.vo.user_vo import CurrentUserModel
from module_hrm.entity.vo.common_vo import CrudResponseModel
from module_hrm.entity.vo.job_vo import (
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
    QTR 任务服务（owner_type=qtr）。
    """

    OWNER_TYPE = "qtr"
    QTR_QUEUE = "qtr"
    QTR_PROCESS_QUEUE = "qtr_process"
    QTR_TASK_KEY = "module_task.scheduler_qtr.job_run_test"

    @classmethod
    def _resolve_queue_name(cls, execution_mode: str | None) -> str:
        """
        根据执行方式解析 QTR 任务投递队列。

        :param execution_mode: 执行方式，支持 thread/process。
        :return: Celery 队列名。
        """
        return cls.QTR_PROCESS_QUEUE if str(execution_mode or "thread").strip().lower() == "process" else cls.QTR_QUEUE

    @classmethod
    def get_job_list_services(
        cls,
        query_db: Session,
        query_object: JobPageQueryModel,
        data_scope_sql: DataScopeExpr,
        is_page: bool = False,
    ):
        """
        获取 QTR 任务列表。

        :param query_db: 数据库会话。
        :param query_object: 查询模型。
        :param data_scope_sql: 数据权限表达式。
        :param is_page: 是否分页。
        :return: 分页结果或列表结果。
        """
        return CeleryJobService.get_job_list_services(
            query_db=query_db,
            owner_type=cls.OWNER_TYPE,
            query_object=query_object,
            data_scope_sql=data_scope_sql,
            is_page=is_page,
        )

    @classmethod
    def add_job_services(cls, query_db: Session, page_object: JobModel, user_info: CurrentUserModel):
        """
        新增 QTR 任务。

        :param query_db: 数据库会话。
        :param page_object: 新增模型。
        :param user_info: 当前用户信息。
        :return: CRUD 响应。
        """
        task_params = page_object.task_kwargs or "{}"
        task_params = json.loads(task_params)
        task_params["userName"] = user_info.user.user_name
        task_params["userId"] = user_info.user.user_id
        task_params["runner"] = user_info.user.user_id
        task_params["deptId"] = user_info.user.dept_id
        page_object.task_kwargs = json.dumps(task_params, ensure_ascii=False)

        page_object.owner_user_id = user_info.user.user_id
        page_object.owner_dept_id = user_info.user.dept_id
        page_object.queue_name = cls._resolve_queue_name(page_object.execution_mode)
        page_object.task_key = cls.QTR_TASK_KEY
        page_object.task_args = "[]"
        return CeleryJobService.add_job_services(query_db=query_db, owner_type=cls.OWNER_TYPE, page_object=page_object)

    @classmethod
    def edit_job_services(cls, query_db: Session, page_object: EditJobModel, user_info: CurrentUserModel):
        """
        编辑 QTR 任务。

        :param query_db: 数据库会话。
        :param page_object: 编辑模型。
        :param user_info: 当前用户信息。
        :return: CRUD 响应。
        """
        if page_object.owner_user_id is None:
            page_object.owner_user_id = user_info.user.user_id
        if page_object.owner_dept_id is None:
            page_object.owner_dept_id = user_info.user.dept_id
        page_object.queue_name = cls._resolve_queue_name(page_object.execution_mode)
        page_object.task_key = cls.QTR_TASK_KEY
        page_object.task_args = "[]"
        return CeleryJobService.edit_job_services(query_db=query_db, owner_type=cls.OWNER_TYPE, page_object=page_object)

    @classmethod
    def change_status(cls, query_db: Session, task_id: int, enabled: bool, update_by: str = ""):
        """
        修改 QTR 任务启停状态。

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
        手动执行一次 QTR 任务。

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
        删除 QTR 任务。

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
        查询 QTR 任务详情。

        :param query_db: 数据库会话。
        :param task_id: 任务ID。
        :return: 任务详情。
        """
        return CeleryJobService.job_detail_services(query_db=query_db, owner_type=cls.OWNER_TYPE, task_id=task_id)

    @classmethod
    def list_running_jobs_services(cls, query_db: Session, data_scope_sql: DataScopeExpr) -> list[dict]:
        """
        获取 QTR 任务运行态快照。

        :param query_db: 数据库会话。
        :param data_scope_sql: 数据权限表达式。
        :return: 运行态任务列表。
        """
        return CeleryJobService.list_running_job_tasks_services(
            query_db=query_db,
            owner_type=cls.OWNER_TYPE,
            data_scope_sql=data_scope_sql,
        )

    @classmethod
    def cancel_running_job_services(
        cls,
        query_db: Session,
        page_object: ControlRunningTaskModel,
        data_scope_sql: DataScopeExpr,
    ) -> CrudResponseModel:
        """
        取消 QTR 任务执行（撤销未执行任务）。

        :param query_db: 数据库会话。
        :param page_object: 控制任务请求模型。
        :param data_scope_sql: 数据权限表达式。
        :return: CRUD 响应。
        """
        return CeleryJobService.revoke_running_job_services(
            query_db=query_db,
            owner_type=cls.OWNER_TYPE,
            page_object=page_object,
            terminate=False,
            data_scope_sql=data_scope_sql,
        )

    @classmethod
    def terminate_running_job_services(
        cls,
        query_db: Session,
        page_object: ControlRunningTaskModel,
        data_scope_sql: DataScopeExpr,
    ) -> CrudResponseModel:
        """
        终止 QTR 任务执行（尝试强制终止运行中任务）。

        :param query_db: 数据库会话。
        :param page_object: 控制任务请求模型。
        :param data_scope_sql: 数据权限表达式。
        :return: CRUD 响应。
        """
        return CeleryJobService.revoke_running_job_services(
            query_db=query_db,
            owner_type=cls.OWNER_TYPE,
            page_object=page_object,
            terminate=True,
            data_scope_sql=data_scope_sql,
        )

    @staticmethod
    async def export_job_list_services(request, job_list: list):
        """
        导出 QTR 任务列表。

        :param request: 请求对象（兼容原签名，当前未使用）。
        :param job_list: 任务列表。
        :return: Excel 二进制内容。
        """
        return await CeleryJobService.export_job_list_services(job_list)
