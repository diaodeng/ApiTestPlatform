from __future__ import annotations

import io
from ftplib import FTP, all_errors as ftp_errors, error_perm
from pathlib import Path, PurePosixPath
from typing import Any

try:
    import paramiko
except Exception:  # pragma: no cover - optional dependency
    paramiko = None


SUPPORTED_STORAGE_MODES = {"local", "ftp", "sftp"}


def is_sftp_available() -> bool:
    return paramiko is not None


def server_root_dir() -> Path:
    return Path(__file__).resolve().parents[2]


def workspace_root_dir() -> Path:
    return Path(__file__).resolve().parents[3]


def default_local_root_dir() -> Path:
    return server_root_dir() / "case_data" / "image"


def legacy_default_local_root_dir() -> Path:
    return workspace_root_dir() / "case_data" / "image"


def normalize_storage_mode(mode: Any) -> str:
    normalized = str(mode or "local").strip().lower()
    if normalized not in SUPPORTED_STORAGE_MODES:
        return "local"
    return normalized


def resolve_local_root_dir(local_directory: Any = None) -> Path:
    raw_value = str(local_directory or "").strip()
    if not raw_value:
        return default_local_root_dir()
    path = Path(raw_value).expanduser()
    if not path.is_absolute():
        path = server_root_dir() / path
    return path.resolve()


def build_default_storage_config() -> dict[str, Any]:
    return {
        "mode": "local",
        "localDirectory": "",
        "ftp": {
            "host": "",
            "port": 21,
            "username": "",
            "password": "",
            "baseDir": "",
            "passive": True,
            "timeoutSec": 15,
            "encoding": "utf-8",
        },
        "sftp": {
            "host": "",
            "port": 22,
            "username": "",
            "password": "",
            "baseDir": "",
            "timeoutSec": 15,
        },
    }


def normalize_storage_config(raw_config: Any) -> dict[str, Any]:
    defaults = build_default_storage_config()
    config = dict(raw_config or {}) if isinstance(raw_config, dict) else {}
    ftp_config = config.get("ftp") if isinstance(config.get("ftp"), dict) else {}
    sftp_config = config.get("sftp") if isinstance(config.get("sftp"), dict) else {}
    normalized = {
        **defaults,
        **config,
        "mode": normalize_storage_mode(config.get("mode")),
        "ftp": {**defaults["ftp"], **ftp_config},
        "sftp": {**defaults["sftp"], **sftp_config},
    }
    normalized["effectiveLocalDirectory"] = str(resolve_local_root_dir(normalized.get("localDirectory")))
    normalized["sftpAvailable"] = is_sftp_available()
    return normalized


def build_storage_metadata(
    metadata: dict[str, Any] | None,
    *,
    storage_type: str,
    storage_path: str,
) -> dict[str, Any]:
    merged_metadata = dict(metadata or {})
    merged_metadata["_storageType"] = storage_type
    merged_metadata["_storagePath"] = storage_path
    return merged_metadata


def public_asset_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(metadata, dict):
        return {}
    return {key: value for key, value in metadata.items() if not str(key).startswith("_")}


def _ensure_ftp_config(config: dict[str, Any]) -> None:
    if not str(config.get("host") or "").strip():
        raise RuntimeError("FTP 存储未配置 host")
    if not str(config.get("username") or "").strip():
        raise RuntimeError("FTP 存储未配置 username")


def _connect_ftp(config: dict[str, Any]) -> FTP:
    _ensure_ftp_config(config)
    ftp = FTP()
    ftp.encoding = str(config.get("encoding") or "utf-8")
    ftp.connect(
        host=str(config.get("host") or ""),
        port=int(config.get("port") or 21),
        timeout=max(int(config.get("timeoutSec") or 15), 1),
    )
    ftp.login(str(config.get("username") or ""), str(config.get("password") or ""))
    ftp.set_pasv(bool(config.get("passive", True)))
    return ftp


def _ensure_ftp_directory(ftp: FTP, directory: str) -> None:
    normalized_directory = PurePosixPath(directory or "/")
    current_path = ""
    for part in normalized_directory.parts:
        if part in ("", ".", "/"):
            continue
        current_path = f"{current_path}/{part}" if current_path else part
        try:
            ftp.mkd(current_path)
        except error_perm as exc:
            message = str(exc)
            if "File exists" in message or message.startswith("550") or message.startswith("521"):
                continue
            raise


def _store_via_ftp(config: dict[str, Any], storage_path: str, image_bytes: bytes) -> None:
    ftp = _connect_ftp(config)
    try:
        directory = str(PurePosixPath(storage_path).parent)
        if directory and directory not in (".", "/"):
            _ensure_ftp_directory(ftp, directory)
        buffer = io.BytesIO(image_bytes)
        ftp.storbinary(f"STOR {storage_path}", buffer)
    except ftp_errors as exc:
        raise RuntimeError(f"FTP 存储失败: {exc}") from exc
    finally:
        try:
            ftp.quit()
        except Exception:
            try:
                ftp.close()
            except Exception:
                pass


