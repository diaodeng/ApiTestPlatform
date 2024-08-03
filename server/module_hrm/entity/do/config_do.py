from sqlalchemy import Column, Integer, String, BigInteger

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

    config_id = Column(BigInteger, primary_key=True, unique=True, nullable=False, default=snowIdWorker.get_id, comment='配置ID')
    config_name = Column(String(50), nullable=False, comment='配置名称')
    config_info = Column(String(1024), nullable=True, comment='配置信息')
    sort = Column(Integer, nullable=False, default=0, comment='显示顺序')
    status = Column(String(1), nullable=False, default='0', comment='状态（0正常 1停用）')
    remark = Column(String(500), nullable=True, default='', comment='备注')

