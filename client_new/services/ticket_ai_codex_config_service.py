from __future__ import annotations

import json
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

    # 任务级 [otel] 托管块的起止标记；刷新时先移除旧块再追加新块，避免残留旧地址/密钥
    OTEL_BLOCK_BEGIN = "# --- ticket-ai otel begin (managed) ---"
    OTEL_BLOCK_END = "# --- ticket-ai otel end (managed) ---"

    @classmethod
    def apply_otel_config(cls, codex_home: Path, provider_env_overrides: dict[str, str]) -> None:
        """
        在任务级 config.toml 中写入/刷新托管 [otel] 段，启用 Codex 原生 OTLP 上报。

        Codex 不读取 OTEL_* 环境变量，必须通过 CODEX_HOME 下 config.toml 的 [otel]
        段配置；且项目级 .codex/config.toml 会忽略 otel 键，因此必须写在任务级
        CODEX_HOME（用户层级）。写入后用 tomllib 校验合法性，失败则还原旧内容。
        :param codex_home: 任务级 Codex 配置目录
        :param provider_env_overrides: 服务端下发的 Provider 环境变量（含 OTEL_*）
        """
        endpoint = str(provider_env_overrides.get("OTEL_EXPORTER_OTLP_ENDPOINT") or "").strip().rstrip("/")
        if not endpoint:
            logger.debug("未下发 OTEL 端点，跳过 Codex [otel] 配置写入")
            return
        # OTEL_EXPORTER_OTLP_HEADERS 格式为 key=value；这里只取 Authorization 头的值
        auth_value = ""
        for pair in str(provider_env_overrides.get("OTEL_EXPORTER_OTLP_HEADERS") or "").split(","):
            name, separator, value = pair.strip().partition("=")
            if separator and name.strip().lower() == "authorization":
                auth_value = value.strip()
                break
        if not auth_value:
            logger.warning("OTEL_HEADERS 中缺少 Authorization，跳过 Codex [otel] 配置写入")
            return
        service_name = str(provider_env_overrides.get("OTEL_SERVICE_NAME") or "ticket-ai-analysis").strip()
        session_id = str(provider_env_overrides.get("OTEL_SESSION_ID") or "").strip()
        user_id = str(provider_env_overrides.get("OTEL_USER_ID") or "").strip()

        def toml_string(raw_value: str) -> str:
            # JSON 字符串语法与 TOML basic string 兼容，统一走 json.dumps 转义
            return json.dumps(raw_value, ensure_ascii=False)

        config_file = codex_home / "config.toml"
        original_text = config_file.read_text(encoding="utf-8") if config_file.exists() else ""
        # 移除旧托管块（含块标记行本身），保证重试/换 Provider 时地址与密钥被整体刷新
        lines = original_text.splitlines()
        cleaned_lines: list[str] = []
        inside_managed_block = False
        for line in lines:
            if line.strip() == cls.OTEL_BLOCK_BEGIN:
                inside_managed_block = True
                continue
            if line.strip() == cls.OTEL_BLOCK_END:
                inside_managed_block = False
                continue
            if not inside_managed_block:
                cleaned_lines.append(line)
        base_text = "\n".join(cleaned_lines).rstrip("\n")
        otel_lines = [
            "",
            cls.OTEL_BLOCK_BEGIN,
            "[otel]",
            f"environment = {toml_string(service_name)}",
            "log_user_prompt = false",
            "exporter = { otlp-http = { endpoint = "
            + toml_string(f"{endpoint}/v1/logs")
            + ', protocol = "binary", headers = { Authorization = '
            + toml_string(auth_value)
            + " } } }",
            "metrics_exporter = { otlp-http = { endpoint = "
            + toml_string(f"{endpoint}/v1/metrics")
            + ', protocol = "binary", headers = { Authorization = '
            + toml_string(auth_value)
            + " } } }",
            "trace_exporter = { otlp-http = { endpoint = "
            + toml_string(f"{endpoint}/v1/traces")
            + ', protocol = "binary", headers = { Authorization = '
            + toml_string(auth_value)
            + " } } }",
        ]
        if session_id or user_id:
            otel_lines.append("")
            otel_lines.append("[otel.span_attributes]")
            if session_id:
                otel_lines.append(f'"session.id" = {toml_string(session_id)}')
            if user_id:
                otel_lines.append(f'"user.id" = {toml_string(user_id)}')
        otel_lines.append(cls.OTEL_BLOCK_END)
        new_text = f"{base_text}\n{chr(10).join(otel_lines)}\n" if base_text else f"{chr(10).join(otel_lines)}\n"
        try:
            tomllib.loads(new_text)
        except Exception as exc:
            logger.error(f"Codex [otel] 配置生成后 TOML 校验失败，保留原配置: {exc}")
            return
        if new_text != original_text:
            config_file.parent.mkdir(parents=True, exist_ok=True)
            config_file.write_text(new_text, encoding="utf-8")
            logger.info(f"已写入 Codex 任务级 [otel] 配置: endpoint={endpoint}, session_id={session_id or '<none>'}")
