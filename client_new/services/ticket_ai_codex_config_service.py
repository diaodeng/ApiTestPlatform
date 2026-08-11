from __future__ import annotations

import shutil
from pathlib import Path

import tomllib
from loguru import logger


class TicketAiCodexConfigService:
    """负责为工单 AI Worker 准备任务级 Codex 配置文件。"""

    BASE_CONFIG_FILES = ("config.toml", "config.self.toml", "auth.json", "version.json", ".env")

    @classmethod
    def copy_task_home_files(cls, source_home: Path, target_home: Path) -> None:
        """
        将 Codex 基础配置及其引用的模型目录复制到任务级配置目录。

        :param source_home: 用户级 Codex 配置目录
        :param target_home: 任务级 Codex 配置目录
        :return: 无
        """
        target_home.mkdir(parents=True, exist_ok=True)
        for file_name in cls.BASE_CONFIG_FILES:
            cls.copy_file_if_absent(source_home / file_name, target_home / file_name)
        cls.copy_model_catalog(source_home, target_home)

    @staticmethod
    def copy_file_if_absent(source_file: Path, target_file: Path) -> None:
        """
        在源文件存在且目标文件不存在时复制配置文件，保留同一任务重试时的现场。

        :param source_file: 源配置文件
        :param target_file: 目标配置文件
        :return: 无
        """
        if not source_file.exists():
            logger.debug(f"Codex 配置源文件不存在，跳过复制: {source_file}")
            return
        if target_file.exists():
            logger.debug(f"Codex 任务配置文件已存在，跳过覆盖: {target_file}")
            return
        target_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_file, target_file)
        logger.info(f"已复制 Codex 任务配置文件: {source_file.name}")

    @classmethod
    def copy_model_catalog(cls, source_home: Path, target_home: Path) -> None:
        """
        复制 config.toml 中 model_catalog_json 引用的相对模型目录文件。

        Codex 会相对 CODEX_HOME 读取该文件；任务级 CODEX_HOME 若只复制 config.toml，
        Worker 会在启动阶段因文件缺失返回 os error 2。

        :param source_home: 用户级 Codex 配置目录
        :param target_home: 任务级 Codex 配置目录
        :return: 无
        :raises FileNotFoundError: 配置引用的模型目录文件不存在
        :raises ValueError: 相对路径越出 Codex Home 边界
        """
        config_file = target_home / "config.toml"
        if not config_file.exists():
            logger.info("Codex config.toml 不存在，不需要复制模型目录文件")
            return
        config_data = tomllib.loads(config_file.read_text(encoding="utf-8"))
        catalog_value = str(config_data.get("model_catalog_json") or "").strip()
        if not catalog_value:
            logger.info("Codex config.toml 未配置 model_catalog_json，跳过模型目录复制")
            return

        catalog_path = Path(catalog_value)
        if catalog_path.is_absolute():
            if not catalog_path.is_file():
                raise FileNotFoundError(f"Codex model_catalog_json 文件不存在: {catalog_path}")
            logger.info(f"Codex model_catalog_json 使用可访问的绝对路径，无需复制: {catalog_path}")
            return

        source_root = source_home.resolve()
        target_root = target_home.resolve()
        source_file = (source_home / catalog_path).resolve()
        target_file = (target_home / catalog_path).resolve()
        if not source_file.is_relative_to(source_root) or not target_file.is_relative_to(target_root):
            raise ValueError(f"Codex model_catalog_json 相对路径越出配置目录: {catalog_value}")
        if target_file.is_file():
            logger.info(f"Codex 任务模型目录已存在，保留当前任务现场: {target_file}")
            return
        if not source_file.is_file():
            raise FileNotFoundError(f"Codex model_catalog_json 文件不存在: {source_file}")
        cls.copy_file_if_absent(source_file, target_file)
