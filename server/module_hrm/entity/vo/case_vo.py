import json
import logging
from datetime import datetime
from typing import Optional, List, Any, Dict

from pydantic import BaseModel, ConfigDict, field_serializer, model_validator, Field
from pydantic.alias_generators import to_camel

from module_admin.annotation.pydantic_annotation import as_query, as_form
from module_hrm.entity.vo.case_vo_detail_for_handle import TestCase
from module_hrm.entity.vo.common_vo import CommonDataModel, QueryModel
from module_hrm.enums.enums import RunTypeEnum, DataType
from utils.common_util import CamelCaseUtil


class CaseModel(CommonDataModel):
    """
    主要用于输入入库前的序列化，其他的建议用CaseModelForApi
    用例信息表对应pydantic模型, 用于存数据库前转化数据
    """
    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True)

    case_id: int | str | None = None
    type: Optional[int] = None
    case_name: Optional[str] = None
    project_id: Optional[int] = None
    module_id: Optional[int] = None
    include: Optional[Any] = None
    request: Optional[Any] = None
    notes: Optional[str] = None
    desc2mind: Optional[str] = None
    sort: Optional[int] = None
    status: Optional[int] = None
    # create_by: Optional[str] = None
    # create_time: Optional[datetime] = None
    # update_by: Optional[str] = None
    # update_time: Optional[datetime] = None
    remark: Optional[str] = None

    @model_validator(mode="before")
    def convert_address(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        values = CamelCaseUtil.transform_result(values)
        request_data = values.get('request')
        if isinstance(request_data, str):
            values["request"] = TestCase(**json.loads(request_data))
        elif isinstance(request_data, dict):
            values["request"] = TestCase(**request_data)
        return values

    @field_serializer('request')
    def request_data(self, request: Any):
        if isinstance(request, str):
            return request
        elif isinstance(request, (dict, list)):
            return json.dumps(request, ensure_ascii=False)
        elif isinstance(request, TestCase):
            return request.model_dump_json(by_alias=True, exclude_unset=True)
        else:
            return request

    @field_serializer('include')
    def include_data(self, include: Any):
        if isinstance(include, str):
            return include
        elif isinstance(include, (dict, list)):
            return json.dumps(include, ensure_ascii=False)
        else:
            return include


class FeishuRobotModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True)
    url: Optional[str] = None
    secret: Optional[str] = None
    keywords: Optional[list] = Field(default_factory=lambda: [])
    at_user_id: Optional[list] = Field(default_factory=lambda: [])
    push: bool = False


class ForwardRulesForRunModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True)
    match_type: Optional[int] = None  # module_hrm.enums.enums.ForwardRuleMatchTypeEnum
    origin_url: str | None = None
    target_url: Optional[str] = None


class ForwardConfigModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True)
    forward_rule_ids: Optional[list] = Field(default_factory=lambda: [])
    agent_code: Optional[str] = None
    forward_rules: list[ForwardRulesForRunModel] = Field(default_factory=lambda: [])
    agent_id: Optional[int] = None
    forward: bool = False


class ProjectDebugtalkInfoModel(BaseModel):
    module_names: list[str] = Field(default_factory=lambda: [])
    func_map: dict[str, Any] = Field(default_factory=lambda: {})
    module_instance: list[Any] = Field(default_factory=lambda: [])


class CaseRunModel(BaseModel):
    """
    用于用例运行前的序列化
    """
    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True)

    ids: Optional[int | List | None] = None  # 执行的数据源的ID
    run_type: Optional[int] = RunTypeEnum.case.value  # 用例执行数据源，项目、模块、套件、用例
    run_model: Optional[int | None] = None  # 执行方式，1手动，2定时任务
    report_name: Optional[str] = None  # 测试报告名称
    report_id: Optional[int] = -1  # 测试报告名称
    is_async: Optional[bool] = False  # 本次执行同步或异步
    log_level: Optional[int] = logging.INFO  # 日志级别
    repeat_num: int = 1  # 用例重复执行次数
    env: int  # 环境id
    concurrent: int = 1  # 并发数(同时执行的用例数)
    run_by_sort: Optional[bool] = False
    case_data: Optional[CaseModel | dict | None] = None  # 用例数据
    runner: Any = None

    forward_config: Optional[ForwardConfigModel] = ForwardConfigModel()

    push: bool = False
    feishu_robot: Optional[FeishuRobotModel] = FeishuRobotModel()

    global_vars: dict = Field(default_factory=lambda: {})
    project_debugtalk_set: dict[str | int, ProjectDebugtalkInfoModel] = Field(default_factory=lambda: {})  # 当前加载的所有debugtalk


class CaseModuleProjectModel(BaseModel):
    """
    用例和用例和项目关联表对应pydantic模型
    """
    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True)

    case_id: Optional[int] = None
    module_id: Optional[int] = None
    project_id: Optional[int] = None


class CaseQueryModel(CaseModel):
    """
    用例管理不分页查询模型
    """
    begin_time: Optional[str] = None
    end_time: Optional[str] = None


class CaseQuery(CaseModel):
    """
    用例查询
    """
    module_id: Optional[int] = None
    project_id: Optional[int] = None


@as_query
@as_form
class CasePageQueryModel(QueryModel, CaseQueryModel):
    """
    用例管理分页查询模型
    """

    suite_id: Optional[int] = None
    data_type: Optional[int] = None


class AddCaseModel(CaseModel):
    """
    新增用例模型
    """
    type: Optional[str | int] = DataType.case.value


class DeleteCaseModel(BaseModel):
    """
    删除用例模型
    """
    model_config = ConfigDict(alias_generator=to_camel)

    case_ids: str
    update_by: Optional[str] = None
    update_time: Optional[datetime] = None
