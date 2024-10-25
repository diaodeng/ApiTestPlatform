from sqlalchemy import Integer, String, Text, BigInteger

from config.database import Base, mapped_column, Mapped
from module_hrm.entity.do.common_do import BaseModel
from module_hrm.enums.enums import DataType
from utils.snowflake import snowIdWorker


class ApiInfo(Base, BaseModel):
    class Meta:
        verbose_name = 'API信息'

    __tablename__ = 'hrm_api_info'

    api_id: Mapped[int] = mapped_column(BigInteger, comment='api_id', nullable=False, unique=True, default=snowIdWorker.get_id,
                           index=True)
    type: Mapped[int] = mapped_column(Integer, nullable=False, comment='目录/API', default=DataType.api.value)
    api_type: Mapped[int] = mapped_column(Integer, nullable=True, comment='API的类型', default=None)  # TstepTypeEnum
    name: Mapped[str] = mapped_column(String(500), comment='目录名/API名称', nullable=False)
    path: Mapped[str] = mapped_column(String(500), comment='接口路劲(请求地址), 为空则是目录', nullable=True)
    interface = mapped_column(String(500), comment='为空则是目录，具体接口用于搜索', nullable=True)
    parent_id: Mapped[int] = mapped_column(BigInteger, comment='父目录的id', nullable=True, default=None)
    author: Mapped[str] = mapped_column(String(20), comment='创建人', nullable=False)
    request_info: Mapped[str] = mapped_column(Text, comment='请求信息', nullable=True)
    request_data_demo: Mapped[str] = mapped_column(Text, comment='请求信息demo', nullable=True)
    response_data_demo: Mapped[str] = mapped_column(Text, comment='响应信息demo', nullable=True)
    desc: Mapped[str] = mapped_column(Text, comment='接口描述', nullable=True, default=None)
