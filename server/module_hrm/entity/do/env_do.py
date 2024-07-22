from sqlalchemy import Column, Integer, String, Text, BigInteger

from config.database import Base
from module_hrm.entity.do.common_do import BaseModel
from utils.snowflake import snowIdWorker


class HrmEnv(Base, BaseModel):
    """
    环境管理
    """
    class Meta:
        verbose_name = '环境管理'
    __tablename__ = 'hrm_env'

    env_id = Column(BigInteger, primary_key=True, unique=True, nullable=False, default=snowIdWorker.get_id(), comment='环境id')
    env_name = Column(String(30), nullable=True, default='', comment='环境名称')
    env_url = Column(String(120), nullable=True, default=None, comment='环境地址')
    env_config = Column(String(1024), nullable=True, default=None, comment='环境配置')
    order_num = Column(Integer, default=0, comment='显示顺序')
    simple_desc = Column(Text, nullable=True, comment='备注')
    status = Column(String(1), nullable=True, default=0, comment='环境状态（0正常 1停用）')
    del_flag = Column(String(1), nullable=True, default=0, comment='删除标志（0代表存在 2代表删除）')

