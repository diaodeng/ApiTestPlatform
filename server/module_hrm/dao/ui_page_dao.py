import datetime

from sqlalchemy.orm import Session

from module_admin.entity.vo.user_vo import CurrentUserModel
from module_hrm.entity.do.ui_page_do import QtrUIPage
from module_hrm.entity.do.ui_page_relation_do import QtrPageRelation
from module_hrm.entity.vo.page_vo import PageModel, PageAddModel, PageQueryModel, \
    PagePageQueryModel, PageModelForApi, DeletePageModel
from module_hrm.enums.enums import QtrDataStatusEnum
from module_hrm.exceptions import ExistsError
from module_hrm.utils.util import PermissionHandler
from utils.log_util import logger
from utils.page_util import PageUtil


class PageOperation(object):
    def __init__(self):
        pass

    @staticmethod
    def check_name_repeat(query_db: Session, page_info: PageModelForApi):

        query_data = query_db.query(QtrUIPage).filter(
            QtrUIPage.name == page_info.name,
            QtrUIPage.project_id == page_info.project_id,
            QtrUIPage.module_id == page_info.module_id,
        )
        if page_info.module_id:
            query_data = query_data.filter(QtrUIPage.module_id != page_info.module_id)
        if query_data.first():
            raise ExistsError(f"已存在名为【{page_info.name}】的方法，请检查或修改名称！")

    @staticmethod
    def get(query_db: Session, page_id: int) -> QtrUIPage | None:

        page_data_obj = query_db.query(QtrUIPage).filter(QtrUIPage.page_id == page_id).first()
        return page_data_obj

    @staticmethod
    def get_page_detail_by_info(query_db: Session, page_info: PageModelForApi):
        query = query_db.query(QtrUIPage)
        if page_info.page_id:
            query = query.filter(QtrUIPage.page_id == page_info.page_id)
        if page_info.name:
            query = query.filter(QtrUIPage.name == page_info.name)

        return query.first()

    @staticmethod
    def get_page_children_by_info(query_db: Session, page_info: PageModelForApi):
        # 可能是页面，也可能是元素，需要返回类型
        query = query_db.query(QtrUIPage).join(QtrPageRelation)
        if page_info.page_id:
            query = query.filter(QtrUIPage.page_id == page_info.page_id)
        if page_info.name:
            query = query.filter(QtrUIPage.name == page_info.name)

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


            query = query_db.query(QtrUIPage).filter(QtrUIPage.page_id.in_(ids))
            if permanent_delete:
                query_db.query(QtrPageRelation).filter(QtrPageRelation.page_id.in_(ids)).delete()
                query.delete()
            else:
                query.update({
                    "status": QtrDataStatusEnum.deleted.value,
                    "update_by": user.user.user_id,
                    "update_time": datetime.datetime.now(),
                })
            query_db.commit()
        except Exception as e:
            logger.error(f"删除page失败：{ids}")
            logger.error(e, exc_info=True)
            raise TypeError(f"删除page失败：{e}")
        return "删除成功"

    @staticmethod
    def update(query_db: Session, page_info: PageModelForApi, user: CurrentUserModel = None):
        PermissionHandler.check_is_self(user, page_info)

        PageOperation.check_name_repeat(query_db, page_info)

        data_info = page_info.model_dump(exclude_unset=True, by_alias=True)
        data_info = PageModel(**data_info).model_dump(exclude_unset=True)
        old_data = query_db.query(QtrUIPage).filter(QtrUIPage.page_id == page_info.page_id)
        old_data.update(data_info)
        query_db.commit()
        return PageModelForApi.from_orm(old_data.first()).model_dump(by_alias=True)

    @staticmethod
    def move_page(query_db: Session, move_info: PageModel, ids):
        update_data_info = {}
        if move_info.project_id:
            update_data_info['project_id'] = move_info.project_id
        if move_info.module_id:
            update_data_info['module_id'] = move_info.module_id

        # TODO 检查要移动的页面与他的父页面是否在同一个项目或者模块

        data = query_db.query(QtrUIPage).filter(QtrUIPage.page_id.in_(ids)).update(update_data_info)
        query_db.commit()
        return data

    @staticmethod
    def add(query_db: Session, page_info: PageModel | PageModelForApi):
        PageOperation.check_name_repeat(query_db, page_info)
        data_info = page_info.model_dump(exclude_unset=True, by_alias=True)
        data_info = PageModel(**data_info).model_dump(exclude_unset=True)
        new_page_obj = QtrUIPage(**data_info)
        query_db.add(new_page_obj)
        query_db.commit()

        return PageModelForApi.model_validate(new_page_obj).model_dump(by_alias=True)

    @staticmethod
    def copy(query_db: Session, id, name=None):
        """
        复制page信息，默认插入到当前项目、莫夸
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
            page = query_db.query(QtrUIPage).filter(QtrUIPage.page_id == id).first()
            if not name:
                name = page.name + "-副本"
            page.page_id = None
            page.name = name
            query_db.add(page)
            new_id = page.page_id
            datas.append(new_id)

            child_ids = query_db.query(QtrPageRelation.child_id).filter(QtrPageRelation.page_id == id).all()
            new_instance_list = []
            for child_id in child_ids:
                new_instance = QtrPageRelation()
                new_instance.child_id = child_id
                new_instance.page_id = new_id
                new_instance_list.append(new_instance)

            query_db.add_all(new_instance_list)

            logger.info('{name}复制成功'.format(name=name))
        query_db.commit()
        return datas

    @staticmethod
    def query_list(query_db: Session, query_info: PagePageQueryModel, data_scope_sql: str, is_page: bool = True):
        """
        查询page列表
        :param query_db: 数据库session
        :param query_info:
        :param data_scope_sql: 数据权限sql
        :param is_page: bool
        :return:    ··
        """
        # 1. 先查询出所有的page
        query_obj = query_db.query(QtrUIPage)
        # 2. 再根据page的名称、请求方式、项目、模块进行过滤
        if query_info.manager:
            query_obj = query_obj.filter(QtrUIPage.manager == query_info.manager)
        if query_info.name:
            query_obj = query_obj.filter(QtrUIPage.name.like(f"%{query_info.name}%"))
        if query_info.project_id:
            query_obj = query_obj.filter(QtrUIPage.project_id == query_info.project_id)
        if query_info.module_id:
            query_obj = query_obj.filter(QtrUIPage.module_id == query_info.module_id)

        query_obj = query_obj.filter(eval(data_scope_sql))

        # 添加排序条件
        query_obj = query_obj.order_by(QtrUIPage.sort, QtrUIPage.create_time.desc(),
                                       QtrUIPage.update_time.desc()).distinct()

        post_list = PageUtil.paginate(query_obj, query_info.page_num, query_info.page_size, is_page)

        return post_list
