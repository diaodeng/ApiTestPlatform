from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from config.database import Base
from utils.snowflake import snowIdWorker


class HrmModuleCommonPrompt(Base):
    """
    按模块业务编码跨项目复用的工单 AI 分析说明。
    """

    __tablename__ = "hrm_module_common_prompt"
    __table_args__ = (
        UniqueConstraint("module_code", name="uq_hrm_module_common_prompt_module_code"),
        Index("idx_hrm_module_common_prompt_enabled", "enabled"),
        Index("idx_hrm_module_common_prompt_del_flag", "del_flag"),
    )

    prompt_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        nullable=False,
        unique=True,
        default=snowIdWorker.get_id,
        comment="模块通用提示词ID",
    )
    module_code: Mapped[str] = mapped_column(String(128), nullable=False, comment="模块业务编码")
    prompt_content: Mapped[str] = mapped_column(Text, nullable=False, comment="模块通用说明")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, comment="是否启用")
    create_by: Mapped[str] = mapped_column(String(64), nullable=True, default="", comment="创建者")
    create_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, comment="创建时间")
    update_by: Mapped[str] = mapped_column(String(64), nullable=True, default="", comment="更新者")
    update_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, comment="更新时间")
    remark: Mapped[str] = mapped_column(String(500), nullable=True, default="", comment="备注")
    del_flag: Mapped[str] = mapped_column(String(1), nullable=False, default="0", comment="删除标志")
