from sqlalchemy.orm import Session

from module_admin.entity.vo.common_vo import DataScopeExpr
from module_hrm.entity.vo.job_vo import DeleteJobLogModel, JobLogPageQueryModel
from module_task.celery_job_service import CeleryJobService


class JobLogService:
    """
    QTR 任务日志服务（owner_type=qtr）。
    """

    OWNER_TYPE = "qtr"

    @classmethod
    def get_job_log_list_services(
        cls,
        query_db: Session,
        query_object: JobLogPageQueryModel,
        data_scope_sql: DataScopeExpr,
        is_page: bool = False,
    ):
        """
        获取 QTR 任务日志列表。

        :param query_db: 数据库会话。
        :param query_object: 查询模型。
        :param data_scope_sql: 数据权限表达式。
        :param is_page: 是否分页。
        :return: 分页结果或列表结果。
        """
        return CeleryJobService.get_job_log_list_services(
            query_db=query_db,
            owner_type=cls.OWNER_TYPE,
            query_object=query_object,
            data_scope_sql=data_scope_sql,
            is_page=is_page,
        )

    @classmethod
    def delete_job_log_services(cls, query_db: Session, page_object: DeleteJobLogModel):
        """
        删除 QTR 任务日志。

        :param query_db: 数据库会话。
        :param page_object: 删除模型。
        :return: CRUD 响应。
        """
        return CeleryJobService.delete_job_log_services(
            query_db=query_db,
            owner_type=cls.OWNER_TYPE,
            page_object=page_object,
        )

    @classmethod
    def clear_job_log_services(cls, query_db: Session, data_scope_sql: DataScopeExpr = True):
        """
        清空 QTR 任务日志。

        :param query_db: 数据库会话。
        :param data_scope_sql: 数据权限表达式。
        :return: CRUD 响应。
        """
        return CeleryJobService.clear_job_log_services(
            query_db=query_db,
            owner_type=cls.OWNER_TYPE,
            data_scope_sql=data_scope_sql,
        )

    @staticmethod
    async def export_job_log_list_services(request, job_log_list: list):
        """
        导出 QTR 任务日志。

        :param request: 请求对象（兼容原签名，当前未使用）。
        :param job_log_list: 日志列表。
        :return: Excel 二进制内容。
        """
        return await CeleryJobService.export_job_log_list_services(job_log_list)
