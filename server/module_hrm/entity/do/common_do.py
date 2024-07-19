from config.database import Base
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, BigInteger


class BaseModel(Base):
    id = Column(Integer, primary_key=True, autoincrement=True, comment='ID')
    create_by = Column(String(100), nullable=True, default='', comment='创建者')
    update_by = Column(String(100), nullable=True, default='', comment='更新者')
    create_time = Column(DateTime, nullable=False, comment='创建时间')
    update_time = Column(DateTime, nullable=False, comment='更新时间')
