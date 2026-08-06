import httpx

from modules.credential.entity.vo.credential_vo import CredentialAuthConfigModel
from modules.credential.service.credential_refresh_service import CredentialRefreshService


def _response(payload=None, headers=None):
    return httpx.Response(
        200,
        json=payload or {},
        headers=headers or {},
        request=httpx.Request("POST", "https://example.test/refresh"),
    )


def test_extract_response_secret_supports_json_header_and_set_cookie():
    response = _response(
        {"data": {"accessToken": "new-token"}},
        {"X-Refresh-Version": "v2", "Set-Cookie": "SESSION=new-session; Path=/; HttpOnly"},
    )

    result = CredentialRefreshService._extract_response_secret(
        {"cookie": "OLD=keep", "headers": {"X-Old": "keep"}},
        response,
        {
            "token": "json:data.accessToken",
            "version": "header:X-Refresh-Version",
        },
    )

    assert result["token"] == "new-token"
    assert result["version"] == "v2"
    assert result["cookies"]["SESSION"] == "new-session"
    assert result["cookies"]["OLD"] == "keep"


def test_execute_http_request_carries_existing_cookie_and_renders_template(monkeypatch):
    captured = {}

    def fake_request(method, url, **kwargs):
        captured.update(method=method, url=url, kwargs=kwargs)
        return _response({"ok": True})

    monkeypatch.setattr("modules.credential.service.credential_refresh_service.httpx.request", fake_request)
    CredentialRefreshService._execute_http_request(
        "https://example.test/refresh",
        {"method": "POST", "body": {"user": "${secret.username}"}},
        {"username": "alice", "cookies": {"SESSION": "session-value"}},
    )

    assert captured["method"] == "POST"
    assert captured["kwargs"]["cookies"] == {"SESSION": "session-value"}
    assert captured["kwargs"]["json"] == {"user": "alice"}


def test_totp_generation_is_six_digits():
    assert CredentialRefreshService._generate_totp("JBSWY3DPEHPK3PXP").isdigit()
    assert len(CredentialRefreshService._generate_totp("JBSWY3DPEHPK3PXP")) == 6


def test_auth_config_normalizes_nullable_database_json_fields():
    model = CredentialAuthConfigModel.model_validate(
        {
            "loginRequestTemplate": None,
            "loginResponseMapping": None,
            "refreshRequestTemplate": None,
            "refreshResponseMapping": None,
            "targetHostPatterns": None,
        }
    )

    assert model.login_request_template == {}
    assert model.login_response_mapping == {}
    assert model.refresh_request_template == {}
    assert model.refresh_response_mapping == {}
    assert model.target_host_patterns == []
