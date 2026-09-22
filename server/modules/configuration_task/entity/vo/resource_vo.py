"""配置任务资源接口契约，统一使用 camelCase 和 Pydantic 校验。"""

import base64
import binascii
import hashlib
import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic.alias_generators import to_camel

from module_admin.annotation.pydantic_annotation import as_query

RESOURCE_PROVIDER_TYPE = Literal["agent_local", "sftp", "report"]
RESOURCE_PROVIDER_EXECUTION_SIDE = Literal["agent", "server"]
RESOURCE_STATUS = Literal["PENDING", "UPLOADING", "READY", "FAILED", "EXPIRED", "DELETING", "DELETED"]
SHA256_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")
OBJECT_KEY_SEGMENT_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
# 下载回传单文件上限：与传输协议单文件上限保持一致。
MAX_DOWNLOAD_FILE_BYTES = 100 * 1024 * 1024


class ResourceBaseModel(BaseModel):
    """资源接口模型基础类，兼容 ORM 属性并对外使用驼峰字段。"""

    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True, populate_by_name=True)


class ResourceCreateModel(ResourceBaseModel):
    """创建 Agent 本地资源元数据请求，不接收文件内容或绝对路径。"""

    provider_type: RESOURCE_PROVIDER_TYPE = "agent_local"
    provider_execution_side: RESOURCE_PROVIDER_EXECUTION_SIDE = "agent"
    agent_code: str = Field(min_length=1, max_length=128)
    object_key: str = Field(min_length=1, max_length=512)
    original_file_name: str = Field(min_length=1, max_length=255)
    mime_type: str = Field(default="application/octet-stream", min_length=1, max_length=255)
    file_size: int = Field(ge=0, le=9223372036854775807)
    sha256: str = Field(min_length=64, max_length=64)
    version: int = Field(default=1, ge=1, le=2147483647)
    expires_at: datetime | None = None
    remark: str = Field(default="", max_length=2000)

    @field_validator("agent_code", "original_file_name", "mime_type", mode="before")
    @classmethod
    def strip_text_fields(cls, value: str) -> str:
        """去掉首尾空白，拒绝空的资源展示或归属字段。"""
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("资源文本字段不能为空")
        return normalized

    @field_validator("original_file_name")
    @classmethod
    def validate_original_file_name(cls, value: str) -> str:
        """原始文件名仅用于展示，禁止携带路径分隔符。"""
        if "/" in value or "\\" in value or value in {".", ".."}:
            raise ValueError("原始文件名不能包含路径")
        return value

    @field_validator("object_key")
    @classmethod
    def validate_object_key(cls, value: str) -> str:
        """校验受控相对 key，拒绝绝对路径、盘符、空段和路径穿越。"""
        normalized = str(value or "").strip().replace("\\", "/")
        if not normalized or normalized.startswith("/") or re.match(r"^[A-Za-z]:", normalized):
            raise ValueError("objectKey 必须是受控相对 key，不能是绝对路径")
        segments = normalized.split("/")
        if any(not segment or segment in {".", ".."} for segment in segments):
            raise ValueError("objectKey 不能包含空路径段或 .. 路径穿越")
        if any(not OBJECT_KEY_SEGMENT_PATTERN.fullmatch(segment) for segment in segments):
            raise ValueError("objectKey 仅支持字母、数字、点、下划线和短横线")
        return normalized

    @field_validator("sha256")
    @classmethod
    def validate_sha256(cls, value: str) -> str:
        """校验 SHA-256 十六进制摘要并统一为小写。"""
        normalized = str(value or "").strip()
        if not SHA256_PATTERN.fullmatch(normalized):
            raise ValueError("sha256 必须是 64 位十六进制字符串")
        return normalized.lower()


@as_query
class ResourceQueryModel(ResourceBaseModel):
    """资源列表查询参数，resourceId 由 Pydantic 解析为内部整数。"""

    resource_id: int | None = Field(default=None, ge=1)
    agent_code: str | None = Field(default=None, min_length=1, max_length=128)
    status: RESOURCE_STATUS | None = None
    keyword: str = Field(default="", max_length=128)
    limit: int = Field(default=50, ge=1, le=200)

    @field_validator("agent_code", mode="before")
    @classmethod
    def normalize_agent_code(cls, value: str | None) -> str | None:
        """统一查询文本空白，空字符串按未传处理。"""
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None

    @field_validator("keyword", mode="before")
    @classmethod
    def normalize_keyword(cls, value: str | None) -> str:
        """keyword 未传时 as_query 会给 None，必须按空串处理，否则 str 校验失败。"""
        if value is None:
            return ""
        normalized = str(value).strip()
        return normalized


