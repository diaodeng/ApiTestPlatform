from sqlalchemy import String, Text, ForeignKey, BigInteger, Integer
from sqlalchemy.orm import mapped_column, Mapped

from config.database import Base
from module_hrm.entity.do.common_do import BaseModel
from module_hrm.enums.enums import QtrDataStatusEnum
from utils.snowflake import snowIdWorker


def _set_default_debugtalk():
    common_str = """import json \r\nimport requests \r\n\r\nfrom loguru import logger \r\n\r\n"""
    before_test = "def before_test():\r\n\t'''# 默认回调-开始测试前'''\r\n\tpass\r\n\r\n"
    before_test_case = "def before_test_case(test_case):\r\n\t'''# 默认回调-用例开始执行前'''\r\n\tpass\r\n\r\n"
    before_test_step = "def before_test_step(test_step):\r\n\t'''# 默认回调-步骤开始执行前'''\r\n\tpass\r\n\r\n"
    before_request_validate = "def before_test_step(vali:list[dict]):\r\n\t'''# 默认回调-校验前的回调'''\r\n\tpass\r\n\r\n"
    after_test_step = """def after_test_step(test_step):\r\n\t'''# 默认回调-步骤执行后'''\r\n\tpass\r\n\r\n"""
    after_test_case = """def after_test_case(test_case):\r\n\t'''# 默认回调-用例执行后'''\r\n\tpass\r\n"""
    after_test = """def after_test():\r\n\t'''# 默认回调-测试执行后'''\r\n\tpass\r\n"""
    debugtalk_str = common_str + before_test + before_test_case + before_test_step + before_request_validate + after_test_step + after_test_case + after_test

    return debugtalk_str


class HrmDebugTalk(Base, BaseModel):
    """
    DebugTalk信息表
    """

    class Meta:
        verbose_name = '驱动py文件'

    __tablename__ = 'hrm_debugtalk'

    debugtalk_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, unique=True, nullable=False,
                                              default=snowIdWorker.get_id,
                                              comment='DebugTalkID')

    # 外键字段，引用 Project 的 id
    project_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('hrm_project.project_id'), nullable=True,
                                            default=None,
                                            comment='项目ID')

    # 引用 Project，表示 DebugTalk 属于哪个 Project
    # project = relationship("HrmProject", back_populates="hrm_debugtalk")

    debugtalk: Mapped[str] = mapped_column(Text(collation='utf8_general_ci'), nullable=True,
                                           default=_set_default_debugtalk(),
                                           comment='#debugtalk.py')
    status: Mapped[str] = mapped_column(Integer, default=QtrDataStatusEnum.normal.value,
                                        comment='状态（2正常 1停用）')  # QtrDataStatusEnum
    del_flag: Mapped[str] = mapped_column(String(1, collation='utf8_general_ci'), default='0',
                                          comment='删除标志（0代表存在 2代表删除）')

    def __repr__(self):
        return f"<{self.debugtalk_id} -- {self.project_id})>"
