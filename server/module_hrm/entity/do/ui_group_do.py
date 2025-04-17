from sqlalchemy import Integer, String, Text, BigInteger
from sqlalchemy.orm import mapped_column, Mapped

from config.database import Base
from module_hrm.entity.do.common_do import BaseModel
from utils.snowflake import snowIdWorker


class QtrUIElementGroup(Base, BaseModel):
    """
    UI元素分组信息表
    """

    class Meta:
        verbose_name = 'UI测试元素分组管理'

    __tablename__ = 'qtr_elements_group'

    group_id: Mapped[BigInteger] = mapped_column(BigInteger, unique=True, primary_key=True, nullable=False,
                                                   default=snowIdWorker.get_id, comment='元素分组ID')
    name: Mapped[String] = mapped_column(String(500), nullable=False, comment='元素分组名称')
    project_id: Mapped[BigInteger] = mapped_column(BigInteger, nullable=True, default=-1, comment='项目ID')
    module_id: Mapped[BigInteger] = mapped_column(BigInteger, nullable=True, default=-1, comment='模块ID')
    page_id: Mapped[BigInteger] = mapped_column(BigInteger, nullable=True, default=-1, comment='元素分组所属页面ID')
    group_type: Mapped[Integer] = mapped_column(Integer, nullable=False, default=1, comment='1元素、2方法')
    notes: Mapped[Text] = mapped_column(Text, nullable=True, comment='提示')
    sort: Mapped[Integer] = mapped_column(Integer, nullable=False, default=0, comment='显示顺序')
    status: Mapped[Integer] = mapped_column(Integer, nullable=False, default=2, comment='状态（2正常 1停用）,QtrDataStatusEnum')
    remark: Mapped[Text] = mapped_column(Text, nullable=True, default='', comment='备注')
