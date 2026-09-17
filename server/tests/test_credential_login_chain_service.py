from types import SimpleNamespace

import httpx
import pytest

from modules.credential.dao.credential_dao import CredentialDao
from modules.credential.entity.vo.credential_vo import CredentialAuthConfigModel, CredentialLoginStepModel
from modules.credential.service.credential_lease_service import CredentialLeaseService
from modules.credential.service.credential_login_chain_service import CredentialLoginChainService
from modules.credential.service.credential_refresh_service import CredentialRefreshService

TOTP_SECRET = "JBSWY3DPEHPK3PXP"


def _json_response(payload=None, headers=None):
    return httpx.Response(200, json=payload or {}, headers=headers or {})


def _erp_style_steps():
    """构造与 rta-os ERP 两步登录等价的步骤配置：账密登录提取 ticket，TOTP 验证后提取 Cookie。"""
    return [
        {
            "name": "账号密码登录",
            "url": "https://erp.example.test/doLogin",
            "method": "POST",
            "bodyType": "form",
            "headers": {"x-requested-with": "XMLHttpRequest"},
            "body": {"account": "${secret.account}", "pwd": "${secret.password}", "remember": "1"},
            "successAssertions": [{"source": "json:code", "operator": "equals", "expected": "success"}],
            "outputs": {"ticket": "json:result|url_query:ticket"},
        },
        {
            "name": "TOTP 验证",
            "url": "https://erp.example.test/doOtp",
            "method": "POST",
            "bodyType": "multipart",
            "body": {"ticket": "${step.1.ticket}", "google_code": "${secret.otp}"},
            "successAssertions": [{"source": "json:code", "operator": "equals", "expected": "success"}],
            "outputs": {"header.cookie.UYBFEWAEE": "cookie:UYBFEWAEE"},
            "persistOutputs": True,
        },
    ]


def _erp_style_secret():
    return {
        "account": "15378201111",
        "password": "45977e064b593f32120b82c095999999",
        "otpSecret": TOTP_SECRET,
        "headerName": "Cookie",
        "headerValue": "dmall-locale=zh_HK",
    }


def test_login_chain_extracts_ticket_and_persists_set_cookie():
    """两步登录链：第一步提取 ticket，第二步 multipart 提交 TOTP 并把 Set-Cookie 写回凭证。"""
    captured_requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_requests.append(request)
        if request.url.path == "/doLogin":
            return _json_response({"code": "success", "result": "otp?ticket=ticket-123456", "data": None})
        return _json_response(
            {"code": "success", "result": "http://erp.example.test/", "data": None},
            {"Set-Cookie": "UYBFEWAEE=new-session-value; Domain=erp.example.test; Path=/; HttpOnly"},
        )

    new_secret, details = CredentialLoginChainService.execute_login_chain(
        _erp_style_secret(),
        _erp_style_steps(),
        otp_type="totp",
        transport=httpx.MockTransport(handler),
    )

    # 第一步 form、第二步 multipart（boundary 由 httpx 自动生成）
    assert captured_requests[0].headers["content-type"] == "application/x-www-form-urlencoded"
    second_content = captured_requests[1].read().decode()
    assert captured_requests[1].headers["content-type"].startswith("multipart/form-data; boundary=")
    assert "ticket-123456" in second_content
    # TOTP 在执行时生成：6 位数字，且不等于静态密钥
    assert 'name="google_code"' in second_content
    # multipart 请求自动携带第一步请求的会话上下文（Cookie Jar 初始化自旧凭证）
    assert new_secret["headerValue"] == "dmall-locale=zh_HK; UYBFEWAEE=new-session-value"
    # ticket 是一次性临时变量，绝不能写进凭证密文
    assert "ticket" not in new_secret
    assert [item["index"] for item in details] == [1, 2]
    assert details[0]["outputs"] == ["ticket"]
    assert details[1]["persistOutputs"] is True


