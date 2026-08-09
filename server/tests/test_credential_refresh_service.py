import httpx

from modules.credential.entity.vo.credential_vo import CredentialAuthConfigModel, CredentialResponseAssertionModel
from modules.credential.service.credential_refresh_service import CredentialRefreshService
from modules.credential.service.credential_resolve_service import CredentialResolveService
from modules.credential.service.credential_service import CredentialService


def _response(payload=None, headers=None):
    return httpx.Response(
        200,
        json=payload or {},
        headers=headers or {},
        request=httpx.Request("POST", "https://example.test/refresh"),
    )


def test_extract_response_secret_supports_json_header_and_explicit_cookie_overwrite():
    response = _response(
        {"data": {"accessToken": "new-token"}},
        {"X-Refresh-Version": "v2", "Set-Cookie": "SESSION=new-session; Path=/; HttpOnly"},
    )

    result, extracted = CredentialRefreshService._extract_response_secret(
        {"cookie": "OLD=keep", "headers": {"X-Old": "keep"}},
        response,
        {
            "token": "json:data.accessToken",
            "version": "header:X-Refresh-Version",
            "cookies": "cookies",
        },
    )

    assert extracted is True
    assert result["token"] == "new-token"
    assert result["version"] == "v2"
    assert result["cookies"]["SESSION"] == "new-session"
    assert "OLD" not in result["cookies"]


def test_extract_response_secret_does_not_implicitly_merge_set_cookie():
    response = _response(headers={"Set-Cookie": "SESSION=new-session; Path=/"})
    result, extracted = CredentialRefreshService._extract_response_secret({"cookies": {"OLD": "keep"}}, response, {})
    assert extracted is False
    assert result == {"cookies": {"OLD": "keep"}}


def test_extract_response_secret_does_not_clear_cookies_when_response_has_no_set_cookie():
    result, extracted = CredentialRefreshService._extract_response_secret(
        {"cookies": {"OLD": "keep"}},
        _response({"ok": True}),
        {"cookies": "cookies"},
    )

    assert extracted is False
    assert result == {"cookies": {"OLD": "keep"}}


def test_extract_response_secret_updates_named_cookie_in_cookie_header_from_raw_set_cookie():
    response = _response(headers={"Set-Cookie": "new-value"})
    result, extracted = CredentialRefreshService._extract_response_secret(
        {"headerName": "Cookie", "headerValue": "dmall-locale=zh_HK; UYBFEWAEE=old-value; login_token=token"},
        response,
        {"header.cookie.UYBFEWAEE": "header:set-cookie"},
    )
    assert extracted is True
    assert result["headerValue"] == "dmall-locale=zh_HK; UYBFEWAEE=new-value; login_token=token"


def test_extract_response_secret_appends_named_cookie_when_not_present():
    response = _response(headers={"Set-Cookie": "new-value"})
    result, extracted = CredentialRefreshService._extract_response_secret(
        {"headerName": "cookie", "headerValue": "SESSION=old"},
        response,
        {"header.cookie.UYBFEWAEE": "header:set-cookie"},
    )
    assert extracted is True
    assert result["headerValue"] == "SESSION=old; UYBFEWAEE=new-value"


def test_extract_response_secret_rejects_structured_cookie_writeback_for_primary_cookie_header():
    try:
        CredentialRefreshService._extract_response_secret(
            {"headerName": "Cookie", "headerValue": "SESSION=old"},
            _response(headers={"Set-Cookie": "SESSION=new; Path=/"}),
            {"cookies.SESSION": "cookie:SESSION"},
        )
    except ValueError as exc:
        assert "header.cookie" in str(exc)
    else:
        raise AssertionError("主 Cookie Header 不能写入结构化 cookies")


def test_extract_response_secret_allows_header_authentication_with_structured_cookie_writeback():
    result, extracted = CredentialRefreshService._extract_response_secret(
        {"headerName": "Authorization", "headerValue": "Bearer old"},
        _response(headers={"Set-Cookie": "SESSION=new; Path=/"}),
        {"cookies.SESSION": "cookie:SESSION"},
    )

    assert extracted is True
    assert result["cookies"] == {"SESSION": "new"}


def test_extract_response_secret_rejects_multiple_raw_set_cookie_values():
    response = httpx.Response(
        200,
        headers=[("Set-Cookie", "first-value"), ("Set-Cookie", "second-value")],
        request=httpx.Request("POST", "https://example.test/refresh"),
    )
    try:
        CredentialRefreshService._extract_response_secret(
            {"headerName": "Cookie", "headerValue": "UYBFEWAEE=old-value"},
            response,
            {"header.cookie.UYBFEWAEE": "header:set-cookie"},
        )
    except ValueError as exc:
        assert "多个 Set-Cookie" in str(exc)
    else:
        raise AssertionError("多条 Set-Cookie 必须拒绝写入单个 Cookie 字段")


def test_extract_response_secret_selects_one_raw_set_cookie_by_one_based_index():
    response = httpx.Response(
        200,
        headers=[("Set-Cookie", "first-value"), ("Set-Cookie", "second-value")],
        request=httpx.Request("POST", "https://example.test/refresh"),
    )
    result, extracted = CredentialRefreshService._extract_response_secret(
        {"headerName": "Cookie", "headerValue": "UYBFEWAEE=old-value"},
        response,
        {"header.cookie.UYBFEWAEE": "header:set-cookie[2]"},
    )
    assert extracted is True
    assert result["headerValue"] == "UYBFEWAEE=second-value"


