from typing import Optional

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from module_admin.annotation.pydantic_annotation import as_query
from module_hrm.entity.vo.common_vo import CommonDataModel, QueryModel
from module_hrm.enums.enums import QtrDataStatusEnum


class ProjectModel(CommonDataModel):
    """
    椤圭洰琛ㄥ搴攑ydantic妯″瀷
    """

    project_id: Optional[int] = None
    project_code: Optional[str] = None
    project_name: Optional[str] = None
    responsible_name: Optional[str] = None
    test_user: Optional[str] = None
    dev_user: Optional[str] = None
    publish_app: Optional[str] = None
    simple_desc: Optional[str] = None
    other_desc: Optional[str] = None
    order_num: Optional[int] = None
    status: Optional[int] = QtrDataStatusEnum.normal.value
    del_flag: Optional[str] = None


@as_query
class ProjectQueryModel(QueryModel, ProjectModel):
    """
    椤圭洰绠＄悊涓嶅垎椤垫煡璇㈡ā鍨?
    """
    pass


class DeleteProjectModel(BaseModel):
    """
    鍒犻櫎椤圭洰妯″瀷
    """
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    project_ids: str
    update_by: Optional[str] = None
    update_time: Optional[str] = None
