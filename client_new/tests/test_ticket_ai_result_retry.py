"""Agent 端补救重试（结果不可解析后 resume 纠错一轮）的回归测试。

背景：工单 INC00002000624N 分析中 deepseek-v4-flash 在字符串值内输出
未转义双引号导致解析失败（AI_WORKER_RESULT_INVALID）。除升级解析修复
算法外，Agent 端增加自动补救重试：保留首次现场后 resume 同一会话发送
纠错指令再执行一轮，成功则合并 token 走正常成功链路。
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from services.ticket_ai_analysis_service import TicketAiAnalysisService


def _base_kwargs(tmp_path: Path, task_id: int = 1001) -> dict:
    """构造补救重试的最小入参集合。"""
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    return {
        "event_sender": None,
        "req_data": {"taskId": task_id, "requestType": 6, "command": "run_ticket_ai_analysis"},
        "context_payload": {"selectedAiProviderCode": "openai_com"},
        "provider_type": "codex",
        "provider_env_overrides": {},
        "provider_code": "openai_com",
        "worker_model": "deepseek-v4-flash-0731",
        "workspace_dir": workspace,
        "result_file": workspace / "result.json",
        "schema_payload": {"type": "object"},
        "timeout_sec": 60,
        "task_started_ns": 0,
        "submitted_by_name": "tester",
        "selected_worker_model": "deepseek-v4-flash-0731",
        "ticket_id": 42,
    }


@pytest.mark.asyncio
async def test_retry_returns_none_when_first_result_text_empty(tmp_path):
    """首次连结果文本都没有时不做补救重试，直接放弃。"""
    kwargs = _base_kwargs(tmp_path)
    # result.json 不存在 → 结果文本为空
    outcome = await TicketAiAnalysisService._retry_worker_after_unparseable_result(**kwargs)
    assert outcome is None


@pytest.mark.asyncio
async def test_retry_preserves_first_attempt_files_and_returns_none_on_failed_retry(tmp_path, monkeypatch):
    """重试仍失败时返回 None，且首次现场被转存为 attempt1 文件。"""
    kwargs = _base_kwargs(tmp_path)
    workspace: Path = kwargs["workspace_dir"]
    result_file: Path = kwargs["result_file"]
    result_file.write_text('{"broken": "x {"k": "v"} y"}', encoding="utf-8")
    (workspace / "worker.stdout.txt").write_text("first-stdout", encoding="utf-8")
    (workspace / "worker.stderr.txt").write_text("first-stderr", encoding="utf-8")

    monkeypatch.setattr(
        TicketAiAnalysisService,
        "_copy_session_for_resume",
        classmethod(lambda cls, workspace_dir, provider_type, source: (True, ["--resume"])),
    )
    monkeypatch.setattr(
        TicketAiAnalysisService,
        "_prepare_ai_home",
        classmethod(lambda cls, workspace_dir, provider_type, overrides=None: workspace_dir / ".ai_home"),
    )
    monkeypatch.setattr(
        TicketAiAnalysisService,
        "_load_worker_env",
        classmethod(lambda cls, ai_home, provider_type, overrides=None: {}),
    )

    async def fake_run_worker_process(*args, **kwargs):
        return SimpleNamespace(returncode=0, stdout="retry-stdout", stderr="")

    monkeypatch.setattr(TicketAiAnalysisService, "_run_worker_process", staticmethod(fake_run_worker_process))
    # 重试后结果仍是"json-repair 也救不回"的残缺 JSON（截断无闭合花括号）
    result_file.write_text('{"still": "broken no closing brace', encoding="utf-8")

    async def fake_check_canceled(event_sender, task_id):
        return False

    monkeypatch.setattr(TicketAiAnalysisService, "_check_task_canceled", staticmethod(fake_check_canceled))

    outcome = await TicketAiAnalysisService._retry_worker_after_unparseable_result(**kwargs)
    assert outcome is None
    # 首次现场已转存（attempt1 文件在转存时生成，之后 result.json 被重写不影响）
    assert (workspace / "worker.attempt1.stdout.txt").read_text(encoding="utf-8") == "first-stdout"
    assert (workspace / "worker.attempt1.stderr.txt").read_text(encoding="utf-8") == "first-stderr"


@pytest.mark.asyncio
async def test_retry_success_returns_success_payload_with_merged_token(tmp_path, monkeypatch):
    """重试解析成功时返回成功响应，命令行含 resume 标志并携带 token。"""
    kwargs = _base_kwargs(tmp_path)
    workspace: Path = kwargs["workspace_dir"]
    result_file: Path = kwargs["result_file"]
    result_file.write_text('{"broken": true}', encoding="utf-8")
    good_result = json.dumps(
        {"ticket_id": 42, "root_cause": "修复成功", "analysis_summary": "ok"},
        ensure_ascii=False,
    )

    monkeypatch.setattr(
        TicketAiAnalysisService,
        "_copy_session_for_resume",
        classmethod(lambda cls, workspace_dir, provider_type, source: (True, ["--resume"])),
    )
    monkeypatch.setattr(
        TicketAiAnalysisService,
        "_prepare_ai_home",
        classmethod(lambda cls, workspace_dir, provider_type, overrides=None: workspace_dir / ".ai_home"),
    )
    monkeypatch.setattr(
        TicketAiAnalysisService,
        "_load_worker_env",
        classmethod(lambda cls, ai_home, provider_type, overrides=None: {}),
    )
    captured_command: dict[str, list[str]] = {}

    def fake_build_worker_command(cls, **kwargs):
        captured_command["value"] = ["codex", "exec"]
        return ["codex", "exec"]

    monkeypatch.setattr(TicketAiAnalysisService, "_build_worker_command", classmethod(fake_build_worker_command))

    async def fake_run_worker_process(command, prompt, cwd, env, timeout):
        captured_command["value"] = command
        # 验证纠错指令包含转义要求
        assert "转义" in prompt
        result_file.write_text(good_result, encoding="utf-8")
        return SimpleNamespace(returncode=0, stdout="retry-ok", stderr="")

    monkeypatch.setattr(TicketAiAnalysisService, "_run_worker_process", staticmethod(fake_run_worker_process))

    async def fake_check_canceled(event_sender, task_id):
        return False

    monkeypatch.setattr(TicketAiAnalysisService, "_check_task_canceled", staticmethod(fake_check_canceled))
    monkeypatch.setattr(
        TicketAiAnalysisService,
        "_parse_failure_token_usage",
        classmethod(lambda cls, **kwargs: {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}),
    )
    monkeypatch.setattr(
        "services.ticket_ai_analysis_service.TicketAiObservabilityService",
        SimpleNamespace(report_task_span=lambda *a, **k: None),
    )

    outcome = await TicketAiAnalysisService._retry_worker_after_unparseable_result(**kwargs)
    assert outcome is not None
    assert outcome["success"] is True
    assert outcome["status"] == "success"
    assert outcome["repaired_retry"] is True
    assert outcome["token_usage"] == {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}
    assert outcome["result"]["analysis_result"]["root_cause"] == "修复成功"
    assert "--resume" in outcome["result"]["command_line"]


@pytest.mark.asyncio
async def test_retry_returns_none_when_provider_not_support_resume(tmp_path, monkeypatch):
    """Provider 不支持 resume（resume_flag 缺失）时跳过补救，不做任何执行。"""
    kwargs = _base_kwargs(tmp_path)
    kwargs["provider_type"] = "unknown_provider"
    workspace: Path = kwargs["workspace_dir"]
    (workspace / "result.json").write_text('{"broken": true}', encoding="utf-8")

    def fail_copy(*args, **kwargs):
        raise AssertionError("不应触发 resume 复制")

    monkeypatch.setattr(TicketAiAnalysisService, "_copy_session_for_resume", classmethod(fail_copy))
    outcome = await TicketAiAnalysisService._retry_worker_after_unparseable_result(**kwargs)
    assert outcome is None
