"""Agent 侧网页取证文件服务。

该服务只负责将 Agent 产生的截图写入现有受控资源目录，并登记 manifest 元数据。
对调用方只返回受控 locator（objectKey），不暴露本地绝对路径，也不返回文件正文。
"""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from services.agent_resource_storage import (
    ManifestValidationError,
    ResourceManifest,
    ResourceManifestStore,
    utc_now_iso,
)


_SAFE_FILE_NAME = re.compile(r"[^A-Za-z0-9._-]+")
_DEFAULT_TTL_SECONDS = 24 * 60 * 60


class AgentEvidenceFileService:
    """把网页截图安全落盘到 Agent 资源 manifest 管理的目录。"""

    def __init__(
        self,
        store: ResourceManifestStore | None = None,
        *,
        manifest_ttl_seconds: float = _DEFAULT_TTL_SECONDS,
    ) -> None:
        """初始化取证文件服务，可注入 manifest store 方便测试。"""
        self.store = store or ResourceManifestStore()
        self.manifest_ttl_seconds = max(1.0, float(manifest_ttl_seconds))

    def save_screenshot(
        self,
        content: bytes,
        *,
        original_file_name: str,
        mime_type: str = "image/png",
    ) -> dict[str, Any]:
        """原子写入截图并登记 manifest，返回不含正文的受控元数据。"""
        if not isinstance(content, bytes) or not content:
            raise ValueError("截图正文为空")

        resource_id = f"evidence_{uuid.uuid4().hex}"
        file_name = self._safe_file_name(original_file_name)
        final_path = self.store.resource_path(resource_id)
        temporary_path: Path | None = None
        try:
            temporary_path = self._write_temporary_file(content)
            file_size, sha256 = self._hash_file(temporary_path)
            if final_path.exists():
                raise RuntimeError("截图资源标识冲突")
            os.replace(temporary_path, final_path)
            temporary_path = None
            now = utc_now_iso()
            manifest = ResourceManifest(
                resource_id=resource_id,
                locator=self.store.locator_for(resource_id),
                original_file_name=file_name,
                mime_type=str(mime_type or "image/png"),
                size=file_size,
                sha256=sha256,
                version=1,
                created=now,
                expires=self._future_expiry(),
                last_used=now,
            )
            self.store.save(manifest)
            return {
                "resourceId": manifest.resource_id,
                "objectKey": manifest.locator,
                "fileName": manifest.original_file_name,
                "mimeType": manifest.mime_type,
                "fileSize": manifest.size,
                "sha256": manifest.sha256,
                "version": manifest.version,
            }
        except (OSError, ManifestValidationError, RuntimeError, ValueError):
            if final_path.exists() and not final_path.is_symlink():
                try:
                    final_path.unlink()
                except OSError:
                    pass
            raise
        finally:
            if temporary_path is not None:
                try:
                    temporary_path.unlink(missing_ok=True)
                except OSError:
                    pass

    def _write_temporary_file(self, content: bytes) -> Path:
        """将截图写到受控临时目录并持久化后再交给调用方原子替换。"""
        self.store.tmp_root.mkdir(parents=True, exist_ok=True)
        file_descriptor, temporary_name = tempfile.mkstemp(
            prefix=".evidence-", suffix=".part", dir=str(self.store.tmp_root)
        )
        temporary_path = Path(temporary_name)
        try:
            with os.fdopen(file_descriptor, "wb") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            return temporary_path
        except Exception:
            try:
                os.close(file_descriptor)
            except OSError:
                pass
            temporary_path.unlink(missing_ok=True)
            raise

    @staticmethod
    def _hash_file(path: Path) -> tuple[int, str]:
        """读取已落盘文件，计算最终大小和 SHA-256。"""
        digest = hashlib.sha256()
        size = 0
        with path.open("rb") as handle:
            while block := handle.read(1024 * 1024):
                size += len(block)
                digest.update(block)
        return size, digest.hexdigest()

    def _future_expiry(self) -> str:
        """生成 Agent 本地资源的默认过期时间。"""
        expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=self.manifest_ttl_seconds
        )
        return expires_at.isoformat(timespec="seconds").replace("+00:00", "Z")

    @staticmethod
    def _safe_file_name(value: Any) -> str:
        """清理展示文件名，拒绝路径语义，只保留单层文件名。"""
        text = str(value or "screenshot.png").replace("\\", "/").split("/")[-1]
        text = _SAFE_FILE_NAME.sub("_", text).strip("._-")
        if not text:
            text = "screenshot.png"
        if "." not in text:
            text = f"{text}.png"
        return text[:180]


__all__ = ["AgentEvidenceFileService"]
