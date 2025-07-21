from typing import Type

from sqlalchemy import select, case, Sequence
from sqlalchemy.orm import Session
from sqlalchemy.sql import or_, func  # 不能把删掉，数据权限sql依赖

from module_admin.entity.do.dept_do import SysDept  # 不能把删掉，数据权限sql依赖
from module_admin.entity.do.role_do import SysRoleDept  # 不能把删掉，数据权限sql依赖

from module_admin.entity.vo.user_vo import CurrentUserModel
from module_hrm.dao.suite_dao import SuiteDetailDao
from module_hrm.entity.do.mock_do import MockRules, RuleRequest, RuleResponse
from module_hrm.entity.do.module_do import HrmModule
from module_hrm.entity.do.project_do import HrmProject
from module_hrm.entity.dto.mock_dto import MockModel, MockResponseModel, MockRequestModel, MockResponseModelForDb, \
    MockModelForDb
from module_hrm.entity.vo.mock_vo import MockPageQueryModel, DeleteMockRuleModel, MockResponsePageQueryModel, \
    MockRequestPageQueryModel, DeleteMockResponseModel, AddMockResponseModel
from module_hrm.utils.util import PermissionHandler
from utils.page_util import PageUtil, PageResponseModel


class MockRuleDao:
    """
    mock规则管理数据库操作层
    """

    @classmethod
    def get_by_id(cls, db: Session, rule_id: int):
        """
        根据mock规则id获取在用mock规则详细信息
        :param db: orm对象
        :param rule_id: mock规则id
        :return: 在用mock规则信息对象
        """
        info = db.query(MockRules).filter(MockRules.rule_id == rule_id).first()

        return info

    @classmethod
    def get_detail_by_info(cls, db: Session, mock_rule: MockPageQueryModel) -> MockRules | None:
        """
        根据mock规则参数获取mock规则信息
        :param db: orm对象
        :param mock_rule: mock规则参数对象
        :return: mock规则信息对象
        """
        info = db.query(MockRules)
        if mock_rule.path:
            info = info.filter(MockRules.path == mock_rule.path)
        if mock_rule.method:
            info = info.filter(MockRules.method == mock_rule.method)
        if mock_rule.name:
            info = info.filter(MockRules.name == mock_rule.name)
        if mock_rule.status:
            info = info.filter(MockRules.status == mock_rule.status)

        info = info.first()

        return info

    @classmethod
    def get_list(cls, db: Session,
                 query_object: MockPageQueryModel,
                 is_page: bool = False,
                 data_scope_sql: str = 'true') -> PageResponseModel | list[MockModel] | None:
        """
        根据查询参数获取mock规则列表信息
        :param db: orm对象
        :param query_object: 查询参数对象
        :param is_page: 是否开启分页
        :return: mock规则列表信息对象
        """
        # 创建查询的基本部分
        query = db.query(MockRules,
                         HrmProject.project_name,
                         HrmModule.module_name
                         ).outerjoin(HrmProject,
                                     MockRules.project_id == HrmProject.project_id).outerjoin(HrmModule,
                                                                                              MockRules.module_id == HrmModule.module_id)
        if query_object.path:
            query = query.filter(MockRules.path == query_object.path)
        #     query = query.filter(MockRules.path.like(f'%{query_object.path}%'))

        query = query.filter(eval(data_scope_sql))

        if query_object.type:
            query = query.filter(MockRules.type == query_object.type)

        if query_object.only_self:
            query = query.filter(MockRules.manager == query_object.manager)

        # 根据module_id和project_id是否提供来查询
        if query_object.project_id:
            query = query.filter(MockRules.project_id == query_object.project_id)
        if query_object.module_id:
            query = query.filter(MockRules.module_id == query_object.module_id)

        # 根据其他查询参数添加过滤条件
        if query_object.name:
            query = query.filter(MockRules.name.like(f'%{query_object.name}%'))
        if query_object.status is not None:
            query = query.filter(MockRules.status == query_object.status)
        if query_object.rule_id is not None:
            query = query.filter(MockRules.rule_id == query_object.rule_id)

        # 添加排序条件
        query = query.order_by(MockRules.priority, MockRules.create_time.desc(),
                               MockRules.update_time.desc()).distinct()

        post_list = PageUtil.paginate(query, query_object.page_num, query_object.page_size, is_page)

        return post_list

    @classmethod
    def add(cls, db: Session, mock_rule: MockModelForDb):
        """
        新增mock规则数据库操作
        :param db: orm对象
        :param mock_rule: mock规则对象
        :return:
        """
        if not isinstance(mock_rule, MockModelForDb):
            mock_rule = MockModelForDb(**mock_rule.model_dump(exclude_unset=True, by_alias=True))
        data_dict = mock_rule.model_dump(exclude_unset=True)
        db_case = MockRules(**data_dict)
        db.add(db_case)
        db.flush()
        db.commit()

        return db_case

    @classmethod
    def edit(cls, db: Session, mock_rule: MockModel, user: CurrentUserModel = None):
        """
        编辑mock规则数据库操作
        :param db: orm对象
        :param mock_rule: 编辑页面获取的CaseModel对象
        :return:
        """
        if not isinstance(mock_rule, MockModel):
            mock_rule = MockModel(**mock_rule.model_dump(exclude_unset=True, by_alias=True))

        rule_data = mock_rule.model_dump(exclude_unset=True)
        PermissionHandler.check_is_self(user,
                                        db.query(MockRules).filter(MockRules.rule_id == mock_rule.rule_id).first())

        db.query(MockRules).filter(MockRules.rule_id == mock_rule.rule_id).update(rule_data)
        db.flush()
        db.commit()

    @classmethod
    def delete(cls, db: Session, mock_rule: DeleteMockRuleModel, user: CurrentUserModel = None):
        """
        删除mock规则数据库操作
        :param db: orm对象
        :param mock_rule: mock规则对象
        :return:
        """
        PermissionHandler.check_is_self(user,
                                        db.query(MockRules).filter(MockRules.rule_id.in_(mock_rule.rule_ids)).first())
        db.query(MockRules).filter(MockRules.rule_id.in_(mock_rule.rule_ids)).delete()
        db.flush()
        db.commit()



