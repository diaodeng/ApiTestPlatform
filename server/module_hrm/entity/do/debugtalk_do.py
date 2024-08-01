from sqlalchemy import Column, String, Text, ForeignKey, BigInteger

from config.database import Base
from module_hrm.entity.do.common_do import BaseModel
from utils.snowflake import snowIdWorker


class HrmDebugTalk(Base, BaseModel):
    """
    用户信息表
    """
    class Meta:
        verbose_name = '驱动py文件'
    __tablename__ = 'hrm_debugtalk'

    debugtalk_id = Column(BigInteger, primary_key=True, unique=True, nullable=False, default=snowIdWorker.get_id, comment='DebugTalkID')

    # 外键字段，引用 Project 的 id
    project_id = Column(BigInteger, ForeignKey('hrm_project.project_id'), nullable=False)

    # 引用 Project，表示 DebugTalk 属于哪个 Project
    # project = relationship("HrmProject", back_populates="hrm_debugtalk")

    debugtalk = Column(Text(collation='utf8_general_ci'), nullable=True, comment='#debugtalk.py')
    status = Column(String(1, collation='utf8_general_ci'), default='0', comment='状态（0正常 1停用）')
    del_flag = Column(String(1, collation='utf8_general_ci'), default='0', comment='删除标志（0代表存在 2代表删除）')

    # def __repr__(self):
    #     return f"<{self.project.project_name})>"
