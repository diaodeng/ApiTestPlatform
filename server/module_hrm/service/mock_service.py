import asyncio
import re
import json
import datetime
import random
import time
import uuid
import jmespath
from typing import List

from jinja2 import Environment, BaseLoader
from fastapi import Request, Response
from requests.cookies import MockResponse

from sqlalchemy.orm import Session
from sqlalchemy.util import await_only

from module_admin.entity.vo.user_vo import CurrentUserModel
from module_hrm.dao.mock_dao import MockRuleDao, MockResponseDao
from module_hrm.dao.suite_dao import SuiteDetailDao
from module_hrm.entity.do.mock_do import MockRules, RuleResponse, RuleRequest
from module_hrm.entity.dto.mock_dto import MockModel, MockRequestModel, MockResponseModel, MockModelForDb, \
    MockResponseModelForDb, MockConditionModel
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
    def get_rule_for_mock(cls, query_db: Session, path: str, method: str) -> List[MockModel]:
        rules = MockRuleDao.get_list_for_mock(query_db, path, method)
        rules = CamelCaseUtil.transform_result(rules)
        return [MockModel(**data) for data in rules]

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

        result_data = result.model_dump(by_alias=True)
        result_data["response"] = add_response_result.result

        return CrudResponseModel(is_success=True, message=f"mock规则添加成功", result=result_data)

    @classmethod
    def copy_mock_rule_services(cls, query_db: Session, page_object: AddMockRuleModel):
        """
        新增mock规则信息service
        :param query_db: orm对象
        :param page_object: 新增mock规则对象
        :return: 新增mock规则校验结果
        """
        mock_rule = MockRuleDao.get_by_id(query_db, page_object.rule_id)
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

                new_rule = MockRuleDao.add(query_db, MockModelForDb(**new_data))

                # 复制mock响应
                original_records = MockResponseDao.get_list(query_db, MockResponsePageQueryModel(rule_id=page_object.rule_id))
                new_records = []
                for record in original_records:
                    # 获取所有字段的字典表示（排除主键）
                    exclude_key = ["id", "rule_id", "create_time", "update_time", "rule_response_id"]
                    data = {c.name: getattr(record, c.name)
                            for c in RuleResponse.__table__.columns
                            if not c.primary_key and c.name not in exclude_key}

                    # 修改特定字段
                    data['rule_id'] = new_rule.rule_id
                    data["manager"] = page_object.manager
                    data["create_by"] = page_object.create_by
                    data["update_by"] = page_object.update_by

                    # 创建新对象
                    new_records.append(RuleResponse(**data))

                # 批量添加
                query_db.bulk_save_objects(new_records)
                query_db.commit()

                result = dict(is_success=True, message='复制成功')
            except Exception as e:
                query_db.rollback()
                raise e

        return CrudResponseModel(**result)

    @classmethod
    def edit_mock_rule_services(cls, query_db: Session, page_object: AddMockRuleModel, user: CurrentUserModel = None):
        """
        编辑mock规则信息service
        :param query_db: orm对象
        :param page_object: 编辑mock规则对象
        :return: 编辑mock规则校验结果
        """
        if not page_object.type:
            raise ValueError("参数错误，请指定type")
        if not page_object.name:
            raise ValueError("mock规则名不能为空")
        if not page_object.path:
            raise ValueError("mock路径不能为空")
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
        edit_response = page_object.response
        edit_response_res = MockResponseService.edit_mock_response_services(query_db, edit_response, user)
        if not edit_response_res.is_success:
            return edit_response_res

        return CrudResponseModel(**result)

    @classmethod
    def change_rule_info(cls, query_db: Session, page_object: AddMockRuleModel, user: CurrentUserModel = None):
        info = MockRuleDao.get_by_id(query_db, page_object.rule_id)
        if not info:
            return CrudResponseModel(is_success=False, message='mock规则不存在')

        try:
            MockRuleDao.edit(query_db, page_object, user)
            return CrudResponseModel(is_success=True, message='更新成功')
        except Exception as e:
            query_db.rollback()
            raise e


    @classmethod
    def delete_mock_rule_services(cls, query_db: Session, page_object: DeleteMockRuleModel,
                                  user: CurrentUserModel = None):
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
            MockResponseDao.delete_by_rule_id(query_db, page_object.rule_ids, user)
            MockRuleDao.delete(query_db, page_object, user)
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

        rule_response = MockResponseService.get_by_rule_id(query_db, rule_id)
        if rule_response:
            default_res = None
            for res in rule_response:
                if res.is_default:
                    default_res = res
                    break
            if not default_res:
                default_res = rule_response[0]

        data = CamelCaseUtil.transform_result(mock_rule)
        result = AddMockRuleModel(**data)
        result.response = default_res
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
    def get_by_rule_id(cls, query_db: Session, rule_id: int, name: str = None) -> List[MockResponseModel]:
        """
        获取mock规则响应信息service
        :param rule_id: mock规则id
        :return: mock规则响应信息对象
        """
        info = query_db.query(RuleResponse).filter(RuleResponse.rule_id == rule_id)
        if name:
            info = info.filter(RuleResponse.name.like(f'%{name}%'))
        info = info.all()
        return [MockResponseModel(**data) for data in CamelCaseUtil.transform_result(info)]

    @classmethod
    def get_mock_response_list_services(cls, query_db: Session, query_object: MockResponsePageQueryModel,
                                        is_page: bool = False,
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

        mock_rule = MockResponseDao.get_detail_by_info(query_db, MockResponsePageQueryModel(name=page_object.name, rule_id=page_object.rule_id))
        if mock_rule:
            result = dict(is_success=False, message='当前mock规则中响应名称已存在')
        else:
            try:
                add_mock_rule = MockResponseModelForDb(**page_object.model_dump(by_alias=True))
                mock_rule_dao = MockResponseDao.add(query_db, add_mock_rule)
                result = dict(is_success=True,
                              message='新增成功',
                              result=MockResponseModel.model_validate(mock_rule_dao).model_dump(by_alias=True))
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
        mock_rule = MockResponseDao.get_detail_by_info(query_db, MockResponsePageQueryModel(
            rule_response_id=page_object.rule_response_id))
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

                MockResponseDao.add(query_db, MockResponseModelForDb(**new_data))

                result = dict(is_success=True, message='复制成功')
            except Exception as e:
                query_db.rollback()
                raise e

        return CrudResponseModel(**result)

    @classmethod
    def edit_mock_response_services(cls, query_db: Session, page_object: AddMockResponseModel,
                                    user: CurrentUserModel = None):
        """
        编辑mock规则信息service
        :param query_db: orm对象
        :param page_object: 编辑mock规则对象
        :return: 编辑mock规则校验结果
        """
        # edit = page_object.model_dump(exclude_unset=True)
        info = MockResponseDao.get_by_id(query_db, page_object.rule_response_id)
        if not info:
            return CrudResponseModel(is_success=False, message='mock规则不存在')

        if page_object.name and info.name != page_object.name:
            mock_rule = MockResponseDao.get_detail_by_info(query_db, AddMockResponseModel(name=page_object.name,
                                                                                          ruleId=page_object.rule_id))
            if mock_rule:
                result = dict(is_success=False, message='mock规则名称已存在')
                return CrudResponseModel(**result)
        try:
            MockResponseDao.edit(query_db, page_object, user)
            result = dict(is_success=True, message='更新成功')
        except Exception as e:
            query_db.rollback()
            raise e

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
    def get_response_detail_services(cls, query_db: Session, rule_response_id: int) -> MockResponseModel | None:
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

    @classmethod
    def set_default_response(cls, query_db: Session, rule_response_info: AddMockResponseModel,
                            user: CurrentUserModel = None):
        mock_rule = query_db.query(RuleResponse).filter(RuleResponse.rule_id == rule_response_info.rule_id).all()
        for item in mock_rule:
            item_obj = AddMockResponseModel.model_validate(item)
            if item_obj.response_condition == rule_response_info.response_condition:
                item.update_time = datetime.datetime.now()
                item.update_by = user.user.user_id if user else None
                if item.rule_response_id == rule_response_info.rule_response_id:
                    item.is_default = 1
                else:
                    item.is_default = 0
        query_db.commit()

    @classmethod
    def get_by_response_condition(cls, query_db: Session, rule_response_info: AddMockResponseModel) -> List[MockResponseModel]:
        mock_rule = query_db.query(RuleResponse).filter(RuleResponse.rule_id == rule_response_info.rule_id).all()
        matched_response = []
        for item in mock_rule:
            item_obj = AddMockResponseModel.model_validate(item)
            if ConditionMatcher.condition_match_condition(rule_response_info.response_condition, item_obj.response_condition):
                matched_response.append(item_obj)
        return matched_response


class ConditionMatcher:
    def __init__(self, request: Request, conditions: List[MockConditionModel] | None = None):
        self.request = request
        self.conditions = conditions

    @classmethod
    def condition_match_condition(cls, conditions: List[MockConditionModel], conditions_target: List[MockConditionModel]) -> bool:
        """
        比较条件是否匹配，条件列表中的条件必须全部包含在目标列表的条件中
        :param conditions: 条件列表
        :param conditions_target: 目标条件列表
        :return: 是否匹配
        """
        if not conditions and not conditions_target:
            return True
        conditions_target = conditions_target or []
        conditions = conditions or []
        condition_obj = {}
        for condition in conditions:
            condition_obj[condition.key] = f"{condition.source}{condition.value}{condition.operator}{condition.data_type}"
        target_condition_obj = {}
        for condition in conditions_target:
            target_condition_obj[condition.key] = f"{condition.source}{condition.value}{condition.operator}{condition.data_type}"

        return all(k in target_condition_obj and target_condition_obj[k] == v for k, v in condition_obj.items())

    def match_condition(self, conditions: List[MockConditionModel]) -> bool:
        """匹配请求条件"""
        c_conditions = conditions or self.conditions or []
        for condition in c_conditions:
            if not self._match_condition(condition):
                return False
        return True

    def _match_condition(self, condition: MockConditionModel):
        # 获取请求中的实际值
        actual_value = self._get_request_value(condition.source, condition.key)

        # 根据操作符进行匹配
        operator = condition.operator
        expected_value = condition.value

        # 类型转换
        if condition.data_type == 'number' and actual_value is not None:
            try:
                actual_value = float(actual_value)
                expected_value = float(expected_value)
            except ValueError:
                return False

        # 匹配逻辑
        if operator == '=':
            return actual_value == expected_value
        elif operator == '!=':
            return actual_value != expected_value
        elif operator == '>':
            return actual_value > expected_value
        elif operator == '<':
            return actual_value < expected_value
        elif operator == 'contains':
            return expected_value in str(actual_value)
        elif operator == 'regex':
            return bool(re.match(expected_value, str(actual_value)))
        elif operator == 'regex_search':
            return bool(re.search(expected_value, str(actual_value)))
        elif operator == 'exists':
            return actual_value is not None
        return False

    def _get_request_value(self, source, key):
        """从请求中获取值"""
        if source == 'query':
            return self.request.query_params.get(key)
        elif source == 'header':
            return self.request.headers.get(key)
        elif source == 'path':
            # 路径参数处理（如 /users/<id>）
            return self.request.path_params.get(key)
        elif source == 'body':
            try:
                if hasattr(self.request, "body_data"):
                    body = self.request.body_data
                    # 支持JSONPath（简化版）
                    return jmespath.search(key, body)
                    # keys = key.split('.')
                    # value = body
                    # for k in keys:
                    #     if k in value:
                    #         value = value[k]
                    #     else:
                    #         return None
                    # return value
                return None
            except:
                return None
        return None


class RuleMatcher:
    def __init__(self, request: Request, query_db: Session, path):
        self.request = request
        self.query_db = query_db
        self.rules = MockService.get_rule_for_mock(query_db, path, request.method)
        self.condition_matcher = ConditionMatcher(request)

    def match_request(self) -> MockModel | None:
        """匹配当前请求的规则"""
        for rule in self.rules:
            if self.condition_matcher.match_condition(rule.rule_condition):
                return rule
        return None  # 无匹配规则

    async def match_response(self) -> dict | None:
        matched_rule = self.match_request()
        if matched_rule:
            rule_response = MockResponseService.get_by_rule_id(self.query_db, matched_rule.rule_id)
            matched_response = await MockResponseMatcher(self.request, rule_response).match_request()
            if matched_response:
                response_gen = ResponseGenerator(self.request, matched_response)
                return await response_gen.generate_response()
        return None


class MockResponseMatcher:
    def __init__(self, request: Request, mock_rule_response: List[MockResponseModel | RuleResponse]):
        self.request: Request = request
        self.mock_rule_response: List[MockResponseModel] = mock_rule_response
        self.condition_matcher = ConditionMatcher(request)

    async def match_request(self) -> MockResponseModel | None:
        """匹配当前请求的规则"""
        default_response = None
        matched_response = []
        for response in self.mock_rule_response:
            if self.condition_matcher.match_condition(response.response_condition):
                matched_response.append(response)
                if response.is_default:
                    default_response = response
        if default_response:
            return default_response
        if len(matched_response) > 0:
            return matched_response[0]
        return None


class ResponseGenerator:
    def __init__(self, request: Request, response: MockResponseModel):
        self.request: Request = request
        self.response = response

    async def generate_response(self) -> dict:
        """生成最终响应"""
        # 处理延迟
        if self.response.delay > 0:
            await asyncio.sleep(self.response.delay / 1000.0)

        # 渲染响应体
        body = await self._render_template()

        return {
            'status_code': self.response.status_code,
            'headers': {data.key: data.value for data in self.response.headers_template},
            'content': body
        }


    async def _render_template(self):
        """渲染动态模板"""
        context = {
            'request': {
                'path': self.request.path_params,
                'method': self.request.method,
                'args': dict(self.request.query_params),
                'headers': dict(self.request.headers),
                "body": getattr(self.request, "body_data", None),
            },
            'random': {
                'int': lambda a, b: random.randint(a, b),
                'string': lambda l: ''.join(random.choices('abcdefghijklmnopqrstuvwxyz', k=l))
            },
            'time': {
                'now': time.time(),
                'iso': datetime.datetime.now().isoformat(),
                'format': lambda format: datetime.datetime.now().strftime(format)
            },
            'uuid': str(uuid.uuid4())
        }

        env = Environment(loader=BaseLoader())
        template = env.from_string(self.response.body_template)
        return template.render(**context)
