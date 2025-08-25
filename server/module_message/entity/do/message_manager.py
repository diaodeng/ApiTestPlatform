from datetime import datetime

from sqlalchemy import String, Text, BigInteger, DateTime, Float, Integer
from sqlalchemy.orm import mapped_column, Mapped

from config.database import Base
from utils.snowflake import snowIdWorker
from .common_do import BaseModel
from ...enums.enums import PushWayEnum, QtrDataStatusEnum, PushConfigTypeEnum


class QtrMessageManager(Base, BaseModel):
    class Meta:
        verbose_name = '消息推送方式配置管理'

    __tablename__ = 'qtr_message_manager'

    message_id: Mapped[int] = mapped_column(BigInteger, unique=True, primary_key=True, nullable=False,
                                           default=snowIdWorker.get_id,
                                           comment='通知ID')
    name: Mapped[str] = mapped_column(String(500), nullable=False, comment='通知方式名称')
    type: Mapped[int] = mapped_column(Integer, nullable=False, default=PushWayEnum.FEISHU_BOT.value, comment='通知类型')
    desc: Mapped[str] = mapped_column(Text, nullable=True, default="", comment='描述信息')
    status: Mapped[int] = mapped_column(Integer, nullable=False, default=QtrDataStatusEnum.normal.value, comment='')
    config_type: Mapped[int] = mapped_column(Integer, nullable=False, default=PushConfigTypeEnum.CUSTOM.value, comment='配置类型')
    config: Mapped[str] = mapped_column(Text, nullable=False, default="", comment='配置内容')
