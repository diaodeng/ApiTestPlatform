from sqlalchemy import Integer, String, Text, BigInteger
from sqlalchemy.orm import mapped_column, Mapped

from config.database import Base
from module_hrm.entity.do.common_do import BaseModel
from module_hrm.enums.enums import UrlContentEnum
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


class QtrForwardRulesDetail(Base, BaseModel):
    """
    环境管理
    """

    class Meta:
        verbose_name = '转发规则管理'

    __tablename__ = 'qtr_forward_rules_detail'

    rule_detail_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, unique=True, nullable=False,
                                                default=snowIdWorker.get_id,
                                                comment='规则详情Id')
    rule_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False,
                                         comment='规则Id')
    rule_detail_name: Mapped[str] = mapped_column(String(50), nullable=True, default='', comment='规则名称')
    match_type: Mapped[int] = mapped_column(BigInteger, nullable=False, default=1,
                                            comment='规则匹配类型,module_hrm.enums.enums.ForwardRuleMatchTypeEnum')
    origin_url: Mapped[str] = mapped_column(String(500), nullable=True, default='', comment='原始url')
    replace_content: Mapped[int] = mapped_column(Integer, default=UrlContentEnum.URL.value, comment='替换内容')
    target_url: Mapped[str] = mapped_column(String(500), nullable=True, default=None, comment='目标URL')
    order_num: Mapped[int] = mapped_column(Integer, default=1, comment='显示顺序')
    simple_desc: Mapped[str] = mapped_column(Text, nullable=True, comment='备注')
    status: Mapped[int] = mapped_column(Integer, nullable=True, default=2, comment='规则状态（2启用 1禁用）')
    del_flag: Mapped[int] = mapped_column(Integer, nullable=True, default=1, comment='删除标志（1代表存在 2代表删除）')
