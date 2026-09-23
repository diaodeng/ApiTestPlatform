"""Agent 资源 manifest 的受控本地存储。

该模块只负责资源索引和受控路径解析，不提供任意文件读取、删除或目录浏览能力。
资源文件由 ``agent_file_service`` 写入，manifest 使用独立文件原子替换，避免把
AgentConfigModel 变成资源数据库。
"""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Mapping

from loguru import logger


_MANIFEST_VERSION = 1
_RESOURCE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_SHA256_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")


class ManifestValidationError(ValueError):
    """manifest 字段或受控 locator 不符合协议。"""


@dataclass(frozen=True)
class ResourceManifest:
    """一个已完成 Agent 本地资源的元数据快照。"""

    resource_id: str
    locator: str
    original_file_name: str
    mime_type: str
    size: int
    sha256: str
    version: int
    created: str
    expires: str
    last_used: str

    def to_dict(self) -> dict[str, Any]:
        """将实体转换为 manifest JSON 对象。"""
        return asdict(self)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ResourceManifest":
        """从 JSON 映射校验并构造 manifest 实体。"""
        required = (
            "resource_id",
            "locator",
            "original_file_name",
            "mime_type",
            "size",
            "sha256",
            "version",
            "created",
            "expires",
            "last_used",
        )
        missing = [name for name in required if name not in value]
        if missing:
            raise ManifestValidationError(f"manifest 缺少字段: {','.join(missing)}")
        resource_id = str(value["resource_id"])
        locator = str(value["locator"])
        if not _RESOURCE_ID_PATTERN.fullmatch(resource_id):
            raise ManifestValidationError("resource_id 不合法")
        if not _SHA256_PATTERN.fullmatch(str(value["sha256"])):
            raise ManifestValidationError("sha256 不合法")
        try:
            size = int(value["size"])
            version = int(value["version"])
        except (TypeError, ValueError) as exc:
            raise ManifestValidationError("size 或 version 不合法") from exc
        if size < 0 or version < 1:
            raise ManifestValidationError("size 或 version 超出范围")
        if not isinstance(value["original_file_name"], str) or not value["original_file_name"]:
            raise ManifestValidationError("original_file_name 不合法")
        if not isinstance(value["mime_type"], str):
            raise ManifestValidationError("mime_type 不合法")
        for field in ("created", "expires", "last_used"):
            if not isinstance(value[field], str) or not value[field]:
                raise ManifestValidationError(f"{field} 不合法")
        return cls(
            resource_id=resource_id,
            locator=locator,
            original_file_name=value["original_file_name"],
            mime_type=value["mime_type"],
            size=size,
            sha256=str(value["sha256"]).lower(),
            version=version,
            created=value["created"],
            expires=value["expires"],
            last_used=value["last_used"],
        )


