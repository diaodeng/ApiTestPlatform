"""Web upload_file 资源解析和 Agent 请求日志脱敏测试。"""

from pathlib import Path

import pytest

from services.agent_resource_storage import ResourceManifest, ResourceManifestStore, utc_now_iso
from services.web_test_service import (
    UploadFileResolutionError,
    _resolve_upload_file_paths,
)


def _resource(store: ResourceManifestStore, resource_id: str, payload: bytes = b"demo") -> Path:
    path = store.resource_path(resource_id)
    path.write_bytes(payload)
    store.save(
        ResourceManifest(
            resource_id=resource_id,
            locator=store.locator_for(resource_id),
            original_file_name="demo.txt",
            mime_type="text/plain",
            size=len(payload),
            sha256="a" * 64,
            version=1,
            created=utc_now_iso(),
            expires=utc_now_iso(),
            last_used=utc_now_iso(),
        )
    )
    return path


def test_upload_file_resolves_agent_manifest_by_resource_id(tmp_path: Path):
    store = ResourceManifestStore(tmp_path)
    path = _resource(store, "res-demo")

    resolved = _resolve_upload_file_paths(
        {"fileKey": "price_tag"},
        {"resourceBindings": {"price_tag": {"resourceId": "res-demo"}}, "resourceApplicationRoot": str(tmp_path)},
    )

    assert resolved == [path]


def test_upload_file_rejects_multiple_files_when_disabled(tmp_path: Path):
    store = ResourceManifestStore(tmp_path)
    _resource(store, "res-a")
    _resource(store, "res-b")

    paths = _resolve_upload_file_paths(
        {"resourceIds": ["res-a", "res-b"]},
        {"resourceApplicationRoot": str(tmp_path)},
    )
    assert len(paths) == 2

    with pytest.raises(UploadFileResolutionError, match="未绑定"):
        _resolve_upload_file_paths({"fileKey": "missing"}, {"resourceApplicationRoot": str(tmp_path)})


def test_upload_file_never_uses_file_path_parameter(tmp_path: Path):
    outside = tmp_path / "outside.txt"
    outside.write_text("not a resource", encoding="utf-8")

    with pytest.raises(UploadFileResolutionError):
        _resolve_upload_file_paths(
            {"filePath": str(outside)},
            {"resourceApplicationRoot": str(tmp_path)},
        )
