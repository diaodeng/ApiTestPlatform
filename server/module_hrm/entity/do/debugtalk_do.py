from sqlalchemy import Column, String, Text, ForeignKey, BigInteger
from sqlalchemy.orm import relationship

from config.database import Base
from module_hrm.entity.do.common_do import BaseModel
from utils.snowflake import snowIdWorker


def _set_default_debugtalk():
    common_str = """import logging \r\n\r\nimport json \r\nimport requests \r\n\r\nlogger = logging.getLogger('QTestRunner') \r\n"""
    before_test = "def before_test(request):\r\n\t'''# 用例执行前调用'''\r\n\tpass\r\n\r\n"
    after_test = "def after_test(response):\r\n\t'''# 测试执行后调用'''\r\n\tpass\r\n\r\n"
    before_request = """def before_teststep(request):\r\n\t'''# 步骤执行前调用'''\r\n\tpass\r\n\r\n"""
    after_request = """def after_teststep(response):\r\n\t'''# 步骤执行后调用'''\r\n\tpass\r\n"""
    debugtalk_str = common_str + before_test + after_test + before_request + after_request

    return debugtalk_str


class HrmDebugTalk(Base, BaseModel):
    """
    DebugTalk信息表
    """

    class Meta:
        verbose_name = '驱动py文件'

    __tablename__ = 'hrm_debugtalk'

    debugtalk_id = Column(BigInteger, primary_key=True, unique=True, nullable=False, default=snowIdWorker.get_id,
                          comment='DebugTalkID')

    # 外键字段，引用 Project 的 id
    project_id = Column(BigInteger, ForeignKey('hrm_project.project_id'), nullable=True, default=None, comment='项目ID')

    # 引用 Project，表示 DebugTalk 属于哪个 Project
    project = relationship("HrmProject", back_populates="hrm_debugtalk")

    debugtalk = Column(Text(collation='utf8_general_ci'), nullable=True, default=_set_default_debugtalk(),
                       comment='#debugtalk.py')
    status = Column(String(1, collation='utf8_general_ci'), default='0', comment='状态（0正常 1停用）')
    del_flag = Column(String(1, collation='utf8_general_ci'), default='0', comment='删除标志（0代表存在 2代表删除）')

    def __repr__(self):
        return f"<{self.project.project_name})>"
