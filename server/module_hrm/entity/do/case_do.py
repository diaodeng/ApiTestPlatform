from sqlalchemy import Integer, String, Text, BigInteger, Index, Boolean
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


class HrmCaseParams(Base, BaseModel):
    """
    模块信息表
    """


    class Meta:
        verbose_name = '用例参数化信息'

    __tablename__ = 'hrm_case_params'

    case_id: Mapped[BigInteger] = mapped_column(BigInteger, nullable=False, comment='用例、配置ID')
    # params_id: Mapped[BigInteger] = mapped_column(BigInteger, unique=True, primary_key=True, nullable=False,
    #                                               default=snowIdWorker.get_id, comment='用例、配置ID')
    enabled: Mapped[Boolean] = mapped_column(Boolean, nullable=False, default=True, comment='是否启用')
    col_sort: Mapped[Integer] = mapped_column(Integer, nullable=False, default=0, comment='列排序')
    row_id: Mapped[String] = mapped_column(String(36), nullable=False, comment='行ID')
    sort_key: Mapped[Integer] = mapped_column(Integer, nullable=False, default=0, comment='行排序键')
    col_name: Mapped[String] = mapped_column(String(500), nullable=False, comment='列名')
    params_name: Mapped[String] = mapped_column(String(500), nullable=False, comment='参数名称')
    col_value: Mapped[LONGTEXT] = mapped_column(LONGTEXT, nullable=False, comment='列值')
    params_type: Mapped[Integer] = mapped_column(Integer, comment='1 字符串 2 数字 3 列表 4 字典', default=1,
                                          nullable=False)

    __table_args__ = (
        Index("idx_case_enabled_sort", "case_id", "enabled", "sort_key", "row_id"),  # 联合索引
        Index("idx_case_sort", "case_id", "sort_key", "row_id"),  # 联合索引
        Index("idx_case_row", "case_id", "row_id"),  # 联合索引
    )



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
