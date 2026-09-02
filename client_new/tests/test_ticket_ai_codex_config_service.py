from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from services.ticket_ai_codex_config_service import TicketAiCodexConfigService


class TicketAiCodexConfigServiceTests(unittest.TestCase):
    """验证任务级 Codex Home 的配置文件复制规则。"""

    def test_copy_task_home_files_copies_relative_model_catalog(self) -> None:
        """配置模型目录为相对路径时，应同步复制到任务级 Codex Home。"""
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_home = root / "source"
            target_home = root / "target"
            source_home.mkdir()
            (source_home / "config.toml").write_text(
                'model_catalog_json = "catalogs/models.json"\n',
                encoding="utf-8",
            )
            catalog_file = source_home / "catalogs" / "models.json"
            catalog_file.parent.mkdir()
            catalog_file.write_text('{"models": []}\n', encoding="utf-8")

            TicketAiCodexConfigService.copy_task_home_files(source_home, target_home)

            self.assertEqual(
                (target_home / "catalogs" / "models.json").read_text(encoding="utf-8"),
                '{"models": []}\n',
            )

    def test_copy_task_home_files_raises_for_missing_model_catalog(self) -> None:
        """配置引用的模型目录缺失时，应在启动 Worker 前返回明确错误。"""
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_home = root / "source"
            target_home = root / "target"
            source_home.mkdir()
            (source_home / "config.toml").write_text(
                'model_catalog_json = "missing.json"\n',
                encoding="utf-8",
            )

            with self.assertRaisesRegex(FileNotFoundError, "model_catalog_json 文件不存在"):
                TicketAiCodexConfigService.copy_task_home_files(source_home, target_home)

    def test_copy_task_home_files_skips_unconfigured_model_catalog(self) -> None:
        """未配置模型目录时，应只复制基础文件并正常完成。"""
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_home = root / "source"
            target_home = root / "target"
            source_home.mkdir()
            (source_home / "config.toml").write_text('model = "gpt-test"\n', encoding="utf-8")

            TicketAiCodexConfigService.copy_task_home_files(source_home, target_home)

            self.assertTrue((target_home / "config.toml").is_file())
            self.assertEqual(list(target_home.glob("*.json")), [])

    def test_copy_model_catalog_keeps_existing_task_catalog(self) -> None:
        """任务模型目录已存在时，即使源文件被清理也应保留重试现场。"""
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_home = root / "source"
            target_home = root / "target"
            source_home.mkdir()
            target_home.mkdir()
            (target_home / "config.toml").write_text(
                'model_catalog_json = "models.json"\n',
                encoding="utf-8",
            )
            (target_home / "models.json").write_text('{"task": true}\n', encoding="utf-8")

            TicketAiCodexConfigService.copy_model_catalog(source_home, target_home)

            self.assertEqual(
                (target_home / "models.json").read_text(encoding="utf-8"),
                '{"task": true}\n',
            )


    def test_apply_otel_config_writes_and_refreshes_managed_block(self) -> None:
        """apply_otel_config 应写入合法 [otel] 段，且刷新时整体替换旧块。"""
        import tomllib

        with tempfile.TemporaryDirectory() as temp_dir:
            codex_home = Path(temp_dir)
            (codex_home / "config.toml").write_text('model = "gpt-test"\n', encoding="utf-8")
            overrides = {
                "OTEL_EXPORTER_OTLP_ENDPOINT": "https://observe.example/observe",
                "OTEL_EXPORTER_OTLP_HEADERS": "Authorization=Bearer key-1",
                "OTEL_SERVICE_NAME": "ticket-ai-analysis",
                "OTEL_SESSION_ID": "ticket-ai-task-1001",
            }

            TicketAiCodexConfigService.apply_otel_config(codex_home, overrides)

            config_file = codex_home / "config.toml"
            data = tomllib.loads(config_file.read_text(encoding="utf-8"))
            trace_exporter = data["otel"]["trace_exporter"]["otlp-http"]
            self.assertEqual(trace_exporter["endpoint"], "https://observe.example/observe/v1/traces")
            self.assertEqual(trace_exporter["protocol"], "binary")
            self.assertEqual(trace_exporter["headers"]["Authorization"], "Bearer key-1")
            self.assertEqual(data["otel"]["span_attributes"]["session.id"], "ticket-ai-task-1001")

            # 刷新场景：换端点/密钥后旧值必须被整体替换
            overrides_v2 = {
                "OTEL_EXPORTER_OTLP_ENDPOINT": "https://new.example/observe",
                "OTEL_EXPORTER_OTLP_HEADERS": "Authorization=Bearer key-2",
                "OTEL_SERVICE_NAME": "ticket-ai-analysis",
            }
            TicketAiCodexConfigService.apply_otel_config(codex_home, overrides_v2)
            data_v2 = tomllib.loads(config_file.read_text(encoding="utf-8"))
            trace_exporter_v2 = data_v2["otel"]["trace_exporter"]["otlp-http"]
            self.assertEqual(trace_exporter_v2["endpoint"], "https://new.example/observe/v1/traces")
            self.assertEqual(trace_exporter_v2["headers"]["Authorization"], "Bearer key-2")
            self.assertNotIn("span_attributes", data_v2["otel"])
            # 原有配置不能被破坏
            self.assertEqual(data_v2["model"], "gpt-test")

    def test_apply_otel_config_skips_without_endpoint(self) -> None:
        """未下发 OTEL 端点时不应改动 config.toml。"""
        with tempfile.TemporaryDirectory() as temp_dir:
            codex_home = Path(temp_dir)
            (codex_home / "config.toml").write_text('model = "gpt-test"\n', encoding="utf-8")
            before = (codex_home / "config.toml").read_text(encoding="utf-8")

            TicketAiCodexConfigService.apply_otel_config(codex_home, {})

            self.assertEqual((codex_home / "config.toml").read_text(encoding="utf-8"), before)


if __name__ == "__main__":
    unittest.main()
