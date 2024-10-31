from sqlalchemy import Integer, String, Text, BigInteger

from config.database import Base, mapped_column, Mapped
from module_hrm.entity.do.common_do import BaseModel
from utils.snowflake import snowIdWorker


class QtrForwardRules(Base, BaseModel):
    """
    环境管理
    """

    class Meta:
        verbose_name = '转发规则管理'

    __tablename__ = 'qtr_forward_rules'

    rule_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, unique=True, nullable=False,
                                         default=snowIdWorker.get_id,
                                         comment='规则Id')
    rule_name: Mapped[str] = mapped_column(String(50), nullable=True, default='', comment='规则名称')
    origin_url: Mapped[str] = mapped_column(String(500), nullable=True, default='', comment='原始url')
    target_url: Mapped[str] = mapped_column(String(500), nullable=True, default=None, comment='目标URL')
    order_num: Mapped[int] = mapped_column(Integer, default=1, comment='显示顺序')
    simple_desc: Mapped[str] = mapped_column(Text, nullable=True, comment='备注')
    status: Mapped[int] = mapped_column(Integer, nullable=True, default=2, comment='规则状态（2启用 1禁用）')
    del_flag: Mapped[int] = mapped_column(Integer, nullable=True, default=1, comment='删除标志（1代表存在 2代表删除）')