def utc_now_iso() -> str:
    """返回不含本地时区歧义的 UTC ISO 时间。"""
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def default_application_root() -> Path:
    """计算稳定应用根目录，不依赖当前工作目录。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


class ResourceManifestStore:
    """存储 Agent 本地资源 manifest，并解析受控资源 locator。"""

    def __init__(self, root: str | os.PathLike[str] | None = None):
        self.root = Path(root or default_application_root()).expanduser().resolve()
        self.storage_root = self.root / "storage"
        self.data_root = self.storage_root / "data"
        self.resources_root = self.storage_root / "resources"
        self.tmp_root = self.resources_root / ".tmp"
        self.manifest_path = self.data_root / "resource_manifest.json"
        self._lock = threading.RLock()
        self._ensure_layout()

    def _ensure_layout(self) -> None:
        """创建并检查资源目录，拒绝目录级符号链接逃逸。"""
        self._ensure_directory(self.storage_root)
        self._ensure_directory(self.data_root)
        self._ensure_directory(self.resources_root)
        self._ensure_directory(self.tmp_root)

    @staticmethod
    def _ensure_directory(path: Path) -> None:
        if path.exists() and (path.is_symlink() or not path.is_dir()):
            raise ManifestValidationError("资源存储目录不可用")
        path.mkdir(parents=True, exist_ok=True)
        if path.is_symlink():
            raise ManifestValidationError("资源存储目录不可用")

    def _empty_document(self) -> dict[str, Any]:
        return {"version": _MANIFEST_VERSION, "resources": {}}

    def _load_document(self) -> dict[str, Any]:
        """读取 manifest；缺失、损坏或结构错误时安全返回空文档。"""
        if not self.manifest_path.exists():
            return self._empty_document()
        if self.manifest_path.is_symlink() or not self.manifest_path.is_file():
            logger.warning("资源 manifest 文件类型不受支持，按空清单处理")
            return self._empty_document()
        try:
            raw = json.loads(self.manifest_path.read_text(encoding="utf-8"))
            resources = raw.get("resources", {}) if isinstance(raw, dict) else {}
            if not isinstance(resources, dict):
                raise ManifestValidationError("manifest resources 结构错误")
            valid: dict[str, dict[str, Any]] = {}
            for resource_id, value in resources.items():
                if not isinstance(value, Mapping):
                    logger.warning(f"忽略结构异常的资源清单项: resource_id={resource_id}")
                    continue
                try:
                    item = ResourceManifest.from_mapping(value)
                    if item.resource_id != str(resource_id):
                        raise ManifestValidationError("resource_id 键值不一致")
                    self._validate_locator(item.locator, item.resource_id)
                    valid[item.resource_id] = item.to_dict()
                except ManifestValidationError:
                    logger.warning(f"忽略不合法的资源清单项: resource_id={resource_id}")
            return {"version": _MANIFEST_VERSION, "resources": valid}
        except (OSError, json.JSONDecodeError, ManifestValidationError) as exc:
            logger.warning(f"读取资源 manifest 失败，按空清单处理: error={type(exc).__name__}")
            return self._empty_document()

    def _atomic_write_document(self, document: Mapping[str, Any]) -> None:
        """通过同目录临时文件、flush、fsync 和 replace 原子写入 manifest。"""
        self._ensure_layout()
        payload = json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True)
        fd, temporary_name = tempfile.mkstemp(
            prefix=".resource_manifest.", suffix=".tmp", dir=str(self.data_root)
        )
        temporary_path = Path(temporary_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(payload)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, self.manifest_path)
        finally:
            if temporary_path.exists():
                try:
                    temporary_path.unlink()
                except OSError:
                    logger.warning("清理 manifest 临时文件失败")

    def _validate_locator(self, locator: str, resource_id: str | None = None) -> Path:
        """校验 locator 为 storage 根下的相对路径并返回解析后的路径。"""
        if not locator or "\x00" in locator or "\\" in locator:
            raise ManifestValidationError("locator 不合法")
        posix = PurePosixPath(locator)
        windows = PureWindowsPath(locator)
        if posix.is_absolute() or windows.is_absolute() or any(part == ".." for part in posix.parts):
            raise ManifestValidationError("locator 不合法")
        if posix.parts[:1] != ("resources",) or len(posix.parts) != 2:
            raise ManifestValidationError("locator 不在受控资源目录")
        target_id = posix.parts[1]
        if not _RESOURCE_ID_PATTERN.fullmatch(target_id):
            raise ManifestValidationError("locator 不合法")
        if resource_id is not None and target_id != resource_id:
            raise ManifestValidationError("locator 与 resource_id 不一致")
        candidate = (self.storage_root / Path(*posix.parts)).resolve(strict=False)
        storage_resolved = self.storage_root.resolve()
        try:
            candidate.relative_to(storage_resolved)
        except ValueError as exc:
            raise ManifestValidationError("locator 越出资源目录") from exc
        current = self.storage_root
        for part in posix.parts:
            current = current / part
            if current.exists() and current.is_symlink():
                raise ManifestValidationError("locator 包含符号链接")
        return candidate

    def read(self) -> dict[str, dict[str, Any]]:
        """读取资源条目映射；返回副本，调用方不能修改内部状态。"""
        with self._lock:
            return dict(self._load_document()["resources"])

    def load(self) -> dict[str, dict[str, Any]]:
        """read 的语义别名，便于服务层表达读取动作。"""
        return self.read()

    def read_manifest(self) -> dict[str, Any]:
        """读取包含 manifest 版本和 resources 的完整 JSON 结构。"""
        with self._lock:
            document = self._load_document()
            return {"version": document["version"], "resources": dict(document["resources"])}

    def get(self, resource_id: str) -> ResourceManifest | None:
        """按资源 ID 读取一条 manifest。"""
        with self._lock:
            value = self._load_document()["resources"].get(resource_id)
            return ResourceManifest.from_mapping(value) if value else None

    def save(self, resource: ResourceManifest | Mapping[str, Any]) -> ResourceManifest:
        """校验并原子保存一条资源 manifest。"""
        item = resource if isinstance(resource, ResourceManifest) else ResourceManifest.from_mapping(resource)
        self._validate_locator(item.locator, item.resource_id)
        with self._lock:
            document = self._load_document()
            document["resources"][item.resource_id] = item.to_dict()
            self._atomic_write_document(document)
        return item

    def save_resource(self, **fields: Any) -> ResourceManifest:
        """按字段保存资源，作为服务层更直观的公开 API。"""
        return self.save(ResourceManifest.from_mapping(fields))

    def upsert(self, resource: ResourceManifest | Mapping[str, Any]) -> ResourceManifest:
        """save 的公开 upsert 别名。"""
        return self.save(resource)

    def remove(self, resource_id: str) -> bool:
        """仅从 manifest 移除指定资源索引，不触碰资源文件。"""
        with self._lock:
            document = self._load_document()
            if resource_id not in document["resources"]:
                return False
            document["resources"].pop(resource_id, None)
            self._atomic_write_document(document)
            return True

    def resolve_locator(self, locator: str, resource_id: str | None = None) -> Path:
        """将已校验的受控 locator 解析为内部路径，不接受任意用户路径。"""
        with self._lock:
            return self._validate_locator(locator, resource_id)

    def resource_path(self, resource_id: str) -> Path:
        """按受控资源 ID计算内部文件路径。"""
        if not _RESOURCE_ID_PATTERN.fullmatch(str(resource_id)):
            raise ManifestValidationError("resource_id 不合法")
        return self._validate_locator(f"resources/{resource_id}", str(resource_id))

    @staticmethod
    def locator_for(resource_id: str) -> str:
        """生成标准相对 locator。"""
        if not _RESOURCE_ID_PATTERN.fullmatch(str(resource_id)):
            raise ManifestValidationError("resource_id 不合法")
        return f"resources/{resource_id}"


__all__ = [
    "ManifestValidationError",
    "ResourceManifest",
    "ResourceManifestStore",
    "default_application_root",
    "utc_now_iso",
]