class ResourceIdPathModel(ResourceBaseModel):
    """资源路径 ID 契约；内部用整数查询，避免前端以 JavaScript Number 处理大 ID。"""

    resource_id: int = Field(gt=0)


class ResourceReadyModel(ResourceBaseModel):
    """Agent 文件完成后的元数据确认请求，不包含文件传输内容。"""

    file_size: int = Field(ge=0, le=9223372036854775807)
    sha256: str = Field(min_length=64, max_length=64)
    version: int | None = Field(default=None, ge=1, le=2147483647)

    @field_validator("sha256")
    @classmethod
    def validate_sha256(cls, value: str) -> str:
        """确认消息中的 SHA-256 必须是标准十六进制摘要。"""
        normalized = str(value or "").strip()
        if not SHA256_PATTERN.fullmatch(normalized):
            raise ValueError("sha256 必须是 64 位十六进制字符串")
        return normalized.lower()


MAX_TRANSFER_CHUNK_BYTES = 512 * 1024
MAX_RESOURCE_FILE_BYTES = 100 * 1024 * 1024
MAX_TRANSFER_CHUNKS = 4096
TRANSFER_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class ResourceTransferBeginModel(ResourceBaseModel):
    """开始资源传输请求；文件元数据以已登记资源为准。"""

    transfer_id: str | None = Field(default=None, min_length=1, max_length=128)

    @field_validator("transfer_id")
    @classmethod
    def validate_transfer_id(cls, value: str | None) -> str | None:
        """校验可选幂等传输标识，拒绝路径和不可控字符。"""
        if value is None:
            return None
        normalized = str(value).strip()
        if not TRANSFER_ID_PATTERN.fullmatch(normalized):
            raise ValueError("transferId 不是有效的传输标识")
        return normalized


class ResourceTransferChunkModel(ResourceBaseModel):
    """资源分片请求；正文只允许受限 Base64 数据。"""

    index: int = Field(ge=0, lt=MAX_TRANSFER_CHUNKS)
    offset: int = Field(ge=0, le=9223372036854775807)
    total_bytes: int = Field(ge=0, le=MAX_RESOURCE_FILE_BYTES)
    chunk_bytes: int | None = Field(default=None, ge=1, le=MAX_TRANSFER_CHUNK_BYTES)
    chunk_sha256: str = Field(min_length=64, max_length=64)
    data: str = Field(min_length=4, max_length=MAX_TRANSFER_CHUNK_BYTES * 2)

    @field_validator("chunk_sha256")
    @classmethod
    def validate_chunk_sha256(cls, value: str) -> str:
        """校验并归一化分片 SHA-256。"""
        normalized = str(value or "").strip()
        if not SHA256_PATTERN.fullmatch(normalized):
            raise ValueError("chunkSha256 必须是 64 位十六进制字符串")
        return normalized.lower()

    @field_validator("data")
    @classmethod
    def validate_base64_data(cls, value: str) -> str:
        """校验分片 Base64 可解码且不超过单块上限。"""
        try:
            decoded = base64.b64decode(value.encode("ascii"), validate=True)
        except (UnicodeEncodeError, binascii.Error, ValueError) as exc:
            raise ValueError("data 必须是合法 Base64") from exc
        if not decoded or len(decoded) > MAX_TRANSFER_CHUNK_BYTES:
            raise ValueError("分片不能为空且不能超过 512 KiB")
        return value

    @model_validator(mode="after")
    def validate_chunk_metadata(self) -> "ResourceTransferChunkModel":
        """确认声明的分片字节数与 Base64 实际内容一致。"""
        decoded = base64.b64decode(self.data.encode("ascii"), validate=True)
        if self.chunk_bytes is not None and self.chunk_bytes != len(decoded):
            raise ValueError("chunkBytes 与分片实际大小不一致")
        if hashlib.sha256(decoded).hexdigest() != self.chunk_sha256:
            raise ValueError("chunkSha256 与分片内容不一致")
        return self


