"""Unidata 大数据查询接口契约模型。

对外接口的路径、查询、请求和响应契约全部使用 Pydantic 模型定义和校验。
"""
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel

from module_admin.annotation.pydantic_annotation import as_query


class UnidataBaseModel(BaseModel):
    """Unidata 接口模型基础类，统一 camelCase 对外暴露。"""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class UnidataSourceModel(UnidataBaseModel):
    """大数据查询数据源（不含任何密钥，密钥在统一凭证中）。"""

    code: str = Field(min_length=1, max_length=32, description="数据源编码，如 uat")
    name: str = Field(min_length=1, max_length=64, description="数据源显示名称")
    base_url: str = Field(min_length=1, max_length=256, description="Unidata 网关地址")
    workbench_code: str = Field(min_length=1, max_length=64, description="工作台编码")
    credential_binding_id: str = Field(default="", max_length=32, description="统一凭证绑定 ID（Authorization 头来源）")
    default_engine: Literal["kyuubi", "starrocks"] = "kyuubi"
    enabled: bool = True
    remark: str = Field(default="", max_length=256)


class UnidataSourceOptionModel(UnidataBaseModel):
    """前端数据源切换下拉项。"""

    code: str
    name: str
    default_engine: Literal["kyuubi", "starrocks"] = "kyuubi"


class UnidataEngineStatusModel(UnidataBaseModel):
    """单个查询引擎的可用性探测结果。"""

    engine: str = Field(description="引擎标识：kyuubi / starrocks")
    available: bool = Field(description="探测是否可用")
    message: str = Field(default="", max_length=500, description="不可用时的原因（来自 Unidata 报错）")


class UnidataDatabaseModel(UnidataBaseModel):
    """权限驱动的数据库条目。"""

    name: str = Field(description="库名（已剥离高亮）")
    layer: str = Field(description="所属分层：stable / gray06 / gray08 等")
    auth_types: list[str] = Field(default_factory=list, description="授权类型集合：R/RW/C")
    wildcard: bool = Field(default=False, description="是否存在整库通配授权")


@as_query
class UnidataTableQueryModel(UnidataBaseModel):
    """表列表查询参数。"""

    db_name: str = Field(min_length=1, max_length=128, description="精确库名")
    keyword: str = Field(default="", max_length=128, description="表名/中文名过滤关键字（可选）")
    page_no: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class UnidataTableModel(UnidataBaseModel):
    """库下的表条目。"""

    name: str = Field(description="表全名 db.table（已剥离高亮）")
    table_name: str = Field(default="", description="短表名")
    chinese_name: str = Field(default="", description="中文名")
    comment: str = Field(default="", description="表描述")
    owner: str = Field(default="", description="负责人")


class UnidataTablePageModel(UnidataBaseModel):
    """表列表分页响应。"""

    total: int = 0
    rows: list[UnidataTableModel] = Field(default_factory=list)


@as_query
class UnidataColumnQueryModel(UnidataBaseModel):
    """表字段清单查询参数。"""

    table_full_name: str = Field(min_length=1, max_length=256, description="表全名，db.table 格式")


class UnidataColumnModel(UnidataBaseModel):
    """表字段元数据。"""

    name: str = Field(description="字段名")
    type: str = Field(default="", description="字段类型")
    comment: str = Field(default="", description="字段备注")


class UnidataQueryRequestModel(UnidataBaseModel):
    """只读 SQL 查询请求。

    SQL 语句由 Unidata 服务端强校验（仅允许单条 SELECT/WITH/EXPLAIN/SHOW CREATE TABLE），
    平台只透传并限制行数与超时上限，不做 SQL 方言解析。
    """

    sql: str = Field(min_length=1, max_length=20000, description="只读 SQL，仅支持单条查询语句")
    max_rows: int = Field(default=200, ge=1, le=10000, description="最大返回行数")
    timeout_seconds: int = Field(default=180, ge=1, le=600, description="查询超时秒数")
    engine: Literal["kyuubi", "starrocks"] | None = Field(default=None, description="查询引擎，缺省用数据源默认引擎")

    @model_validator(mode="after")
    def validate_sql_not_blank(self):
        """拒绝纯空白的 SQL，避免无意义请求打到 Unidata。"""
        if not self.sql.strip():
            raise ValueError("SQL 不能为空白")
        return self


class UnidataQueryColumnModel(UnidataBaseModel):
    """查询结果列。"""

    name: str
    type: str = ""


class UnidataQueryResultModel(UnidataBaseModel):
    """只读 SQL 查询结果。"""

    sql_type: str = ""
    columns: list[UnidataQueryColumnModel] = Field(default_factory=list)
    rows: list[dict[str, Any]] = Field(default_factory=list)
    row_count: int = 0
    truncated: bool = False
    elapsed_ms: int = 0
