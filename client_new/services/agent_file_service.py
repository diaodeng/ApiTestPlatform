"""Agent 资源分片发布服务。

协议仅支持受控的 JSON 控制命令和 Base64 数据块，不提供任意文件读取、删除、
目录浏览或 SFTP。完整资源写入 ``storage/resources/.tmp`` 后，校验通过才原子
rename 到 ``storage/resources/<resource_id>`` 并写入 manifest。
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import hashlib
import os
import re
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

from services.agent_resource_storage import (
    ManifestValidationError,
    ResourceManifest,
    ResourceManifestStore,
    utc_now_iso,
)


FILE_RESOURCE_REQUEST_TYPE = 7
FILE_RESOURCE_COMMANDS = frozenset(
    {
        "file_publish_begin",
        "file_chunk",
        "file_publish_commit",
        "file_stat",
        "file_cleanup",
        "file_read",
        "file_delete",
        "file_list",
    }
)
DEFAULT_CHUNK_LIMIT = 512 * 1024
DEFAULT_FILE_LIMIT = 100 * 1024 * 1024
DEFAULT_MAX_TRANSFERS = 4
DEFAULT_TRANSFER_TTL_SECONDS = 30 * 60
DEFAULT_MANIFEST_TTL_SECONDS = 24 * 60 * 60
_HEX_SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")
_RESOURCE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class AgentFileError(ValueError):
    """资源命令可安全返回给对端的协议错误。"""

    def __init__(self, code: str, message: str = "资源操作失败"):
        super().__init__(message)
        self.code = code
        self.public_message = message


@dataclass
class _Transfer:
    """内存中的单个发布事务状态。"""

    transfer_id: str
    resource_id: str
    original_file_name: str
    mime_type: str
    expected_size: int
    expected_sha256: str
    version: int
    expires: str
    created: str
    part_path: Path
    chunks: dict[int, tuple[int, int, str]] = field(default_factory=dict)
    received_ranges: list[tuple[int, int]] = field(default_factory=list)
    last_activity: float = field(default_factory=time.monotonic)


class AgentFileService:
    """处理 Agent 本地资源的 begin/chunk/commit/stat/cleanup 命令。"""

    def __init__(
        self,
        store: ResourceManifestStore | None = None,
        *,
        root: str | os.PathLike[str] | None = None,
        max_chunk_size: int = DEFAULT_CHUNK_LIMIT,
        max_file_size: int = DEFAULT_FILE_LIMIT,
        max_concurrent_transfers: int = DEFAULT_MAX_TRANSFERS,
        transfer_ttl_seconds: float = DEFAULT_TRANSFER_TTL_SECONDS,
        manifest_ttl_seconds: float = DEFAULT_MANIFEST_TTL_SECONDS,
    ):
        self.store = store or ResourceManifestStore(root)
        self.max_chunk_size = max(1, int(max_chunk_size))
        self.max_file_size = max(1, int(max_file_size))
        self.max_concurrent_transfers = max(1, int(max_concurrent_transfers))
        self.transfer_ttl_seconds = max(1.0, float(transfer_ttl_seconds))
        self.manifest_ttl_seconds = max(1.0, float(manifest_ttl_seconds))
        self._transfers: dict[str, _Transfer] = {}
        self._lock = threading.RLock()

    @staticmethod
    def is_resource_command(message: Any) -> bool:
        """判断消息是否是独立资源协议命令。"""
        return isinstance(message, dict) and (
            message.get("requestType") == FILE_RESOURCE_REQUEST_TYPE
            or message.get("command") in FILE_RESOURCE_COMMANDS
        )

    def handle_command(self, message: dict[str, Any]) -> dict[str, Any]:
        """同步处理一个资源小 JSON 命令，返回不含文件正文的响应。"""
        command = str(message.get("command") or "").strip()
        try:
            if command not in FILE_RESOURCE_COMMANDS:
                raise AgentFileError("UNSUPPORTED_COMMAND", "不支持的资源命令")
            self.cleanup_expired()
            if command == "file_publish_begin":
                result = self.publish_begin(message)
            elif command == "file_chunk":
                result = self.file_chunk(message)
            elif command == "file_publish_commit":
                result = self.publish_commit(message)
            elif command == "file_stat":
                result = self.file_stat(message)
            elif command == "file_list":
                result = self.file_list(message)
            elif command == "file_read":
                result = self.file_read(message)
            elif command == "file_delete":
                result = self.file_delete(message)
            else:
                result = self.file_cleanup(message)
            return {
                "success": True,
                "request_type": FILE_RESOURCE_REQUEST_TYPE,
                "command": command,
                "data": result,
            }
        except AgentFileError as exc:
            logger.warning(f"Agent资源命令失败: command={command}, code={exc.code}")
            return {
                "success": False,
                "request_type": FILE_RESOURCE_REQUEST_TYPE,
                "command": command,
                "error_code": exc.code,
                "error_message": exc.public_message,
            }
        except Exception as exc:
            logger.exception(f"Agent资源命令异常: command={command}, error={exc}")
            return {
                "success": False,
                "request_type": FILE_RESOURCE_REQUEST_TYPE,
                "command": command,
                "error_code": "RESOURCE_INTERNAL_ERROR",
                "error_message": "资源操作失败",
            }

    async def handle_command_async(self, message: dict[str, Any]) -> dict[str, Any]:
        """在事件循环中执行资源命令，避免同步磁盘操作阻塞 Agent 接收协程。"""
        return await asyncio.to_thread(self.handle_command, message)

    def publish_begin(self, message: dict[str, Any]) -> dict[str, Any]:
        """创建发布事务和空的 .part 文件。"""
        resource_id = self._resource_id(
            message.get("resource_id") if "resource_id" in message else message.get("resourceId")
        )
        transfer_id = self._transfer_id(
            message.get("transfer_id") if "transfer_id" in message else message.get("transferId")
        )
        try:
            size_value = message.get("size")
            if size_value is None:
                size_value = message.get("totalBytes")
            expected_size = int(size_value)
        except (TypeError, ValueError) as exc:
            raise AgentFileError("INVALID_SIZE", "文件大小不合法") from exc
        if expected_size < 0 or expected_size > self.max_file_size:
            raise AgentFileError("FILE_TOO_LARGE", "文件超过大小限制")
        expected_sha256 = str(message.get("sha256") or "").lower()
        if not _HEX_SHA256.fullmatch(expected_sha256):
            raise AgentFileError("INVALID_SHA256", "文件校验值不合法")
        original_file_name = str(message.get("original_file_name", message.get("originalFileName")) or "")
        if not original_file_name or "\x00" in original_file_name:
            raise AgentFileError("INVALID_FILE_NAME", "文件名不合法")
        mime_type = str(message.get("mime_type", message.get("mimeType")) or "application/octet-stream")
        with self._lock:
            self.cleanup_expired()
            existing = self._transfers.get(transfer_id)
            if existing:
                if (
                    existing.resource_id == resource_id
                    and existing.expected_size == expected_size
                    and existing.expected_sha256 == expected_sha256
                ):
                    existing.last_activity = time.monotonic()
                    return self._begin_result(existing)
                raise AgentFileError("TRANSFER_CONFLICT", "传输标识已被其他发布占用")
            if len(self._transfers) >= self.max_concurrent_transfers:
                raise AgentFileError("TOO_MANY_TRANSFERS", "并发发布数量已达上限")
            part_path = self.store.tmp_root / f"{transfer_id}.part"
            if part_path.exists() and (part_path.is_symlink() or not part_path.is_file()):
                raise AgentFileError("TEMP_PATH_INVALID", "临时资源不可用")
            part_path.parent.mkdir(parents=True, exist_ok=True)
            with open(part_path, "wb"):
                pass
            now = utc_now_iso()
            transfer = _Transfer(
                transfer_id=transfer_id,
                resource_id=resource_id,
                original_file_name=original_file_name,
                mime_type=mime_type,
                expected_size=expected_size,
                expected_sha256=expected_sha256,
                version=max(1, int(message.get("version") or 1)),
                expires=str(message.get("expires") or message.get("expiresAt") or ""),
                created=now,
                part_path=part_path,
            )
            self._transfers[transfer_id] = transfer
            logger.info(
                f"Agent资源发布开始: transfer_id={transfer_id}, resource_id={resource_id}, size={expected_size}"
            )
            return self._begin_result(transfer)

    def file_chunk(self, message: dict[str, Any]) -> dict[str, Any]:
        """校验并按 offset 写入一个 Base64 分片，允许乱序及相同分片重试。"""
        transfer_id = self._transfer_id(message.get("transfer_id", message.get("transferId")))
        try:
            index = int(message.get("index"))
            offset = int(message.get("offset"))
        except (TypeError, ValueError) as exc:
            raise AgentFileError("INVALID_CHUNK_POSITION", "分片位置不合法") from exc
        if index < 0 or offset < 0:
            raise AgentFileError("INVALID_CHUNK_POSITION", "分片位置不合法")
        encoded = message.get("data")
        if not isinstance(encoded, str):
            raise AgentFileError("INVALID_CHUNK_DATA", "分片数据不合法")
        try:
            chunk = base64.b64decode(encoded.encode("ascii"), validate=True)
        except (ValueError, UnicodeEncodeError, binascii.Error) as exc:
            raise AgentFileError("INVALID_CHUNK_DATA", "分片数据不合法") from exc
        if len(chunk) > self.max_chunk_size:
            raise AgentFileError("CHUNK_TOO_LARGE", "分片超过大小限制")
        chunk_sha256 = str(message.get("chunk_sha256", message.get("chunkSha256")) or "").lower()
        if not _HEX_SHA256.fullmatch(chunk_sha256) or hashlib.sha256(chunk).hexdigest() != chunk_sha256:
            raise AgentFileError("CHUNK_CHECKSUM_MISMATCH", "分片校验失败")
        with self._lock:
            transfer = self._transfers.get(transfer_id)
            if not transfer:
                raise AgentFileError("TRANSFER_NOT_FOUND", "传输不存在或已过期")
            transfer.last_activity = time.monotonic()
            if offset + len(chunk) > transfer.expected_size:
                raise AgentFileError("SIZE_OVERFLOW", "分片超出文件大小")
            old = transfer.chunks.get(index)
            fingerprint = (offset, len(chunk), chunk_sha256)
            if old:
                if old != fingerprint:
                    raise AgentFileError("CHUNK_CONFLICT", "重复分片校验不一致")
                return {"transfer_id": transfer_id, "index": index, "offset": offset, "received": len(chunk), "idempotent": True}
            if self._overlaps_other_chunk(transfer, offset, offset + len(chunk)):
                raise AgentFileError("CHUNK_OVERLAP", "分片范围重叠")
            try:
                with open(transfer.part_path, "r+b") as handle:
                    handle.seek(offset)
                    handle.write(chunk)
                    handle.flush()
                    os.fsync(handle.fileno())
            except (OSError, ValueError) as exc:
                raise AgentFileError("WRITE_FAILED", "分片写入失败") from exc
            transfer.chunks[index] = fingerprint
            transfer.received_ranges.append((offset, offset + len(chunk)))
            received = sum(end - start for start, end in transfer.received_ranges)
            logger.info(
                f"Agent资源分片写入: transfer_id={transfer_id}, index={index}, offset={offset}, bytes={len(chunk)}"
            )
            return {"transfer_id": transfer_id, "index": index, "offset": offset, "received": received, "idempotent": False}

    def publish_commit(self, message: dict[str, Any]) -> dict[str, Any]:
        """验证完整 .part 的长度和 SHA-256，原子进入资源目录并写 manifest。"""
        transfer_id = self._transfer_id(message.get("transfer_id", message.get("transferId")))
        with self._lock:
            transfer = self._transfers.get(transfer_id)
            if not transfer:
                raise AgentFileError("TRANSFER_NOT_FOUND", "传输不存在或已过期")
            transfer.last_activity = time.monotonic()
            if not self._is_complete(transfer):
                raise AgentFileError("INCOMPLETE_FILE", "文件分片尚未完整")
            try:
                actual_size, actual_sha256 = self._hash_file(transfer.part_path)
            except OSError as exc:
                raise AgentFileError("STAT_FAILED", "文件校验失败") from exc
            if actual_size != transfer.expected_size:
                raise AgentFileError("SIZE_MISMATCH", "文件大小校验失败")
            if actual_sha256 != transfer.expected_sha256:
                raise AgentFileError("CHECKSUM_MISMATCH", "文件校验失败")
            final_path = self.store.resource_path(transfer.resource_id)
            if final_path.exists():
                if final_path.is_symlink() or not final_path.is_file():
                    raise AgentFileError("RESOURCE_PATH_INVALID", "资源路径不可用")
                old_size, old_sha256 = self._hash_file(final_path)
                if old_size != actual_size or old_sha256 != actual_sha256:
                    raise AgentFileError("RESOURCE_CONFLICT", "资源已存在且校验值不同")
                transfer.part_path.unlink(missing_ok=True)
            else:
                os.replace(transfer.part_path, final_path)
            now = utc_now_iso()
            expires = transfer.expires or self._future_expiry()
            manifest = ResourceManifest(
                resource_id=transfer.resource_id,
                locator=self.store.locator_for(transfer.resource_id),
                original_file_name=transfer.original_file_name,
                mime_type=transfer.mime_type,
                size=actual_size,
                sha256=actual_sha256,
                version=transfer.version,
                created=transfer.created,
                expires=expires,
                last_used=now,
            )
            self.store.save(manifest)
            self._transfers.pop(transfer_id, None)
            logger.info(
                f"Agent资源发布完成: transfer_id={transfer_id}, resource_id={transfer.resource_id}, size={actual_size}"
            )
            return {"resource_id": manifest.resource_id, "locator": manifest.locator, **manifest.to_dict()}

    def file_read(self, message: dict[str, Any]) -> dict[str, Any]:
        """读取受控资源内容并返回 Base64；返回前重新校验实际文件摘要。"""
        resource_id = self._resource_id(message.get("resource_id", message.get("resourceId")))
        with self._lock:
            manifest = self.store.get(resource_id)
            if manifest is None:
                raise AgentFileError("RESOURCE_NOT_FOUND", "资源不存在")
            self._ensure_not_expired(manifest)
            path = self.store.resolve_locator(manifest.locator, manifest.resource_id)
            if path.is_symlink() or not path.is_file():
                raise AgentFileError("RESOURCE_PATH_INVALID", "资源不可用")
            try:
                content = path.read_bytes()
            except OSError:
                raise AgentFileError("READ_FAILED", "资源读取失败") from None
            actual_size = len(content)
            if actual_size > self.max_file_size:
                raise AgentFileError("FILE_TOO_LARGE", "资源超过可回传大小")
            actual_sha256 = hashlib.sha256(content).hexdigest()
            self._validate_manifest_content(manifest, actual_size, actual_sha256)
            self._validate_expected_content(message, actual_size, actual_sha256)
            manifest.last_used = utc_now_iso()
            self.store.save(manifest)
            import base64 as _base64

            return {
                "resource_id": manifest.resource_id,
                "original_file_name": manifest.original_file_name,
                "mime_type": manifest.mime_type,
                "size": actual_size,
                "sha256": actual_sha256,
                "data": _base64.b64encode(content).decode("ascii"),
            }

    def file_delete(self, message: dict[str, Any]) -> dict[str, Any]:
        """删除受控资源文件与 manifest 条目；资源不存在视为已删除（幂等）。"""
        resource_id = self._resource_id(message.get("resource_id", message.get("resourceId")))
        with self._lock:
            manifest = self.store.get(resource_id)
            if manifest is None:
                return {"resource_id": resource_id, "deleted": False, "exists": False}
            try:
                path = self.store.resolve_locator(manifest.locator, manifest.resource_id)
                if path.is_file() and not path.is_symlink():
                    path.unlink()
            except OSError:
                raise AgentFileError("DELETE_FAILED", "资源删除失败") from None
            self.store.remove(resource_id)
            logger.info(f"Agent受控资源已删除: resource_id={resource_id}")
            return {"resource_id": resource_id, "deleted": True, "exists": False}

    def _upload_inputs_root(self) -> Path:
        """受控上传根目录：与资源根平级，独立于资源 manifest 生命周期管理。"""
        return self.store.storage_root / "upload_inputs"

    def file_list(self, message: dict[str, Any]) -> dict[str, Any]:
        """列出受控上传目录一层的条目，供编辑器"Agent 目录文件"模式选择。

        只返回相对路径、类型、大小与修改时间戳，不返回绝对路径与文件内容；
        prefix 允许定位到受控根内的子目录，但拒绝反斜杠、盘符、绝对路径与 .. 逃逸，
        并跳过符号链接，保证列出的条目都落在受控根目录内。
        """
        raw_prefix = str(message.get("prefix") or "").strip()
        if "\\" in raw_prefix or ":" in raw_prefix or raw_prefix.startswith("/"):
            raise AgentFileError("PATH_INVALID", "目录前缀不合法")
        parts = [part for part in raw_prefix.split("/") if part and part != "."]
        if any(part == ".." for part in parts):
            raise AgentFileError("PATH_INVALID", "目录前缀不合法")
        root = self._upload_inputs_root()
        with self._lock:
            try:
                root.mkdir(parents=True, exist_ok=True)
                root_resolved = root.resolve(strict=True)
                target = root_resolved.joinpath(*parts).resolve(strict=True) if parts else root_resolved
            except (OSError, RuntimeError):
                raise AgentFileError("LIST_FAILED", "上传目录不存在或不可用") from None
            if target != root_resolved and root_resolved not in target.parents:
                raise AgentFileError("PATH_INVALID", "目录前缀越界")
            if target.is_symlink() or not target.is_dir():
                raise AgentFileError("PATH_INVALID", "目录前缀不是有效目录")
            entries: list[dict[str, Any]] = []
            try:
                for child in sorted(target.iterdir(), key=lambda item: item.name):
                    if child.is_symlink():
                        # 跳过符号链接，防止通过链接逃逸出受控目录
                        continue
                    rel_path = "/".join((*parts, child.name)) if parts else child.name
                    if child.is_dir():
                        entries.append(
                            {"path": rel_path, "type": "directory", "size": 0, "modified_at": 0}
                        )
                        continue
                    if not child.is_file():
                        continue
                    stat = child.stat()
                    entries.append(
                        {
                            "path": rel_path,
                            "type": "file",
                            "size": stat.st_size,
                            "modified_at": int(stat.st_mtime),
                        }
                    )
            except OSError:
                raise AgentFileError("LIST_FAILED", "读取上传目录失败") from None
        logger.info(f"Agent受控上传目录列表: prefix={raw_prefix or '/'}, entries={len(entries)}")
        return {"prefix": "/".join(parts), "entries": entries}

    def file_stat(self, message: dict[str, Any]) -> dict[str, Any]:
        """只返回实际文件元数据和受控资源存在性，不返回文件内容。"""
        resource_id = self._resource_id(message.get("resource_id", message.get("resourceId")))
        with self._lock:
            manifest = self.store.get(resource_id)
            if manifest is None:
                raise AgentFileError("RESOURCE_NOT_FOUND", "资源不存在")
            self._ensure_not_expired(manifest)
            path = self.store.resolve_locator(manifest.locator, manifest.resource_id)
            if path.is_symlink() or not path.is_file():
                raise AgentFileError("RESOURCE_PATH_INVALID", "资源不可用")
            try:
                actual_size, actual_sha256 = self._hash_file(path)
            except OSError:
                raise AgentFileError("STAT_FAILED", "资源校验失败") from None
            self._validate_manifest_content(manifest, actual_size, actual_sha256)
            self._validate_expected_content(message, actual_size, actual_sha256)
            return {
                "resource_id": manifest.resource_id,
                "exists": True,
                "size": actual_size,
                "sha256": actual_sha256,
                "version": manifest.version,
                "mime_type": manifest.mime_type,
                "original_file_name": manifest.original_file_name,
                "locator": manifest.locator,
                "expires": manifest.expires,
                "last_used": manifest.last_used,
            }

    @staticmethod
    def _ensure_not_expired(manifest: ResourceManifest) -> None:
        """拒绝读取已超过 manifest expires 的 Agent 本地资源。"""
        try:
            expires_epoch = AgentFileService._parse_time(manifest.expires)
        except (TypeError, ValueError, OverflowError) as exc:
            raise AgentFileError("INVALID_EXPIRY", "资源过期时间不合法") from exc
        if expires_epoch <= time.time():
            raise AgentFileError("RESOURCE_EXPIRED", "资源已过期")

    @staticmethod
    def _validate_manifest_content(
        manifest: ResourceManifest,
        actual_size: int,
        actual_sha256: str,
    ) -> None:
        """确认当前文件仍与 Agent manifest 登记的大小和摘要一致。"""
        if actual_size != manifest.size:
            raise AgentFileError("SIZE_MISMATCH", "资源实际大小与 manifest 不一致")
        if actual_sha256 != manifest.sha256:
            raise AgentFileError("CHECKSUM_MISMATCH", "资源实际摘要与 manifest 不一致")

    @staticmethod
    def _validate_expected_content(
        message: dict[str, Any],
        actual_size: int,
        actual_sha256: str,
    ) -> None:
        """校验服务端传入的期望大小和摘要，失败时不返回文件正文。"""
        raw_size = message.get("expected_size")
        if raw_size is None:
            raw_size = message.get("expectedSize")
        if raw_size is not None:
            try:
                expected_size = int(raw_size)
            except (TypeError, ValueError) as exc:
                raise AgentFileError("INVALID_EXPECTED_SIZE", "期望文件大小不合法") from exc
            if expected_size != actual_size:
                raise AgentFileError("SIZE_MISMATCH", "资源实际大小与期望值不一致")

        expected_sha256 = message.get("expected_sha256")
        if expected_sha256 is None:
            expected_sha256 = message.get("expectedSha256")
        if expected_sha256 is not None:
            normalized_sha256 = str(expected_sha256 or "").lower()
            if not _HEX_SHA256.fullmatch(normalized_sha256):
                raise AgentFileError("INVALID_EXPECTED_SHA256", "期望文件摘要不合法")
            if normalized_sha256 != actual_sha256:
                raise AgentFileError("CHECKSUM_MISMATCH", "资源实际摘要与期望值不一致")

    def file_cleanup(self, message: dict[str, Any]) -> dict[str, Any]:
        """清理过期传输和过期 manifest 对应文件；不接受任意路径。"""
        removed_transfers, removed_resources = self.cleanup_expired()
        return {"removed_transfers": removed_transfers, "removed_resources": removed_resources}

    def cleanup_expired(self) -> tuple[int, int]:
        """按 TTL 清理未完成 .part 与已过期资源。"""
        now = time.monotonic()
        removed_transfers = 0
        removed_resources = 0
        with self._lock:
            for transfer_id, transfer in list(self._transfers.items()):
                if now - transfer.last_activity <= self.transfer_ttl_seconds:
                    continue
                try:
                    transfer.part_path.unlink(missing_ok=True)
                except OSError:
                    logger.warning(f"清理过期资源临时文件失败: transfer_id={transfer_id}")
                self._transfers.pop(transfer_id, None)
                removed_transfers += 1
            # 仅清理 manifest 已知的过期文件；不遍历或删除任意目录内容。
            manifest = self.store.read()
            now_epoch = time.time()
            for resource_id, raw in list(manifest.items()):
                try:
                    expires_epoch = self._parse_time(raw.get("expires"))
                except (TypeError, ValueError):
                    continue
                if expires_epoch > now_epoch:
                    continue
                try:
                    path = self.store.resolve_locator(str(raw.get("locator")), resource_id)
                    if path.exists() and not path.is_symlink() and path.is_file():
                        path.unlink()
                    self.store.remove(resource_id)
                    removed_resources += 1
                except (OSError, ManifestValidationError):
                    logger.warning(f"清理过期 Agent 资源失败: resource_id={resource_id}")
            return removed_transfers, removed_resources

    @staticmethod
    def _parse_time(value: Any) -> float:
        from datetime import datetime

        text = str(value or "").replace("Z", "+00:00")
        return datetime.fromisoformat(text).timestamp()

    def _future_expiry(self) -> str:
        from datetime import datetime, timedelta, timezone

        return (datetime.now(timezone.utc) + timedelta(seconds=self.manifest_ttl_seconds)).isoformat(timespec="seconds").replace("+00:00", "Z")

    @staticmethod
    def _hash_file(path: Path) -> tuple[int, str]:
        digest = hashlib.sha256()
        size = 0
        with open(path, "rb") as handle:
            while block := handle.read(1024 * 1024):
                size += len(block)
                digest.update(block)
        return size, digest.hexdigest()

    @staticmethod
    def _overlaps_other_chunk(transfer: _Transfer, start: int, end: int) -> bool:
        return any(start < old_end and end > old_start for old_start, old_end in transfer.received_ranges)

    @staticmethod
    def _is_complete(transfer: _Transfer) -> bool:
        if not transfer.expected_size:
            return not transfer.received_ranges
        ranges = sorted(transfer.received_ranges)
        cursor = 0
        for start, end in ranges:
            if start != cursor:
                return False
            cursor = end
        return cursor == transfer.expected_size

    @staticmethod
    def _resource_id(value: Any) -> str:
        text = str(value or "")
        if not _RESOURCE_ID.fullmatch(text):
            raise AgentFileError("INVALID_RESOURCE_ID", "资源标识不合法")
        return text

    @staticmethod
    def _transfer_id(value: Any) -> str:
        text = str(value or "")
        if not _RESOURCE_ID.fullmatch(text):
            raise AgentFileError("INVALID_TRANSFER_ID", "传输标识不合法")
        return text

    def _begin_result(self, transfer: _Transfer) -> dict[str, Any]:
        """返回发布事务的控制信息，不返回文件内容。"""
        return {
            "transfer_id": transfer.transfer_id,
            "resource_id": transfer.resource_id,
            "size": transfer.expected_size,
            "max_chunk_size": self.max_chunk_size,
        }


__all__ = [
    "AgentFileError",
    "AgentFileService",
    "FILE_RESOURCE_COMMANDS",
    "FILE_RESOURCE_REQUEST_TYPE",
]
