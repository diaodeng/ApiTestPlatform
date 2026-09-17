import json
import time
from typing import Any

import httpx
from sqlalchemy.orm import Session

from modules.credential.dao.credential_dao import CredentialDao
from modules.credential.entity.vo.credential_vo import CredentialLoginStepModel, validate_login_step_references
from modules.credential.util.credential_http_util import (
    extract_response_secret,
    generate_totp,
    mask_request_for_log,
    read_response_value,
    response_cookies,
    secret_cookies,
    validate_response_success_assertions,
)
from modules.credential.util.credential_secret_util import decrypt_secret
from utils.log_util import logger


class CredentialLoginChainService:
    """多步 HTTP 登录链执行服务。

    按配置顺序执行多个 HTTP 登录步骤（例如：账号密码登录 -> 提取一次性 ticket -> TOTP 验证 -> 提取 Set-Cookie）。
    整条链共用一个 httpx.Client，步骤间的会话 Cookie（如 WAF 下发的 acw_tc）自动延续；
    标记 persist_outputs 的步骤输出写回凭证密文，其余输出仅作为临时步骤变量供后续步骤引用，链结束即丢弃。
    任何一步失败即终止整链，由调用方保证旧凭证快照不被覆盖。
    """

    @classmethod
    def execute_login_chain(
        cls,
        secret: dict[str, Any],
        login_steps: list[Any],
        otp_type: str = "none",
        otp_code: str | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """执行多步登录链。

        参数 secret 为解密后的凭证字段；login_steps 为认证配置中的步骤列表（dict 或已校验模型）。
        返回 (提取到的新凭证 secret, 逐步执行明细)；全部步骤成功且至少一个步骤写回凭证才算成功，否则抛出异常。
        transport 参数仅供单测注入 httpx.MockTransport，业务调用不传。
        """
        steps = [cls._normalize_step(item) for item in login_steps]
        if not steps:
            raise ValueError("未配置多步登录链")
        validate_login_step_references(steps)
        step_variables: dict[str, str] = {}
        new_secret = dict(secret)
        persisted_any = False
        details: list[dict[str, Any]] = []
        # 整条链共用一个 Client：步骤间 Set-Cookie 自动进入 Cookie Jar 并在后续请求中携带。
        with httpx.Client(cookies=secret_cookies(secret), timeout=30, transport=transport) as client:
            for index, step in enumerate(steps, start=1):
                started_at = time.monotonic()
                working_secret = cls._prepare_secret_with_otp(secret, otp_type, otp_code)
                response = cls._execute_step_request(client, index, step, working_secret, step_variables)
                logger.info(
                    f"登录链第{index}步响应：status={response.status_code},cookies={response.cookies},"
                    f"响应信息：{response.content.decode('utf-8', errors='replace')}"
                )
                cls._validate_step_assertions(index, step, response)
                if step.persist_outputs:
                    # persist_outputs 步骤按响应映射规则写回凭证，来源语法与单步登录的响应映射完全一致。
                    new_secret, extracted_any = extract_response_secret(new_secret, response, step.outputs)
                    if extracted_any:
                        persisted_any = True
                    output_names = list(step.outputs.keys())
                else:
                    output_names = cls._extract_step_variables(index, step, response, step_variables)
                details.append(
                    {
                        "index": index,
                        "name": step.name or f"步骤{index}",
                        "url": step.url,
                        "method": step.method,
                        "status": response.status_code,
                        "elapsedMs": int((time.monotonic() - started_at) * 1000),
                        "outputs": output_names,
                        "persistOutputs": step.persist_outputs,
                    }
                )
        if not persisted_any:
            raise ValueError(
                "登录链执行成功但没有任何步骤提取到新凭证，请在最终步骤配置输出并开启【写回凭证】(persistOutputs)"
            )
        return new_secret, details

    @classmethod
    def test_login_flow(cls, db: Session, credential_id: int, otp_code: str | None = None) -> dict[str, Any]:
        """测试指定凭证的多步登录链；只执行认证链并返回逐步明细，不写回凭证密文。"""
        credential = CredentialDao.get_credential(db, credential_id)
        if not credential:
            raise ValueError("凭证不存在")
        if not credential.enabled:
            raise ValueError("凭证未启用")
        if credential.auth_mode != "http_login":
            raise ValueError("仅 HTTP 自动登录模式的凭证支持多步登录链测试")
        config = CredentialDao.get_auth_config(db, credential_id)
        login_steps = list(getattr(config, "login_steps", None) or []) if config else []
        if not login_steps:
            raise ValueError("当前凭证未配置多步登录链，请先在登录配置中添加认证步骤")
        old_secret = decrypt_secret(credential.secret_cipher_text)
        otp_type = config.otp_type if config else "none"
        new_secret, details = cls.execute_login_chain(old_secret, login_steps, otp_type, otp_code)
        updated_fields = [key for key in new_secret if new_secret.get(key) != old_secret.get(key)]
        logger.info(f"凭证多步登录链测试成功且未写回凭证，credential_id={credential_id}，steps={len(details)}")
        return {
            "success": True,
            "message": "登录流程测试成功，本次测试未写回凭证",
            "steps": details,
            "updatedFields": updated_fields,
        }

    @staticmethod
    def _normalize_step(item: Any) -> CredentialLoginStepModel:
        """把配置中的步骤 dict 归一化为已校验模型；非法配置在此处即报错。"""
        if isinstance(item, CredentialLoginStepModel):
            return item
        return CredentialLoginStepModel.model_validate(item)

    @staticmethod
    def _prepare_secret_with_otp(secret: dict[str, Any], otp_type: str, otp_code: str | None) -> dict[str, Any]:
        """按 OTP 类型准备本步骤的模板变量上下文；TOTP 在每个步骤执行前重新生成，避免长链跨窗口。"""
        working = dict(secret)
        if otp_type == "totp":
            if not working.get("otpSecret"):
                raise ValueError("TOTP 登录缺少已加密保存的 TOTP 密钥")
            working["otp"] = generate_totp(str(working["otpSecret"]))
        elif otp_type in {"sms", "email", "manual"}:
            if not otp_code:
                raise ValueError("当前 OTP 类型需要本次手工输入验证码或确认值")
            working["otp"] = otp_code
        elif otp_type not in {"none", ""}:
            raise ValueError("不支持的 OTP 类型")
        return working

    @classmethod
    def _execute_step_request(
        cls,
        client: httpx.Client,
        index: int,
        step: CredentialLoginStepModel,
        secret: dict[str, Any],
        step_variables: dict[str, str],
    ) -> httpx.Response:
        """渲染并执行单个登录步骤请求；请求日志统一脱敏。"""
        url = cls._render_template(step.url, secret, step_variables)
        headers = {str(k): cls._render_template(str(v), secret, step_variables) for k, v in step.headers.items()}
        kwargs: dict[str, Any] = {"headers": headers}
        if step.method not in {"GET", "HEAD"} and step.body_type != "none":
            if step.body_type == "form":
                body = cls._render_template(step.body or {}, secret, step_variables)
                if not isinstance(body, dict):
                    raise ValueError(f"登录链第{index}步的 form 请求体必须是对象")
                kwargs["data"] = body
            elif step.body_type == "json":
                kwargs["json"] = cls._render_template(step.body, secret, step_variables)
            elif step.body_type == "multipart":
                body = cls._render_template(step.body or {}, secret, step_variables)
                if not isinstance(body, dict):
                    raise ValueError(f"登录链第{index}步的 multipart 请求体必须是对象")
                # multipart 由 httpx 自动生成 boundary，忽略用户手填的 Content-Type 以免 boundary 不一致。
                headers.pop("Content-Type", None)
                headers.pop("content-type", None)
                kwargs["files"] = {str(key): (None, str(value)) for key, value in body.items()}
        masked_kwargs = json.dumps(mask_request_for_log(kwargs), ensure_ascii=False)
        logger.info(f"登录链第{index}步请求：url:{url},method:{step.method},{masked_kwargs}")
        return client.request(step.method, url, **kwargs)

    @staticmethod
    def _validate_step_assertions(index: int, step: CredentialLoginStepModel, response: httpx.Response) -> None:
        """校验单步 HTTP 状态与业务成功断言；失败时带上步骤定位信息，便于从日志直接判断是哪一步出错。"""
        step_label = step.name or step.url
        if response.status_code < 200 or response.status_code >= 300:
            raise ValueError(f"登录链第{index}步（{step_label}）失败：HTTP {response.status_code}")
        try:
            validate_response_success_assertions(response, step.success_assertions)
        except ValueError as exc:
            raise ValueError(f"登录链第{index}步（{step_label}）失败：{exc}") from exc

    @staticmethod
    def _extract_step_variables(
        index: int,
        step: CredentialLoginStepModel,
        response: httpx.Response,
        step_variables: dict[str, str],
    ) -> list[str]:
        """提取临时步骤变量（如 ticket）；提取失败立即终止整链，避免后续步骤带着空值继续请求。"""
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        cookies = response_cookies(response)
        extracted_names: list[str] = []
        for variable_name, source in step.outputs.items():
            value = read_response_value(payload, response, cookies, source)
            if value is None:
                raise ValueError(
                    f"登录链第{index}步（{step.name or step.url}）未能提取变量 {variable_name}"
                    f"（来源 {source}），响应中可能没有该字段"
                )
            step_variables[f"step.{index}.{variable_name}"] = str(value)
            extracted_names.append(variable_name)
        return extracted_names

    @classmethod
    def _render_template(cls, template: Any, secret: dict[str, Any], step_variables: dict[str, str]) -> Any:
        """渲染步骤模板，支持 ${secret.字段} 与 ${step.N.变量} 两类扁平占位符。"""
        if isinstance(template, str):
            value = template
            for key, item in secret.items():
                value = value.replace("${secret." + key + "}", str(item))
            for key, item in step_variables.items():
                value = value.replace("${" + key + "}", str(item))
            return value
        if isinstance(template, list):
            return [cls._render_template(item, secret, step_variables) for item in template]
        if isinstance(template, dict):
            return {key: cls._render_template(item, secret, step_variables) for key, item in template.items()}
        return template
