import datetime

from sqlalchemy.orm import Session

from module_admin.entity.vo.user_vo import CurrentUserModel
from module_hrm.entity.do.ui_function_manager_do import QtrFunctions
from module_hrm.entity.do.ui_function_relation_do import QtrFunctionsRelation
from module_hrm.entity.vo.function_vo import FunctionModel, FunctionQueryModel, FunctionAddModel, \
    FunctionModelForApi, FunctionPageQueryModel, DeleteFunctionModel
from module_hrm.enums.enums import QtrDataStatusEnum
from module_hrm.exceptions import ExistsError
from module_hrm.utils.util import PermissionHandler
from utils.log_util import logger
from utils.page_util import PageUtil


class FunctionOperation(object):
    def __init__(self):
        pass

    @staticmethod
    def check_name_repeat(query_db: Session, function_info: FunctionModelForApi):

        query_data = query_db.query(QtrFunctions).filter(
            QtrFunctions.name == function_info.name,
            QtrFunctions.project_id == function_info.project_id,
            QtrFunctions.module_id == function_info.module_id,
            QtrFunctions.group_id == function_info.group_id
        )
        if function_info.function_id:
            query_data = query_data.filter(QtrFunctions.function_id != function_info.function_id)
        if query_data.first():
            raise ExistsError(f"已存在名为【{function_info.name}】的方法，请检查或修改名称！")

    @staticmethod
    def get(query_db: Session, function_id: int) -> QtrFunctions | None:

        function_data_obj = query_db.query(QtrFunctions).filter(QtrFunctions.function_id == function_id).first()
        return function_data_obj

    @staticmethod
    def get_function_detail_by_info(query_db: Session, function_info: FunctionModelForApi):
        query = query_db.query(QtrFunctions)
        if function_info.function_id:
            query = query.filter(QtrFunctions.function_id == function_info.function_id)
        if function_info.name:
            query = query.filter(QtrFunctions.name == function_info.name)

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


            query = query_db.query(QtrFunctions).filter(QtrFunctions.function_id.in_(ids))
            if permanent_delete:
                query_db.query(QtrFunctionsRelation).filter(QtrFunctionsRelation.function_id.in_(ids)).delete()
                query.delete()
            else:
                query.update({
                    "status": QtrDataStatusEnum.deleted.value,
                    "update_by": user.user.user_id,
                    "update_time": datetime.datetime.now(),
                })
            query_db.commit()
        except Exception as e:
            logger.error(f"删除function失败：{ids}")
            logger.error(e, exc_info=True)
            raise TypeError(f"删除function失败：{e}")
        return "删除成功"

    @staticmethod
    def update(query_db: Session, function_info: FunctionModelForApi, user: CurrentUserModel = None):
        PermissionHandler.check_is_self(user, function_info)

        FunctionOperation.check_name_repeat(query_db, function_info)

        data_info = function_info.model_dump(exclude_unset=True, by_alias=True)
        data_info = FunctionModel(**data_info).model_dump(exclude_unset=True)
        # data_info.pop("function_id")
        # data_info.pop("type")
        old_data = query_db.query(QtrFunctions).filter(QtrFunctions.function_id == function_info.function_id)
        old_data.update(data_info)
        query_db.commit()
        # return QtrFunctions.objects.get(id=function_id)
        return FunctionModelForApi.from_orm(old_data.first()).model_dump(by_alias=True)

    @staticmethod
    def move_function(query_db: Session, move_info: FunctionModel, ids):
        update_data_info = {}
        if move_info.project_id:
            update_data_info['project_id'] = move_info.project_id
        if move_info.module_id:
            update_data_info['module_id'] = move_info.module_id
        if move_info.group_id:
            update_data_info['group_id'] = move_info.group_id

        data = query_db.query(QtrFunctions).filter(QtrFunctions.function_id.in_(ids)).update(update_data_info)
        query_db.commit()
        return data

    @staticmethod
    def add(query_db: Session, function_info: FunctionModel | FunctionModelForApi):
        FunctionOperation.check_name_repeat(query_db, function_info)
        data_info = function_info.model_dump(exclude_unset=True, by_alias=True)
        data_info = FunctionModel(**data_info).model_dump(exclude_unset=True)
        new_function_obj = QtrFunctions(**data_info)
        query_db.add(new_function_obj)
        query_db.commit()

        return FunctionModelForApi.model_validate(new_function_obj).model_dump(by_alias=True)

    @staticmethod
    def copy(query_db: Session, id, name=None):
        """
        复制function信息，默认插入到当前项目、莫夸
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
            function = query_db.query(QtrFunctions).filter(QtrFunctions.function_id == id).first()
            if not name:
                name = function.name + "-副本"
            function.function_id = None
            function.name = name
            query_db.add(function)
            new_id = function.function_id
            datas.append(new_id)

            child_ids = query_db.query(QtrFunctionsRelation.child_id).filter(QtrFunctionsRelation.function_id == id).all()
            new_instance_list = []
            for child_id in child_ids:
                new_instance = QtrFunctionsRelation()
                new_instance.child_id = child_id
                new_instance.function_id = new_id
                new_instance_list.append(new_instance)

            query_db.add_all(new_instance_list)

            logger.info('{name}复制成功'.format(name=name))
        query_db.commit()
        return datas

    @staticmethod
    def query_list(query_db: Session, query_info: FunctionPageQueryModel, data_scope_sql: str, is_page: bool = True):
        """
        查询function列表
        :param query_db: 数据库session
        :param query_info:
        :param data_scope_sql: 数据权限sql
        :param is_page: bool
        :return:
        """
        # 1. 先查询出所有的function
        query_obj = query_db.query(QtrFunctions)
        # 2. 再根据function的名称、请求方式、项目、模块进行过滤
        if query_info.manager:
            query_obj = query_obj.filter(QtrFunctions.manager == query_info.manager)
        if query_info.name:
            query_obj = query_obj.filter(QtrFunctions.name.like(f"%{query_info.name}%"))
        if query_info.project_id:
            query_obj = query_obj.filter(QtrFunctions.project_id == query_info.project_id)
        if query_info.module_id:
            query_obj = query_obj.filter(QtrFunctions.module_id == query_info.module_id)
        if query_info.group_id:
            query_obj = query_obj.filter(QtrFunctions.group_id == query_info.group_id)

        query_obj = query_obj.filter(eval(data_scope_sql))

        # 添加排序条件
        query_obj = query_obj.order_by(QtrFunctions.sort, QtrFunctions.create_time.desc(),
                                       QtrFunctions.update_time.desc()).distinct()

        post_list = PageUtil.paginate(query_obj, query_info.page_num, query_info.page_size, is_page)

        return post_list
