from sqlalchemy.orm import Session
from sqlalchemy.sql import or_, func # 不能把删掉，数据权限sql依赖

from module_admin.entity.do.dept_do import SysDept # 不能把删掉，数据权限sql依赖
from module_admin.entity.do.role_do import SysRoleDept # 不能把删掉，数据权限sql依赖

from module_hrm.entity.do.case_do import HrmCase, HrmCaseModuleProject
from module_hrm.entity.do.module_do import HrmModule
from module_hrm.entity.do.project_do import HrmProject
from module_hrm.entity.dto.case_dto import CaseModelForApi
from module_hrm.entity.vo.case_vo import *
from module_hrm.enums.enums import DataType
from utils.page_util import PageUtil


class ConfigDao:
    """
    配置管理数据库操作层
    """

    @classmethod
    def get_config_select(cls, db: Session, query_object: CasePageQueryModel, is_page: bool = False, data_scope_sql:str='true'):
        """
        根据查询参数获取用例列表信息
        :param db: orm对象
        :param query_object: 查询参数对象
        :param is_page: 是否开启分页
        :return: 用例列表信息对象
        """
        # 创建查询的基本部分
        query = db.query(HrmCase,
                         HrmProject.project_name,
                         HrmModule.module_name
                         ).outerjoin(HrmProject,
                                     HrmCase.project_id == HrmProject.project_id).outerjoin(HrmModule,
                                                                                            HrmCase.module_id == HrmModule.module_id)

        query = query.filter(HrmCase.type == DataType.config.value, eval(data_scope_sql))

        if query_object.only_self:
            query = query.filter(HrmCase.manager == query_object.manager)

        # 根据module_id和project_id是否提供来查询
        if query_object.project_id:
            query = query.filter(or_(HrmCase.project_id == query_object.project_id, HrmCase.project_id == None))
        else:
            query = query.filter(HrmCase.project_id == None)
        if query_object.module_id:
            query = query.filter(or_(HrmCase.module_id == query_object.module_id, HrmCase.module_id == None))
        else:
            query = query.filter(HrmCase.module_id == None)

        # 添加排序条件
        query = query.order_by(HrmCase.sort, HrmCase.create_time.desc(), HrmCase.update_time.desc()).distinct()

        post_list = PageUtil.paginate(query, query_object.page_num, query_object.page_size, is_page)

        return post_list
