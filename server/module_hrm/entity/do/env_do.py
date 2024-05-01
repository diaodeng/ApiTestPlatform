from sqlalchemy import Column, Integer, String, DateTime, Text
from config.database import Base
from datetime import datetime


class HrmEnv(Base):
    """
    环境管理
    """
    class Meta:
        verbose_name = '环境管理'
    __tablename__ = 'hrm_env'

    env_id = Column(Integer, primary_key=True, autoincrement=True, comment='环境id')
    env_name = Column(String(30), nullable=True, default='', comment='环境名称')
    env_url = Column(String(120), nullable=True, default=None, comment='环境地址')
    order_num = Column(Integer, default=0, comment='显示顺序')
    simple_desc = Column(Text, nullable=True, comment='备注')
    status = Column(String(1), nullable=True, default=0, comment='环境状态（0正常 1停用）')
    del_flag = Column(String(1), nullable=True, default=0, comment='删除标志（0代表存在 2代表删除）')
    create_by = Column(String(64), nullable=True, default='', comment='创建者')
    create_time = Column(DateTime, nullable=True, default=datetime.now(), comment='创建时间')
    update_by = Column(String(64), nullable=True, default='', comment='更新者')
    update_time = Column(DateTime, nullable=True, default=datetime.now(), comment='更新时间')
