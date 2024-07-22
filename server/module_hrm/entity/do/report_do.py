from sqlalchemy import Column, String, Text, BigInteger

from config.database import Base
from utils.snowflake import snowIdWorker
from .common_do import BaseModel


class HrmReport(Base, BaseModel):
    class Meta:
        verbose_name = '测试报告'

    __tablename__ = 'hrm_report'

    report_id = Column(BigInteger, unique=True, primary_key=True, nullable=False, default=snowIdWorker.get_id(), comment='报告ID')
    report_name = Column(String(100), nullable=False, comment='套件名')
    start_at = Column(String(40), nullable=False, comment='用例执行时间')
    status = Column(BigInteger, nullable=False, comment='用例执行状态：1-成功，2-失败，3-跳过')
    total = Column(BigInteger, nullable=False, comment='用例总数')
    success = Column(BigInteger, nullable=False, comment='用例成功数')
    report_content = Column(Text, nullable=False, comment='报告内容')

