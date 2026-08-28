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

    def test_prompt_forbids_shell_file_write_for_final_json(self):
        """提示词应明确要求直接输出最终 JSON，避免 Worker 自行用 shell/heredoc 写结果文件。"""
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
            log_analysis_mode="digest",
        )

        self.assertIn("不要调用 shell、python 或 PowerShell", prompt)
        self.assertIn("去创建、写入、拼接任何结果文件", prompt)
        self.assertIn("不要使用 heredoc", prompt)
        self.assertIn("系统会自动保存结果文件", prompt)

    def test_prompt_supports_agent_log_cache_path(self):
        """Agent 复用日志缓存时，提示词应指向缓存目录而不是任务临时目录。"""
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
            source_logs_path="D:/workspace/log_cache/ticket_1/log_pull_2/source_logs",
        )

        self.assertIn("D:/workspace/log_cache/ticket_1/log_pull_2/source_logs/", prompt)
        self.assertNotIn("D:/workspace/task/source_logs/ 执行一次", prompt)

    def test_result_schema_accepts_serialized_ids_and_analysis_extensions(self):
        """结果 Schema 应兼容 BIGINT 字符串和提示词约定的扩展分析字段。"""
        mapping = SimpleNamespace(
            repo_url="https://example.invalid/repo.git",
            branch_name="main",
        )
        ticket = SimpleNamespace(ticket_id=2044099516136448, project_id=2011261968542720)
        schema = TicketAiAnalysisService._build_result_schema(ticket, mapping, "1.3.9.5")
        payload = {
            "ticket_id": str(ticket.ticket_id),
            "project_id": "WE-惠康",
            "version_key": "wemn_vender_master_1.3.9.5",
            "repo_url": mapping.repo_url,
            "branch_name": mapping.branch_name,
            "root_cause": "root cause",
            "analysis_summary": "summary",
            "related_files": [],
            "related_functions": [],
            "fix_suggestion": "fix",
            "confidence": "high",
            "evidence": [],
            "risk_items": [],
            "next_steps": [],
            "similar_cases": [],
            "sop_suggestion": "sop",
            "owner_suggestion": "owner",
            "monitoring_suggestion": "monitoring",
            "needs_human_review": False,
        }

        self.assertTrue(TicketAiAnalysisService._validate_analysis_result_schema(payload, schema))

    def test_result_schema_accepts_string_similar_cases(self):
        """similar_cases 应与增强字段一致接受叙述字符串（INC00001894981 失败回归）。"""
        mapping = SimpleNamespace(repo_url="https://example.invalid/repo.git", branch_name="main")
        ticket = SimpleNamespace(ticket_id=2044099516136448, project_id=2011261968542720)
        schema = TicketAiAnalysisService._build_result_schema(ticket, mapping, "1.3.9.5")
        payload = {
            "ticket_id": str(ticket.ticket_id),
            "project_id": ticket.project_id,
            "version_key": "1.3.9.7",
            "repo_url": mapping.repo_url,
            "branch_name": mapping.branch_name,
            "root_cause": "root cause",
            "analysis_summary": "summary",
            "related_files": [],
            "related_functions": [],
            "fix_suggestion": "fix",
            "confidence": 0.82,
            "evidence": [],
            "risk_items": [],
            "next_steps": [],
            # 模型实际输出：叙述字符串而非数组
            "similar_cases": "历史相似工单 INC00001789443（POS小票缺QR码）属打印内容缺失类",
        }

        self.assertTrue(TicketAiAnalysisService._validate_analysis_result_schema(payload, schema))
        violations = TicketAiAnalysisService._collect_schema_violations(payload, schema)
        self.assertEqual(violations, [])

    def test_collect_schema_violations_reports_field_details(self):
        """校验失败时应输出具体违规字段而不是空诊断。"""
        mapping = SimpleNamespace(repo_url="https://example.invalid/repo.git", branch_name="main")
        ticket = SimpleNamespace(ticket_id=1, project_id=2)
        schema = TicketAiAnalysisService._build_result_schema(ticket, mapping, "v1")
        # similar_cases 回填数组、monitoring_suggestion 写成数字，制造联合类型外违规
        payload = {
            "ticket_id": 1,
            "project_id": 2,
            "version_key": "v1",
            "repo_url": "repo",
            "branch_name": "main",
            "root_cause": "root",
            "analysis_summary": "summary",
            "related_files": [],
            "related_functions": [],
            "fix_suggestion": "fix",
            "confidence": 0.9,
            "evidence": [],
            "risk_items": [],
            "next_steps": [],
            "similar_cases": [],
            "monitoring_suggestion": 123,
        }

        self.assertFalse(TicketAiAnalysisService._validate_analysis_result_schema(payload, schema))
        violations = TicketAiAnalysisService._collect_schema_violations(payload, schema)
        self.assertTrue(any("monitoring_suggestion" in item for item in violations))

    def test_normalized_result_wraps_string_enhancement_fields(self):
        """归一化应把叙述字符串增强字段包装为单元素数组。"""
        mapping = SimpleNamespace(repo_url="repo", branch_name="main")
        ticket = SimpleNamespace(ticket_id=1001, project_id=2002)

        result = TicketAiAnalysisService._normalize_analysis_result(
            result_payload={"similar_cases": "历史相似工单 INC00001789443", "sop_suggestion": "先查小票数据"},
            ticket=ticket,
            mapping=mapping,
            version_key="v1",
        )

        self.assertEqual(result["similar_cases"], ["历史相似工单 INC00001789443"])
        self.assertEqual(result["sop_suggestion"], ["先查小票数据"])
        # 数组类型输入保持不变
        result_list = TicketAiAnalysisService._normalize_analysis_result(
            result_payload={"similar_cases": ["INC00001789443"]},
            ticket=ticket,
            mapping=mapping,
            version_key="v1",
        )
        self.assertEqual(result_list["similar_cases"], ["INC00001789443"])

    def test_normalized_result_uses_authoritative_ticket_ids(self):
        """归一化结果不应保留 Agent 误填的工单号或项目名称。"""
        mapping = SimpleNamespace(repo_url="repo", branch_name="main")
        ticket = SimpleNamespace(ticket_id=1001, project_id=2002)

        result = TicketAiAnalysisService._normalize_analysis_result(
            result_payload={"ticket_id": "wrong", "project_id": "项目名称"},
            ticket=ticket,
            mapping=mapping,
            version_key="v1",
        )

        self.assertEqual(result["ticket_id"], 1001)
        self.assertEqual(result["project_id"], 2002)


if __name__ == "__main__":
    unittest.main()
