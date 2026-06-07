from sqlalchemy import BigInteger, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from config.database import Base
from module_hrm.entity.do.common_do import BaseModel
from module_hrm.enums.enums import QtrDataStatusEnum
from utils.snowflake import snowIdWorker


class HrmProject(Base, BaseModel):
    """
    鐜绠＄悊
    """

    class Meta:
        verbose_name = '椤圭洰绠＄悊'

    __tablename__ = 'hrm_project'

    project_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        nullable=False,
        unique=True,
        default=snowIdWorker.get_id,
        comment='椤圭洰id',
    )
    project_code: Mapped[str] = mapped_column(String(128), nullable=True, default='', comment='椤圭洰涓氬姟缂栫爜')
    project_name: Mapped[str] = mapped_column(String(120), nullable=True, default='', comment='椤圭洰鍚嶇О')
    responsible_name: Mapped[str] = mapped_column(String(30), nullable=True, default='', comment='璐熻矗浜?')
    test_user: Mapped[str] = mapped_column(String(30), nullable=True, default='', comment='娴嬭瘯浜哄憳')
    dev_user: Mapped[str] = mapped_column(String(30), nullable=True, default='', comment='寮€鍙戜汉鍛?')
    publish_app: Mapped[str] = mapped_column(String(60), nullable=True, default='', comment='鍙戝竷搴旂敤')
    simple_desc: Mapped[str] = mapped_column(Text, nullable=True, default='', comment='绠€瑕佹弿杩?')
    other_desc: Mapped[str] = mapped_column(Text, nullable=True, default='', comment='鍏朵粬淇℃伅')
    order_num: Mapped[int] = mapped_column(Integer, default=0, comment='鏄剧ず椤哄簭')
    status: Mapped[int] = mapped_column(
        Integer,
        nullable=True,
        default=QtrDataStatusEnum.normal.value,
        comment='鐘舵€侊紙2姝ｅ父 1鍋滅敤锛?',
    )
    del_flag: Mapped[str] = mapped_column(String(1), nullable=True, default=0, comment='鍒犻櫎鏍囧織锛?浠ｈ〃瀛樺湪 2浠ｈ〃鍒犻櫎锛?')

    def __repr__(self):
        return f"<{self.project_name})>"
