from sqlalchemy.orm import Session

from module_admin.entity.do.ai_task_execution_do import SysAiTaskExecution
from module_admin.entity.vo.ai_task_execution_vo import AiTaskExecutionQueryModel


class AiTaskExecutionDao:
    """
    AI 任务执行审计数据库访问层。
    """

    @classmethod
    def get_ai_task_execution_by_id(cls, db: Session, execution_id: int):
        """
        根据执行ID获取审计记录。
        :param db: orm对象
        :param execution_id: 执行ID
        :return: 审计记录或None
        """
        return (
            db.query(SysAiTaskExecution)
            .filter(SysAiTaskExecution.execution_id == execution_id, SysAiTaskExecution.del_flag == "0")
            .first()
        )

    @classmethod
    def get_ai_task_execution_list(cls, db: Session, query_object: AiTaskExecutionQueryModel):
        """
        根据查询条件获取审计记录分页数据。
        :param db: orm对象
        :param query_object: 查询对象
        :return: 分页结果字典
        """
        query = db.query(SysAiTaskExecution).filter(SysAiTaskExecution.del_flag == "0")
        if query_object.task_type:
            query = query.filter(SysAiTaskExecution.task_type == query_object.task_type)
        if query_object.source_type:
            query = query.filter(SysAiTaskExecution.source_type == query_object.source_type)
        if query_object.source_ref:
            query = query.filter(SysAiTaskExecution.source_ref.like(f"%{query_object.source_ref}%"))
        if query_object.provider_code:
            query = query.filter(SysAiTaskExecution.provider_code == query_object.provider_code)
        if query_object.status:
            query = query.filter(SysAiTaskExecution.status == query_object.status)
        if query_object.keyword:
            like_keyword = f"%{query_object.keyword}%"
            query = query.filter(
                (SysAiTaskExecution.task_name.like(like_keyword))
                | (SysAiTaskExecution.source_ref.like(like_keyword))
                | (SysAiTaskExecution.error_message.like(like_keyword))
            )
        query = query.order_by(SysAiTaskExecution.create_time.desc(), SysAiTaskExecution.execution_id.desc())
        total = query.count()
        rows = query.offset((query_object.page_num - 1) * query_object.page_size).limit(query_object.page_size).all()
        return {
            "rows": rows,
            "page_num": query_object.page_num,
            "page_size": query_object.page_size,
            "total": total,
            "has_next": total > query_object.page_num * query_object.page_size,
        }

    @classmethod
    def add_ai_task_execution_dao(cls, db: Session, execution_data: dict):
        """
        新增审计记录。
        :param db: orm对象
        :param execution_data: 需要写入数据库的字典
        :return: 新增后的数据库对象
        """
        db_execution = SysAiTaskExecution(**execution_data)
        db.add(db_execution)
        db.flush()
        return db_execution

    @classmethod
    def edit_ai_task_execution_dao(cls, db: Session, execution_id: int, execution_data: dict):
        """
        更新审计记录。
        :param db: orm对象
        :param execution_id: 执行ID
        :param execution_data: 更新字段字典
        :return: 无
        """
        (
            db.query(SysAiTaskExecution)
            .filter(SysAiTaskExecution.execution_id == execution_id, SysAiTaskExecution.del_flag == "0")
            .update(execution_data)
        )
