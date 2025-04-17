from sqlalchemy import Integer, String, Text, BigInteger
from sqlalchemy.orm import mapped_column, Mapped

from config.database import Base
from module_hrm.entity.do.common_do import BaseModel
from module_hrm.enums.enums import DataType
from utils.snowflake import snowIdWorker


class QtrElements(Base, BaseModel):
    """
    模块信息表
    """

    class Meta:
        verbose_name = 'UI测试元素管理'

    __tablename__ = 'qtr_elements'

    element_id: Mapped[BigInteger] = mapped_column(BigInteger, unique=True, primary_key=True, nullable=False,
                                                   default=snowIdWorker.get_id, comment='元素ID')
    type: Mapped[Integer] = mapped_column(Integer, comment='元素类型：文本、图片', default=DataType.case.value,
                                          nullable=False)
    name: Mapped[String] = mapped_column(String(500), nullable=False, comment='元素名称')
    value: Mapped[String] = mapped_column(String(500), nullable=False, comment='元素值')
    project_id: Mapped[BigInteger] = mapped_column(BigInteger, nullable=True, default=-1, comment='项目ID')
    module_id: Mapped[BigInteger] = mapped_column(BigInteger, nullable=True, default=-1, comment='模块ID')
    page_id: Mapped[BigInteger] = mapped_column(BigInteger, nullable=True, default=-1, comment='元素所属页面ID')
    group_id: Mapped[BigInteger] = mapped_column(BigInteger, nullable=True, default=-1, comment='元素分组ID')
    notes: Mapped[Text] = mapped_column(Text, nullable=True, comment='提示')
    sort: Mapped[Integer] = mapped_column(Integer, nullable=False, default=0, comment='显示顺序')
    status: Mapped[int] = mapped_column(Integer, nullable=False, default=2, comment='状态（2正常 1停用）,QtrDataStatusEnum')
    remark: Mapped[Text] = mapped_column(Text, nullable=True, default='', comment='备注')