def test_extract_response_secret_updates_named_structured_cookie():
    response = _response(headers={"Set-Cookie": "SESSION=new-session; Path=/"})
    result, extracted = CredentialRefreshService._extract_response_secret(
        {"cookies": {"SESSION": "old-session", "tenant": "prod"}},
        response,
        {"cookies.SESSION": "cookie:SESSION"},
    )
    assert extracted is True
    assert result["cookies"] == {"SESSION": "new-session", "tenant": "prod"}


def test_response_success_assertions_require_every_rule_to_pass():
    response = _response({"code": "0000", "data": {"success": True}}, {"X-Result": "OK"})

    CredentialRefreshService._validate_response_success_assertions(
        response,
        [
            {"source": "status", "operator": "in", "expected": [200, 201]},
            {"source": "json:code", "operator": "equals", "expected": "0000"},
            {"source": "json:data.success", "operator": "equals", "expected": True},
            {"source": "header:X-Result", "operator": "not_empty"},
        ],
    )

    try:
        CredentialRefreshService._validate_response_success_assertions(
            response,
            [{"source": "json:code", "operator": "equals", "expected": "1001"}],
        )
    except ValueError as exc:
        assert "响应成功断言第 1 条未通过" in str(exc)
    else:
        raise AssertionError("业务状态不满足成功断言时必须终止刷新")


def test_secret_cookies_merges_primary_and_structured_cookies():
    cookies = CredentialRefreshService._secret_cookies(
        {"cookie": "SESSION=primary; locale=zh-CN", "cookies": {"SESSION": "updated", "tenant": "prod"}}
    )

    assert cookies == {"SESSION": "updated", "locale": "zh-CN", "tenant": "prod"}


def test_resolve_cookie_header_merges_primary_and_browser_cookie_by_name():
    header = CredentialResolveService._build_cookie_header(
        {
            "cookie": "SESSION=primary; locale=zh-CN",
            "cookies": [{"name": "SESSION", "value": "browser", "domain": "example.test", "path": "/"}],
        },
        "https://example.test/api/refresh",
    )

    assert header == "SESSION=browser; locale=zh-CN"


def test_resolve_cookie_header_supports_primary_cookie_header():
    header = CredentialResolveService._build_cookie_header(
        {"headerName": "Cookie", "headerValue": "SESSION=primary; locale=zh-CN"},
        "https://example.test/api/refresh",
    )

    assert header == "SESSION=primary; locale=zh-CN"


def test_clear_primary_secret_fields_preserves_additional_authentication():
    secret = {
        "headerName": "Authorization",
        "headerValue": "Bearer old-token",
        "token": "old-token",
        "headers": {"X-CSRF-Token": "csrf-value"},
        "cookies": {"tenant": "prod"},
        "username": "alice",
    }

    CredentialService._clear_primary_secret_fields(secret)

    assert secret == {
        "headers": {"X-CSRF-Token": "csrf-value"},
        "cookies": {"tenant": "prod"},
        "username": "alice",
    }


def test_response_assertion_model_rejects_invalid_source_and_in_expected_value():
    for config in (
        {"source": "body.code", "operator": "equals", "expected": "0000"},
        {"source": "status", "operator": "in", "expected": 200},
    ):
        try:
            CredentialResponseAssertionModel.model_validate(config)
        except ValueError:
            continue
        raise AssertionError("不合法的成功断言配置必须被接口模型拒绝")


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


def test_execute_http_request_renders_cookie_from_http_header_secret(monkeypatch):
    captured = {}

    def fake_request(method, url, **kwargs):
        captured.update(method=method, url=url, kwargs=kwargs)
        return _response({"ok": True})

    monkeypatch.setattr("modules.credential.service.credential_refresh_service.httpx.request", fake_request)
    CredentialRefreshService._execute_http_request(
        "https://example.test/refresh",
        {"method": "POST", "headers": {"cookie": "${secret.cookie}"}},
        {"headerName": "cookie", "headerValue": "SESSION=session-value"},
    )

    assert captured["kwargs"]["headers"]["cookie"] == "SESSION=session-value"


def test_execute_http_request_renders_header_value_template(monkeypatch):
    captured = {}

    def fake_request(method, url, **kwargs):
        captured.update(method=method, url=url, kwargs=kwargs)
        return _response({"ok": True})

    monkeypatch.setattr("modules.credential.service.credential_refresh_service.httpx.request", fake_request)
    CredentialRefreshService._execute_http_request(
        "https://example.test/refresh",
        {"method": "POST", "headers": {"X-Refresh-Key": "${secret.headerValue}"}},
        {"headerName": "X-API-Key", "headerValue": "api-key-value"},
    )

    assert captured["kwargs"]["headers"]["X-Refresh-Key"] == "api-key-value"


def test_template_secret_exposes_header_value_for_legacy_snake_case_field():
    template_secret = CredentialRefreshService._build_template_secret(
        {"header_name": "X-API-Key", "header_value": "legacy-value"}
    )

    assert template_secret["headerValue"] == "legacy-value"


def test_mask_request_for_log_hides_cookie_and_password_values():
    masked = CredentialRefreshService._mask_request_for_log(
        {
            "headers": {"cookie": "SESSION=session-value", "origin": "https://example.test"},
            "cookies": {"SESSION": "session-value"},
            "json": {"password": "plain-password", "account": "alice"},
        }
    )

    assert masked == {
        "headers": {"cookie": "******", "origin": "******"},
        "cookies": "******",
        "json": {"password": "******", "account": "alice"},
    }


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
            "loginSuccessAssertions": None,
            "refreshSuccessAssertions": None,
            "targetHostPatterns": None,
        }
    )

    assert model.login_request_template == {}
    assert model.login_response_mapping == {}
    assert model.refresh_request_template == {}
    assert model.refresh_response_mapping == {}
    assert model.login_success_assertions == []
    assert model.refresh_success_assertions == []
    assert model.target_host_patterns == []
