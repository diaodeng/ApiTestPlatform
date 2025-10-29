from datetime import datetime

from sqlalchemy import String, BigInteger, DateTime, Float, Integer, Index
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import mapped_column, Mapped

from config.database import Base
from utils.snowflake import snowIdWorker
from .common_do import BaseModel


class HrmRunDetail(Base, BaseModel):
    class Meta:
        verbose_name = '测试报告详情'

    __tablename__ = 'hrm_run_detail'

    detail_id: Mapped[int] = mapped_column(BigInteger, unique=True, primary_key=True, nullable=False,
                                           default=snowIdWorker.get_id,
                                           comment='报告ID')
    run_id: Mapped[int] = mapped_column(BigInteger, index=True, comment='用例ID/api_id')
    report_id: Mapped[int] = mapped_column(BigInteger, nullable=True, default=-1, index=True, comment='测试报告ID')
    run_name: Mapped[str] = mapped_column(String(500), comment='用例名称/api_名称')
    run_type: Mapped[int] = mapped_column(Integer, nullable=False,
                                          comment='执行方式：1-用例，2-api，3-case_debug, 4-api_debug')
    run_start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now(),
                                                     comment='执行开始时间')
    run_end_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now(),
                                                   comment='执行结束时间')
    run_duration: Mapped[float] = mapped_column(Float, nullable=False, default=0, comment='执行耗时')
    run_detail: Mapped[str] = mapped_column(LONGTEXT, nullable=False, default=None, comment='执行详情')
    status: Mapped[int] = mapped_column(Integer, nullable=False, comment='用例执行状态：1-成功，2-失败，3-跳过')

    __table_args__ = (
        Index("idx_report_detail", "report_id", "status", "run_start_time", "run_end_time", "manager", "run_id"),  # 联合索引
        Index("idx_case_detail", "run_id", "status","run_type",  "run_start_time", "run_end_time", "manager"),  # 联合索引
    )