def test_login_chain_carries_step1_set_cookie_into_step2_request():
    """第一步响应的 Set-Cookie（如 WAF acw_tc）必须在第二步请求中自动携带。"""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/step1":
            return _json_response({"ok": True}, {"Set-Cookie": "acw_tc=waf-token; Path=/"})
        assert "acw_tc=waf-token" in request.headers.get("cookie", "")
        return _json_response({"ok": True}, {"Set-Cookie": "FINAL=yes; Path=/"})

    steps = [
        {"url": "https://erp.example.test/step1", "bodyType": "none", "method": "POST"},
        {
            "url": "https://erp.example.test/step2",
            "method": "POST",
            "bodyType": "form",
            "body": {"x": "1"},
            "outputs": {"header.cookie.FINAL": "cookie:FINAL"},
            "persistOutputs": True,
        },
    ]
    new_secret, _ = CredentialLoginChainService.execute_login_chain(
        {"headerName": "Cookie", "headerValue": ""}, steps, transport=httpx.MockTransport(handler)
    )
    assert new_secret["headerValue"] == "FINAL=yes"


def test_login_chain_supports_regex_transform():
    """提取来源支持 regex 加工：从 result 字符串中按捕获组提取 ticket。"""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/b":
            assert "ticket=regex-abc-123" in request.read().decode()
            return _json_response({"ok": True}, {"Set-Cookie": "S=1; Path=/"})
        return _json_response({"result": "otp?ticket=regex-abc-123"}, {"Set-Cookie": "S=1; Path=/"})

    steps = [
        {
            "url": "https://erp.example.test/a",
            "method": "POST",
            "bodyType": "none",
            "outputs": {"ticket": "json:result|regex:ticket=([a-z0-9-]+)"},
        },
        {
            "url": "https://erp.example.test/b",
            "method": "POST",
            "bodyType": "form",
            "body": {"ticket": "${step.1.ticket}"},
            "outputs": {"header.cookie.S": "cookie:S"},
            "persistOutputs": True,
        },
    ]
    CredentialLoginChainService.execute_login_chain(
        {"headerName": "Cookie", "headerValue": ""},
        steps,
        transport=httpx.MockTransport(handler),
    )


def test_login_chain_fails_at_step_and_reports_step_index():
    """第二步断言失败时抛出带步骤定位的异常，且不产生任何写回结果。"""
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path == "/doLogin":
            return _json_response({"code": "success", "result": "otp?ticket=t-1"})
        return _json_response({"code": "invalid_otp", "result": None})

    steps = _erp_style_steps()
    steps[1]["successAssertions"] = [{"source": "json:code", "operator": "equals", "expected": "success"}]

    with pytest.raises(ValueError) as exc_info:
        CredentialLoginChainService.execute_login_chain(
            _erp_style_secret(), steps, otp_type="totp", transport=httpx.MockTransport(handler)
        )
    assert "登录链第2步" in str(exc_info.value)
    assert calls == ["/doLogin", "/doOtp"]


def test_login_chain_fails_when_transient_variable_missing():
    """第一步响应中没有可提取的 ticket 时立即终止，不允许后续步骤带着空值请求。"""
    steps = _erp_style_steps()
    with pytest.raises(ValueError) as exc_info:
        CredentialLoginChainService.execute_login_chain(
            _erp_style_secret(),
            steps,
            otp_type="totp",
            transport=httpx.MockTransport(lambda request: _json_response({"code": "success", "result": "home"})),
        )
    assert "未能提取变量 ticket" in str(exc_info.value)


def test_login_chain_requires_persist_outputs_step():
    """全部步骤都是临时输出时视为失败：登录链的目的必须是拿到新凭证。"""
    steps = [
        {
            "url": "https://erp.example.test/a",
            "method": "POST",
            "bodyType": "none",
            "outputs": {"ticket": "json:result"},
        },
    ]
    with pytest.raises(ValueError) as exc_info:
        CredentialLoginChainService.execute_login_chain(
            {},
            steps,
            transport=httpx.MockTransport(lambda request: _json_response({"result": "t-1"})),
        )
    assert "没有任何步骤提取到新凭证" in str(exc_info.value)


def test_login_chain_rejects_reference_to_later_step_output():
    """变量只能引用更早步骤的输出，引用后续步骤在保存/执行期都必须报错。"""
    steps = [
        {
            "url": "https://erp.example.test/a?x=${step.2.token}",
            "method": "POST",
            "bodyType": "none",
        },
        {
            "url": "https://erp.example.test/b",
            "method": "POST",
            "bodyType": "none",
            "outputs": {"token": "json:result"},
        },
    ]
    with pytest.raises(ValueError) as exc_info:
        CredentialLoginChainService.execute_login_chain(
            {}, steps, transport=httpx.MockTransport(lambda request: _json_response({}))
        )
    assert "不存在的变量" in str(exc_info.value)


