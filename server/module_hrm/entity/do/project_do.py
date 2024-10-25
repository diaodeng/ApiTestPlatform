from sqlalchemy import Integer, String, Text, BigInteger

from config.database import Base, mapped_column, Mapped
from module_hrm.entity.do.common_do import BaseModel
from utils.snowflake import snowIdWorker


class HrmProject(Base, BaseModel):
    """
    环境管理
    """

    class Meta:
        verbose_name = '项目管理'

    __tablename__ = 'hrm_project'

    project_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, nullable=False, unique=True, default=snowIdWorker.get_id,
                               comment='项目id')
    project_name: Mapped[str] = mapped_column(String(120), nullable=True, default='', comment='项目名称')
    responsible_name: Mapped[str] = mapped_column(String(30), nullable=True, default='', comment='负责人')
    test_user: Mapped[str] = mapped_column(String(30), nullable=True, default='', comment='测试人员')
    dev_user: Mapped[str] = mapped_column(String(30), nullable=True, default='', comment='开发人员')
    publish_app: Mapped[str] = mapped_column(String(60), nullable=True, default='', comment='发布应用')
    simple_desc: Mapped[str] = mapped_column(Text, nullable=True, default='', comment='简要描述')
    other_desc: Mapped[str] = mapped_column(Text, nullable=True, default='', comment='其他信息')
    order_num: Mapped[int] = mapped_column(Integer, default=0, comment='显示顺序')
    status: Mapped[int] = mapped_column(Integer, nullable=True, default=2, comment='状态（2正常 1停用）')
    del_flag: Mapped[str] = mapped_column(String(1), nullable=True, default=0, comment='删除标志（0代表存在 2代表删除）')

    def __repr__(self):
        return f"<{self.project_name})>"
