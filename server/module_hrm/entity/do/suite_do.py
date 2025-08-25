from sqlalchemy import String, BigInteger, Integer, Text
from sqlalchemy.orm import mapped_column, Mapped

from config.database import Base
from utils.snowflake import snowIdWorker
from .common_do import BaseModel
from ...enums.enums import QtrDataStatusEnum


class QtrSuite(Base, BaseModel):
    class Meta:
        verbose_name = '测试套件'

    __tablename__ = 'qtr_suite'

    suite_id: Mapped[int] = mapped_column(BigInteger, unique=True, primary_key=True, nullable=False,
                                          default=snowIdWorker.get_id,
                                          comment='测试套件Id')
    suite_name: Mapped[str] = mapped_column(String(120), nullable=False, comment='测试套件名称')
    order_num: Mapped[int] = mapped_column(Integer, default=0, comment='显示顺序')
    simple_desc: Mapped[str] = mapped_column(Text, nullable=True, comment='备注')
    status: Mapped[int] = mapped_column(Integer, nullable=True, default=QtrDataStatusEnum.normal.value,
                                        comment='环境状态（2正常 1停用）')  # QtrDataStatusEnum
    del_flag: Mapped[str] = mapped_column(String(1), nullable=True, default=0, comment='删除标志（0代表存在 2代表删除）')


class QtrSuiteDetail(Base, BaseModel):
    class Meta:
        verbose_name = '测试套件详情'

    __tablename__ = 'qtr_suite_detail'

    suite_detail_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, nullable=False,
                                                 default=snowIdWorker.get_id,
                                                 comment='测试套件详情Id')
    suite_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False, comment='测试套件Id')
    data_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment='数据Id', index=True)
    data_type: Mapped[int] = mapped_column(Integer, nullable=False, comment='数据类型')
    order_num: Mapped[int] = mapped_column(Integer, default=0, comment='显示顺序')
    status: Mapped[int] = mapped_column(Integer, nullable=True, default=2,
                                        comment='环境状态（2正常 1停用）')  # QtrDataStatusEnum
    del_flag: Mapped[str] = mapped_column(String(1), nullable=True, default=0, comment='删除标志（0代表存在 2代表删除）')
    simple_desc: Mapped[str] = mapped_column(Text, nullable=True, comment='备注')
