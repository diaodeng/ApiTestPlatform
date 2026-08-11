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


if __name__ == "__main__":
    unittest.main()
