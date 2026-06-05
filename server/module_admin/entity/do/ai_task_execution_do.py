from datetime import datetime

from sqlalchemy import BigInteger, Column, DateTime, JSON, String

from config.database import Base
from config.sqlalchemy_types import long_text_type
from utils.snowflake import snowIdWorker


class SysAiTaskExecution(Base):
    """
    AI 任务执行审计表，用于记录轻量 AI 调用的入参、出参和状态。
    """

    __tablename__ = "sys_ai_task_execution"

    execution_id = Column(
        BigInteger,
        primary_key=True,
        nullable=False,
        unique=True,
        default=snowIdWorker.get_id,
        comment="执行ID",
    )
    task_type = Column(String(64, collation="utf8_general_ci"), nullable=False, comment="任务类型编码")
    task_name = Column(String(128, collation="utf8_general_ci"), nullable=False, default="", comment="任务名称")
    source_type = Column(String(64, collation="utf8_general_ci"), nullable=True, default="", comment="来源类型")
    source_id = Column(BigInteger, nullable=True, comment="来源ID")
    source_ref = Column(String(128, collation="utf8_general_ci"), nullable=True, default="", comment="来源引用")
    provider_code = Column(String(64, collation="utf8_general_ci"), nullable=True, default="", comment="Provider编码")
    prompt_code = Column(String(64, collation="utf8_general_ci"), nullable=True, default="", comment="提示词编码")
    model_name = Column(String(128, collation="utf8_general_ci"), nullable=True, default="", comment="模型名称")
    base_url = Column(String(500, collation="utf8_general_ci"), nullable=True, default="", comment="调用地址")
    status = Column(String(32, collation="utf8_general_ci"), nullable=False, default="pending", comment="执行状态")
    request_payload = Column(JSON, nullable=True, comment="请求载荷")
    response_payload = Column(JSON, nullable=True, comment="响应载荷")
    response_text = Column(long_text_type(), nullable=True, comment="原始响应文本")
    token_usage = Column(JSON, nullable=True, comment="Token用量")
    error_message = Column(long_text_type(), nullable=True, comment="错误信息")
    created_by_id = Column(BigInteger, nullable=True, comment="创建人ID")
    created_by_name = Column(String(100, collation="utf8_general_ci"), nullable=True, default="", comment="创建人名称")
    create_time = Column(DateTime, nullable=False, default=datetime.now, comment="创建时间")
    update_time = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now, comment="更新时间")
    del_flag = Column(String(1, collation="utf8_general_ci"), nullable=False, default="0", comment="删除标志（0存在 2删除）")
