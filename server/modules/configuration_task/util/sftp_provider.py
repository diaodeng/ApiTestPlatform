"""SFTP Provider 服务：统一 SFTP 文件读写，供资源上传/下载回传使用。

设计约束：
- 凭证只保存 binding_id；运行时通过统一凭证模块解密，不在资源记录或日志中保存明文；
- 远端定位使用服务端生成的 POSIX object_key，拒绝绝对路径、`..` 路径穿越和反斜杠；
- 所有网络 IO 方法均为同步实现，异步调用方必须通过 run_in_threadpool 包裹；
- 失败时清理远端临时对象，不留下孤儿 `.part`；
- host key 默认 AutoAdd 策略（首期内网场景），后续可扩展 known_hosts 严格校验。
"""

import hashlib
import os
import posixpath
from dataclasses import dataclass
from typing import Any

import paramiko
from loguru import logger

SFTP_CONNECT_TIMEOUT_SECONDS = 15
SFTP_OPERATION_TIMEOUT_SECONDS = 60
SFTP_MAX_OBJECT_KEY_LENGTH = 512


@dataclass
class SftpConfig:
    """一次 SFTP 连接的运行时配置，由凭证绑定解析而来。"""

    host: str
    port: int = 22
    username: str = ""
    password: str = ""
    private_key: str = ""
    private_key_passphrase: str = ""
    base_directory: str = ""


class SftpProviderError(RuntimeError):
    """SFTP 操作失败，message 面向用户脱敏，不包含主机名之外的基础设施细节。"""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def validate_object_key(object_key: str) -> str:
    """校验远端对象 key：必须是从 base_directory 出发的受控相对 POSIX 路径。"""
    normalized = str(object_key or "").strip().replace("\\", "/")
    if not normalized:
        raise SftpProviderError("INVALID_OBJECT_KEY", "objectKey 不能为空")
    if len(normalized) > SFTP_MAX_OBJECT_KEY_LENGTH:
        raise SftpProviderError("INVALID_OBJECT_KEY", "objectKey 超过长度限制")
    if normalized.startswith("/"):
        raise SftpProviderError("INVALID_OBJECT_KEY", "objectKey 不能是绝对路径")
    if "://" in normalized:
        raise SftpProviderError("INVALID_OBJECT_KEY", "objectKey 不能包含协议前缀")
    segments = normalized.split("/")
    for segment in segments:
        if not segment or segment in {".", ".."}:
            raise SftpProviderError("INVALID_OBJECT_KEY", "objectKey 不能包含空段或路径穿越")
        if segment.startswith("~"):
            raise SftpProviderError("INVALID_OBJECT_KEY", "objectKey 不能包含用户目录展开")
    return normalized


def _full_remote_path(config: SftpConfig, object_key: str) -> str:
    """拼接 base_directory 与受控 object_key，返回远端 POSIX 绝对路径。"""
    validated = validate_object_key(object_key)
    base = str(config.base_directory or "").strip().replace("\\", "/").rstrip("/")
    if base.startswith("/"):
        return posixpath.join(base, validated)
    return "/" + posixpath.join(base, validated) if base else "/" + validated


def resolve_sftp_config(secret: dict[str, Any]) -> SftpConfig:
    """从统一凭证 secret 中解析 SFTP 连接配置；缺失必填字段明确报错。"""
    host = str(secret.get("host") or "").strip()
    if not host:
        raise SftpProviderError("SFTP_CONFIG_INVALID", "SFTP 凭证缺少 host")
    try:
        port = int(secret.get("port") or 22)
    except (TypeError, ValueError):
        raise SftpProviderError("SFTP_CONFIG_INVALID", "SFTP 凭证 port 不合法") from None
    return SftpConfig(
        host=host,
        port=port,
        username=str(secret.get("username") or "").strip(),
        password=str(secret.get("password") or ""),
        private_key=str(secret.get("privateKey") or secret.get("private_key") or ""),
        private_key_passphrase=str(secret.get("privateKeyPassphrase") or secret.get("private_key_passphrase") or ""),
        base_directory=str(secret.get("baseDirectory") or secret.get("base_directory") or "").strip(),
    )


