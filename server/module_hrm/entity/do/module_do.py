from sqlalchemy import Integer, String, Text, BigInteger

from config.database import Base, mapped_column, Mapped
from module_hrm.entity.do.common_do import BaseModel
from utils.snowflake import snowIdWorker


class HrmModule(Base, BaseModel):
    """
    模块信息表
    """

    class Meta:
        verbose_name = '模块信息'

    __tablename__ = 'hrm_module'

    module_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, nullable=False, unique=True,
                                          default=snowIdWorker.get_id,
                                          comment='模块ID')
    project_id: Mapped[int] = mapped_column(BigInteger, nullable=True, comment='项目ID')
    module_name: Mapped[str] = mapped_column(String(50), nullable=False, comment='模块名称')
    test_user: Mapped[str] = mapped_column(String(50), nullable=True, comment='测试负责人')
    simple_desc: Mapped[str] = mapped_column(String(200), nullable=True, comment='简要信息')
    other_desc: Mapped[str] = mapped_column(String(200), nullable=True, comment='其他信息')
    desc2mind = mapped_column(Text, nullable=True, comment='脑图')
    sort: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment='显示顺序')
    status: Mapped[int] = mapped_column(Integer, nullable=False, default=2, comment='状态（2正常 1停用）')
    remark: Mapped[str] = mapped_column(String(500), nullable=True, default='', comment='备注')


class HrmModuleProject(Base):
    """
    模块和项目关联表
    """

    class Meta:
        verbose_name = "模块和项目关联表"

    __tablename__ = 'hrm_module_project'

    module_id = mapped_column(BigInteger, primary_key=True, nullable=False, comment='模块ID')
    project_id = mapped_column(BigInteger, primary_key=True, nullable=False, comment='项目ID')
