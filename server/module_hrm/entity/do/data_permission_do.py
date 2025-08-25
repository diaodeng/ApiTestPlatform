from sqlalchemy import Integer, String, Text, BigInteger
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import mapped_column, Mapped

from config.database import Base
from module_hrm.entity.do.common_do import BaseModel
from module_hrm.enums.enums import DataType
from utils.snowflake import snowIdWorker


# 权限表，存储部门、岗位、用户等与数据的关联
class DataPermission(Base, BaseModel):
    class Meta:
        verbose_name = '数据权限'
    __tablename__ = 'data_permissions'
    data_id: Mapped[BigInteger] = mapped_column(BigInteger, comment='数据Id')
    user_id: Mapped[BigInteger] = mapped_column(BigInteger, comment='用户Id')
    department_id: Mapped[BigInteger] = mapped_column(BigInteger, comment='部门Id')
    position_id: Mapped[BigInteger] = mapped_column(BigInteger, comment='岗位Id')
    permission_level: Mapped[Integer] = mapped_column(Integer, comment='权限类型')  # 例如：read, write, etc.
    #
    # data = relationship('Data')
    # user = relationship('User')
    # department = relationship('Department')
    # position = relationship('Position')