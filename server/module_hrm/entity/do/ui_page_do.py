## UI测试用来页面归类的

from sqlalchemy import Integer, String, Text, BigInteger
from sqlalchemy.orm import mapped_column, Mapped

from config.database import Base
from module_hrm.entity.do.common_do import BaseModel
from utils.snowflake import snowIdWorker


class QtrUIPage(Base, BaseModel):
    """
    页面信息管理表
    """

    class Meta:
        verbose_name = 'UI测试页面管理'

    __tablename__ = 'qtr_page'

    page_id: Mapped[BigInteger] = mapped_column(BigInteger, unique=True, primary_key=True, nullable=False,
                                                   default=snowIdWorker.get_id, comment='元素ID')
    name: Mapped[String] = mapped_column(String(500), nullable=False, comment='页面名称')
    project_id: Mapped[BigInteger] = mapped_column(BigInteger, nullable=True, default=-1, comment='项目ID,-1表示全局')
    module_id: Mapped[BigInteger] = mapped_column(BigInteger, nullable=True, default=-1, comment='模块ID,-1表示全局')
    notes: Mapped[Text] = mapped_column(Text, nullable=True, comment='提示')
    sort: Mapped[Integer] = mapped_column(Integer, nullable=False, default=0, comment='显示顺序')
    type: Mapped[Integer] = mapped_column(Integer, nullable=False, default=1, comment='页面类型，1菜单，2页面')
    status: Mapped[int] = mapped_column(Integer, nullable=False, default=2, comment='状态（2正常 1停用）,QtrDataStatusEnum')
    remark: Mapped[Text] = mapped_column(Text, nullable=True, default='', comment='备注')
