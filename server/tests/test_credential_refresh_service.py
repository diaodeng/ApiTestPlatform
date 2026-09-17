from types import SimpleNamespace

import httpx

from modules.credential.dao.credential_dao import CredentialDao
from modules.credential.entity.vo.credential_vo import CredentialAuthConfigModel, CredentialResponseAssertionModel
from modules.credential.service.credential_lease_service import CredentialLeaseService
from modules.credential.util.credential_http_util import (
    extract_response_secret,
    generate_totp,
    mask_request_for_log,
    secret_cookies,
    validate_response_success_assertions,
)
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

    result, extracted = extract_response_secret(
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
    result, extracted = extract_response_secret({"cookies": {"OLD": "keep"}}, response, {})
    assert extracted is False
    assert result == {"cookies": {"OLD": "keep"}}


def test_extract_response_secret_does_not_clear_cookies_when_response_has_no_set_cookie():
    result, extracted = extract_response_secret(
        {"cookies": {"OLD": "keep"}},
        _response({"ok": True}),
        {"cookies": "cookies"},
    )

    assert extracted is False
    assert result == {"cookies": {"OLD": "keep"}}


def test_extract_response_secret_updates_named_cookie_in_cookie_header_from_raw_set_cookie():
    response = _response(headers={"Set-Cookie": "new-value"})
    result, extracted = extract_response_secret(
        {"headerName": "Cookie", "headerValue": "dmall-locale=zh_HK; UYBFEWAEE=old-value; login_token=token"},
        response,
        {"header.cookie.UYBFEWAEE": "header:set-cookie"},
    )
    assert extracted is True
    assert result["headerValue"] == "dmall-locale=zh_HK; UYBFEWAEE=new-value; login_token=token"


def test_extract_response_secret_appends_named_cookie_when_not_present():
    response = _response(headers={"Set-Cookie": "new-value"})
    result, extracted = extract_response_secret(
        {"headerName": "cookie", "headerValue": "SESSION=old"},
        response,
        {"header.cookie.UYBFEWAEE": "header:set-cookie"},
    )
    assert extracted is True
    assert result["headerValue"] == "SESSION=old; UYBFEWAEE=new-value"


def test_extract_response_secret_rejects_structured_cookie_writeback_for_primary_cookie_header():
    try:
        extract_response_secret(
            {"headerName": "Cookie", "headerValue": "SESSION=old"},
            _response(headers={"Set-Cookie": "SESSION=new; Path=/"}),
            {"cookies.SESSION": "cookie:SESSION"},
        )
    except ValueError as exc:
        assert "header.cookie" in str(exc)
    else:
        raise AssertionError("主 Cookie Header 不能写入结构化 cookies")


def test_extract_response_secret_allows_header_authentication_with_structured_cookie_writeback():
    result, extracted = extract_response_secret(
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
        extract_response_secret(
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
    result, extracted = extract_response_secret(
        {"headerName": "Cookie", "headerValue": "UYBFEWAEE=old-value"},
        response,
        {"header.cookie.UYBFEWAEE": "header:set-cookie[2]"},
    )
    assert extracted is True
    assert result["headerValue"] == "UYBFEWAEE=second-value"


def test_extract_response_secret_updates_named_structured_cookie():
    response = _response(headers={"Set-Cookie": "SESSION=new-session; Path=/"})
    result, extracted = extract_response_secret(
        {"cookies": {"SESSION": "old-session", "tenant": "prod"}},
        response,
        {"cookies.SESSION": "cookie:SESSION"},
    )
    assert extracted is True
    assert result["cookies"] == {"SESSION": "new-session", "tenant": "prod"}


def test_response_success_assertions_require_every_rule_to_pass():
    response = _response({"code": "0000", "data": {"success": True}}, {"X-Result": "OK"})

    validate_response_success_assertions(
        response,
        [
            {"source": "status", "operator": "in", "expected": [200, 201]},
            {"source": "json:code", "operator": "equals", "expected": "0000"},
            {"source": "json:data.success", "operator": "equals", "expected": True},
            {"source": "header:X-Result", "operator": "not_empty"},
        ],
    )

    try:
        validate_response_success_assertions(
            response,
            [{"source": "json:code", "operator": "equals", "expected": "1001"}],
        )
    except ValueError as exc:
        assert "响应成功断言第 1 条未通过" in str(exc)
    else:
        raise AssertionError("业务状态不满足成功断言时必须终止刷新")


def test_secret_cookies_merges_primary_and_structured_cookies():
    cookies = secret_cookies(
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
    masked = mask_request_for_log(
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
    assert generate_totp("JBSWY3DPEHPK3PXP").isdigit()
    assert len(generate_totp("JBSWY3DPEHPK3PXP")) == 6


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



def test_execute_http_refresh_with_login_fallback_retries_refresh_with_login_secret(monkeypatch):
    refresh_url = 'https://example.test/refresh'
    login_url = 'https://example.test/login'
    refresh_request_config = {'method': 'POST', 'headers': {'X-Step': 'refresh'}}
    login_request_config = {'method': 'POST', 'headers': {'X-Step': 'login'}}
    old_secret = {'headerName': 'Cookie', 'headerValue': 'SESSION=old', 'cookies': {'SESSION': 'old'}}
    login_secret = {'headerName': 'Cookie', 'headerValue': 'SESSION=new', 'cookies': {'SESSION': 'new'}}
    final_secret = {'headerName': 'Cookie', 'headerValue': 'SESSION=final', 'cookies': {'SESSION': 'final'}}
    calls = []

    def fake_execute_http_auth_step(url, request_config, secret, otp_type, otp_code, assertions, mapping, action_label):
        calls.append({
            'url': url,
            'request_config': request_config,
            'secret': secret,
            'otp_type': otp_type,
            'otp_code': otp_code,
            'action_label': action_label,
        })
        if url == refresh_url and len([item for item in calls if item['url'] == refresh_url]) == 1:
            raise ValueError('refresh failed')
        if url == login_url:
            assert secret == old_secret
            return login_secret
        if url == refresh_url and secret == login_secret:
            return final_secret
        raise AssertionError(f'未预期的调用：{url}')

    monkeypatch.setattr(
        CredentialRefreshService,
        '_execute_http_auth_step',
        fake_execute_http_auth_step,
    )

    result = CredentialRefreshService._execute_http_refresh_with_login_fallback(
        SimpleNamespace(
            refresh_url=refresh_url,
            login_url=login_url,
            refresh_request_template=refresh_request_config,
            login_request_template=login_request_config,
            refresh_response_mapping={},
            login_response_mapping={},
            refresh_success_assertions=[],
            login_success_assertions=[],
            response_mapping={},
            refresh_method='POST',
            login_method='POST',
            otp_type='none',
        ),
        old_secret,
        'none',
        None,
        5,
    )

    assert result == final_secret
    assert [item['url'] for item in calls] == [refresh_url, login_url, refresh_url]
    assert calls[0]['request_config'] == refresh_request_config
    assert calls[1]['request_config'] == login_request_config
    assert calls[2]['secret'] == login_secret
    assert calls[0]['action_label'] == 'HTTP 刷新'
    assert calls[1]['action_label'] == 'HTTP 登录'
    assert calls[2]['action_label'] == 'HTTP 刷新'


def test_refresh_credential_http_refresh_uses_login_fallback_helper(monkeypatch):
    refresh_calls = []
    credential = SimpleNamespace(
        enabled=True,
        revision=7,
        auth_mode='http_refresh',
        secret_cipher_text='cipher-text',
    )
    config = SimpleNamespace(
        refresh_url='https://example.test/refresh',
        login_url='https://example.test/login',
        otp_type='none',
    )
    old_secret = {'headerName': 'Cookie', 'headerValue': 'SESSION=old'}
    new_secret = {'headerName': 'Cookie', 'headerValue': 'SESSION=new'}
    update_payloads = []
    operation_logs = []
    commits = []

    monkeypatch.setattr(CredentialDao, 'get_credential', lambda db, credential_id: credential)
    monkeypatch.setattr(CredentialDao, 'get_auth_config', lambda db, credential_id: config)

    def fake_acquire(db, credential_id, operation_type, operator):
        return 'lease-token'

    def fake_release(db, lease_token):
        commits.append('release')

    def fake_update_credential(db, credential_id, values, expected_revision=None):
        update_payloads.append(
            {
                'credential_id': credential_id,
                'values': values,
                'expected_revision': expected_revision,
            }
        )
        return True

    def fake_add_operation_log(db, values):
        operation_logs.append(values)

    monkeypatch.setattr(CredentialLeaseService, 'acquire', fake_acquire)
    monkeypatch.setattr(CredentialLeaseService, 'release', fake_release)
    monkeypatch.setattr(CredentialDao, 'update_credential', fake_update_credential)
    monkeypatch.setattr(CredentialDao, 'add_operation_log', fake_add_operation_log)

    def fake_decrypt_secret(cipher_text):
        return old_secret

    def fake_encrypt_secret(secret):
        return f"encrypted:{secret['headerValue']}"

    def fake_mask_secret(secret):
        return f"masked:{secret['headerValue']}"

    monkeypatch.setattr('modules.credential.service.credential_refresh_service.decrypt_secret', fake_decrypt_secret)
    monkeypatch.setattr('modules.credential.service.credential_refresh_service.encrypt_secret', fake_encrypt_secret)
    monkeypatch.setattr('modules.credential.service.credential_refresh_service.mask_secret', fake_mask_secret)

    def fake_refresh_with_login_fallback(
        config_obj,
        secret,
        otp_type,
        otp_code,
        credential_id,
    ):
        refresh_calls.append(
            {
                'config': config_obj,
                'secret': secret,
                'otp_type': otp_type,
                'otp_code': otp_code,
                'credential_id': credential_id,
            }
        )
        return new_secret

    monkeypatch.setattr(
        CredentialRefreshService,
        '_execute_http_refresh_with_login_fallback',
        fake_refresh_with_login_fallback,
    )

    class FakeDb:
        def commit(self):
            commits.append('commit')

    result = CredentialRefreshService.refresh_credential(FakeDb(), 5, 7, 'operator-a')

    assert result == {'success': True, 'message': '刷新成功', 'status': 'success'}
    assert refresh_calls == [
        {
            'config': config,
            'secret': old_secret,
            'otp_type': 'none',
            'otp_code': None,
            'credential_id': 5,
        }
    ]
    assert len(update_payloads) == 1
    update_call = update_payloads[0]
    assert update_call['credential_id'] == 5
    assert update_call['expected_revision'] == 7
    assert update_call['values']['secret_cipher_text'] == 'encrypted:SESSION=new'
    assert update_call['values']['secret_mask'] == 'masked:SESSION=new'
    assert update_call['values']['revision'] == 8
    assert update_call['values']['last_refresh_status'] == 'success'
    assert update_call['values']['last_refresh_message'] == 'HTTP 刷新成功'
    assert update_call['values']['update_by'] == 'operator-a'
    assert update_call['values']['last_refresh_time'] == update_call['values']['update_time']
    assert operation_logs == [
        {
            'credential_id': 5,
            'operation_type': 'refresh',
            'status': 'success',
            'revision': 8,
            'message': 'HTTP 刷新并写回成功',
            'operator': 'operator-a',
        }
    ]
    assert commits == ['commit', 'release', 'commit']
