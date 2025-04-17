from sqlalchemy import Integer, BigInteger
from sqlalchemy.orm import mapped_column, Mapped

from config.database import Base
from module_hrm.entity.do.common_do import BaseModel
from utils.snowflake import snowIdWorker


class QtrFunctionsRelation(Base, BaseModel):
    """
    模块信息表
    """

    class Meta:
        verbose_name = ('UI方法关系')

    __tablename__ = 'qtr_functions_relation'
    relation_id: Mapped[BigInteger] = mapped_column(BigInteger, nullable=False, default=snowIdWorker.get_id, index=True, comment='主键ID')
    function_id: Mapped[BigInteger] = mapped_column(BigInteger, nullable=False, index=True, comment='方法ID')
    child_id: Mapped[BigInteger] = mapped_column(BigInteger, nullable=False, comment='关联的子方法ID')
    sort: Mapped[BigInteger] = mapped_column(Integer, nullable=False, comment='关联方法的顺序')