class ResourceTransferCommitModel(ResourceBaseModel):
    """提交资源传输请求，不接收文件正文。"""

    pass


class ResourceTransferResponseModel(ResourceBaseModel):
    """资源传输响应；传输 ID 和资源 ID 均按字符串返回。"""

    transfer_id: str
    resource_id: str
    agent_code: str
    status: Literal["PENDING", "UPLOADING", "READY", "FAILED", "COMPLETED", "EXPIRED"]
    received_bytes: int = 0
    received_chunks: int = 0
    error_code: str = ""
    error_message: str = ""
    session_id: str = ""


class ResourceDetailModel(ResourceBaseModel):
    """资源详情响应；resourceId 永远按字符串返回。"""

    resource_id: str
    provider_type: RESOURCE_PROVIDER_TYPE
    provider_execution_side: RESOURCE_PROVIDER_EXECUTION_SIDE
    agent_code: str
    object_key: str
    original_file_name: str
    mime_type: str
    file_size: int
    checksum_algorithm: str
    sha256: str
    version: int
    status: RESOURCE_STATUS
    expires_at: datetime | None = None
    deleted_at: datetime | None = None
    error_code: str = ""
    error_message: str = ""
    create_by: str = ""
    create_time: datetime | None = None
    update_by: str = ""
    update_time: datetime | None = None
    last_audit_at: datetime | None = None
    audit_message: str = ""
    remark: str = ""


class ResourceSftpCreateModel(ResourceBaseModel):
    """SFTP 资源上传请求：文件正文直接随请求提交，服务端写入 SFTP 后登记资源。"""

    agent_code: str = Field(min_length=1, max_length=128, description="资源归属Agent编码（仅作归属标记）")
    credential_binding_id: str = Field(min_length=1, max_length=64, description="SFTP凭证绑定ID")
    object_key: str = Field(min_length=1, max_length=512, description="远端受控相对 key")
    original_file_name: str = Field(min_length=1, max_length=255)
    mime_type: str = Field(default="application/octet-stream", min_length=1, max_length=255)
    version: int = Field(default=1, ge=1, le=2147483647)
    expires_at: datetime | None = None
    remark: str = Field(default="", max_length=2000)

    @field_validator("agent_code", "original_file_name", "mime_type", mode="before")
    @classmethod
    def strip_text_fields(cls, value: str) -> str:
        """去掉首尾空白，拒绝空的资源展示或归属字段。"""
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("资源文本字段不能为空")
        return normalized

    @field_validator("original_file_name")
    @classmethod
    def validate_original_file_name(cls, value: str) -> str:
        """原始文件名仅用于展示，禁止携带路径分隔符。"""
        if "/" in value or "\\" in value or value in {".", ".."}:
            raise ValueError("原始文件名不能包含路径")
        return value


class ResourceSftpUploadModel(ResourceBaseModel):
    """SFTP 上传文件正文：受限 Base64，最大 100 MiB。"""

    data: str = Field(min_length=4, max_length=MAX_RESOURCE_FILE_BYTES * 2)

    @field_validator("data")
    @classmethod
    def validate_base64_data(cls, value: str) -> str:
        """校验文件 Base64 可解码且不超过单文件上限。"""
        try:
            decoded = base64.b64decode(value.encode("ascii"), validate=True)
        except (UnicodeEncodeError, binascii.Error, ValueError) as exc:
            raise ValueError("data 必须是合法 Base64") from exc
        if not decoded or len(decoded) > MAX_RESOURCE_FILE_BYTES:
            raise ValueError("文件不能为空且不能超过 100 MiB")
        return value


class ResourceDownloadModel(ResourceBaseModel):
    """资源下载回传响应：Base64 正文 + 元数据；不返回 Agent 绝对路径或 SFTP 主机信息。"""

    resource_id: str
    original_file_name: str
    mime_type: str
    file_size: int
    sha256: str
    data: str


class ResourceDeleteModel(ResourceBaseModel):
    """资源删除请求；强制删除仅管理员可用。"""

    force: bool = False
    reason: str = Field(default="", max_length=500)
