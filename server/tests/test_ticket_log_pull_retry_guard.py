from types import SimpleNamespace

import pytest

from modules.ticket.dao.ticket_log_pull_dao import TicketLogPullDao
from modules.ticket.service.log_pull.ticket_log_pull_service import TicketLogPullService


class DummyUser:
    """仅用于通过类型参数传递，不会在失败分支中被实际读取。"""

    user = SimpleNamespace(user_name="tester")


def test_get_external_config_services_returns_all_environments(monkeypatch):
    """外部环境列表接口仍应返回全部环境，不应依赖单个环境参数。"""
    monkeypatch.setattr(TicketLogPullService, "ensure_param_config_rows", lambda db: None)
    monkeypatch.setattr(
        TicketLogPullDao,
        "get_external_config_row",
        lambda db: SimpleNamespace(
            config_value='{"dev": {"baseUrl": "https://dev.example.com"}, "prod": {"baseUrl": "https://prod.example.com"}}'
        ),
    )

    result = TicketLogPullService.get_external_config_services(object())

    assert result == {
        "environments": {
            "dev": {"baseUrl": "https://dev.example.com"},
            "prod": {"baseUrl": "https://prod.example.com"},
        }
    }


def test_retry_log_pull_services_rejects_missing_environment(monkeypatch):
    """旧记录没有保存 environment 时，重新拉取应直接失败并给出明确提示。"""
    record = SimpleNamespace(id=2011730395835392, ticket_id=1001, status="success")
    payload = SimpleNamespace(environment="")
    log_steps: list[dict[str, str]] = []

    monkeypatch.setattr(TicketLogPullDao, "get_record_by_id", lambda db, record_id: record)
    monkeypatch.setattr(TicketLogPullService, "_build_retry_payload", lambda record: payload)
    monkeypatch.setattr(TicketLogPullService, "_log_chain_step", lambda *args, **kwargs: log_steps.append(kwargs))
    monkeypatch.setattr(
        TicketLogPullService,
        "create_log_pull_services",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("缺少环境信息时不应继续创建任务")),
    )

    result = TicketLogPullService.retry_log_pull_services(object(), 2011730395835392, DummyUser())

    assert result.is_success is False
    assert result.message == "当前记录缺少环境信息，无法重新拉取"
    assert log_steps[-1]["reason"] == "当前记录缺少环境信息，无法重新拉取"


def test_build_external_request_headers_wraps_credential_errors(monkeypatch):
    """凭证解析失败时，应透出更明确的日志拉取上下文错误。"""
    from modules.credential.service.credential_resolve_service import CredentialResolveService

    monkeypatch.setattr(
        CredentialResolveService,
        "resolve_http_headers",
        lambda db, binding_id, target_url: (_ for _ in ()).throw(ValueError("凭证已过期")),
    )

    with pytest.raises(ValueError, match="日志拉取外部接口凭证不可用：凭证已过期"):
        TicketLogPullService._build_external_request_headers(
            object(),
            {"credentialBindingId": "binding-1"},
            "https://example.com/api/logs",
        )
