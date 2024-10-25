from datetime import datetime

from sqlalchemy import String, Text, BigInteger, DateTime, Float, Integer

from config.database import Base, mapped_column, Mapped
from utils.snowflake import snowIdWorker
from .common_do import BaseModel


class HrmReport(Base, BaseModel):
    class Meta:
        verbose_name = '测试报告'

    __tablename__ = 'hrm_report'

    report_id: Mapped[int] = mapped_column(BigInteger, unique=True, primary_key=True, nullable=False, default=snowIdWorker.get_id,
                              comment='报告ID')
    report_name: Mapped[str] = mapped_column(String(500), nullable=False, comment='报告名')
    start_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, comment='用例执行时间')
    test_duration: Mapped[float] = mapped_column(Float, nullable=False, default=0, comment='用例执行时长')
    status: Mapped[int] = mapped_column(Integer, nullable=False, default=2, comment='用例执行状态：1-成功，2-失败，3-跳过')
    total: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment='用例总数')
    success: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment='用例成功数')
    report_content: Mapped[str] = mapped_column(Text, nullable=False, default="", comment='报告内容')
