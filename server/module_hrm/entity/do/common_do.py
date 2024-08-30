from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, BigInteger
from datetime import datetime


class BaseModel():

    id = Column(Integer, primary_key=True, autoincrement=True, comment='ID')
    create_by = Column(String(100), nullable=True, default='', comment='创建者')
    update_by = Column(String(100), nullable=True, default='', comment='更新者')
    manager = Column(BigInteger, nullable=True, default=None, comment='管理者')
    create_time = Column(DateTime, nullable=False, default=datetime.now, comment='创建时间')
    update_time = Column(DateTime, nullable=False, default=datetime.now, comment='更新时间')
