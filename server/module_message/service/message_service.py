from sqlalchemy.orm import Session

from module_admin.service.dict_service import Request, DictDataService
from module_message.dao.message_manager_dao import MessageManagerDao
from module_message.entity.do.message_manager import QtrMessageManager
from module_message.entity.dto.common_dto import CrudResponseModel
from module_message.entity.dto.message_manager_dto import MessageManagerModel
from module_message.entity.vo.message_manager_vo import MessageManagerPageQueryModel, MessageDeleteModel
from utils.common_util import export_list2excel, CamelCaseUtil


class MessageService:
    """
    管理模块服务层
    """

    @classmethod
    def get_message_list_services(cls, query_db: Session, query_object: MessageManagerPageQueryModel, data_scope_sql: str, is_page: bool = False) -> list[QtrMessageManager]:
        """
        获取列表信息service
        :param query_db: orm对象
        :param query_object: 查询参数对象
        :param data_scope_sql: 数据权限依赖sql
        :param is_page: 是否开启分页
        :return: 列表信息对象
        """
        message_list_result = MessageManagerDao.get_message_list(query_db, query_object, data_scope_sql, is_page)

        return message_list_result

    @classmethod
    def add_message_services(cls, query_db: Session, page_object: MessageManagerModel):
        """
        新增信息service
        :param query_db: orm对象
        :param page_object: 新增对象
        :return: 新增校验结果
        """
        message = MessageManagerDao.get_message_detail_by_info(query_db, page_object)
        if message:
            result = dict(is_success=False, message='已存在')
        else:
            try:
                MessageManagerDao.add_message_dao(query_db, page_object)
                query_db.commit()
                result = dict(is_success=True, message='新增成功')
            except Exception as e:
                query_db.rollback()
                raise e

        return CrudResponseModel(**result)

    @classmethod
    def edit_message_services(cls, query_db: Session, page_object: MessageManagerModel):
        """
        编辑信息service
        :param query_db: orm对象
        :param page_object: 编辑对象
        :return: 编辑校验结果
        """

        message_info = cls.message_detail_services(query_db, page_object.message_id)
        if message_info:

            try:
                MessageManagerDao.edit_message_dao(query_db, page_object)
                query_db.commit()
                result = dict(is_success=True, message='更新成功')
            except Exception as e:
                query_db.rollback()
                raise e
        else:
            result = dict(is_success=False, message='不存在')

        return CrudResponseModel(**result)

    @classmethod
    def delete_message_services(cls, query_db: Session, page_object: MessageDeleteModel):
        """
        删除信息service
        :param query_db: orm对象
        :param page_object: 删除对象
        :return: 删除校验结果
        """

        try:
            MessageManagerDao.delete_message_dao(query_db, page_object)
            query_db.commit()
            result = dict(is_success=True, message='删除成功')
        except Exception as e:
            query_db.rollback()
            raise e

        return CrudResponseModel(**result)

    @classmethod
    def message_detail_services(cls, query_db: Session, message_id: int):
        """
        获取详细信息service
        :param query_db: orm对象
        :param message_id: id
        :return: id对应的信息
        """
        message = MessageManagerDao.get_message_detail_by_id(query_db, data_id=message_id)
        result = MessageManagerModel(**CamelCaseUtil.transform_result(message))

        return result

    @staticmethod
    async def export_message_list_services(query_db: Session, query_object: MessageManagerPageQueryModel, data_scope_sql: str):
        """
        导出信息service
        :param query_db: 数据库连接
        :param query_object: 查询对象
        :param data_scope_sql: 数据权限依赖sql
        :return: 信息对应excel的二进制数据
        """
        # 创建一个映射字典，将英文键映射到中文键
        data = MessageService.get_message_list_services(query_db, query_object, data_scope_sql, is_page=False)
        mapping_dict = {
            "messageId": "任务编码",
            "messageName": "任务名称",
            "messageGroup": "任务组名",
            "messageExecutor": "任务执行器",
            "invokeTarget": "调用目标字符串",
            "messageArgs": "位置参数",
            "messageKwargs": "关键字参数",
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

        new_data = [{key: value for key, value in item.__dict__.items()} for item in
                    data]
        binary_data = export_list2excel(new_data)

        return binary_data

    @staticmethod
    async def export_message_list_temp_services():
        data = [{
            "messageId": "任务编码",
            "messageName": "任务名称",
            "messageGroup": "任务组名",
            "messageExecutor": "任务执行器",
            "invokeTarget": "调用目标字符串",
            "messageArgs": "位置参数",
            "messageKwargs": "关键字参数",
            "cronExpression": "cron执行表达式",
            "misfirePolicy": "计划执行错误策略",
            "concurrent": "是否并发执行",
            "status": "状态",
            "createBy": "创建者",
            "createTime": "创建时间",
            "updateBy": "更新者",
            "updateTime": "更新时间",
            "remark": "备注",
        }]
        binary_data = export_list2excel(data)

        return binary_data