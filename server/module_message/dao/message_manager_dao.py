from sqlalchemy.orm import Session
from sqlalchemy.sql import or_, func # 不能把删掉，数据权限sql依赖

from module_admin.entity.do.dept_do import SysDept # 不能把删掉，数据权限sql依赖
from module_admin.entity.do.role_do import SysRoleDept # 不能把删掉，数据权限sql依赖
from module_message.entity.do.message_manager import QtrMessageManager
from module_message.entity.dto.message_manager_dto import MessageManagerModel
from module_message.entity.vo.message_manager_vo import MessageManagerPageQueryModel, MessageDeleteModel
from utils.page_util import PageUtil


class MessageManagerDao:
    """
    消息推送配置管理模块数据库操作层
    """

    @classmethod
    def get_message_detail_by_id(cls, db: Session, data_id: int) -> QtrMessageManager|None:
        """
        根据id获取详细信息
        :param db: orm对象
        :param data_id: 数据id
        :return: 信息对象
        """
        message_info = db.query(QtrMessageManager) \
            .filter(QtrMessageManager.message_id == data_id) \
            .first()

        return message_info

    @classmethod
    def get_message_detail_by_info(cls, db: Session, message: MessageManagerModel) -> QtrMessageManager|None:
        """
        根据参数获取信息
        :param db: orm对象
        :param message: 参数对象
        :return: 信息对象
        """
        message_info = db.query(QtrMessageManager) \
            .filter(QtrMessageManager.name == message.name if message.name else True,
                    QtrMessageManager.push_way == message.push_way if message.push_way else True,
                    QtrMessageManager.status == message.status if message.status else True,
                    QtrMessageManager.config_type == message.config_type if message.config_type else True) \
            .first()

        return message_info

    @classmethod
    def get_message_list(cls, db: Session, query_object: MessageManagerPageQueryModel, data_scope_sql: str,  is_page: bool = False) -> list[QtrMessageManager]:
        """
        根据查询参数获取列表信息
        :param db: orm对象
        :param query_object: 查询参数对象
        :param data_scope_sql: 数据权限依赖sql
        :param is_page: 是否开启分页
        :return: 列表信息对象
        """
        query = db.query(QtrMessageManager) \
            .filter(QtrMessageManager.name.like(f'%{query_object.message_name}%') if query_object.message_name else True,
                    QtrMessageManager.push_way == query_object.push_way if query_object.push_way else True,
                    QtrMessageManager.status == query_object.status if query_object.status else True,
                    QtrMessageManager.config_type == query_object.config_type if query_object.config_type else True,
                    eval(data_scope_sql)
                    ) \
            .order_by(QtrMessageManager.create_time.desc(), QtrMessageManager.update_time.desc()).distinct()
        message_list = PageUtil.paginate(query, query_object.page_num, query_object.page_size, is_page)

        return message_list

    @classmethod
    def add_message_dao(cls, db: Session, message: MessageManagerModel):
        """
        新增数据库操作
        :param db: orm对象
        :param message: 对象
        :return:
        """
        model_data = message.model_dump(exclude_unset=True)
        db_message = QtrMessageManager(**model_data)
        db.add(db_message)
        db.flush()

        return db_message

    @classmethod
    def edit_message_dao(cls, db: Session, message: MessageManagerModel):
        """
        编辑数据库操作
        :param db: orm对象
        :param message: 需要更新的字典
        :return:
        """
        db.query(QtrMessageManager) \
            .filter(QtrMessageManager.message_id == message.message_id) \
            .update(message.model_dump(exclude_unset=True))

    @classmethod
    def delete_message_dao(cls, db: Session, message: MessageDeleteModel):
        """
        删除数据库操作
        :param db: orm对象
        :param message: 对象
        :return:
        """
        db.query(QtrMessageManager) \
            .filter(QtrMessageManager.message_id.in_(message.message_ids)) \
            .delete()
