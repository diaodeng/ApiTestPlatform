import unittest
from unittest.mock import patch

from modules.ticket.service.ai.ticket_ai_analysis_service import TicketAiAnalysisService


class TicketAiGatewayUrlTests(unittest.TestCase):
    """验证跨进程 Agent 网关使用本机路由，不携带外部代理前缀。"""

    @patch("modules.ticket.service.ai.ticket_ai_analysis_service.AppConfig.app_port", 8080)
    @patch("modules.ticket.service.ai.ticket_ai_analysis_service.AppConfig.app_root_path", "/prod-api")
    def test_gateway_url_does_not_include_external_root_path(self):
        """生产代理前缀不应出现在本机 FastAPI 网关地址中。"""
        self.assertEqual(
            TicketAiAnalysisService._build_agent_gateway_url("qtr/agent/ai-analysis/send/agent"),
            "http://127.0.0.1:8080/qtr/agent/ai-analysis/send/agent",
        )


if __name__ == "__main__":
    unittest.main()
