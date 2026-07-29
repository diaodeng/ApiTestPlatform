from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel

from module_admin.annotation.pydantic_annotation import as_query
from module_hrm.entity.vo.common_vo import QueryModel


class TicketVersionBaseModel(BaseModel):
    """项目版本中心基础模型。"""

    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True, populate_by_name=True)

    project_id: int = Field(description="所属项目ID")
    project_name: str = Field(default="", description="所属项目名称")
    version_key: str = Field(description="版本标识")
    version_name: str = Field(default="", description="版本展示名称")
    lifecycle_status: str = Field(default="confirmed", description="版本状态")
    planned_release_at: datetime | None = Field(default=None, description="计划发布时间")
    default_branch: str = Field(default="", description="默认代码分支")
    enabled: bool = Field(default=True, description="是否启用")
    remark: str | None = Field(default=None, description="备注")

    @field_validator("version_key")
    @classmethod
    def validate_version_key(cls, value: str) -> str:
        """校验版本标识不能为空。"""
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("版本标识不能为空")
        return normalized


class TicketVersionCreateModel(TicketVersionBaseModel):
    """创建项目版本模型。"""


class TicketVersionUpdateModel(TicketVersionBaseModel):
    """更新项目版本模型。"""

    version_id: int = Field(description="版本ID")


@as_query
class TicketVersionOptionsQueryModel(BaseModel):
    """版本下拉选项查询模型。"""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    project_id: int = Field(description="所属项目ID")
    include_discovered: bool = Field(default=True, description="是否包含待确认版本")


@as_query
class TicketVersionQueryModel(QueryModel):
    """项目版本查询模型。"""

    project_id: int | None = Field(default=None, description="所属项目ID")
    lifecycle_status: str | None = Field(default=None, description="版本状态")
    enabled: bool | None = Field(default=None, description="是否启用")
    keyword: str | None = Field(default=None, description="版本关键字")


class TicketVersionReleaseBaseModel(BaseModel):
    """版本发布记录基础模型。"""

    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True, populate_by_name=True)

    version_id: int = Field(description="版本ID")
    environment: str = Field(default="production", description="发布环境")
    batch_no: str = Field(default="default", description="发布批次")
    release_status: str = Field(default="planned", description="发布状态")
    planned_release_at: datetime | None = Field(default=None, description="计划发布时间")
    released_at: datetime | None = Field(default=None, description="实际发布时间")
    rollback_at: datetime | None = Field(default=None, description="回滚时间")
    ci_url: str = Field(default="", description="CI/CD 链接")
    remark: str | None = Field(default=None, description="发布说明")


class TicketVersionReleaseCreateModel(TicketVersionReleaseBaseModel):
    """创建版本发布记录模型。"""


class TicketVersionReleaseUpdateModel(TicketVersionReleaseBaseModel):
    """更新版本发布记录模型。"""

    release_id: int = Field(description="发布记录ID")


class TicketVersionReleaseResponseModel(TicketVersionReleaseBaseModel):
    """版本发布记录接口响应模型。"""

    version_id: str = Field(description="版本ID，字符串避免前端整数精度丢失")
    release_id: int = Field(description="发布记录ID")
    release_by: str = Field(default="", description="发布人")

    @field_validator("version_id", mode="before")
    @classmethod
    def serialize_version_id(cls, value: int | str) -> str:
        """将 ORM 版本ID转换为浏览器可精确传输的字符串。"""
        return str(value)


class TicketVersionOptionResponseModel(BaseModel):
    """版本中心下拉选项接口响应模型。"""

    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True, populate_by_name=True)

    version_id: str = Field(description="版本ID，字符串避免前端整数精度丢失")
    version_key: str = Field(description="版本标识")
    version_name: str = Field(description="版本展示名称")
    lifecycle_status: str = Field(description="版本状态")
    default_branch: str = Field(default="", description="默认代码分支")

    @field_validator("version_id", mode="before")
    @classmethod
    def serialize_version_id(cls, value: int | str) -> str:
        """将 ORM 版本ID转换为浏览器可精确传输的字符串。"""
        return str(value)


class TicketVersionListItemResponseModel(TicketVersionBaseModel):
    """版本列表接口响应模型。"""

    version_id: str = Field(description="版本ID，字符串避免前端整数精度丢失")
    source: str = Field(default="", description="首次来源")
    release_count: int = Field(default=0, description="发布记录数量")
    latest_release: TicketVersionReleaseResponseModel | None = Field(default=None, description="最近发布记录")

    @field_validator("version_id", mode="before")
    @classmethod
    def serialize_version_id(cls, value: int | str) -> str:
        """将 ORM 版本ID转换为浏览器可精确传输的字符串。"""
        return str(value)


@as_query
class TicketVersionReleaseQueryModel(QueryModel):
    """版本发布记录查询模型。"""

    version_id: int = Field(description="版本ID")
