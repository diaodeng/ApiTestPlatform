from sqlalchemy import Column, String, BigInteger, ForeignKey, Integer, Text
from sqlalchemy.orm import relationship

from config.database import Base
from utils.snowflake import snowIdWorker
from .common_do import BaseModel


class QtrSuite(Base, BaseModel):
    class Meta:
        verbose_name = '测试套件'
    __tablename__ = 'qtr_suite'

    suite_id = Column(BigInteger, unique=True, primary_key=True, nullable=False, default=snowIdWorker.get_id, comment='测试套件Id')
    suite_name = Column(String(120), nullable=False, comment='测试套件名称')
    order_num = Column(Integer, default=0, comment='显示顺序')
    simple_desc = Column(Text, nullable=True, comment='备注')
    status = Column(String(1), nullable=True, default=0, comment='环境状态（0正常 1停用）')
    del_flag = Column(String(1), nullable=True, default=0, comment='删除标志（0代表存在 2代表删除）')


class QtrSuiteDetail(Base, BaseModel):
    class Meta:
        verbose_name = '测试套件详情'

    __tablename__ = 'qtr_suite_detail'

    suite_detail_id = Column(BigInteger, primary_key=True, nullable=False, default=snowIdWorker.get_id, comment='测试套件详情Id')
    suite_id = Column(BigInteger, nullable=False, comment='测试套件Id')
    data_id = Column(BigInteger, nullable=False, comment='数据Id')
    data_type = Column(BigInteger, nullable=False, comment='数据类型')
    order_num = Column(Integer, default=0, comment='显示顺序')
    status = Column(String(1), nullable=True, default=0, comment='环境状态（0正常 1停用）')
    del_flag = Column(String(1), nullable=True, default=0, comment='删除标志（0代表存在 2代表删除）')
    simple_desc = Column(Text, nullable=True, comment='备注')
