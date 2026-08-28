from services.ticket_ai_analysis_service import TicketAiAnalysisService


def test_worker_failure_prefers_provider_quota_error_over_ticket_business_error():
    """
    Worker 输出同时包含工单业务 Error 和 Provider 配额异常时，应返回 Provider 错误。
    """
    stderr = """
    Error: [COP508] This coupon cannot be used now
    Unable to open session log file: Os { code: 5, kind: PermissionDenied }
    ERROR: stream disconnected before completion: Allocated quota exceeded, please increase your quota limit.
    """

    failure = TicketAiAnalysisService._classify_worker_failure(stderr, "", 1)

    assert failure["error_code"] == "AI_PROVIDER_QUOTA_EXCEEDED"
    assert "Allocated quota exceeded" in failure["error_message"]
    assert "COP508" not in failure["error_message"]
    assert failure["worker_exit_code"] == 1
    assert failure["diagnostics"][0]["code"] == "AI_WORKER_PERMISSION_DENIED"


def test_worker_permission_denied_is_fatal_only_when_no_later_provider_error_exists():
    """只有 PermissionDenied 时才将其作为主错误返回。"""
    failure = TicketAiAnalysisService._classify_worker_failure(
        'Unable to open session log file: Os { code: 5, kind: PermissionDenied }!',
        "",
        1,
    )

    assert failure["error_code"] == "AI_WORKER_PERMISSION_DENIED"
    assert "PermissionDenied" in failure["error_message"]
