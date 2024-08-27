from sqlalchemy import Column, Integer, String, Text, BigInteger

from config.database import Base
from module_hrm.entity.do.common_do import BaseModel
from module_hrm.enums.enums import DataType
from utils.snowflake import snowIdWorker


class ApiInfo(Base, BaseModel):
    class Meta:
        verbose_name = 'API信息'

    __tablename__ = 'hrm_api_info'

    api_id = Column(BigInteger, comment='api_id', nullable=True, default=snowIdWorker.get_id, index=True)
    type = Column(Integer, nullable=False, comment='目录/API', default=DataType.api.value)
    name = Column(String(200), comment='目录名/API名称', nullable=False)
    path = Column(String(500), comment='接口路劲(请求地址), 为空则是目录', nullable=True)
    interface = Column(String(500), comment='为空则是目录，具体接口用于搜索', nullable=True)
    parent_id = Column(BigInteger, comment='父目录的id', nullable=True, default=None)
    author = Column(String(20), comment='创建人', nullable=False)
    request_info = Column(Text, comment='请求信息', nullable=True)
    request_data_demo = Column(Text, comment='请求信息demo', nullable=True)
    response_data_demo = Column(Text, comment='响应信息demo', nullable=True)
    desc = Column(Text, comment='接口描述', nullable=True, default=None)
