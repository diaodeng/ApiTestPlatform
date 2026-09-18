import json
from datetime import datetime, timedelta
from typing import Any

import httpx
from sqlalchemy.orm import Session

from modules.credential.dao.credential_dao import CredentialDao
from modules.credential.entity.do.credential_do import AuthCredentialOperationLog
from modules.credential.service.credential_lease_service import CredentialLeaseService
from modules.credential.service.credential_login_chain_service import CredentialLoginChainService
from modules.credential.util.credential_http_util import (
    describe_response_cookies,
    extract_response_secret,
    generate_totp,
    mask_request_for_log,
    mask_response_for_log,
    secret_cookies,
    validate_response_success_assertions,
)
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
        login_steps = list(getattr(config, "login_steps", None) or []) if config else []
        refresh_steps = list(getattr(config, "refresh_steps", None) or []) if config else []
        if credential.auth_mode == "http_refresh" and not refresh_url and not refresh_steps:
            return {"success": False, "message": "未配置 HTTP 刷新地址或多步刷新链", "status": "invalid_config"}
        if credential.auth_mode == "http_login" and not login_url and not login_steps:
            return {"success": False, "message": "未配置 HTTP 登录地址或多步登录链", "status": "invalid_config"}
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
                new_secret = cls._execute_http_login(config, login_steps, old_secret, otp_type, otp_code)
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
            secret = {**secret, "otp": generate_totp(str(secret["otpSecret"]))}
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
        cookies = secret_cookies(secret)
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
        logger.info(f"{action_label}请求：url:{url},method:{method},{json.dumps(mask_request_for_log(kwargs), ensure_ascii=False)}")
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
        logger.info(
            f"{action_label}响应状态：{response.status_code},响应cookies：{describe_response_cookies(response)},"
            f"响应头：{mask_request_for_log({'headers': dict(response.headers)})['headers']},"
            f"响应信息：{mask_response_for_log(response.content)}"
        )
        response.raise_for_status()
        validate_response_success_assertions(response, assertions)
        new_secret, extracted_any = extract_response_secret(secret, response, mapping)
        if not extracted_any:
            if "登录" in action_label:
                raise ValueError("登录响应未提取到新凭证，请在凭证编辑页配置【登录响应映射】。")
            raise ValueError("刷新响应未提取到新凭证，请在凭证编辑页配置【响应提取规则】。若当前凭证主要依赖 Cookie 鉴权，可将凭证类型改为 HTTP Cookie。")
        return new_secret

    @classmethod
    def _execute_http_login(
        cls,
        config,
        login_steps: list[Any],
        secret: dict[str, Any],
        otp_type: str,
        otp_code: str | None,
    ) -> dict[str, Any]:
        """执行 HTTP 登录：配置了多步登录链时走链式执行，否则走单步登录模板。"""
        if login_steps:
            new_secret, _ = CredentialLoginChainService.execute_step_chain(
                secret, login_steps, otp_type, otp_code, action_label="登录链"
            )
            return new_secret
        return cls._execute_http_auth_step(
            str(getattr(config, "login_url", "") or "").strip(),
            cls._request_config(config, "http_login"),
            secret,
            otp_type,
            otp_code,
            cls._response_success_assertions(config, "http_login"),
            cls._response_mapping(config, "http_login"),
            "HTTP 登录",
        )

    @classmethod
    def _execute_http_refresh(
        cls,
        config,
        refresh_steps: list[Any],
        secret: dict[str, Any],
        otp_type: str,
        otp_code: str | None,
    ) -> dict[str, Any]:
        """执行 HTTP 刷新：配置了多步刷新链时走链式执行，否则走单步刷新模板。"""
        if refresh_steps:
            new_secret, _ = CredentialLoginChainService.execute_step_chain(
                secret, refresh_steps, otp_type, otp_code, action_label="刷新链"
            )
            return new_secret
        return cls._execute_http_auth_step(
            str(getattr(config, "refresh_url", "") or "").strip(),
            cls._request_config(config, "http_refresh"),
            secret,
            otp_type,
            otp_code,
            cls._response_success_assertions(config, "http_refresh"),
            cls._response_mapping(config, "http_refresh"),
            "HTTP 刷新",
        )

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
        refresh_steps = list(getattr(config, "refresh_steps", None) or [])
        try:
            return cls._execute_http_refresh(config, refresh_steps, secret, otp_type, otp_code)
        except Exception as refresh_exc:
            login_url = str(getattr(config, "login_url", "") or "").strip()
            login_steps = list(getattr(config, "login_steps", None) or [])
            if not login_url and not login_steps:
                raise
            logger.warning(f"HTTP 刷新失败，准备使用登录兜底后重试，credential_id={credential_id}，error={refresh_exc}")
            try:
                login_secret = cls._execute_http_login(config, login_steps, secret, otp_type, otp_code)
            except Exception as login_exc:
                raise ValueError(f"HTTP 刷新失败且登录兜底失败：原始刷新失败={refresh_exc}；登录失败={login_exc}") from login_exc
            try:
                return cls._execute_http_refresh(config, refresh_steps, login_secret, otp_type, otp_code)
            except Exception as retry_exc:
                raise ValueError(f"HTTP 刷新在登录兜底后仍然失败：原始刷新失败={refresh_exc}；登录后重试失败={retry_exc}") from retry_exc