class SftpProvider:
    """SFTP 文件读写 Provider；一个实例对应一次连接，用完关闭。"""

    def __init__(self, config: SftpConfig):
        self._config = config
        self._client: paramiko.SSHClient | None = None
        self._sftp: paramiko.SFTPClient | None = None

    # ---------- 连接管理 ----------

    def _ensure_connected(self) -> paramiko.SFTPClient:
        """懒建立 SFTP 连接；凭证认证优先私钥，其次密码。"""
        if self._sftp is not None:
            return self._sftp
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            connect_kwargs: dict[str, Any] = {
                "hostname": self._config.host,
                "port": self._config.port,
                "username": self._config.username,
                "timeout": SFTP_CONNECT_TIMEOUT_SECONDS,
                "allow_agent": False,
                "look_for_keys": False,
            }
            if self._config.private_key:
                key_file = self._write_temp_key()
                try:
                    client.connect(
                        key_filename=key_file,
                        passphrase=self._config.private_key_passphrase or None,
                        **connect_kwargs,
                    )
                finally:
                    try:
                        os.unlink(key_file)
                    except OSError:
                        pass
            else:
                client.connect(password=self._config.password or None, **connect_kwargs)
            sftp = client.open_sftp()
            sftp.get_channel().settimeout(SFTP_OPERATION_TIMEOUT_SECONDS)
        except Exception as exc:
            try:
                client.close()
            except Exception:
                pass
            logger.warning(f"SFTP 连接失败: code=CONNECT_FAILED, error_type={exc.__class__.__name__}")
            raise SftpProviderError("CONNECT_FAILED", "SFTP 连接失败，请检查凭证与网络") from exc
        self._client = client
        self._sftp = sftp
        return self._sftp

    def _write_temp_key(self) -> str:
        """把凭证中的私钥内容写入临时文件供 paramiko 读取；用后即删。"""
        import tempfile

        handle = tempfile.NamedTemporaryFile(mode="w", suffix=".pem", delete=False, encoding="utf-8")
        try:
            normalized = self._config.private_key.replace("\\n", "\n")
            handle.write(normalized)
            handle.flush()
        finally:
            handle.close()
        return handle.name

    def close(self) -> None:
        """关闭 SFTP 与 SSH 连接；幂等。"""
        if self._sftp is not None:
            try:
                self._sftp.close()
            except Exception:
                pass
            self._sftp = None
        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None

    def __enter__(self) -> "SftpProvider":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    # ---------- 文件操作 ----------

    def upload(self, object_key: str, content: bytes) -> dict[str, Any]:
        """上传文件：先写远端 `.part`，完整写入后原子 rename 到正式 key。

        :return: {"objectKey", "size", "sha256"}
        """
        validated = validate_object_key(object_key)
        full_path = _full_remote_path(self._config, validated)
        part_path = f"{full_path}.part"
        sha256 = hashlib.sha256(content).hexdigest()
        try:
            sftp = self._ensure_connected()
            remote_dir = posixpath.dirname(full_path)
            self._mkdirs(remote_dir)
            with sftp.open(part_path, "wb") as handle:
                handle.write(content)
                handle.flush()
            try:
                sftp.rename(part_path, full_path)
            except OSError:
                # 某些 SFTP 服务端 rename 不允许覆盖已存在目标：先删后改名。
                try:
                    sftp.remove(full_path)
                except OSError:
                    pass
                sftp.rename(part_path, full_path)
        except SftpProviderError:
            raise
        except Exception as exc:
            self._cleanup_remote_file(part_path)
            logger.warning(f"SFTP 上传失败: code=UPLOAD_FAILED, error_type={exc.__class__.__name__}")
            raise SftpProviderError("UPLOAD_FAILED", "SFTP 文件上传失败") from exc
        logger.info(f"SFTP 文件上传成功: objectKey={validated}, size={len(content)}")
        return {"objectKey": validated, "size": len(content), "sha256": sha256}

    def download(self, object_key: str) -> bytes:
        """下载文件完整内容；用于资源下载回传。"""
        validated = validate_object_key(object_key)
        full_path = _full_remote_path(self._config, validated)
        try:
            sftp = self._ensure_connected()
            with sftp.open(full_path, "rb") as handle:
                return handle.read()
        except SftpProviderError:
            raise
        except Exception as exc:
            logger.warning(f"SFTP 下载失败: code=DOWNLOAD_FAILED, error_type={exc.__class__.__name__}")
            raise SftpProviderError("DOWNLOAD_FAILED", "SFTP 文件下载失败") from exc

    def stat(self, object_key: str) -> dict[str, Any]:
        """查询远端文件元数据。"""
        validated = validate_object_key(object_key)
        full_path = _full_remote_path(self._config, validated)
        try:
            sftp = self._ensure_connected()
            stat_result = sftp.stat(full_path)
            return {
                "objectKey": validated,
                "size": int(stat_result.st_size),
                "mtime": int(stat_result.st_mtime),
            }
        except SftpProviderError:
            raise
        except Exception as exc:
            logger.warning(f"SFTP stat 失败: code=STAT_FAILED, error_type={exc.__class__.__name__}")
            raise SftpProviderError("STAT_FAILED", "SFTP 文件查询失败") from exc

    def delete(self, object_key: str) -> None:
        """删除远端文件；文件不存在视为已删除（幂等）。"""
        validated = validate_object_key(object_key)
        full_path = _full_remote_path(self._config, validated)
        try:
            sftp = self._ensure_connected()
            try:
                sftp.remove(full_path)
            except OSError:
                return
        except SftpProviderError:
            raise
        except Exception as exc:
            logger.warning(f"SFTP 删除失败: code=DELETE_FAILED, error_type={exc.__class__.__name__}")
            raise SftpProviderError("DELETE_FAILED", "SFTP 文件删除失败") from exc

    # ---------- 内部工具 ----------

    def _mkdirs(self, remote_dir: str) -> None:
        """逐级创建远端目录；已存在时忽略。"""
        if not remote_dir or remote_dir == "/":
            return
        sftp = self._ensure_connected()
        current = ""
        for segment in remote_dir.strip("/").split("/"):
            current = f"{current}/{segment}"
            try:
                sftp.stat(current)
            except OSError:
                try:
                    sftp.mkdir(current)
                except OSError:
                    # 并发创建时目录可能已被建立，重新 stat 确认。
                    sftp.stat(current)

    def _cleanup_remote_file(self, remote_path: str) -> None:
        """清理远端临时文件；失败只记日志。"""
        try:
            if self._sftp is not None:
                self._sftp.remove(remote_path)
        except Exception:
            pass
