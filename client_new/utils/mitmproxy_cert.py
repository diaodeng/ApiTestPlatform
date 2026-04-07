import os
import subprocess
import sys
from pathlib import Path


CERT_FILE_NAMES = ("mitmproxy-ca-cert.cer", "mitmproxy-ca-cert.pem")


def resolve_mitmproxy_cert_path(config) -> Path:
    candidates: list[Path] = []

    raw_cert_path = str(getattr(config, "cert_path", "") or "").strip()
    if raw_cert_path:
        cert_path = Path(raw_cert_path).expanduser()
        if cert_path.is_dir():
            candidates.extend(cert_path / name for name in CERT_FILE_NAMES)
        else:
            candidates.append(cert_path)

    config_dir = (
        str(getattr(config, "mitmproxy_config_dir", "") or "").strip()
        or os.path.join(os.path.expanduser("~"), ".mitmproxy")
    )
    config_dir_path = Path(config_dir).expanduser()
    candidates.extend(config_dir_path / name for name in CERT_FILE_NAMES)

    default_dir = Path.home() / ".mitmproxy"
    candidates.extend(default_dir / name for name in CERT_FILE_NAMES)

    seen = set()
    fallback = None
    for candidate in candidates:
        key = str(candidate)
        if key in seen:
            continue
        seen.add(key)
        if fallback is None:
            fallback = candidate
        if candidate.exists():
            return candidate

    return fallback or (default_dir / CERT_FILE_NAMES[0])


def describe_windows_cert_status(config) -> tuple[bool, bool, str, str]:
    cert_path = resolve_mitmproxy_cert_path(config)
    cert_path_text = str(cert_path)

    if not sys.platform.startswith("win"):
        return (
            False,
            False,
            cert_path_text,
            "当前系统不是 Windows，一键导入当前用户根证书功能不可用。",
        )

    if not cert_path.exists():
        return (
            False,
            False,
            cert_path_text,
            f"未找到 mitmproxy CA 证书：{cert_path_text}",
        )

    try:
        result = _run_certutil(["-user", "-store", "Root"])
    except Exception as e:
        return (
            False,
            True,
            cert_path_text,
            f"证书文件已存在，但检查当前用户根证书库失败：{e}",
        )
    if result.returncode != 0:
        detail = _collect_certutil_output(result)
        return (
            False,
            True,
            cert_path_text,
            f"证书文件已存在，但检查当前用户根证书库失败：{detail or 'certutil 返回非 0'}",
        )

    trusted = "mitmproxy" in (result.stdout or "").lower()
    if trusted:
        message = "当前用户已信任 mitmproxy CA，HTTPS 网站可以正常通过浏览器访问。"
    else:
        message = (
            "当前用户尚未信任 mitmproxy CA，浏览器会提示证书不安全，"
            "HTTPS 网站可能无法打开。"
        )

    return trusted, True, cert_path_text, message


def install_mitmproxy_cert_for_current_user(config) -> tuple[bool, str, str]:
    cert_path = resolve_mitmproxy_cert_path(config)
    cert_path_text = str(cert_path)

    if not sys.platform.startswith("win"):
        return False, "当前系统不是 Windows，暂不支持一键导入证书。", cert_path_text

    if not cert_path.exists():
        return False, f"未找到可导入的 mitmproxy CA 证书：{cert_path_text}", cert_path_text

    try:
        result = _run_certutil(["-user", "-addstore", "Root", cert_path_text])
    except Exception as e:
        return False, f"导入 mitmproxy CA 失败：{e}", cert_path_text
    if result.returncode != 0:
        detail = _collect_certutil_output(result)
        return (
            False,
            f"导入 mitmproxy CA 失败：{detail or 'certutil 返回非 0'}",
            cert_path_text,
        )

    return True, f"已导入 mitmproxy CA 到当前用户根证书库：{cert_path_text}", cert_path_text


def _run_certutil(arguments: list[str]):
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return subprocess.run(
        ["certutil", *arguments],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="ignore",
        timeout=20,
        creationflags=creationflags,
    )


def _collect_certutil_output(result) -> str:
    for value in ((result.stderr or "").strip(), (result.stdout or "").strip()):
        if value:
            return value.splitlines()[-1].strip()
    return ""
