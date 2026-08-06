import base64
import hashlib
import hmac
import struct
import time
from datetime import datetime, timedelta
from http.cookies import SimpleCookie
from typing import Any

import httpx
from sqlalchemy.orm import Session

from modules.credential.dao.credential_dao import CredentialDao
from modules.credential.service.credential_lease_service import CredentialLeaseService
from modules.credential.util.credential_secret_util import decrypt_secret, encrypt_secret, mask_secret
from utils.log_util import logger


class CredentialRefreshService:
    """凭证刷新服务：HTTP 刷新可自动执行，浏览器刷新只记录待人工/Agent 执行状态。"""

    @classmethod
    def refresh_credential(
        cls,
        db: Session,
        credential_id: int,
        expected_revision: int,
        operator: str = "system",
        otp_code: str | None = None,
    ) -> dict[str, Any]:
        """刷新单个凭证；失败不清空旧密文，且使用乐观锁保护新快照。"""
        credential = CredentialDao.get_credential(db, credential_id)
        if not credential or not credential.enabled:
            raise ValueError("凭证不存在或未启用")
        if credential.revision != expected_revision:
            return {"success": False, "message": "凭证版本冲突", "status": "conflict"}
        if credential.auth_mode not in {"http_login", "http_refresh"}:
            return {"success": False, "message": "当前认证方式不能由服务端 HTTP 自动刷新", "status": "manual_required"}
        config = CredentialDao.get_auth_config(db, credential_id)
        url = (config.refresh_url if credential.auth_mode == "http_refresh" else config.login_url) if config else ""
        if not url:
            return {"success": False, "message": "未配置 HTTP 登录或刷新地址", "status": "invalid_config"}
        old_secret = decrypt_secret(credential.secret_cipher_text)
        lease_token = ""
        try:
            try:
                lease_token = CredentialLeaseService.acquire(db, credential_id, "refresh", operator)
            except ValueError as exc:
                CredentialDao.add_operation_log(db, {"credential_id": credential_id, "operation_type": "lease", "status": "conflict", "revision": expected_revision, "message": "凭证已有其他刷新任务持有租约", "operator": operator})
                db.commit()
                return {"success": False, "message": str(exc), "status": "lease_conflict"}
            # 获取租约后再次读取版本，防止等待锁期间其他任务已完成刷新。
            credential = CredentialDao.get_credential(db, credential_id)
            if not credential or credential.revision != expected_revision:
                return {"success": False, "message": "凭证版本冲突", "status": "conflict"}
            old_secret = decrypt_secret(credential.secret_cipher_text)
            request_config = cls._request_config(config, credential.auth_mode)
            response = cls._execute_http_request(
                url,
                request_config,
                old_secret,
                config.otp_type if config else "none",
                otp_code,
            )
            response.raise_for_status()
            new_secret = cls._extract_response_secret(old_secret, response, cls._response_mapping(config, credential.auth_mode))
            if new_secret == old_secret:
                raise ValueError("刷新响应未提取到新凭证，请检查响应字段映射")
            now = datetime.now()
            updated = CredentialDao.update_credential(db, credential_id, {"secret_cipher_text": encrypt_secret(new_secret), "secret_mask": mask_secret(new_secret), "revision": expected_revision + 1, "last_refresh_time": now, "last_refresh_status": "success", "last_refresh_message": "HTTP 刷新成功", "update_by": operator, "update_time": now}, expected_revision)
            if not updated:
                CredentialDao.add_operation_log(db, {"credential_id": credential_id, "operation_type": "refresh", "status": "conflict", "revision": expected_revision, "message": "刷新完成但写回版本冲突，旧快照未覆盖", "operator": operator})
                db.commit()
                return {"success": False, "message": "刷新写回版本冲突", "status": "conflict"}
            CredentialDao.add_operation_log(db, {"credential_id": credential_id, "operation_type": "refresh", "status": "success", "revision": expected_revision + 1, "message": "HTTP 刷新并写回成功", "operator": operator})
            db.commit()
            logger.info(f"凭证 HTTP 刷新成功，credential_id={credential_id}，revision={expected_revision + 1}")
            return {"success": True, "message": "刷新成功", "status": "success"}
        except Exception as exc:
            CredentialDao.update_credential(db, credential_id, {"last_refresh_status": "failed", "last_refresh_message": str(exc)[:500], "update_time": datetime.now()})
            CredentialDao.add_operation_log(db, {"credential_id": credential_id, "operation_type": "refresh", "status": "failed", "revision": expected_revision, "message": str(exc)[:1000], "operator": operator})
            db.commit()
            logger.warning(f"凭证刷新失败且保留旧快照，credential_id={credential_id}，error={exc}")
            return {"success": False, "message": str(exc), "status": "failed"}
        finally:
            if lease_token:
                CredentialLeaseService.release(db, lease_token)
                db.commit()

    @classmethod
    def refresh_due_credentials(cls, db: Session) -> dict[str, int]:
        """定时任务入口：判断是否到期刷新，手工、浏览器和未到期凭证均明确记录跳过原因。"""
        now = datetime.now()
        summary = {"checked": 0, "refreshed": 0, "failed": 0, "skipped": 0}
        for credential in CredentialDao.list_credentials(db):
            summary["checked"] += 1
            interval_due = credential.refresh_interval_sec > 0 and (not credential.last_refresh_time or (now - credential.last_refresh_time).total_seconds() >= credential.refresh_interval_sec)
            expiry_due = bool(credential.expire_time and credential.expire_time <= now + timedelta(minutes=5))
            due = credential.auto_refresh_enabled and (interval_due or expiry_due)
            if not due:
                summary["skipped"] += 1
                continue
            result = cls.refresh_credential(db, credential.credential_id, credential.revision, "credential_scheduler")
            if result["success"]:
                summary["refreshed"] += 1
            elif result["status"] in {"manual_required", "invalid_config", "lease_conflict"}:
                summary["skipped"] += 1
            else:
                summary["failed"] += 1
        logger.info(f"凭证定时刷新完成，checked={summary['checked']}，refreshed={summary['refreshed']}，skipped={summary['skipped']}，failed={summary['failed']}")
        return summary

    @staticmethod
    def _render_request_template(template: Any, secret: dict[str, Any]) -> Any:
        """仅替换形如 ${secret.field} 的请求模板占位符。"""
        if isinstance(template, str):
            value = template
            for key, item in secret.items():
                value = value.replace(f"${{secret.{key}}}", str(item))
            return value
        if isinstance(template, list):
            return [CredentialRefreshService._render_request_template(item, secret) for item in template]
        if isinstance(template, dict):
            return {key: CredentialRefreshService._render_request_template(item, secret) for key, item in template.items()}
        return template

    @classmethod
    def _request_config(cls, config, auth_mode: str) -> dict[str, Any]:
        """读取新旧两种认证配置，旧字段继续作为登录/刷新模板的回退值。"""
        if not config:
            return {}
        is_login = auth_mode == "http_login"
        template = getattr(config, "login_request_template" if is_login else "refresh_request_template", None)
        method = getattr(config, "login_method" if is_login else "refresh_method", None)
        if not template:
            template = config.request_template or {}
        if isinstance(template, dict):
            result = dict(template)
            request_keys = {"method", "headers", "body", "json", "data", "params", "query", "cookies"}
            if not request_keys.intersection(result):
                result = {"body": result}
        else:
            result = {"body": template}
        result.setdefault("method", method or config.request_method or "POST")
        return result

    @classmethod
    def _response_mapping(cls, config, auth_mode: str) -> dict[str, Any]:
        """登录和刷新分别使用响应映射；未迁移数据回退到旧映射。"""
        if not config:
            return {}
        mapping = getattr(config, "login_response_mapping" if auth_mode == "http_login" else "refresh_response_mapping", None)
        return mapping or config.response_mapping or {}

    @classmethod
    def _execute_http_request(
        cls,
        url: str,
        request_config: dict[str, Any],
        secret: dict[str, Any],
        otp_type: str = "none",
        otp_code: str | None = None,
    ):
        """按配置组装请求，并默认携带当前凭证的 Cookie/Header，支持登录和无账号刷新。"""
        if otp_type == "totp":
            if not secret.get("otpSecret"):
                raise ValueError("TOTP 登录缺少已加密保存的 TOTP 密钥")
            secret = {**secret, "otp": cls._generate_totp(str(secret["otpSecret"]))}
        elif otp_type in {"sms", "email", "manual"}:
            if not otp_code:
                raise ValueError("当前 OTP 类型需要本次手工输入验证码或确认值")
            secret = {**secret, "otp": otp_code}
        elif otp_type not in {"none", ""}:
            raise ValueError("不支持的 OTP 类型")
        rendered = cls._render_request_template(request_config, secret)
        method = str(rendered.pop("method", "POST")).upper()
        headers = {str(k): str(v) for k, v in (rendered.pop("headers", {}) or {}).items()}
        headers.update({str(k): str(v) for k, v in (secret.get("headers") or {}).items() if k not in headers})
        header_name = str(secret.get("headerName") or secret.get("header_name") or "").strip()
        header_value = str(secret.get("headerValue") or secret.get("header_value") or secret.get("token") or secret.get("apiKey") or "").strip()
        value_prefix = str(secret.get("valuePrefix") or secret.get("value_prefix") or "")
        if value_prefix and secret.get("token") and not header_value.startswith(value_prefix):
            header_value = f"{value_prefix}{header_value}"
        if header_name and header_value and header_name not in headers:
            headers[header_name] = header_value
        cookies = cls._secret_cookies(secret)
        explicit_cookies = rendered.pop("cookies", None)
        if isinstance(explicit_cookies, dict):
            cookies.update({str(k): str(v) for k, v in explicit_cookies.items()})
        params = rendered.pop("params", rendered.pop("query", None))
        body = rendered.pop("body", rendered.pop("json", None))
        data = rendered.pop("data", None)
        kwargs: dict[str, Any] = {"headers": headers, "cookies": cookies, "timeout": 30}
        if params is not None:
            kwargs["params"] = params
        if data not in (None, {}, "") and method not in {"GET", "HEAD"}:
            kwargs["data"] = data
        elif body is not None and method not in {"GET", "HEAD"}:
            kwargs["json"] = body
        return httpx.request(method, url, **kwargs)

    @staticmethod
    def _generate_totp(secret: str, digits: int = 6, period: int = 30) -> str:
        """使用标准 RFC 6238 算法生成 TOTP，不依赖第三方包。"""
        normalized = secret.replace(" ", "").replace("-", "").upper()
        key = base64.b32decode(normalized + "=" * (-len(normalized) % 8), casefold=True)
        counter = int(time.time() // period)
        digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
        offset = digest[-1] & 0x0F
        code = (struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF) % (10 ** digits)
        return str(code).zfill(digits)

    @staticmethod
    def _secret_cookies(secret: dict[str, Any]) -> dict[str, str]:
        """把 Cookie 字典、Cookie 字符串和 storageState 统一为请求 Cookie。"""
        cookies = secret.get("cookies")
        if isinstance(cookies, dict):
            return {str(k): str(v) for k, v in cookies.items()}
        if isinstance(cookies, list):
            return {str(item.get("name")): str(item.get("value", "")) for item in cookies if isinstance(item, dict) and item.get("name")}
        raw = secret.get("cookie") or secret.get("cookieHeader")
        if raw:
            parsed = SimpleCookie()
            parsed.load(str(raw))
            return {key: morsel.value for key, morsel in parsed.items()}
        storage = secret.get("storageState") or secret.get("storage_state") or {}
        return CredentialRefreshService._secret_cookies(storage) if isinstance(storage, dict) else {}

    @classmethod
    def _extract_response_secret(cls, old_secret: dict[str, Any], response: httpx.Response, mapping: Any) -> dict[str, Any]:
        """从 JSON、响应头和 Set-Cookie 提取新凭证，并保留未变化的旧字段。"""
        result = dict(old_secret)
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        response_cookies = cls._response_cookies(response)
        if isinstance(mapping, dict):
            for secret_key, source in mapping.items():
                value = cls._read_response_value(payload, response, response_cookies, source)
                if value is not None:
                    if str(secret_key) in {"cookies", "headers"} and isinstance(value, dict):
                        merged = cls._secret_cookies(result) if str(secret_key) == "cookies" else dict(result.get("headers") or {})
                        merged.update(value)
                        result[str(secret_key)] = merged
                    else:
                        result[str(secret_key)] = value
        # 未配置映射时，Set-Cookie 仍可按 cookie 字段自动合并，满足手工 Cookie 刷新场景。
        if response_cookies:
            merged = cls._secret_cookies(result)
            merged.update(response_cookies)
            result["cookies"] = merged
            result.pop("cookie", None)
            result.pop("cookieHeader", None)
        return result

    @staticmethod
    def _response_cookies(response: httpx.Response) -> dict[str, str]:
        result: dict[str, str] = {}
        for value in response.headers.get_list("set-cookie"):
            parsed = SimpleCookie()
            parsed.load(value)
            result.update({key: morsel.value for key, morsel in parsed.items()})
        return result

    @classmethod
    def _read_response_value(cls, payload: Any, response: httpx.Response, response_cookies: dict[str, str], source: Any):
        text = str(source or "")
        if text == "cookies" or text == "cookie.*":
            return response_cookies
        if text.startswith("header:"):
            return response.headers.get(text[7:])
        if text.startswith("cookie:"):
            return response_cookies.get(text[7:])
        if text.startswith("json:"):
            text = text[5:]
        value = payload
        for part in text.split(".") if text else []:
            if not isinstance(value, dict) or part not in value:
                return None
            value = value[part]
        return value

    @staticmethod
    def _apply_response_mapping(old_secret: dict[str, Any], payload: Any, mapping: Any) -> dict[str, Any]:
        """按 responseMapping 的 secret字段:响应字段 路径写入新的凭证快照。"""
        result = dict(old_secret)
        if not isinstance(mapping, dict):
            return result
        for secret_key, path in mapping.items():
            value = payload
            for part in str(path).split("."):
                if not isinstance(value, dict) or part not in value:
                    value = None
                    break
                value = value[part]
            if value is not None:
                result[str(secret_key)] = value
        return result
