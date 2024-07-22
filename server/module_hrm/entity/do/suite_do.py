from sqlalchemy import Column, String, BigInteger

from config.database import Base
from utils.snowflake import snowIdWorker
from .common_do import BaseModel


class HrmSuite(Base, BaseModel):
    class Meta:
        verbose_name = '用例集合'
    __tablename__ = 'hrm_suite'

    suite_id = Column(BigInteger, unique=True, primary_key=True, nullable=False, default=snowIdWorker.get_id(), comment='套件ID')
    project_id = Column(BigInteger, nullable=False, comment='项目id')
    suite_name = Column(String(120), nullable=False, comment='套件名')


class HrmSuiteDetail(Base, BaseModel):
    class Meta:
        verbose_name = '用例集合详情'

    __tablename__ = 'hrm_suite_detail'

    suite_id = Column(BigInteger, nullable=False, comment='套件id')
    case_id = Column(BigInteger, nullable=False, comment='用例id')
