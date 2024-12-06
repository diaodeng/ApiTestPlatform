from sqlalchemy import Integer, String, BigInteger
from sqlalchemy.orm import mapped_column, Mapped

from config.database import Base
from module_hrm.entity.do.common_do import BaseModel
from utils.snowflake import snowIdWorker


class HrmConfig(Base, BaseModel):
    """
    模块信息表
    """

    class Meta:
        verbose_name = '配置信息'

    __tablename__ = 'hrm_config'

    config_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, unique=True, nullable=False,
                                           default=snowIdWorker.get_id,
                                           comment='配置ID')
    config_name: Mapped[str] = mapped_column(String(50), nullable=False, comment='配置名称')
    config_info: Mapped[str] = mapped_column(String(1024), nullable=True, comment='配置信息')
    sort: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment='显示顺序')
    status: Mapped[int] = mapped_column(Integer, nullable=False, default=2, comment='状态（2正常 1停用）')
    remark: Mapped[str] = mapped_column(String(500), nullable=True, default='', comment='备注')