class MockResponseDao:
    """
    mock响应管理数据库操作层
    """

    @classmethod
    def get_by_id(cls, db: Session, rule_response_id: int):
        """
        根据mock响应id获取在用mock规则详细信息
        :param db: orm对象
        :param rule_response_id: mock规则id
        :return: 在用mock响应信息对象
        """
        info = db.query(RuleResponse).filter(RuleResponse.rule_response_id == rule_response_id).first()

        return info

    @classmethod
    def get_detail_by_info(cls, db: Session, mock_rule: MockResponseModel|AddMockResponseModel) -> MockRules | None:
        """
        根据mock规则参数获取mock规则信息
        :param db: orm对象
        :param mock_rule: mock规则参数对象
        :return: mock规则信息对象
        """
        info = db.query(RuleResponse)
        if mock_rule.name:
            info = info.filter(RuleResponse.name == mock_rule.name)
        if mock_rule.status:
            info = info.filter(RuleResponse.status == mock_rule.status)
        if mock_rule.is_default:
            info = info.filter(RuleResponse.is_default == mock_rule.is_default)
        if mock_rule.response_condition:
            info = info.filter(RuleResponse.response_condition == mock_rule.response_condition)

        info = info.first()

        return info

    @classmethod
    def get_list(cls, db: Session,
                 query_object: MockResponsePageQueryModel,
                 is_page: bool = False,
                 data_scope_sql: str = 'true') -> PageResponseModel | list[MockModel] | None:
        """
        根据查询参数获取mock规则列表信息
        :param db: orm对象
        :param query_object: 查询参数对象
        :param is_page: 是否开启分页
        :return: mock规则列表信息对象
        """
        # 创建查询的基本部分
        query = db.query(RuleResponse)
        # query = query.filter(eval(data_scope_sql))  # 业务都是基于mock规则查询，不需要校验权限
        if query_object.rule_id:
            query = query.filter(RuleResponse.rule_id == query_object.rule_id)

        if query_object.status:
            query = query.filter(RuleResponse.status == query_object.status)

        if query_object.name:
            query = query.filter(RuleResponse.name == query_object.name)

        # 添加排序条件
        query = query.order_by(RuleResponse.priority, RuleResponse.create_time.desc(),
                               RuleResponse.update_time.desc()).distinct()

        post_list = PageUtil.paginate(query, query_object.page_num, query_object.page_size, is_page)

        return post_list

    @classmethod
    def add(cls, db: Session, mock_response: MockResponseModel|MockResponseModelForDb):
        """
        新增mock规则数据库操作
        :param db: orm对象
        :param mock_rule: mock规则对象
        :return:
        """
        if not isinstance(mock_response, MockResponseModelForDb):
            mock_response = MockResponseModelForDb(**mock_response.model_dump(exclude_unset=True, by_alias=True))
        data_dict = mock_response.model_dump(exclude_unset=True)
        db_rule_response = RuleResponse(**data_dict)
        db.add(db_rule_response)
        db.flush()
        db.commit()

        return db_rule_response

    @classmethod
    def edit(cls, db: Session, mock_rule_response: MockResponseModel, user: CurrentUserModel = None):
        """
        编辑mock规则数据库操作
        :param db: orm对象
        :param mock_rule: 编辑页面获取的CaseModel对象
        :return:
        """
        if not isinstance(mock_rule_response, MockResponseModel):
            mock_rule_response = MockResponseModel(**mock_rule_response.model_dump(exclude_unset=True, by_alias=True))

        rule_data = mock_rule_response.model_dump(exclude_unset=True)
        # PermissionHandler.check_is_self(user,
        #                                 db.query(RuleResponse).filter(RuleResponse.rule_response_id == mock_rule_response.rule_response_id).first())

        db.query(RuleResponse).filter(RuleResponse.rule_response_id == mock_rule_response.rule_response_id).update(rule_data)
        db.flush()
        db.commit()

    @classmethod
    def delete(cls, db: Session, mock_rule_response: DeleteMockResponseModel, user: CurrentUserModel = None):
        """
        删除mock规则数据库操作
        :param db: orm对象
        :param mock_rule: mock规则对象
        :return:
        """
        # PermissionHandler.check_is_self(user,
        #                                 db.query(MockRules).filter(MockRules.rule_id.in_(mock_rule.rule_ids)).first())
        db.query(RuleResponse).filter(RuleResponse.rule_response_id.in_(mock_rule_response.rule_response_ids)).delete()
        db.flush()
        db.commit()
