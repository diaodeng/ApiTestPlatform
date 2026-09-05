import base64
import hashlib
import hmac
import json
import struct
import time
from datetime import datetime, timedelta
from http.cookies import SimpleCookie
from typing import Any

import httpx
from sqlalchemy.orm import Session

from modules.credential.dao.credential_dao import CredentialDao
from modules.credential.entity.do.credential_do import AuthCredentialOperationLog
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
        refresh_url = str(getattr(config, "refresh_url", "") or "").strip() if config else ""
        login_url = str(getattr(config, "login_url", "") or "").strip() if config else ""
        if credential.auth_mode == "http_refresh" and not refresh_url:
            return {"success": False, "message": "未配置 HTTP 刷新地址", "status": "invalid_config"}
        if credential.auth_mode == "http_login" and not login_url:
            return {"success": False, "message": "未配置 HTTP 登录地址", "status": "invalid_config"}
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
            otp_type = config.otp_type if config else "none"
            if credential.auth_mode == "http_refresh":
                new_secret = cls._execute_http_refresh_with_login_fallback(config, old_secret, otp_type, otp_code, credential_id)
            else:
                new_secret = cls._execute_http_auth_step(
                    login_url,
                    cls._request_config(config, credential.auth_mode),
                    old_secret,
                    otp_type,
                    otp_code,
                    cls._response_success_assertions(config, credential.auth_mode),
                    cls._response_mapping(config, credential.auth_mode),
                    "HTTP 登录",
                )
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
    def refresh_due_credentials(cls, db: Session) -> dict[str, Any]:
        """定时任务入口：判断是否到期刷新，手工、浏览器和未到期凭证均明确记录跳过原因。

        跳过原因细分为 auto_refresh_off（未开启自动刷新）、not_due（未到间隔）、
        manual_required / invalid_config / lease_conflict（配置或并发问题），
        便于从任务日志直接判断凭证为何没有被刷新。
        """
        now = datetime.now()
        summary: dict[str, Any] = {"checked": 0, "refreshed": 0, "failed": 0, "skipped": 0, "skip_reasons": {}}
        for credential in CredentialDao.list_credentials(db):
            summary["checked"] += 1
            if not credential.auto_refresh_enabled:
                summary["skipped"] += 1
                summary["skip_reasons"]["auto_refresh_off"] = summary["skip_reasons"].get("auto_refresh_off", 0) + 1
                cls._log_auto_refresh_off_once(db, credential, now)
                continue
            interval_due = credential.refresh_interval_sec > 0 and (not credential.last_refresh_time or (now - credential.last_refresh_time).total_seconds() >= credential.refresh_interval_sec)
            expiry_due = bool(credential.expire_time and credential.expire_time <= now + timedelta(minutes=5))
            if not (interval_due or expiry_due):
                summary["skipped"] += 1
                summary["skip_reasons"]["not_due"] = summary["skip_reasons"].get("not_due", 0) + 1
                continue
            result = cls.refresh_credential(db, credential.credential_id, credential.revision, "credential_scheduler")
            if result["success"]:
                summary["refreshed"] += 1
            elif result["status"] in {"manual_required", "invalid_config", "lease_conflict"}:
                summary["skipped"] += 1
                summary["skip_reasons"][result["status"]] = summary["skip_reasons"].get(result["status"], 0) + 1
            else:
                summary["failed"] += 1
        logger.info(
            f"凭证定时刷新完成，checked={summary['checked']}，refreshed={summary['refreshed']}，"
            f"skipped={summary['skipped']}，failed={summary['failed']}，跳过原因={summary['skip_reasons']}"
        )
        return summary

    @classmethod
    def _log_auto_refresh_off_once(cls, db: Session, credential, now: datetime) -> None:
        """对开启可刷新模式但未开启自动刷新的凭证，每天最多写一条审计日志提醒。

        仅 http_login / http_refresh 模式适用；手工和浏览器模式本身就不支持自动刷新，不记录。
        """
        if credential.auth_mode not in {"http_login", "http_refresh"}:
            return
        recent = (
            db.query(AuthCredentialOperationLog.operation_id)
            .filter(
                AuthCredentialOperationLog.credential_id == credential.credential_id,
                AuthCredentialOperationLog.operation_type == "auto_refresh_off",
                AuthCredentialOperationLog.create_time >= now - timedelta(days=1),
            )
            .first()
        )
        if recent:
            return
        CredentialDao.add_operation_log(
            db,
            {
                "credential_id": credential.credential_id,
                "operation_type": "auto_refresh_off",
                "status": "skipped",
                "revision": credential.revision,
                "message": "凭证未开启自动刷新，定时任务持续跳过该凭证，请注意会话可能过期",
                "operator": "credential_scheduler",
            },
        )
        db.commit()
        logger.warning(
            f"凭证未开启自动刷新已被定时任务跳过，credential_id={credential.credential_id}，credential_name={credential.credential_name}"
        )

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

    @staticmethod
    def _build_template_secret(secret: dict[str, Any]) -> dict[str, Any]:
        """构造请求模板变量上下文，兼容将 Cookie 保存为 HTTP Header 的凭证。"""
        template_secret = dict(secret)
        primary_cookie = template_secret.get("cookie") or template_secret.get("cookieHeader")
        header_name = str(template_secret.get("headerName") or template_secret.get("header_name") or "").strip()
        header_value = template_secret.get("headerValue") or template_secret.get("header_value")
        if header_value is not None and "headerValue" not in template_secret:
            # 兼容历史字段 header_value，并保持模板变量统一使用 camelCase 的 ${secret.headerValue}。
            template_secret["headerValue"] = header_value
        if not primary_cookie and header_name.lower() == "cookie" and header_value:
            # HTTP Header 类型可将 Cookie 保存在 headerName/headerValue 中；模板仍可统一使用 ${secret.cookie}。
            template_secret["cookie"] = header_value
        return template_secret

    @staticmethod
    def _mask_request_for_log(kwargs: dict[str, Any]) -> dict[str, Any]:
        """脱敏刷新请求日志，避免 Cookie、Token、密码等凭证内容写入日志。"""
        sensitive_names = {
            "authorization", "cookie", "set_cookie", "proxy_authorization", "password",
            "passwd", "secret", "token", "api_key", "apikey",
        }
        sensitive_fragments = ("token", "secret", "password", "cookie", "api_key")

        def mask(value: Any, key: str = "") -> Any:
            normalized_key = key.lower().replace("-", "_")
            if normalized_key in sensitive_names or any(name in normalized_key for name in sensitive_fragments):
                return "******"
            if normalized_key == "headers" and isinstance(value, dict):
                # 请求模板可把任意 secret 字段注入自定义 Header，日志中不再按 Header 名称猜测敏感性。
                return {str(item_key): "******" for item_key in value}
            if isinstance(value, dict):
                return {str(item_key): mask(item_value, str(item_key)) for item_key, item_value in value.items()}
            if isinstance(value, list):
                return [mask(item) for item in value]
            return value

        return mask(kwargs)

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
    def _response_success_assertions(cls, config, auth_mode: str) -> list[Any]:
        """读取登录或刷新接口独立配置的业务成功断言。"""
        if not config:
            return []
        assertions = getattr(config, "login_success_assertions" if auth_mode == "http_login" else "refresh_success_assertions", None)
        return assertions if isinstance(assertions, list) else []

    @classmethod
    def _validate_response_success_assertions(cls, response: httpx.Response, assertions: list[Any]) -> None:
        """校验业务成功断言，任何一条不通过都保留旧凭证并终止写回。"""
        if not assertions:
            return
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        response_cookies = cls._response_cookies(response)
        for index, raw_assertion in enumerate(assertions, start=1):
            assertion = raw_assertion.model_dump() if hasattr(raw_assertion, "model_dump") else raw_assertion
            if not isinstance(assertion, dict):
                raise ValueError(f"响应成功断言第 {index} 条格式错误")
            source = str(assertion.get("source") or "").strip()
            operator = str(assertion.get("operator") or "equals")
            expected = assertion.get("expected")
            actual = response.status_code if source == "status" else cls._read_response_value(payload, response, response_cookies, source)
            if cls._matches_response_assertion(actual, operator, expected):
                continue
            message = str(assertion.get("message") or "").strip()
            detail = message or f"来源 {source} 的实际值 {actual!r} 不满足 {operator} {expected!r}"
            raise ValueError(f"响应成功断言第 {index} 条未通过：{detail}")

    @staticmethod
    def _matches_response_assertion(actual: Any, operator: str, expected: Any) -> bool:
        """使用固定操作符比较响应值，避免在凭证刷新中执行任意代码。"""
        if operator == "exists":
            return actual is not None
        if operator == "not_empty":
            if actual is None:
                return False
            if isinstance(actual, str):
                return bool(actual.strip())
            if isinstance(actual, (dict, list, tuple, set)):
                return bool(actual)
            return True
        if operator == "equals":
            return actual == expected
        if operator == "not_equals":
            return actual != expected
        if operator == "contains":
            if isinstance(actual, str):
                return str(expected) in actual
            if isinstance(actual, (dict, list, tuple, set)):
                return expected in actual
            return False
        if operator == "in":
            return isinstance(expected, list) and actual in expected
        raise ValueError(f"不支持的响应成功断言操作符: {operator}")

    @classmethod
    def _execute_http_request(
        cls,
        url: str,
        request_config: dict[str, Any],
        secret: dict[str, Any],
        otp_type: str = "none",
        otp_code: str | None = None,
        action_label: str = "凭证刷新",
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
        rendered = cls._render_request_template(request_config, cls._build_template_secret(secret))
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
        logger.info(f"{action_label}请求：url:{url},method:{method},{json.dumps(cls._mask_request_for_log(kwargs), ensure_ascii=False)}")
        return httpx.request(method, url, **kwargs)

    @classmethod
    def _execute_http_auth_step(
        cls,
        url: str,
        request_config: dict[str, Any],
        secret: dict[str, Any],
        otp_type: str,
        otp_code: str | None,
        assertions: list[Any],
        mapping: Any,
        action_label: str,
    ) -> dict[str, Any]:
        """执行单次 HTTP 登录或刷新，并在成功后提取新凭证。"""
        response = cls._execute_http_request(url, request_config, secret, otp_type, otp_code, action_label)
        logger.info(f"{action_label}响应状态：{response.status_code},响应cookies：{response.cookies},响应头：{response.headers},响应信息：{response.content.decode('utf-8')}")
        response.raise_for_status()
        cls._validate_response_success_assertions(response, assertions)
        new_secret, extracted_any = cls._extract_response_secret(secret, response, mapping)
        if not extracted_any:
            if "登录" in action_label:
                raise ValueError("登录响应未提取到新凭证，请在凭证编辑页配置【登录响应映射】。")
            raise ValueError("刷新响应未提取到新凭证，请在凭证编辑页配置【响应提取规则】。若当前凭证主要依赖 Cookie 鉴权，可将凭证类型改为 HTTP Cookie。")
        return new_secret

    @classmethod
    def _execute_http_refresh_with_login_fallback(
        cls,
        config,
        secret: dict[str, Any],
        otp_type: str,
        otp_code: str | None,
        credential_id: int,
    ) -> dict[str, Any]:
        """先刷新，失败后自动登录兜底，再用登录后的新凭证重试刷新。"""
        refresh_request_config = cls._request_config(config, "http_refresh")
        refresh_assertions = cls._response_success_assertions(config, "http_refresh")
        refresh_mapping = cls._response_mapping(config, "http_refresh")
        try:
            return cls._execute_http_auth_step(
                config.refresh_url,
                refresh_request_config,
                secret,
                otp_type,
                otp_code,
                refresh_assertions,
                refresh_mapping,
                "HTTP 刷新",
            )
        except Exception as refresh_exc:
            login_url = str(getattr(config, "login_url", "") or "").strip()
            if not login_url:
                raise
            logger.warning(f"HTTP 刷新失败，准备使用登录兜底后重试，credential_id={credential_id}，error={refresh_exc}")
            try:
                login_secret = cls._execute_http_auth_step(
                    login_url,
                    cls._request_config(config, "http_login"),
                    secret,
                    otp_type,
                    otp_code,
                    cls._response_success_assertions(config, "http_login"),
                    cls._response_mapping(config, "http_login"),
                    "HTTP 登录",
                )
            except Exception as login_exc:
                raise ValueError(f"HTTP 刷新失败且登录兜底失败：原始刷新失败={refresh_exc}；登录失败={login_exc}") from login_exc
            try:
                return cls._execute_http_auth_step(
                    config.refresh_url,
                    refresh_request_config,
                    login_secret,
                    otp_type,
                    otp_code,
                    refresh_assertions,
                    refresh_mapping,
                    "HTTP 刷新",
                )
            except Exception as retry_exc:
                raise ValueError(f"HTTP 刷新在登录兜底后仍然失败：原始刷新失败={refresh_exc}；登录后重试失败={retry_exc}") from retry_exc

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
        """合并结构化 Cookie、主 Cookie 字符串和 storageState 为请求 Cookie。"""
        result: dict[str, str] = {}
        storage = secret.get("storageState") or secret.get("storage_state")
        if isinstance(storage, dict) and storage:
            result.update(CredentialRefreshService._secret_cookies(storage))
        raw = secret.get("cookie") or secret.get("cookieHeader")
        if raw:
            parsed = SimpleCookie()
            parsed.load(str(raw))
            result.update({key: morsel.value for key, morsel in parsed.items()})
        cookies = secret.get("cookies")
        if isinstance(cookies, dict):
            result.update({str(key): str(value) for key, value in cookies.items() if str(key).strip()})
        elif isinstance(cookies, list):
            result.update({str(item.get("name")): str(item.get("value", "")) for item in cookies if isinstance(item, dict) and item.get("name")})
        return result

    @classmethod
    def _extract_response_secret(cls, old_secret: dict[str, Any], response: httpx.Response, mapping: Any) -> tuple[dict[str, Any], bool]:
        """从 JSON、响应头和 Set-Cookie 提取新凭证，并保留未变化的旧字段。
        返回值: (新的 secret 字典, 是否实际提取到了新内容)。
        """
        result = dict(old_secret)
        extracted_any = False
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        response_cookies = cls._response_cookies(response)
        if isinstance(mapping, dict):
            for secret_key, source in mapping.items():
                value = cls._read_response_value(payload, response, response_cookies, source)
                if value is not None:
                    cls._write_response_value(result, str(secret_key), value)
                    extracted_any = True
        return result, extracted_any

    @classmethod
    def _write_response_value(cls, secret: dict[str, Any], target: str, value: Any) -> None:
        """按显式目标路径写入提取值，禁止未配置规则时隐式更新 Cookie。"""
        normalized_target = target.strip()
        if normalized_target == "header.cookie":
            cls._assert_cookie_header(secret)
            if isinstance(value, (dict, list)):
                raise ValueError("header.cookie 只能写入单个 Cookie Header 字符串")
            # 覆盖整个 Cookie Header，用户需明确接受未包含的 Cookie 会丢失。
            secret["headerValue"] = str(value)
            return

        if normalized_target.startswith("header.cookie."):
            cookie_name = normalized_target[len("header.cookie."):].strip()
            if not cookie_name:
                raise ValueError("header.cookie.<名称> 必须填写要更新的 Cookie 名称")
            cls._assert_cookie_header(secret)
            if isinstance(value, (dict, list)):
                raise ValueError("header.cookie.<名称> 只能写入单个 Cookie 值")
            existing = str(secret.get("headerValue") or secret.get("header_value") or "")
            # 同名项替换；原 Header 中没有该项时按配置约定静默追加。
            secret["headerValue"] = cls._merge_cookies_into_string(existing, {cookie_name: str(value)})
            return

        if normalized_target == "cookies":
            cls._assert_structured_cookie_target_allowed(secret)
            if not isinstance(value, dict):
                raise ValueError("目标字段 cookies 只能接收对象值，例如来源 cookies 或 JSON 对象")
            # 显式配置 cookies ← cookies 表示以本次响应 Cookie 集合整体覆盖旧集合。
            secret["cookies"] = {str(key): str(item) for key, item in value.items() if str(key).strip()}
            return

        if normalized_target.startswith("cookies."):
            cls._assert_structured_cookie_target_allowed(secret)
            cookie_name = normalized_target[len("cookies."):].strip()
            if not cookie_name:
                raise ValueError("cookies.<名称> 必须填写要更新的 Cookie 名称")
            if isinstance(value, (dict, list)):
                raise ValueError("cookies.<名称> 只能写入单个 Cookie 值")
            cookies = cls._secret_cookies(secret)
            cookies[cookie_name] = str(value)
            secret["cookies"] = cookies
            return

        # 普通字段仍按显式字段名整体写入，例如 token、headerValue、headers。
        secret[normalized_target] = value

    @staticmethod
    def _assert_cookie_header(secret: dict[str, Any]) -> None:
        """确认 header.cookie 目标仅用于 Header 名称为 Cookie 的凭证。"""
        header_name = str(secret.get("headerName") or secret.get("header_name") or "").strip()
        if header_name.lower() != "cookie":
            raise ValueError("header.cookie 目标仅适用于 Header 名称为 Cookie 的凭证")

    @staticmethod
    def _assert_structured_cookie_target_allowed(secret: dict[str, Any]) -> None:
        """避免主 Cookie Header 与结构化 Cookie 同时写回，防止下次编辑出现冲突。"""
        header_name = str(secret.get("headerName") or secret.get("header_name") or "").strip()
        if header_name.lower() == "cookie":
            raise ValueError(
                "主 Header 为 Cookie 时不能写入 cookies 或 cookies.<名称>；"
                "请使用 header.cookie 或 header.cookie.<名称> 更新 Cookie Header"
            )

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
            # 未返回标准 Set-Cookie 时不把空对象视作已提取，避免整组覆盖误清空旧 Cookie。
            return response_cookies or None
        if text.startswith("header:"):
            header_name = text[7:].strip()
            raw_set_cookie_index = None
            if header_name.lower().startswith("set-cookie[") and header_name.endswith("]"):
                raw_set_cookie_index = header_name[len("set-cookie["):-1]
                if not raw_set_cookie_index.isdigit() or int(raw_set_cookie_index) < 1:
                    raise ValueError("header:set-cookie[n] 中 n 必须是从 1 开始的响应 Set-Cookie 序号")
                header_name = "set-cookie"
            if header_name.lower() == "set-cookie":
                # Set-Cookie 允许出现多次，不能将多条值拼接后误写入单个 Cookie 字段。
                values = [value.strip() for value in response.headers.get_list("set-cookie") if value.strip()]
                if raw_set_cookie_index is not None:
                    index = int(raw_set_cookie_index) - 1
                    if index >= len(values):
                        raise ValueError(f"响应 Set-Cookie 序号超出范围，当前只有 {len(values)} 条")
                    return values[index]
                if len(values) > 1:
                    raise ValueError(
                        "响应包含多个 Set-Cookie，header:set-cookie 只能读取单条原始值；"
                        "请使用 header:set-cookie[n] 明确选择序号，或使用 cookie:<名称> 提取标准 Cookie"
                    )
                return values[0] if values else None
            return response.headers.get(header_name)
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
    def _merge_cookies_into_string(existing: str, new_cookies: dict[str, str]) -> str:
        """将 Set-Cookie 键值对合并到现有 cookie 字符串中，同名 key 替换值，新 key 追加到末尾。"""
        if not new_cookies:
            return existing
        # 解析现有 cookie 字符串，保持顺序
        pairs: list[tuple[str, str]] = []
        seen_keys: set[str] = set()
        for part in existing.split(";"):
            part = part.strip()
            if not part or "=" not in part:
                continue
            key, _, value = part.partition("=")
            key = key.strip()
            if key and key not in seen_keys:
                pairs.append((key, value.strip()))
                seen_keys.add(key)
        # 合并新 cookie：同名替换，新 key 追加
        for key, value in new_cookies.items():
            key = key.strip()
            if not key:
                continue
            if key in seen_keys:
                for i, (k, _) in enumerate(pairs):
                    if k == key:
                        pairs[i] = (key, value.strip())
                        break
            else:
                pairs.append((key, value.strip()))
                seen_keys.add(key)
        return "; ".join(f"{k}={v}" for k, v in pairs)

