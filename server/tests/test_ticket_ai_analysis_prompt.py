import unittest
from types import SimpleNamespace

from modules.ticket.service.ai.ticket_ai_analysis_service import TicketAiAnalysisService


class TicketAiAnalysisPromptTests(unittest.TestCase):
    """验证工单 AI 分析提示词对日志模式的约束。"""

    def test_hybrid_prompt_requires_source_log_search(self):
        """hybrid 模式下应强制 Agent 检索完整日志目录，避免只依赖摘要。"""
        mapping = SimpleNamespace(
            project_name="门店系统",
            version_key="v1",
            repo_url="https://example.invalid/repo.git",
            branch_name="main",
            local_repo_path="D:/repo",
        )
        ticket = SimpleNamespace(
            ticket_id=1,
            ticket_no="INC001",
            title="支付失败",
            description="用户反馈支付失败",
        )

        prompt = TicketAiAnalysisService._build_prompt(
            "D:/workspace/task",
            mapping,
            ticket,
            log_analysis_mode="hybrid",
        )

        self.assertIn("摘要只作为定位索引", prompt)
        self.assertIn("source_logs_manifest.json", prompt)
        self.assertIn("至少对 D:/workspace/task/source_logs/ 执行一次", prompt)
        self.assertIn("不要只引用 logs_ai_digest.txt", prompt)


if __name__ == "__main__":
    unittest.main()
