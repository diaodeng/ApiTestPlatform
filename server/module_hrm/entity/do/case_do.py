from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, BigInteger
from config.database import Base
from datetime import datetime


class HrmCase(Base):
    """
    模块信息表
    """
    class Meta:
        verbose_name = '用例信息'
    __tablename__ = 'hrm_case'

    id = Column(Integer, primary_key=True, autoincrement=True, comment='ID')
    case_id = Column(BigInteger, unique=True, primary_key=True, nullable=False, comment='用例、配置ID')
    type = Column(Integer, comment='test/config', default=1)
    case_name = Column(String(120), nullable=False, comment='用例名称')
    project_id = Column(BigInteger, nullable=True, comment='项目ID')
    module_id = Column(BigInteger, nullable=True, comment='模块ID')
    include = Column(String(1024), nullable=True, comment='前置config/test')
    request = Column(Text, nullable=True, comment='请求信息')
    notes = Column(String(1024), nullable=True, comment='注释')
    desc2mind = Column(Text, nullable=True, comment='脑图')
    sort = Column(Integer, nullable=False, default=0, comment='显示顺序')
    status = Column(String(1), nullable=False, default='0', comment='状态（0正常 1停用）')
    create_by = Column(String(64), default='', comment='创建者')
    create_time = Column(DateTime, nullable=True, default=datetime.now(), comment='创建时间')
    update_by = Column(String(64), default='', comment='更新者')
    update_time = Column(DateTime, nullable=True, default=datetime.now(), comment='更新时间')
    remark = Column(String(500), nullable=True, default='', comment='备注')


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
