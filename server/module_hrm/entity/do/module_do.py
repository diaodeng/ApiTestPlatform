from sqlalchemy import BigInteger, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from config.database import Base
from module_hrm.entity.do.common_do import BaseModel
from module_hrm.enums.enums import QtrDataStatusEnum
from utils.snowflake import snowIdWorker


class HrmModule(Base, BaseModel):
    """
    妯″潡淇℃伅琛?
    """

    class Meta:
        verbose_name = '妯″潡淇℃伅'

    __tablename__ = 'hrm_module'

    module_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        nullable=False,
        unique=True,
        default=snowIdWorker.get_id,
        comment='妯″潡ID',
    )
    module_code: Mapped[str] = mapped_column(String(128), nullable=True, default='', comment='妯″潡涓氬姟缂栫爜')
    project_id: Mapped[int] = mapped_column(BigInteger, nullable=True, comment='椤圭洰ID')
    module_name: Mapped[str] = mapped_column(String(50), nullable=False, comment='妯″潡鍚嶇О')
    test_user: Mapped[str] = mapped_column(String(50), nullable=True, comment='娴嬭瘯璐熻矗浜?')
    simple_desc: Mapped[str] = mapped_column(String(200), nullable=True, comment='绠€瑕佷俊鎭?')
    other_desc: Mapped[str] = mapped_column(String(200), nullable=True, comment='鍏朵粬淇℃伅')
    desc2mind = mapped_column(Text, nullable=True, comment='鑴戝浘')
    sort: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment='鏄剧ず椤哄簭')
    status: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=QtrDataStatusEnum.normal.value,
        comment='鐘舵€侊紙2姝ｅ父 1鍋滅敤锛?',
    )
    remark: Mapped[str] = mapped_column(String(500), nullable=True, default='', comment='澶囨敞')


class HrmModuleProject(Base):
    """
    妯″潡鍜岄」鐩叧鑱旇〃
    """

    class Meta:
        verbose_name = "妯″潡鍜岄」鐩叧鑱旇〃"

    __tablename__ = 'hrm_module_project'

    module_id = mapped_column(BigInteger, primary_key=True, nullable=False, comment='妯″潡ID')
    project_id = mapped_column(BigInteger, primary_key=True, nullable=False, comment='椤圭洰ID')
