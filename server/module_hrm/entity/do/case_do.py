from sqlalchemy import Column, Integer, String, Text, BigInteger
from sqlalchemy.orm import relationship

from config.database import Base
from module_hrm.entity.do.common_do import BaseModel
from utils.snowflake import snowIdWorker


class HrmCase(Base, BaseModel):
    """
    模块信息表
    """
    class Meta:
        verbose_name = '用例信息'
    __tablename__ = 'hrm_case'

    case_id = Column(BigInteger, unique=True, primary_key=True, nullable=False, default=snowIdWorker.get_id, comment='用例、配置ID')
    type = Column(Integer, comment='3 case/4 config', default=3)
    case_name = Column(String(120), nullable=False, comment='用例名称')
    project_id = Column(BigInteger, nullable=True, default=None,  comment='项目ID')
    module_id = Column(BigInteger, nullable=True, default=None, comment='模块ID')
    include = Column(String(1024), nullable=True, comment='前置config/test')
    request = Column(Text, nullable=True, comment='请求信息')
    notes = Column(String(1024), nullable=True, comment='注释')
    desc2mind = Column(Text, nullable=True, comment='脑图')
    sort = Column(Integer, nullable=False, default=0, comment='显示顺序')
    status = Column(String(1), nullable=False, default='0', comment='状态（0正常 1停用）')
    remark = Column(String(500), nullable=True, default='', comment='备注')
    # qtr_suite_detail = relationship("QtrSuiteDetail", backref="cases")


class HrmCaseModuleProject(Base):
    """
    用例、模块、项目关联表
    """
    class Meta:
        verbose_name = "用例和模块和项目关联表"
    __tablename__ = 'hrm_case_module_project'

    case_id = Column(BigInteger, primary_key=True, nullable=False, comment='用例ID')
    module_id = Column(BigInteger, primary_key=True, nullable=False, comment='项目ID')
    project_id = Column(BigInteger, primary_key=True, nullable=False, comment='项目ID')