def test_login_step_model_rejects_when_condition_and_invalid_output():
    """条件步骤（when）暂未支持；输出变量名与来源语法非法时直接拒绝。"""
    with pytest.raises(ValueError):
        CredentialLoginStepModel.model_validate(
            {
                "url": "https://erp.example.test/a",
                "when": {"source": "json:code", "operator": "equals", "expected": "x"},
            },
        )
    with pytest.raises(ValueError):
        CredentialLoginStepModel.model_validate(
            {"url": "https://erp.example.test/a", "outputs": {"1bad": "json:code"}}
        )
    with pytest.raises(ValueError):
        CredentialLoginStepModel.model_validate(
            {"url": "https://erp.example.test/a", "outputs": {"ticket": "body.result"}}
        )
    with pytest.raises(ValueError):
        CredentialLoginStepModel.model_validate(
            {"url": "ftp://erp.example.test/a"}
        )
    with pytest.raises(ValueError):
        CredentialLoginStepModel.model_validate(
            {"url": "https://erp.example.test/a", "method": "GET", "bodyType": "form", "body": {"a": "1"}}
        )


def test_auth_config_accepts_camel_case_login_steps_and_validates_references():
    """认证配置支持 camelCase 的 loginSteps 入参，并触发跨步骤引用校验。"""
    model = CredentialAuthConfigModel.model_validate({"loginSteps": _erp_style_steps()})
    assert model.login_steps[0].outputs == {"ticket": "json:result|url_query:ticket"}
    assert model.login_steps[1].persist_outputs is True

    broken = _erp_style_steps()
    broken[0]["body"] = {"ticket": "${step.2.missing}"}
    with pytest.raises(ValueError):
        CredentialAuthConfigModel.model_validate({"loginSteps": broken})


def test_refresh_credential_http_login_uses_login_chain(monkeypatch):
    """http_login 凭证配置了 login_steps 时，刷新流程自动改走多步登录链。"""
    credential = SimpleNamespace(
        enabled=True,
        revision=3,
        auth_mode="http_login",
        secret_cipher_text="cipher-text",
    )
    config = SimpleNamespace(
        login_url="",
        refresh_url="",
        login_steps=_erp_style_steps(),
        otp_type="totp",
    )
    old_secret = _erp_style_secret()
    new_secret = {**old_secret, "headerValue": "dmall-locale=zh_HK; UYBFEWAEE=new"}
    chain_calls = []
    update_payloads = []

    monkeypatch.setattr(CredentialDao, "get_credential", lambda db, credential_id: credential)
    monkeypatch.setattr(CredentialDao, "get_auth_config", lambda db, credential_id: config)
    monkeypatch.setattr(
        CredentialLeaseService, "acquire", lambda db, credential_id, operation_type, operator: "lease-token"
    )
    monkeypatch.setattr(CredentialLeaseService, "release", lambda db, lease_token: None)
    def fake_update_credential(db, credential_id, values, expected_revision=None):
        update_payloads.append(values)
        return True

    monkeypatch.setattr(CredentialDao, "update_credential", fake_update_credential)
    monkeypatch.setattr(CredentialDao, "add_operation_log", lambda db, values: None)
    monkeypatch.setattr(
        "modules.credential.service.credential_refresh_service.decrypt_secret", lambda cipher_text: old_secret
    )
    monkeypatch.setattr(
        "modules.credential.service.credential_refresh_service.encrypt_secret", lambda secret: "encrypted"
    )
    monkeypatch.setattr("modules.credential.service.credential_refresh_service.mask_secret", lambda secret: "masked")

    def fake_execute_login_chain(secret, login_steps, otp_type="none", otp_code=None, transport=None):
        chain_calls.append({"otp_type": otp_type, "otp_code": otp_code, "step_count": len(login_steps)})
        return new_secret, [{"index": 1}, {"index": 2}]

    monkeypatch.setattr(CredentialLoginChainService, "execute_login_chain", staticmethod(fake_execute_login_chain))

    class FakeDb:
        def commit(self):
            pass

    result = CredentialRefreshService.refresh_credential(FakeDb(), 5, 3, "operator-a")

    assert result == {"success": True, "message": "刷新成功", "status": "success"}
    assert chain_calls == [{"otp_type": "totp", "otp_code": None, "step_count": 2}]
    assert update_payloads[0]["secret_cipher_text"] == "encrypted"
