from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from module_admin.annotation.pydantic_annotation import as_form, as_query
from module_hrm.entity.vo.common_vo import CommonDataModel, QueryModel
from module_hrm.enums.enums import QtrDataStatusEnum


class ModuleModel(CommonDataModel):
    """
    妯″潡淇℃伅琛ㄥ搴攑ydantic妯″瀷
    """
    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True)

    module_id: Optional[int] = None
    module_code: Optional[str] = None
    project_id: Optional[int] = None
    module_name: Optional[str] = None
    test_user: Optional[str] = None
    simple_desc: Optional[str] = None
    other_desc: Optional[str] = None
    desc2mind: Optional[str] = None
    sort: Optional[int] = None
    status: Optional[int] = QtrDataStatusEnum.normal.value
    remark: Optional[str] = None


class ModuleProjectModel(BaseModel):
    """
    妯″潡鍜岄」鐩叧鑱旇〃瀵瑰簲pydantic妯″瀷
    """
    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True)

    module_id: Optional[int] = None
    project_id: Optional[int] = None


class ModuleQueryModel(ModuleModel):
    """
    妯″潡绠＄悊涓嶅垎椤垫煡璇㈡ā鍨?
    """
    begin_time: Optional[str] = None
    end_time: Optional[str] = None
    project_id: Optional[int] = None


class ModuleQuery(ModuleModel):
    """
    妯″潡鏌ヨ
    """
    project_id: Optional[int] = None


@as_query
@as_form
class ModulePageQueryModel(QueryModel, ModuleQueryModel):
    """
    妯″潡绠＄悊鍒嗛〉鏌ヨ妯″瀷
    """
    pass


class AddModuleModel(ModuleModel):
    """
    鏂板妯″潡妯″瀷
    """
    project_id: Optional[int] = None
    type: Optional[str] = None


class DeleteModuleModel(BaseModel):
    """
    鍒犻櫎妯″潡妯″瀷
    """
    model_config = ConfigDict(alias_generator=to_camel)

    module_ids: str
    update_by: Optional[str] = None
    update_time: Optional[datetime] = None
