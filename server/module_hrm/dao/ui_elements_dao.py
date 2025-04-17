import datetime

from sqlalchemy.orm import Session

from module_admin.entity.vo.user_vo import CurrentUserModel
from module_hrm.entity.do.ui_elements_manager_do import QtrElements
from module_hrm.entity.vo.elements_vo import ElementsModelForApi, ElementsQueryModel, ElementsModel, \
    ElementsPageQueryModel
from module_hrm.enums.enums import QtrDataStatusEnum
from module_hrm.exceptions import ExistsError
from module_hrm.utils.util import PermissionHandler
from utils.log_util import logger
from utils.page_util import PageUtil


class ElementsOperation(object):
    def __init__(self):
        pass

    @staticmethod
    def check_name_repeat(query_db: Session, element_info: ElementsModelForApi):

        query_data = query_db.query(QtrElements).filter(
            QtrElements.name == element_info.name,
            QtrElements.project_id == element_info.project_id,
            QtrElements.module_id == element_info.module_id,
            QtrElements.page_id == element_info.page_id,
            QtrElements.group_id == element_info.group_id
        )
        if element_info.element_id:
            query_data = query_data.filter(QtrElements.element_id != element_info.element_id)
        if query_data.first():
            raise ExistsError(f"已存在名为【{element_info.name}】的元素，请检查或修改名称！")

    @staticmethod
    def get(query_db: Session, element_id: int) -> QtrElements | None:

        element_data_obj = query_db.query(QtrElements).filter(QtrElements.element_id == element_id).first()
        return element_data_obj

    @staticmethod
    def get_element_detail_by_info(query_db: Session, element_info: ElementsModelForApi):
        query = query_db.query(QtrElements)
        if element_info.element_id:
            query = query.filter(QtrElements.element_id == element_info.element_id)
        if element_info.name:
            query = query.filter(QtrElements.name == element_info.name)

        return query.first()

    @staticmethod
    def delete(query_db: Session, ids: list, permanent_delete: bool = False, user: CurrentUserModel = None):
        """
        :param query_db: 数据库session
        :param ids: 待删除的元素ID集合
        :param permanent_delete: 是否永久删除
        :param user: 当前操作的用户信息
        """
        try:

            query = query_db.query(QtrElements).filter(QtrElements.element_id.in_(ids))
            if permanent_delete:
                query.delete()
            else:
                query.update({
                    "status": QtrDataStatusEnum.deleted.value,
                    "update_by": user.user.user_id,
                    "update_time": datetime.datetime.now(),
                })
            query_db.commit()
        except Exception as e:
            logger.error(f"删除element失败：{ids}")
            logger.error(e, exc_info=True)
            raise TypeError(f"删除element失败：{e}")
        return "删除成功"

    @staticmethod
    def update(query_db: Session, element_info: ElementsModelForApi, user: CurrentUserModel = None):
        PermissionHandler.check_is_self(user, element_info)

        ElementsOperation.check_name_repeat(query_db, element_info)

        data_info = element_info.model_dump(exclude_unset=True, by_alias=True)
        data_info = ElementsModel(**data_info).model_dump(exclude_unset=True)
        # data_info.pop("element_id")
        # data_info.pop("type")
        old_data = query_db.query(QtrElements).filter(QtrElements.element_id == element_info.element_id)
        old_data.update(data_info)
        query_db.commit()
        # return QtrElements.objects.get(id=element_id)
        return ElementsModelForApi.from_orm(old_data.first()).model_dump(by_alias=True)

    @staticmethod
    def move_element(query_db: Session, move_info: ElementsModel, ids):
        update_data_info = {}
        if move_info.project_id:
            update_data_info['project_id'] = move_info.project_id
        if move_info.module_id:
            update_data_info['module_id'] = move_info.module_id
        if move_info.page_id:
            update_data_info['page_id'] = move_info.page_id
        if move_info.group_id:
            update_data_info['group_id'] = move_info.group_id

        data = query_db.query(QtrElements).filter(QtrElements.element_id.in_(ids)).update(update_data_info)
        query_db.commit()
        return data

    @staticmethod
    def add(query_db: Session, element_info: ElementsModel | ElementsModelForApi):
        ElementsOperation.check_name_repeat(query_db, element_info)
        data_info = element_info.model_dump(exclude_unset=True, by_alias=True)
        data_info = ElementsModel(**data_info).model_dump(exclude_unset=True)
        new_element_obj = QtrElements(**data_info)
        query_db.add(new_element_obj)
        query_db.commit()

        return ElementsModelForApi.model_validate(new_element_obj).model_dump(by_alias=True)

    @staticmethod
    def copy(query_db: Session, id, name=None):
        """
        复制element信息，默认插入到当前项目、莫夸
        :param id: str or int: 复制源
        :param name: str：新名称，不指定则在原名称后加-副本
        :return: ok or tips
        """
        if not isinstance(id, list):
            ids = [id]
        else:
            ids = id

        datas = []
        for id in ids:
            element = query_db.query(QtrElements).filter(QtrElements.element_id == id).first()
            if not name:
                name = element.name + "-副本"
            element.element_id = None
            element.name = name
            query_db.add(element)
            datas.append(element.element_id)
            logger.info('{name}element复制成功'.format(name=name))
        query_db.commit()
        return datas

    @staticmethod
    def query_list(query_db: Session, query_info: ElementsPageQueryModel, data_scope_sql: str, is_page: bool = True):
        """
        查询element列表
        :param query_db: 数据库session
        :param query_info:
        :param data_scope_sql: 数据权限sql
        :param is_page: bool
        :return:
        """
        # 1. 先查询出所有的element
        query_obj = query_db.query(QtrElements)
        # 2. 再根据element的名称、请求方式、项目、模块进行过滤
        if query_info.manager:
            query_obj = query_obj.filter(QtrElements.manager == query_info.manager)
        if query_info.name:
            query_obj = query_obj.filter(QtrElements.name.like(f"%{query_info.name}%"))
        if query_info.project_id:
            query_obj = query_obj.filter(QtrElements.project_id == query_info.project_id)
        if query_info.module_id:
            query_obj = query_obj.filter(QtrElements.module_id == query_info.module_id)
        if query_info.page_id:
            query_obj = query_obj.filter(QtrElements.page_id == query_info.page_id)
        if query_info.group_id:
            query_obj = query_obj.filter(QtrElements.group_id == query_info.group_id)

        query_obj = query_obj.filter(eval(data_scope_sql))

        # 添加排序条件
        query_obj = query_obj.order_by(QtrElements.sort, QtrElements.create_time.desc(),
                                       QtrElements.update_time.desc()).distinct()

        post_list = PageUtil.paginate(query_obj, query_info.page_num, query_info.page_size, is_page)

        return post_list
