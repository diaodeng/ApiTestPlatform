from typing import Any, Optional

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel
from sqlalchemy.sql.elements import ColumnElement


class CrudResponseModel(BaseModel):
    """
    操作响应模型
    """
    is_success: bool
    message: str
    result: Optional[Any] = None
    # 操作结果类型（可选）：created=新建任务 / retried=重试原任务 /
    # attached=接管已有执行中任务 / reused=复用历史成功结果；供前端区分提示。
    outcome: Optional[str] = None


class UploadResponseModel(BaseModel):
    """
    上传响应模型
    """
    model_config = ConfigDict(alias_generator=to_camel)

    file_name: Optional[str] = None
    new_file_name: Optional[str] = None
    original_filename: Optional[str] = None
    url: Optional[str] = None




DataScopeExpr = ColumnElement[bool] | bool
