from sqlalchemy import Column, String, BigInteger, ForeignKey
from sqlalchemy.orm import relationship

from config.database import Base
from utils.snowflake import snowIdWorker
from .common_do import BaseModel


class HrmSuite(Base, BaseModel):
    class Meta:
        verbose_name = '用例集合'
    __tablename__ = 'hrm_suite'

    suite_id = Column(BigInteger, unique=True, primary_key=True, nullable=False, default=snowIdWorker.get_id, comment='套件id')
    suite_name = Column(String(120), nullable=False, comment='套件名')


class HrmSuiteDetail(Base, BaseModel):
    class Meta:
        verbose_name = '用例集合详情'

    __tablename__ = 'hrm_suite_detail'

    suite_id = Column(BigInteger, nullable=False, comment='套件id')
    project_id = Column(BigInteger, nullable=False, comment='项目id')
    # case_id = Column(BigInteger, nullable=False, comment='用例id')
    # case_name = Column(String(120), nullable=False, comment='用例名称')
    # 外键字段，引用 Case 的 id
    case_id = Column(BigInteger, ForeignKey('hrm_case.case_id'), nullable=False)

    # 引用 Case
    cases = relationship("HrmCase", back_populates="hrm_suite_detail")