def _read_via_ftp(config: dict[str, Any], storage_path: str) -> bytes:
    ftp = _connect_ftp(config)
    try:
        buffer = io.BytesIO()
        ftp.retrbinary(f"RETR {storage_path}", buffer.write)
        return buffer.getvalue()
    except ftp_errors as exc:
        raise RuntimeError(f"FTP 读取失败: {exc}") from exc
    finally:
        try:
            ftp.quit()
        except Exception:
            try:
                ftp.close()
            except Exception:
                pass


def _ensure_sftp_config(config: dict[str, Any]) -> None:
    if paramiko is None:
        raise RuntimeError("当前服务未安装 paramiko，无法使用 SFTP 存储")
    if not str(config.get("host") or "").strip():
        raise RuntimeError("SFTP 存储未配置 host")
    if not str(config.get("username") or "").strip():
        raise RuntimeError("SFTP 存储未配置 username")


def _connect_sftp(config: dict[str, Any]):
    _ensure_sftp_config(config)
    transport = paramiko.Transport((str(config.get("host") or ""), int(config.get("port") or 22)))
    transport.banner_timeout = max(int(config.get("timeoutSec") or 15), 1)
    transport.connect(
        username=str(config.get("username") or ""),
        password=str(config.get("password") or ""),
    )
    return transport, paramiko.SFTPClient.from_transport(transport)


def _ensure_sftp_directory(sftp, directory: str) -> None:
    normalized_directory = PurePosixPath(directory or "/")
    current_path = PurePosixPath("/")
    for part in normalized_directory.parts:
        if part in ("", ".", "/"):
            continue
        current_path /= part
        try:
            sftp.stat(str(current_path))
        except FileNotFoundError:
            sftp.mkdir(str(current_path))


def _store_via_sftp(config: dict[str, Any], storage_path: str, image_bytes: bytes) -> None:
    transport, sftp = _connect_sftp(config)
    try:
        directory = str(PurePosixPath(storage_path).parent)
        if directory and directory not in (".", "/"):
            _ensure_sftp_directory(sftp, directory)
        with sftp.open(storage_path, "wb") as remote_file:
            remote_file.write(image_bytes)
    except Exception as exc:
        raise RuntimeError(f"SFTP 存储失败: {exc}") from exc
    finally:
        try:
            sftp.close()
        finally:
            transport.close()


def _read_via_sftp(config: dict[str, Any], storage_path: str) -> bytes:
    transport, sftp = _connect_sftp(config)
    try:
        with sftp.open(storage_path, "rb") as remote_file:
            return remote_file.read()
    except Exception as exc:
        raise RuntimeError(f"SFTP 读取失败: {exc}") from exc
    finally:
        try:
            sftp.close()
        finally:
            transport.close()


def build_storage_path(
    storage_config: dict[str, Any],
    *,
    relative_path: PurePosixPath,
) -> tuple[str, str]:
    mode = normalize_storage_mode(storage_config.get("mode"))
    if mode == "local":
        storage_path = str(resolve_local_root_dir(storage_config.get("localDirectory")) / Path(relative_path.as_posix()))
        return mode, storage_path

    if mode == "ftp":
        base_dir = str(storage_config.get("ftp", {}).get("baseDir") or "").strip().replace("\\", "/")
    else:
        base_dir = str(storage_config.get("sftp", {}).get("baseDir") or "").strip().replace("\\", "/")
    remote_path = PurePosixPath(base_dir or "/") / relative_path
    return mode, remote_path.as_posix()


def store_asset_bytes(
    storage_config: dict[str, Any],
    *,
    relative_path: PurePosixPath,
    image_bytes: bytes,
) -> tuple[str, str]:
    mode, storage_path = build_storage_path(storage_config, relative_path=relative_path)
    if mode == "local":
        target_path = Path(storage_path)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(image_bytes)
        return mode, storage_path
    if mode == "ftp":
        _store_via_ftp(_ensure_dict(storage_config.get("ftp")), storage_path, image_bytes)
        return mode, storage_path
    if mode == "sftp":
        _store_via_sftp(_ensure_dict(storage_config.get("sftp")), storage_path, image_bytes)
        return mode, storage_path
    raise RuntimeError(f"不支持的图片存储方式: {mode}")


def read_asset_bytes(
    storage_config: dict[str, Any],
    *,
    storage_type: str,
    storage_path: str,
) -> bytes:
    normalized_type = normalize_storage_mode(storage_type)
    if normalized_type == "local":
        return Path(storage_path).read_bytes()
    if normalized_type == "ftp":
        return _read_via_ftp(_ensure_dict(storage_config.get("ftp")), storage_path)
    if normalized_type == "sftp":
        return _read_via_sftp(_ensure_dict(storage_config.get("sftp")), storage_path)
    raise RuntimeError(f"不支持的图片读取方式: {normalized_type}")


def _ensure_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}
