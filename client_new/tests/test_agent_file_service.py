"""Agent 本地资源 manifest 与分片发布协议测试。"""

import base64
import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.agent_file_service import AgentFileService
from services.agent_resource_storage import ResourceManifest, ResourceManifestStore, utc_now_iso


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _begin(service: AgentFileService, data: bytes, *, resource_id: str = "res-test") -> dict:
    return service.handle_command(
        {
            "requestType": 7,
            "command": "file_publish_begin",
            "resource_id": resource_id,
            "transfer_id": "transfer-test",
            "original_file_name": "demo.txt",
            "mime_type": "text/plain",
            "size": len(data),
            "sha256": _digest(data),
        }
    )


def _chunk(service: AgentFileService, data: bytes, index: int, offset: int) -> dict:
    return service.handle_command(
        {
            "requestType": 7,
            "command": "file_chunk",
            "transfer_id": "transfer-test",
            "index": index,
            "offset": offset,
            "data": base64.b64encode(data).decode("ascii"),
            "chunk_sha256": _digest(data),
        }
    )


def test_manifest_atomic_round_trip(tmp_path: Path):
    store = ResourceManifestStore(tmp_path)
    item = ResourceManifest(
        resource_id="res-1",
        locator="resources/res-1",
        original_file_name="a.txt",
        mime_type="text/plain",
        size=3,
        sha256=_digest(b"abc"),
        version=1,
        created=utc_now_iso(),
        expires=utc_now_iso(),
        last_used=utc_now_iso(),
    )
    store.save(item)
    assert store.get("res-1") == item
    document = json.loads(store.manifest_path.read_text(encoding="utf-8"))
    assert document["resources"]["res-1"]["locator"] == "resources/res-1"
    assert not list(store.data_root.glob(".resource_manifest.*.tmp"))


def test_manifest_rejects_path_escape_and_symlink(tmp_path: Path):
    store = ResourceManifestStore(tmp_path)
    with pytest.raises(ValueError):
        store.resolve_locator("../outside")
    with pytest.raises(ValueError):
        store.resolve_locator("C:/outside")
    escaped = tmp_path / "outside"
    escaped.mkdir()
    link = store.resources_root / "res-link"
    try:
        link.symlink_to(escaped, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("当前环境不支持创建符号链接")
    with pytest.raises(ValueError):
        store.resolve_locator("resources/res-link", "res-link")


def test_begin_supports_zero_size_file(tmp_path: Path):
    service = AgentFileService(root=tmp_path)
    assert _begin(service, b"")["success"]
    committed = service.handle_command(
        {"requestType": 7, "command": "file_publish_commit", "transfer_id": "transfer-test"}
    )
    assert committed["success"]
    assert (tmp_path / "storage" / "resources" / "res-test").read_bytes() == b""


def test_publish_supports_out_of_order_and_duplicate_chunk(tmp_path: Path):
    payload = b"abcdefgh"
    service = AgentFileService(root=tmp_path, max_chunk_size=4)
    assert _begin(service, payload)["success"]
    assert _chunk(service, payload[4:], 1, 4)["success"]
    assert _chunk(service, payload[:4], 0, 0)["success"]
    duplicate = _chunk(service, payload[:4], 0, 0)
    assert duplicate["success"] and duplicate["data"]["idempotent"] is True
    committed = service.handle_command(
        {"requestType": 7, "command": "file_publish_commit", "transfer_id": "transfer-test"}
    )
    assert committed["success"]
    assert (tmp_path / "storage" / "resources" / "res-test").read_bytes() == payload


def test_chunk_hash_mismatch_and_commit_incomplete(tmp_path: Path):
    payload = b"abcd"
    service = AgentFileService(root=tmp_path, max_chunk_size=4)
    assert _begin(service, payload)["success"]
    wrong = service.handle_command(
        {
            "requestType": 7,
            "command": "file_chunk",
            "transfer_id": "transfer-test",
            "index": 0,
            "offset": 0,
            "data": base64.b64encode(payload).decode("ascii"),
            "chunk_sha256": _digest(b"nope"),
        }
    )
    assert not wrong["success"] and wrong["error_code"] == "CHUNK_CHECKSUM_MISMATCH"
    incomplete = service.handle_command(
        {"requestType": 7, "command": "file_publish_commit", "transfer_id": "transfer-test"}
    )
    assert not incomplete["success"] and incomplete["error_code"] == "INCOMPLETE_FILE"


def test_stat_returns_metadata_without_file_content(tmp_path: Path):
    payload = b"stat-content"
    service = AgentFileService(root=tmp_path)
    assert _begin(service, payload)["success"]
    assert _chunk(service, payload, 0, 0)["success"]
    assert service.handle_command({"requestType": 7, "command": "file_publish_commit", "transfer_id": "transfer-test"})["success"]
    result = service.handle_command({"requestType": 7, "command": "file_stat", "resource_id": "res-test"})
    assert result["success"]
    assert result["data"]["size"] == len(payload)
    assert "content" not in result["data"]
    assert "absolute" not in json.dumps(result, ensure_ascii=False).lower()
