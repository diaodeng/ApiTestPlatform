from datetime import datetime

from sqlalchemy import Integer, String, DateTime, BigInteger
from sqlalchemy.orm import mapped_column, Mapped
from common.common_do import BaseModel as base_model


class BaseModel(base_model):
    pass