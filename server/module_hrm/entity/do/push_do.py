from sqlalchemy import BigInteger, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from config.database import Base
from module_hrm.entity.do.common_do import BaseModel
from utils.snowflake import snowIdWorker


class PushTarget(Base, BaseModel):
    class Meta:
        verbose_name = '推送对象管理'

    __tablename__ = 'qtr_push_target'

    push_id: Mapped[int] = mapped_column(BigInteger, comment='push_id', nullable=False, unique=True,
                                        default=snowIdWorker.get_id,
                                        index=True)
    type: Mapped[int] = mapped_column(Integer, nullable=False, comment='推送途径')  # PushTypeEnum
    allow_push: Mapped[int] = mapped_column(Integer, comment='是否允许推送', nullable=False, default=0)
    name: Mapped[str] = mapped_column(String(500), comment='名称', nullable=False)
    config_content: Mapped[str] = mapped_column(Text, comment='配置数据', nullable=True)
    desc: Mapped[str] = mapped_column(Text, comment='描述', nullable=True, default=None)
