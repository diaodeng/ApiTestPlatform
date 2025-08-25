from sqlalchemy import Integer, String, Text, BigInteger
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import mapped_column, Mapped

from config.database import Base
from module_hrm.entity.do.common_do import BaseModel
from module_hrm.enums.enums import DataType
from utils.snowflake import snowIdWorker


class HrmCase(Base, BaseModel):
    """
    模块信息表
    """

    class Meta:
        verbose_name = '用例信息'

    __tablename__ = 'hrm_case'

    case_id: Mapped[BigInteger] = mapped_column(BigInteger, unique=True, primary_key=True, nullable=False,
                                                default=snowIdWorker.get_id, comment='用例、配置ID')
    type: Mapped[Integer] = mapped_column(Integer, comment='3 case/4 config', default=DataType.case.value,
                                          nullable=False)
    case_name: Mapped[String] = mapped_column(String(500), nullable=False, comment='用例名称')
    project_id: Mapped[BigInteger] = mapped_column(BigInteger, nullable=True, default=None, comment='项目ID')
    module_id: Mapped[BigInteger] = mapped_column(BigInteger, nullable=True, default=None, comment='模块ID')
    include: Mapped[str] = mapped_column(String(1024), nullable=True, comment='前置config/test')
    request: Mapped[LONGTEXT] = mapped_column(LONGTEXT, nullable=True, comment='请求信息')
    notes: Mapped[Text] = mapped_column(Text, nullable=True, comment='注释')
    desc2mind: Mapped[Text] = mapped_column(Text, nullable=True, comment='脑图')
    sort: Mapped[Integer] = mapped_column(Integer, nullable=False, default=0, comment='显示顺序')
    status: Mapped[int] = mapped_column(Integer, nullable=False, default=2,
                                        comment='状态（2正常 1停用）,CaseStatusEnum')
    remark: Mapped[Text] = mapped_column(Text, nullable=True, default='', comment='备注')
    # qtr_suite_detail = relationship("QtrSuiteDetail", backref="cases")


class HrmCaseModuleProject(Base):
    """
    用例、模块、项目关联表
    """

    class Meta:
        verbose_name = "用例和模块和项目关联表"

    __tablename__ = 'hrm_case_module_project'

    case_id = mapped_column(BigInteger, primary_key=True, nullable=False, comment='用例ID')
    module_id = mapped_column(BigInteger, primary_key=True, nullable=False, comment='项目ID')
    project_id = mapped_column(BigInteger, primary_key=True, nullable=False, comment='项目ID')
