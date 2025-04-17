from sqlalchemy import Integer, String, Text, BigInteger, JSON
from sqlalchemy.orm import mapped_column, Mapped

from config.database import Base
from module_hrm.entity.do.common_do import BaseModel
from module_hrm.enums.enums import DataType, FuncTypeEnum
from utils.snowflake import snowIdWorker


class QtrFunctions(Base, BaseModel):
    """
    模块信息表
    """

    class Meta:
        verbose_name = ('UI方法管理')

    __tablename__ = 'qtr_functions'

    function_id: Mapped[BigInteger] = mapped_column(BigInteger, unique=True, primary_key=True, nullable=False,
                                                    default=snowIdWorker.get_id, comment='方法ID')
    type: Mapped[Integer] = mapped_column(Integer, comment='方法类型：基本方法、封装方法', default=FuncTypeEnum.basic.value,
                                          nullable=False)
    name: Mapped[String] = mapped_column(String(500), nullable=False, comment='方法名称')
    info: Mapped[JSON] = mapped_column(JSON, nullable=True, comment='方法参数等其他信息')
    project_id: Mapped[BigInteger] = mapped_column(BigInteger, nullable=True, default=-1, comment='项目ID')
    module_id: Mapped[BigInteger] = mapped_column(BigInteger, nullable=True, default=-1, comment='模块ID')
    group_id: Mapped[BigInteger] = mapped_column(BigInteger, nullable=True, default=-1, comment='方法分组ID')
    notes: Mapped[Text] = mapped_column(Text, nullable=True, comment='提示')
    sort: Mapped[Integer] = mapped_column(Integer, nullable=False, default=0, comment='显示顺序')
    status: Mapped[int] = mapped_column(Integer, nullable=False, default=2, comment='状态（2正常 1停用）,QtrDataStatusEnum')
    remark: Mapped[Text] = mapped_column(Text, nullable=True, default='', comment='备注')
