import json

from sqlalchemy.orm import Session

from module_admin.entity.vo.user_vo import CurrentUserModel
from module_hrm.dao.mock_dao import MockRuleDao, MockResponseDao
from module_hrm.dao.suite_dao import SuiteDetailDao
from module_hrm.entity.do.mock_do import MockRules, RuleResponse, RuleRequest
from module_hrm.entity.dto.mock_dto import MockModel, MockRequestModel, MockResponseModel, MockModelForDb
from module_hrm.entity.vo.mock_vo import MockPageQueryModel, MockResponsePageQueryModel, MockRequestPageQueryModel, \
    AddMockRuleModel, AddMockResponseModel, AddMockRequestModel, DeleteMockRuleModel, DeleteMockResponseModel
from module_hrm.entity.vo.common_vo import CrudResponseModel
from module_hrm.utils.common import db_dd_user_info
from utils.common_util import export_list2excel, CamelCaseUtil
from utils.page_util import PageResponseModel


class MockService:
    """
    mock管理服务层
    """

    @classmethod
    def get_mock_rule_list_services(cls, query_db: Session, query_object: MockPageQueryModel, is_page: bool = False,
                               data_scope_sql: str = 'true'):
        """
        获取mock规则列表信息service
        :param query_db: orm对象
        :param query_object: 查询参数对象
        :param is_page: 是否开启分页
        :return: mock规则列表信息对象
        """
        list_result = MockRuleDao.get_list(query_db, query_object, is_page, data_scope_sql)
        if is_page:
            mock_rule_list_result = PageResponseModel(
                **{
                    **list_result.model_dump(by_alias=True),
                    'rows': [{**row[0], **row[1], **row[2]} for row in list_result.rows]
                }
            )
        else:
            mock_rule_list_result = []
            if list_result:
                mock_rule_list_result = [{**row[0], **row[1], **row[2]} for row in list_result]
        return mock_rule_list_result

    @classmethod
    def add_mock_rule_services(cls, query_db: Session, add_mock_rule: AddMockRuleModel, user_info: CurrentUserModel):
        """
        新增mock规则信息service
        :param query_db: orm对象
        :param page_object: 新增mock规则对象
        :return: 新增mock规则校验结果
        """
        if not add_mock_rule.type:
            raise ValueError("参数错误，请指定type")
        if not add_mock_rule.name:
            raise ValueError("mock规则名不能为空")
        if not add_mock_rule.path:
            raise ValueError("mock路径不能为空")

        db_dd_user_info(add_mock_rule, user_info)
        add_mock_rule.type = 2

        has_mock_rule = MockRuleDao.get_detail_by_info(query_db, MockPageQueryModel(name=add_mock_rule.name))
        if has_mock_rule:
            return CrudResponseModel(is_success=False, message=f'mock规则名称[{has_mock_rule.name}]已存在')

        try:
            mock_rule = MockModelForDb(**add_mock_rule.model_dump(by_alias=True))
            mock_rule_dao = MockRuleDao.add(query_db, mock_rule)
            query_db.commit()
            result = MockModel.model_validate(mock_rule_dao)
        except Exception as e:
            query_db.rollback()
            raise e

        response_data = add_mock_rule.response
        response_data.name = add_mock_rule.name
        response_data.rule_id = result.rule_id
        if not MockResponseService.has_default(query_db, result.rule_id):
            response_data.is_default = 1

        add_response_result = MockResponseService.add_mock_response_services(query_db, response_data)
        if not add_response_result.is_success:
            return CrudResponseModel(is_success=False, message=add_response_result.message)

        return CrudResponseModel(is_success=True, message=f"mock规则添加成功", result=result.model_dump(by_alias=True))

    @classmethod
    def copy_mock_rule_services(cls, query_db: Session, page_object: AddMockRuleModel):
        """
        新增mock规则信息service
        :param query_db: orm对象
        :param page_object: 新增mock规则对象
        :return: 新增mock规则校验结果
        """
        mock_rule = MockRuleDao.get_detail_by_info(query_db, MockPageQueryModel(rule_id=page_object.rule_id))
        if not mock_rule:
            result = dict(is_success=False, message='原mock规则不存在')
        else:
            try:
                new_data = mock_rule.__dict__.copy()
                new_data["name"] = page_object.name
                new_data["manager"] = page_object.manager
                new_data["create_by"] = page_object.create_by
                new_data["update_by"] = page_object.update_by
                new_data.pop("id", None)
                new_data.pop("rule_id", None)
                new_data.pop("create_time", None)
                new_data.pop("update_time", None)
                new_data.pop("_sa_instance_state", None)

                MockRuleDao.add(query_db, MockModel(**new_data))

                result = dict(is_success=True, message='复制成功')
            except Exception as e:
                query_db.rollback()
                raise e

        return CrudResponseModel(**result)

    @classmethod
    def edit_mock_rule_services(cls, query_db: Session, page_object: MockModel, user: CurrentUserModel = None):
        """
        编辑mock规则信息service
        :param query_db: orm对象
        :param page_object: 编辑mock规则对象
        :return: 编辑mock规则校验结果
        """
        # edit = page_object.model_dump(exclude_unset=True)
        info = cls.mock_rule_detail_services(query_db, page_object.rule_id)
        if info:
            if page_object.name and info.name != page_object.name:
                mock_rule = MockRuleDao.get_detail_by_info(query_db, MockPageQueryModel(name=page_object.name))
                if mock_rule:
                    result = dict(is_success=False, message='mock规则名称已存在')
                    return CrudResponseModel(**result)
            try:
                MockRuleDao.edit(query_db, page_object, user)
                result = dict(is_success=True, message='更新成功')
            except Exception as e:
                query_db.rollback()
                raise e
        else:
            result = dict(is_success=False, message='mock规则不存在')

        return CrudResponseModel(**result)

    @classmethod
    def delete_mock_rule_services(cls, query_db: Session, page_object: DeleteMockRuleModel, user: CurrentUserModel = None):
        """
        删除mock规则信息service
        :param query_db: orm对象
        :param page_object: 删除mock规则对象
        :return: 删除mock规则校验结果
        """
        if not page_object.rule_ids:
            result = dict(is_success=False, message='传入mock规则id为空')
            return CrudResponseModel(**result)
        try:
            MockRuleDao.delete(query_db,page_object, user)
            # TODO 删除mock规则关联的响应信息以及请求信息
            result = dict(is_success=True, message='删除成功')
        except Exception as e:
            query_db.rollback()
            raise e

        return CrudResponseModel(**result)

    @classmethod
    def mock_rule_detail_services(cls, query_db: Session, rule_id: int) -> MockModel | None:
        """
        获取mock规则详细信息service
        :param query_db: orm对象
        :param rule_id: mock规则id
        :return: mock规则id对应的信息
        """
        mock_rule = MockRuleDao.get_by_id(query_db, rule_id=rule_id)
        if not mock_rule:
            return None

        data = CamelCaseUtil.transform_result(mock_rule)
        result = MockModel(**data)
        return result

    @staticmethod
    def export_mock_rule_list_services(mock_rule_list: list):
        """
        导出mock规则信息service
        :param mock_rule_list: mock规则信息列表
        :return: mock规则信息对应excel的二进制数据
        """
        # 创建一个映射字典，将英文键映射到中文键
        mapping_dict = {
            "mock_ruleId": "mock规则编号",
            "type": "类型test/config",
            "name": "mock规则名称",
            "projectId": "所属项目",
            "moduleId": "所属模块",
            "include": "前置config/test",
            "request": "请求信息",
            "notes": "注释",
            "desc2mind": "脑图",
            "sort": "显示顺序",
            "status": "状态",
            "createBy": "创建者",
            "createTime": "创建时间",
            "updateBy": "更新者",
            "updateTime": "更新时间",
            "remark": "备注",
        }

        data = mock_rule_list

        for item in data:
            if item.get('status') == '0':
                item['status'] = '正常'
            else:
                item['status'] = '停用'
        new_data = [{mapping_dict.get(key): value for key, value in item.items() if mapping_dict.get(key)} for item in
                    data]
        binary_data = export_list2excel(new_data)

        return binary_data


