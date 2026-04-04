from __future__ import annotations

from sqlalchemy import Text
from sqlalchemy.dialects.mysql import LONGTEXT as MYSQL_LONGTEXT
from sqlalchemy.types import TypeEngine


def long_text_type(collation: str | None = None) -> TypeEngine:
    """MySQL 使用 LONGTEXT，SQLite 退化为 Text。"""
    mysql_type = MYSQL_LONGTEXT(collation=collation) if collation else MYSQL_LONGTEXT()
    return mysql_type.with_variant(Text(), "sqlite")
