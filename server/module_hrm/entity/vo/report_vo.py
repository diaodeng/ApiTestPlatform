import json

from pydantic import BaseModel, ConfigDict, Field, field_serializer, root_validator, model_validator
from pydantic.alias_generators import to_camel
from typing import Union, Optional, List, Any, Text, Dict
from module_hrm.entity.vo.common_vo import QueryModel


class ReportQueryModel(QueryModel):
    """
    报告查询模型
    """
    pass

