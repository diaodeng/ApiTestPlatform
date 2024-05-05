from sqlalchemy.orm import Session
from module_hrm.entity.do.module_do import HrmModule, HrmModuleProject
from module_hrm.entity.vo.module_vo import *
from utils.page_util import PageUtil


class ModuleDao:
    """
    模块管理模块数据库操作层
    """

    @classmethod
    def get_module_by_id(cls, db: Session, module_id: int):
        """
        根据模块id获取在用模块详细信息
        :param db: orm对象
        :param module_id: 模块id
        :return: 在用模块信息对象
        """
        info = db.query(HrmModule) \
            .filter(HrmModule.module_id == module_id,
                    HrmModule.status == 0) \
            .first()

        return info

    @classmethod
    def get_module_detail_by_id(cls, db: Session, module_id: int):
        """
        根据模块id获取模块详细信息
        :param db: orm对象
        :param module_id: 模块id
        :return: 模块信息对象
        """
        info = db.query(HrmModule) \
            .filter(HrmModule.module_id == module_id) \
            .first()

        return info

    @classmethod
    def get_module_detail_by_info(cls, db: Session, module: ModuleQuery):
        """
        根据模块参数获取模块信息
        :param db: orm对象
        :param module: 模块参数对象
        :return: 模块信息对象
        """
        info = db.query(HrmModule) \
            .filter(HrmModule.module_name == module.module_name if module.module_name else True,
                    HrmModule.module_id.in_(db.query(HrmModuleProject.module_id).filter(
                        HrmModuleProject.project_id == module.project_id)) if module.project_id else True,
                    HrmModule.sort == module.sort if module.sort else True) \
            .first()

        return info

    @classmethod
    def get_module_list(cls, db: Session, query_object: ModulePageQueryModel, is_page: bool = False):
        """
        根据查询参数获取模块列表信息
        :param db: orm对象
        :param query_object: 查询参数对象
        :param is_page: 是否开启分页
        :return: 模块列表信息对象
        """
        query = db.query(HrmModule) \
            .filter(HrmModule.module_id.in_(db.query(HrmModuleProject.module_id).filter(
            HrmModuleProject.project_id == query_object.project_id)) if query_object.project_id else True,
                    HrmModule.module_name.like(f'%{query_object.module_name}%') if query_object.module_name else True,
                    HrmModule.status == query_object.status if query_object.status else True
                    ) \
            .order_by(HrmModule.sort) \
            .distinct()
        post_list = PageUtil.paginate(query, query_object.page_num, query_object.page_size, is_page)

        return post_list

    @classmethod
    def get_module_list_all(cls, db: Session, page_object: ModuleModel):
        """
        根据查询参数获取模块列表信息
        :param db: orm对象
        :param page_object: 查询参数对象
        :param data_scope_sql: 数据权限对应的查询sql语句
        :return: 模块列表信息对象
        """
        result = db.query(HrmModule) \
            .filter(HrmModule.project_id == page_object.project_id) \
            .distinct().all()

        return result

    @classmethod
    def get_module_list_show(cls, db: Session, page_object: ModuleModel):
        """
        根据查询参数获取模块列表信息
        :param db: orm对象
        :param page_object: 查询参数对象
        :param data_scope_sql: 数据权限对应的查询sql语句
        :return: 模块列表信息对象
        """
        result = (db.query(HrmModule).distinct().all())

        return result


    @classmethod
    def add_module_dao(cls, db: Session, module: ModuleModel):
        """
        新增模块数据库操作
        :param db: orm对象
        :param module: 模块对象
        :return:
        """
        db_module = HrmModule(**module.model_dump())
        db.add(db_module)
        db.flush()

        return db_module

    @classmethod
    def edit_module_dao(cls, db: Session, module: dict):
        """
        编辑模块数据库操作
        :param db: orm对象
        :param module: 需要更新的模块字典
        :return:
        """
        db.query(HrmModule) \
            .filter(HrmModule.module_id == module.get('module_id')) \
            .update(module)

    @classmethod
    def delete_module_dao(cls, db: Session, module: ModuleModel):
        """
        删除模块数据库操作
        :param db: orm对象
        :param module: 模块对象
        :return:
        """
        db.query(HrmModule) \
            .filter(HrmModule.module_id == module.module_id) \
            .delete()
        db.query(HrmModuleProject).filter(HrmModuleProject.module_id == module.module_id).delete()

    @classmethod
    def add_module_project_dao(cls, db: Session, module_project: ModuleProjectModel):
        """
        新增模块项目关联信息数据库操作
        :param db: orm对象
        :param module_project: 模块和项目关联对象
        :return:
        """
        db_module_project = HrmModuleProject(**module_project.model_dump())
        db.add(db_module_project)
