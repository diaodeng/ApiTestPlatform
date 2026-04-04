from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String
from sqlalchemy.orm import Mapped, declared_attr, mapped_column

from config.database import DATABASE_BACKEND


class BaseModel:
    @classmethod
    def _explicit_primary_key_columns(cls) -> list:
        columns = []
        for name, value in cls.__dict__.items():
            if name == "id":
                continue
            column = getattr(value, "column", None)
            if column is not None and column.primary_key:
                columns.append(column)
        return columns

    @declared_attr
    def id(cls) -> Mapped[int]:
        explicit_primary_key_columns = cls._explicit_primary_key_columns()
        if DATABASE_BACKEND == "sqlite" and explicit_primary_key_columns:
            for column in explicit_primary_key_columns:
                column.primary_key = False
                if not column.unique:
                    column.unique = True
        return mapped_column(Integer, primary_key=True, autoincrement=True, comment='ID')

    dept_id: Mapped[int] = mapped_column(Integer, default=-1, comment='部门ID')
    create_by: Mapped[str] = mapped_column(String(100), nullable=True, default='', comment='创建者')
    update_by: Mapped[str] = mapped_column(String(100), nullable=True, default='', comment='更新者')
    manager: Mapped[int] = mapped_column(BigInteger, nullable=True, default=None, comment='管理者')
    create_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, comment='创建时间')
    update_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, comment='更新时间')
