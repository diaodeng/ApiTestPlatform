## 页面与元素，页面与页面的关系

from sqlalchemy import Integer, String, Text, BigInteger
from sqlalchemy.orm import mapped_column, Mapped

from config.database import Base
from module_hrm.entity.do.common_do import BaseModel
from utils.snowflake import snowIdWorker


class QtrPageRelation(Base, BaseModel):
    """
    页面与元素，页面与页面的关系
    """

    class Meta:
        verbose_name = 'UI页面关系'

    __tablename__ = 'qtr_page_relation'

    relation_id: Mapped[BigInteger] = mapped_column(BigInteger, unique=True, primary_key=True, nullable=False,
                                                   default=snowIdWorker.get_id, comment='元素ID')
    page_id: Mapped[BigInteger] = mapped_column(BigInteger, nullable=True, default=-1, comment='页面ID')
    relation_type: Mapped[Integer] = mapped_column(Integer, nullable=True, default=-1, comment='关联的数据类型：元素、页面、分组')
    child_id: Mapped[BigInteger] = mapped_column(BigInteger, nullable=True, default=-1, comment='页面关联的元素ID或者子页面ID')
    notes: Mapped[Text] = mapped_column(Text, nullable=True, comment='提示')
    sort: Mapped[Integer] = mapped_column(Integer, nullable=False, default=0, comment='显示顺序')
    status: Mapped[int] = mapped_column(Integer, nullable=False, default=2, comment='状态（2正常 1停用）,QtrDataStatusEnum')
    remark: Mapped[Text] = mapped_column(Text, nullable=True, default='', comment='备注')
