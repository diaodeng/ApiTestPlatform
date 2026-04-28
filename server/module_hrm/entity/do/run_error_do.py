from sqlalchemy import BigInteger, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from config.database import Base
from config.sqlalchemy_types import long_text_type
from utils.snowflake import snowIdWorker

from .common_do import BaseModel


class HrmRunError(Base, BaseModel):
    class Meta:
        verbose_name = '测试执行错误事件'

    __tablename__ = 'hrm_run_error'

    error_id: Mapped[int] = mapped_column(
        BigInteger,
        unique=True,
        primary_key=True,
        nullable=False,
        default=snowIdWorker.get_id,
        comment='错误事件ID',
    )
    detail_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False, comment='执行详情ID')
    report_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False, comment='测试报告ID')
    run_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False, comment='用例ID/api_id')
    run_name: Mapped[str] = mapped_column(String(500), nullable=False, default='', comment='用例名称/api名称')
    error_type: Mapped[str] = mapped_column(String(50), nullable=False, default='', comment='错误类型')
    error_source: Mapped[str] = mapped_column(String(50), nullable=False, default='', comment='错误来源')
    error_subtype: Mapped[str] = mapped_column(String(100), nullable=False, default='', comment='错误子类型')
    error_name: Mapped[str] = mapped_column(String(255), nullable=False, default='', comment='错误名称')
    error_template: Mapped[str] = mapped_column(String(500), nullable=False, default='', comment='错误归一化模板')
    fingerprint: Mapped[str] = mapped_column(String(32), nullable=False, default='', comment='错误指纹')
    step_id: Mapped[str] = mapped_column(String(100), nullable=False, default='', comment='步骤ID')
    step_name: Mapped[str] = mapped_column(String(255), nullable=False, default='', comment='步骤名称')
    check_key: Mapped[str] = mapped_column(String(255), nullable=False, default='', comment='断言检查项')
    assert_name: Mapped[str] = mapped_column(String(100), nullable=False, default='', comment='断言方法名')
    expected_value: Mapped[str] = mapped_column(long_text_type(), nullable=False, default='', comment='期望值')
    actual_value: Mapped[str] = mapped_column(long_text_type(), nullable=False, default='', comment='实际值')
    error_message: Mapped[str] = mapped_column(long_text_type(), nullable=False, default='', comment='错误信息')
    error_stack: Mapped[str] = mapped_column(long_text_type(), nullable=False, default='', comment='错误堆栈')

    __table_args__ = (
        Index('idx_run_error_report_type', 'report_id', 'error_type', 'manager'),
        Index('idx_run_error_report_fp', 'report_id', 'fingerprint', 'manager'),
        Index('idx_run_error_detail', 'detail_id', 'manager'),
    )
