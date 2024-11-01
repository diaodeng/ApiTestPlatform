from sqlalchemy import Integer, String, Text, BigInteger, DateTime
from datetime import datetime
from config.database import Base, mapped_column, Mapped
from module_hrm.entity.do.common_do import BaseModel
from utils.snowflake import snowIdWorker


class QtrAgent(Base, BaseModel):
    """
    环境管理
    """

    class Meta:
        verbose_name = 'Agent管理'

    __tablename__ = 'qtr_agent'

    agent_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, unique=True, nullable=False, default=snowIdWorker.get_id,
                           comment='AagentId')
    agent_name: Mapped[str] = mapped_column(String(30), nullable=True, default='', comment='Aagent名称')
    agent_code: Mapped[str] = mapped_column(String(120), nullable=True, default=None, comment='Aagent编码')
    online_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, comment='上线时间')
    offline_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, comment='下线时间')
    order_num: Mapped[int] = mapped_column(Integer, default=0, comment='显示顺序')
    simple_desc: Mapped[str] = mapped_column(Text, nullable=True, comment='备注')
    status: Mapped[int] = mapped_column(Integer, nullable=True, default=0, comment='Agent状态（0在线 1离线）')
    del_flag: Mapped[int] = mapped_column(Integer, nullable=True, default=0, comment='删除标志（0代表存在 2代表删除）')

