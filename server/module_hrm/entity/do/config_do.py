from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from config.database import Base
from datetime import datetime


class HrmConfig(Base):
    """
    模块信息表
    """
    class Meta:
        verbose_name = '配置信息'
    __tablename__ = 'hrm_config'

    config_id = Column(Integer, primary_key=True, autoincrement=True, comment='配置ID')
    config_name = Column(String(50), nullable=False, comment='配置名称')
    config_info = Column(String(1024), nullable=True, comment='配置信息')
    sort = Column(Integer, nullable=False, default=0, comment='显示顺序')
    status = Column(String(1), nullable=False, default='0', comment='状态（0正常 1停用）')
    create_by = Column(String(64), default='', comment='创建者')
    create_time = Column(DateTime, nullable=True, default=datetime.now(), comment='创建时间')
    update_by = Column(String(64), default='', comment='更新者')
    update_time = Column(DateTime, nullable=True, default=datetime.now(), comment='更新时间')
    remark = Column(String(500), nullable=True, default='', comment='备注')

