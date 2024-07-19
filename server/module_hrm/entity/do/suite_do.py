from .common_do import BaseModel
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, BigInteger


class HrmSuite(BaseModel):
    class Meta:
        verbose_name = '用例集合'
        db_table = 'hrm_suite'

    suite_id = Column(BigInteger, unique=True, primary_key=True, nullable=False, comment='套件ID')
    project_id = Column(BigInteger, nullable=False, comment='项目id')
    suite_name = Column(String(120), nullable=False, comment='套件名')


class HrmSuiteDetail(BaseModel):
    class Meta:
        verbose_name = '用例集合详情'
        db_table = 'hrm_suite_detail'

    suite_id = Column(BigInteger, nullable=False, comment='套件id')
    case_id = Column(BigInteger, nullable=False, comment='用例id')
