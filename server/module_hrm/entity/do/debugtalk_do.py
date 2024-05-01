from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship

from config.database import Base
from datetime import datetime
from module_hrm.entity.do.project_do import HrmProject


class HrmDebugTalk(Base):
    """
    用户信息表
    """
    class Meta:
        verbose_name = '驱动py文件'
    __tablename__ = 'hrm_debugtalk'

    debugtalk_id = Column(Integer, primary_key=True, autoincrement=True, comment='DebugTalkID')

    # 外键字段，引用 Project 的 id
    project_id = Column(Integer, ForeignKey('hrm_project.project_id'), nullable=False)

    # 引用 Project，表示 DebugTalk 属于哪个 Project
    # project = relationship("HrmProject", back_populates="hrm_debugtalk")

    debugtalk = Column(Text(collation='utf8_general_ci'), nullable=True, comment='#debugtalk.py')
    status = Column(String(1, collation='utf8_general_ci'), default='0', comment='状态（0正常 1停用）')
    del_flag = Column(String(1, collation='utf8_general_ci'), default='0', comment='删除标志（0代表存在 2代表删除）')
    create_by = Column(String(64, collation='utf8_general_ci'), default='', comment='创建者')
    create_time = Column(DateTime, comment='创建时间', default=datetime.now())
    update_by = Column(String(64, collation='utf8_general_ci'), default='', comment='更新者')
    update_time = Column(DateTime, comment='更新时间', default=datetime.now())

    # def __repr__(self):
    #     return f"<{self.project.project_name})>"
