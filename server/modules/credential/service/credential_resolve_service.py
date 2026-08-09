from fnmatch import fnmatch
from http.cookies import SimpleCookie
from typing import Any
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from modules.credential.dao.credential_dao import CredentialDao
from modules.credential.util.credential_secret_util import decrypt_secret
from utils.log_util import logger


class CredentialResolveService:
    """凭证读取与投影服务；业务只能通过绑定取得 HTTP Header 或 Playwright storageState。"""

    @classmethod
    def resolve_http_headers(cls, db: Session, binding_id: int | str, target_url: str | None = None) -> dict[str, str]:
        """按绑定解析 HTTP 请求头，支持 Header、API Key、Token 及浏览器 Session 投影 Cookie。"""
        binding, credential, secret = cls._resolve_binding_secret(db, binding_id, "http")
        if binding.projection_type not in {"http_header", "http_cookie"}:
            raise ValueError("凭证绑定未配置为 HTTP 投影")
        effective_url = target_url or binding.target_url
        cls._assert_target_allowed(db, binding, credential, effective_url)
        headers = cls._extract_headers(secret)
        if binding.projection_type == "http_cookie":
            cookie_value = cls._build_cookie_header(secret, effective_url)
            if not cookie_value:
                raise ValueError("凭证中没有可投影到目标地址的 Cookie")
            headers["Cookie"] = cookie_value
        logger.info(f"已解析 HTTP 凭证绑定，binding_id={binding.binding_id}，credential_id={credential.credential_id}，target={urlparse(effective_url).netloc if effective_url else '-'}")
        return headers

    @classmethod
    def resolve_playwright_storage_state(cls, db: Session, binding_id: int | str, target_url: str | None = None) -> dict[str, Any]:
        """按绑定读取 Playwright storageState，普通 Web 执行仅读取且不回写。"""
        binding, credential, secret = cls._resolve_binding_secret(db, binding_id, "browser")
        if binding.projection_type != "playwright_storage":
            raise ValueError("凭证绑定未配置为浏览器 storageState 投影")
        cls._assert_target_allowed(db, binding, credential, target_url or binding.target_url)
        storage_state = secret.get("storageState") or secret.get("storage_state")
        if not isinstance(storage_state, dict):
            raise ValueError("浏览器凭证未配置 storageState")
        return storage_state

    @classmethod
    def _resolve_binding_secret(cls, db: Session, binding_id: int | str, channel: str):
        """读取有效绑定与凭证，所有失败均明确抛出而不是退回旧配置。"""
        try:
            parsed_binding_id = int(binding_id)
        except (TypeError, ValueError) as exc:
            raise ValueError("credentialBindingId 必须是整数") from exc
        binding = CredentialDao.get_binding(db, parsed_binding_id)
        if not binding or not binding.enabled:
            raise ValueError("凭证绑定不存在或未启用")
        credential = CredentialDao.get_credential(db, binding.credential_id)
        if not credential or not credential.enabled:
            raise ValueError("绑定的凭证不存在或未启用")
        if credential.expire_time and credential.expire_time <= __import__("datetime").datetime.now():
            raise ValueError("凭证已到期，请先刷新或手工更新")
        try:
            secret = decrypt_secret(credential.secret_cipher_text)
        except ValueError as exc:
            logger.warning(f"凭证解密失败，credential_id={credential.credential_id}，channel={channel}")
            raise ValueError("凭证密文无法解密，请重新配置") from exc
        return binding, credential, secret

    @classmethod
    def _extract_headers(cls, secret: dict[str, Any]) -> dict[str, str]:
        """将不同凭证类型归一为任意 HTTP Header，保留用户配置的 Header 名称。"""
        result = {str(key).strip(): str(value).strip() for key, value in (secret.get("headers") or {}).items() if str(key).strip() and str(value).strip()}
        header_name = str(secret.get("headerName") or secret.get("header_name") or "").strip()
        header_value = str(secret.get("headerValue") or secret.get("header_value") or secret.get("token") or secret.get("apiKey") or "").strip()
        value_prefix = str(secret.get("valuePrefix") or secret.get("value_prefix") or "")
        if value_prefix and secret.get("token") and not header_value.startswith(value_prefix):
            header_value = f"{value_prefix}{header_value}"
        if header_name and header_value:
            result[header_name] = header_value
        return result

    @classmethod
    def _build_cookie_header(cls, secret: dict[str, Any], target_url: str) -> str:
        """合并主 Cookie、结构化 Cookie 和目标域可用的浏览器 Cookie。"""
        cookies = secret.get("cookies")
        pairs_by_name: dict[str, str] = {}
        raw_cookie = str(secret.get("cookie") or secret.get("cookieHeader") or "").strip()
        header_name = str(secret.get("headerName") or secret.get("header_name") or "").strip()
        if not raw_cookie and header_name.lower() == "cookie":
            raw_cookie = str(secret.get("headerValue") or secret.get("header_value") or "").strip()
        if raw_cookie:
            parsed_cookie = SimpleCookie()
            parsed_cookie.load(raw_cookie)
            pairs_by_name.update({name: morsel.value for name, morsel in parsed_cookie.items()})
        if isinstance(cookies, dict):
            pairs_by_name.update({str(name): str(value) for name, value in cookies.items() if str(name).strip()})
            cookies = []
        elif not isinstance(cookies, list):
            storage_state = secret.get("storageState") or secret.get("storage_state") or {}
            cookies = storage_state.get("cookies") if isinstance(storage_state, dict) else []
        parsed = urlparse(target_url)
        host, path, secure = parsed.hostname or "", parsed.path or "/", parsed.scheme == "https"
        for cookie in cookies if isinstance(cookies, list) else []:
            if not isinstance(cookie, dict):
                continue
            cookie_domain = str(cookie.get("domain") or "").lstrip(".").lower()
            cookie_path = str(cookie.get("path") or "/")
            if cookie_domain and not (host.lower() == cookie_domain or host.lower().endswith(f".{cookie_domain}")):
                continue
            if not path.startswith(cookie_path) or (cookie.get("secure") and not secure):
                continue
            name, value = str(cookie.get("name") or "").strip(), str(cookie.get("value") or "")
            if name:
                pairs_by_name[name] = value
        return "; ".join(f"{name}={value}" for name, value in pairs_by_name.items())

    @classmethod
    def _assert_target_allowed(cls, db: Session, binding, credential, target_url: str) -> None:
        """校验绑定或认证配置配置的域名范围，避免凭证被投影到非预期站点。"""
        patterns = binding.target_host_patterns or []
        if not patterns:
            config = CredentialDao.get_auth_config(db, credential.credential_id)
            patterns = config.target_host_patterns if config else []
        if not patterns:
            return
        host = urlparse(target_url).hostname or ""
        if not host or not any(fnmatch(host.lower(), str(pattern).lower()) for pattern in patterns):
            raise ValueError("目标地址不在凭证绑定允许的域名范围内")
