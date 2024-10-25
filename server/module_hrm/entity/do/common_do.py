from datetime import datetime

from sqlalchemy import Integer, String, DateTime, BigInteger
from sqlalchemy.orm import mapped_column, Mapped


class BaseModel():
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment='ID')
    create_by: Mapped[str] = mapped_column(String(100), nullable=True, default='', comment='创建者')
    update_by: Mapped[str] = mapped_column(String(100), nullable=True, default='', comment='更新者')
    manager: Mapped[int] = mapped_column(BigInteger, nullable=True, default=None, comment='管理者')
    create_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, comment='创建时间')
    update_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, comment='更新时间')
