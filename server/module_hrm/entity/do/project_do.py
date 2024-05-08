from sqlalchemy import Column, Integer, String, DateTime, Text, BigInteger
from sqlalchemy.orm import relationship, backref

from config.database import Base
from datetime import datetime


class HrmProject(Base):
    """
    环境管理
    """
    class Meta:
        verbose_name = '项目管理'
    __tablename__ = 'hrm_project'

    id = Column(Integer, primary_key=True, autoincrement=True, comment='项目id')
    project_id = Column(BigInteger, primary_key=True, nullable=False, unique=True, comment='项目id')
    project_name = Column(String(120), nullable=True, default='', comment='项目名称')
    responsible_name = Column(String(30), nullable=True, default='', comment='负责人')
    test_user = Column(String(30), nullable=True, default='', comment='测试人员')
    dev_user = Column(String(30), nullable=True, default='', comment='开发人员')
    publish_app = Column(String(60), nullable=True, default='', comment='发布应用')
    simple_desc = Column(Text, nullable=True, default='', comment='简要描述')
    other_desc = Column(Text, nullable=True, default='', comment='其他信息')
    order_num = Column(Integer, default=0, comment='显示顺序')
    status = Column(String(1), nullable=True, default=0, comment='状态（0正常 1停用）')
    del_flag = Column(String(1), nullable=True, default=0, comment='删除标志（0代表存在 2代表删除）')
    create_by = Column(String(64), nullable=True, default='', comment='创建者')
    create_time = Column(DateTime, nullable=True, default=datetime.now(), comment='创建时间')
    update_by = Column(String(64), nullable=True, default='', comment='更新者')
    update_time = Column(DateTime, nullable=True, default=datetime.now(), comment='更新时间')
    # 配置与DebugTalk的关系
    hrm_debugtalk = relationship("HrmDebugTalk",
                          uselist=False,  # 表示一对一关系
                          cascade="all, delete-orphan",  # 配置级联删除
                          backref=backref('hrm_project', uselist=False))  # 使用backref简化反向引用

    def __repr__(self):
        return f"<{self.project_name})>"