class MockResponseService:
    @classmethod
    def has_default(cls, query_db: Session, rule_id: int):
        """
        判断mock规则是否有默认响应
        :param rule_id: mock规则id
        :return: 判断结果
        """
        mock_response = MockResponseDao.get_detail_by_info(query_db, MockResponsePageQueryModel(rule_id=rule_id))
        if mock_response:
            return True
        return False

    @classmethod
    def get_mock_response_list_services(cls, query_db: Session, query_object: MockResponsePageQueryModel, is_page: bool = False,
                                    data_scope_sql: str = 'true'):
        """
        获取mock规则列表信息service
        :param query_db: orm对象
        :param query_object: 查询参数对象
        :param is_page: 是否开启分页
        :return: mock规则列表信息对象
        """
        list_result = MockResponseDao.get_list(query_db, query_object, is_page, data_scope_sql)
        if is_page:
            mock_rule_list_result = PageResponseModel(
                **{
                    **list_result.model_dump(by_alias=True),
                    'rows': [{**row[0], **row[1], **row[2]} for row in list_result.rows]
                }
            )
        else:
            mock_rule_list_result = []
            if list_result:
                mock_rule_list_result = [{**row[0], **row[1], **row[2]} for row in list_result]
        return mock_rule_list_result

    @classmethod
    def add_mock_response_services(cls, query_db: Session, page_object: AddMockResponseModel):
        """
        新增mock规则信息service
        :param query_db: orm对象
        :param page_object: 新增mock规则对象
        :return: 新增mock规则校验结果
        """
        add_mock_rule = AddMockResponseModel(**page_object.model_dump(by_alias=True))
        mock_rule = MockResponseDao.get_detail_by_info(query_db, MockResponsePageQueryModel(name=page_object.name))
        if mock_rule:
            result = dict(is_success=False, message='mock规则响应名称已存在')
        else:
            try:
                mock_rule_dao = MockResponseDao.add(query_db, add_mock_rule)
                query_db.commit()
                result = dict(is_success=True,
                              message='新增成功',
                              result=MockModel.model_validate(mock_rule_dao).model_dump(by_alias=True))
            except Exception as e:
                query_db.rollback()
                raise e

        return CrudResponseModel(**result)

    @classmethod
    def copy_mock_response_services(cls, query_db: Session, page_object: AddMockResponseModel):
        """
        新增mock规则信息service
        :param query_db: orm对象
        :param page_object: 新增mock规则对象
        :return: 新增mock规则校验结果
        """
        mock_rule = MockResponseDao.get_detail_by_info(query_db, MockResponsePageQueryModel(rule_response_id=page_object.rule_response_id))
        if not mock_rule:
            result = dict(is_success=False, message='原mock规则响应不存在')
        else:
            try:
                new_data = mock_rule.__dict__.copy()
                new_data["name"] = page_object.name
                new_data["manager"] = page_object.manager
                new_data["create_by"] = page_object.create_by
                new_data["update_by"] = page_object.update_by
                new_data.pop("id", None)
                new_data.pop("rule_response_id", None)
                new_data.pop("create_time", None)
                new_data.pop("update_time", None)
                new_data.pop("_sa_instance_state", None)

                MockResponseDao.add(query_db, AddMockResponseModel(**new_data))

                result = dict(is_success=True, message='复制成功')
            except Exception as e:
                query_db.rollback()
                raise e

        return CrudResponseModel(**result)

    @classmethod
    def edit_mock_response_services(cls, query_db: Session, page_object: AddMockResponseModel, user: CurrentUserModel = None):
        """
        编辑mock规则信息service
        :param query_db: orm对象
        :param page_object: 编辑mock规则对象
        :return: 编辑mock规则校验结果
        """
        # edit = page_object.model_dump(exclude_unset=True)
        info = cls.mock_response_detail_services(query_db, page_object.rule_id)
        if info:
            if page_object.name and info.name != page_object.name:
                mock_rule = MockResponseDao.get_detail_by_info(query_db, AddMockResponseModel(name=page_object.name))
                if mock_rule:
                    result = dict(is_success=False, message='mock规则名称已存在')
                    return CrudResponseModel(**result)
            try:
                MockResponseDao.edit(query_db, page_object, user)
                result = dict(is_success=True, message='更新成功')
            except Exception as e:
                query_db.rollback()
                raise e
        else:
            result = dict(is_success=False, message='mock规则不存在')

        return CrudResponseModel(**result)

    @classmethod
    def delete_mock_response_services(cls, query_db: Session, page_object: DeleteMockResponseModel,
                                  user: CurrentUserModel = None):
        """
        删除mock规则信息service
        :param query_db: orm对象
        :param page_object: 删除mock规则对象
        :return: 删除mock规则校验结果
        """
        if not page_object.rule_response_ids:
            result = dict(is_success=False, message='传入mock规则id为空')
            return CrudResponseModel(**result)
        try:
            MockResponseDao.delete(query_db, page_object, user)
            result = dict(is_success=True, message='删除成功')
        except Exception as e:
            query_db.rollback()
            raise e

        return CrudResponseModel(**result)

    @classmethod
    def mock_response_detail_services(cls, query_db: Session, rule_response_id: int) -> MockResponseModel | None:
        """
        获取mock规则详细信息service
        :param query_db: orm对象
        :param rule_id: mock规则id
        :return: mock规则id对应的信息
        """
        mock_rule = MockResponseDao.get_by_id(query_db, rule_response_id=rule_response_id)
        if not mock_rule:
            return None

        data = CamelCaseUtil.transform_result(mock_rule)
        result = MockResponseModel(**data)
        return result