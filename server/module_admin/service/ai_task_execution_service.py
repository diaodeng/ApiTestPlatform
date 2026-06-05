from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from module_admin.dao.ai_task_execution_dao import AiTaskExecutionDao
from module_admin.entity.vo.ai_task_execution_vo import AiTaskExecutionDetailModel, AiTaskExecutionQueryModel
from module_admin.entity.vo.common_vo import CrudResponseModel
from utils.page_util import PageResponseModel


class AiTaskExecutionService:
    """
    AI 任务执行审计服务层。
    """

    @classmethod
    def build_ai_task_execution_model(cls, execution_info) -> AiTaskExecutionDetailModel:
        """
        将数据库对象转换为返回模型。
        :param execution_info: AI任务执行数据库对象
        :return: 返回模型
        """
        return AiTaskExecutionDetailModel.model_validate(execution_info)

    @classmethod
    def get_ai_task_execution_list_services(
        cls,
        query_db: Session,
        query_object: AiTaskExecutionQueryModel,
    ) -> PageResponseModel:
        """
        获取 AI 任务执行审计分页列表。
        :param query_db: orm对象
        :param query_object: 查询对象
        :return: 分页响应对象
        """
        query_result = AiTaskExecutionDao.get_ai_task_execution_list(query_db, query_object)
        rows = [cls.build_ai_task_execution_model(item).model_dump(by_alias=True) for item in query_result["rows"]]
        return PageResponseModel(
            rows=rows,
            page_num=query_result["page_num"],
            page_size=query_result["page_size"],
            total=query_result["total"],
            has_next=query_result["has_next"],
        )

    @classmethod
    def get_ai_task_execution_detail_services(
        cls, query_db: Session, execution_id: int
    ) -> AiTaskExecutionDetailModel | None:
        """
        获取 AI 任务执行审计详情。
        :param query_db: orm对象
        :param execution_id: 执行ID
        :return: 详情模型，不存在时返回None
        """
        execution_info = AiTaskExecutionDao.get_ai_task_execution_by_id(query_db, execution_id)
        if not execution_info:
            return None
        return cls.build_ai_task_execution_model(execution_info)

    @classmethod
    def add_ai_task_execution_services(
        cls,
        query_db: Session,
        execution_data: dict[str, Any],
    ) -> CrudResponseModel:
        """
        新增 AI 任务执行审计记录。
        :param query_db: orm对象
        :param execution_data: 需要保存的执行信息
        :return: 新增结果
        """
        task_type = str(execution_data.get("task_type") or "").strip()
        task_name = str(execution_data.get("task_name") or "").strip()
        if not task_type:
            return CrudResponseModel(is_success=False, message="任务类型不能为空")
        if not task_name:
            return CrudResponseModel(is_success=False, message="任务名称不能为空")
        now = datetime.now()
        data = dict(execution_data)
        data["task_type"] = task_type
        data["task_name"] = task_name
        data["source_type"] = str(data.get("source_type") or "").strip() or None
        data["source_ref"] = str(data.get("source_ref") or "").strip() or None
        data["provider_code"] = str(data.get("provider_code") or "").strip() or None
        data["prompt_code"] = str(data.get("prompt_code") or "").strip() or None
        data["model_name"] = str(data.get("model_name") or "").strip() or None
        data["base_url"] = str(data.get("base_url") or "").strip() or None
        data["status"] = str(data.get("status") or "pending").strip() or "pending"
        data["error_message"] = str(data.get("error_message") or "").strip() or None
        data["created_by_name"] = str(data.get("created_by_name") or "").strip() or None
        data["create_time"] = data.get("create_time") or now
        data["update_time"] = data.get("update_time") or now
        try:
            db_execution = AiTaskExecutionDao.add_ai_task_execution_dao(query_db, data)
            query_db.commit()
            return CrudResponseModel(
                is_success=True,
                message="新增成功",
                result=cls.build_ai_task_execution_model(db_execution),
            )
        except Exception as exc:
            query_db.rollback()
            raise exc

    @classmethod
    def update_ai_task_execution_services(
        cls,
        query_db: Session,
        execution_id: int,
        execution_data: dict[str, Any],
    ) -> CrudResponseModel:
        """
        更新 AI 任务执行审计记录。
        :param query_db: orm对象
        :param execution_id: 执行ID
        :param execution_data: 更新字段
        :return: 更新结果
        """
        execution_info = AiTaskExecutionDao.get_ai_task_execution_by_id(query_db, execution_id)
        if not execution_info:
            return CrudResponseModel(is_success=False, message="审计记录不存在")
        update_data = dict(execution_data)
        if "task_type" in update_data:
            update_data["task_type"] = str(update_data.get("task_type") or "").strip() or execution_info.task_type
        if "task_name" in update_data:
            update_data["task_name"] = str(update_data.get("task_name") or "").strip() or execution_info.task_name
        for key in ("source_type", "source_ref", "provider_code", "prompt_code", "model_name", "base_url", "status"):
            if key in update_data:
                update_data[key] = str(update_data.get(key) or "").strip() or None
        if "error_message" in update_data:
            update_data["error_message"] = str(update_data.get("error_message") or "").strip() or None
        update_data["update_time"] = datetime.now()
        try:
            AiTaskExecutionDao.edit_ai_task_execution_dao(query_db, execution_id, update_data)
            query_db.commit()
            updated_execution = AiTaskExecutionDao.get_ai_task_execution_by_id(query_db, execution_id)
            return CrudResponseModel(
                is_success=True,
                message="修改成功",
                result=cls.build_ai_task_execution_model(updated_execution) if updated_execution else None,
            )
        except Exception as exc:
            query_db.rollback()
            raise exc
