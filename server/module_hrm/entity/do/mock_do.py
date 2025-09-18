from sqlalchemy import Integer, String, Text, BigInteger, JSON
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import mapped_column, Mapped

from config.database import Base
from module_hrm.entity.do.common_do import BaseModel
from module_hrm.enums.enums import DataType, QtrDataStatusEnum
from utils.snowflake import snowIdWorker


class MockRules(Base, BaseModel):
    class Meta:
        verbose_name = 'mock规则信息'

    __tablename__ = 'qtr_mock_rule'

    rule_id: Mapped[int] = mapped_column(BigInteger, comment='rule_id', nullable=False, unique=True,
                                        default=snowIdWorker.get_id,
                                        index=True)
    project_id: Mapped[BigInteger] = mapped_column(BigInteger, nullable=True, default=None, comment='项目ID')
    module_id: Mapped[BigInteger] = mapped_column(BigInteger, nullable=True, default=None, comment='模块ID')
    parent_id: Mapped[int] = mapped_column(BigInteger, comment='父目录的id', nullable=True, default=None, index=True)
    type: Mapped[int] = mapped_column(Integer, nullable=False, comment='rule_type', default=DataType.api.value)  # 目录，rule
    mock_type: Mapped[int] = mapped_column(Integer, nullable=False, comment='mockType', default=DataType.api.value)  # 请求中拦截，响应中拦截，修改请求参数
    rule_tag: Mapped[str] = mapped_column(String(50), comment='rule_tag', nullable=True)

    name: Mapped[str] = mapped_column(String(500), comment='mock规则名称', nullable=False)
    path: Mapped[str] = mapped_column(String(500), comment='请求路径', nullable=False, index=True)
    method = mapped_column(String(10), comment='HTTP方法', nullable=True, default="GET", index=True)
    priority: Mapped[int] = mapped_column(Integer, comment='优先级', nullable=False, default=1)
    rule_condition: Mapped[str] = mapped_column(Text, comment='mock规则的命中条件', nullable=True, default=None)
    status: Mapped[int] = mapped_column(Integer, comment='mock规则状态', nullable=False, default=QtrDataStatusEnum.normal.value)  # 启用、禁用、删除 QtrDataStatusEnum
    desc: Mapped[str] = mapped_column(Text, comment='MOCK描述', nullable=True, default=None)


class RuleResponse(Base, BaseModel):
    __tablename__ = 'qtr_rule_response'

    rule_response_id: Mapped[int] = mapped_column(BigInteger, comment='rule_response_id', nullable=False, unique=True,
                                         default=snowIdWorker.get_id,
                                         index=True)
    name: Mapped[str] = mapped_column(String(500), comment='mock响应名称', nullable=False)
    response_tag: Mapped[str] = mapped_column(String(50), comment='response_tag or version', nullable=True)
    is_default: Mapped[int] = mapped_column(Integer, comment='默认响应', nullable=False, default=0)
    status: Mapped[int] = mapped_column(Integer, comment='mock规则状态', nullable=False, default=QtrDataStatusEnum.normal.value)  # 启用、禁用、删除
    priority: Mapped[int] = mapped_column(Integer, comment='优先级', nullable=False, default=1)
    response_condition: Mapped[str] = mapped_column(Text, comment='mock规则的命中条件', nullable=True, default=None)
    rule_id: Mapped[int] = mapped_column(BigInteger, comment='rule_id', nullable=False, index=True)
    status_code: Mapped[int] = mapped_column(Integer, comment='响应状态码', nullable=False, default=1)
    headers_template: Mapped[str] = mapped_column(Text, comment='响应头模板', nullable=True, default=None)
    body_template: Mapped[str] = mapped_column(LONGTEXT, comment='响应体模板', nullable=True, default=None)
    delay: Mapped[int] = mapped_column(Integer, comment='响应延时，毫秒', nullable=False, default=0)
    desc: Mapped[str] = mapped_column(Text, comment='MOCK描述', nullable=True, default=None)


class RuleRequest(Base, BaseModel):
    __tablename__ = 'qtr_rule_request'
    rule_request_id: Mapped[int] = mapped_column(BigInteger, comment='rule_request_id', nullable=False, unique=True,
                                                  default=snowIdWorker.get_id,
                                                  index=True)
    name: Mapped[str] = mapped_column(String(500), comment='mock请求名称', nullable=False)
    request_tag: Mapped[str] = mapped_column(String(50), comment='request_tag or version', nullable=True)
    is_default: Mapped[int] = mapped_column(Integer, comment='默认请求', nullable=False, default=0)  # 默认、非默认
    status: Mapped[int] = mapped_column(Integer, comment='mock规则状态', nullable=False, default=QtrDataStatusEnum.normal.value)  # 启用、禁用、删除
    priority: Mapped[int] = mapped_column(Integer, comment='优先级', nullable=False, default=1)
    request_condition: Mapped[str] = mapped_column(Text, comment='mock规则的命中条件', nullable=True, default=None)
    rule_id: Mapped[int] = mapped_column(BigInteger, comment='rule_id', nullable=False, index=True)
    # response_id: Mapped[int] = mapped_column(BigInteger, comment='关联的响应id', nullable=False, index=True)
    # status_code: Mapped[int] = mapped_column(Integer, comment='相应状态码', nullable=False, default=1)
    headers_template: Mapped[str] = mapped_column(Text, comment='请求头模板', nullable=True, default=None)
    body_template: Mapped[str] = mapped_column(Text, comment='请求体体模板', nullable=True, default=None)
    query_template: Mapped[str] = mapped_column(Text, comment='查询参数模板', nullable=True, default=None)
    desc: Mapped[str] = mapped_column(Text, comment='MOCK描述', nullable=True, default=None)