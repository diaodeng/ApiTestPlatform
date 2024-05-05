from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from config.database import Base
from datetime import datetime


class HrmModule(Base):
    """
    模块信息表
    """
    class Meta:
        verbose_name = '模块信息'
    __tablename__ = 'hrm_module'

    module_id = Column(Integer, primary_key=True, autoincrement=True, comment='模块ID')
    project_id = Column(Integer, nullable=True, comment='项目ID')
    module_name = Column(String(50), nullable=False, comment='模块名称')
    test_user = Column(String(50), nullable=True, comment='测试负责人')
    simple_desc = Column(String(200), nullable=True, comment='简要信息')
    other_desc = Column(String(200), nullable=True, comment='其他信息')
    desc2mind = Column(Text, nullable=True, comment='脑图')
    # belong_project = Column(Integer, ForeignKey('hrm_project.project_id', ondelete='CASCADE'))
    sort = Column(Integer, nullable=False, default=0, comment='显示顺序')
    status = Column(String(1), nullable=False, default='0', comment='状态（0正常 1停用）')
    create_by = Column(String(64), default='', comment='创建者')
    create_time = Column(DateTime, nullable=True, default=datetime.now(), comment='创建时间')
    update_by = Column(String(64), default='', comment='更新者')
    update_time = Column(DateTime, nullable=True, default=datetime.now(), comment='更新时间')
    remark = Column(String(500), nullable=True, default='', comment='备注')


class HrmModuleProject(Base):
    """
    模块和项目关联表
    """
    class Meta:
        verbose_name = "模块和项目关联表"
    __tablename__ = 'hrm_module_project'

    module_id = Column(Integer, primary_key=True, nullable=False, comment='模块ID')
    project_id = Column(Integer, primary_key=True, nullable=False, comment='项目ID')
