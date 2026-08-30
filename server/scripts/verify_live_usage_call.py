"""
真实验证脚本：从 .env.prod 数据库读取 Provider 配置，真实调用 AI 文本生成接口，
验证修改后的 generate_text_with_usage 能解析出上游 Token 用量。
只读数据库配置 + 只调用 AI 接口，不写任何库。
"""
import json
import sys
from pathlib import Path

SERVER_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVER_ROOT))

import pymysql  # noqa: E402

from module_admin.service.ai_provider_protocol_service import (  # noqa: E402
    AiProviderProtocolService,
)


class SimpleProvider:
    """最小 Provider 鸭子类型，避免加载 ORM 启动流程。"""

    def __init__(self, row: dict):
        self.provider_id = row.get("provider_id")
        self.provider_code = row.get("provider_code")
        self.api_protocol = row.get("api_protocol")
        self.base_url = row.get("base_url")
        self.default_model = row.get("default_model")
        self.api_key_cipher_text = row.get("api_key_cipher_text")
        self.connection_config = row.get("connection_config")
        if isinstance(self.connection_config, str):
            try:
                self.connection_config = json.loads(self.connection_config)
            except Exception:
                self.connection_config = {}


def load_env_prod() -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in (SERVER_ROOT / ".env.prod").read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip("'\"")
    return values


def main() -> None:
    env = load_env_prod()
    conn = pymysql.connect(
        host=env["DB_HOST"],
        port=int(env["DB_PORT"]),
        user=env["DB_USERNAME"],
        password=env["DB_PASSWORD"],
        database=env["DB_DATABASE"],
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=10,
    )
    try:
        with conn.cursor() as cursor:
            # 读取轻量 AI 实际在用的 Provider（prod 库审计记录显示 provider_code=openai_com）
            cursor.execute(
                "SELECT provider_id, provider_code, api_protocol, base_url, default_model, "
                "api_key_cipher_text, connection_config "
                "FROM sys_ai_provider WHERE del_flag='0' AND enabled=1 LIMIT 10"
            )
            rows = cursor.fetchall()
    finally:
        conn.close()

    print(f"prod 库可用 Provider 数量: {len(rows)}")
    target = None
    for row in rows:
        print(f"- {row['provider_code']} protocol={row['api_protocol']} model={row['default_model']}")
        if row["provider_code"] == "openai_com":
            target = row
    if target is None and rows:
        target = rows[0]
    if target is None:
        print("未找到可用 Provider，跳过真实调用")
        return

    provider = SimpleProvider(target)
    print()
    print(f"=== 真实调用: provider={provider.provider_code}, protocol={provider.api_protocol}, "
          f"model={provider.default_model}, base_url={provider.base_url}")
    result = AiProviderProtocolService.generate_text_with_usage(
        provider=provider,
        system_prompt="你是Token统计验证助手。",
        user_prompt="请只回复两个字：成功",
        temperature=0,
        timeout_sec=60,
    )
    print(f"回复文本: {result.text[:100]}")
    print(f"Token 用量: {result.token_usage}")
    if result.token_usage:
        assert isinstance(result.token_usage, dict), "token_usage 应为 dict"
        keys = set(result.token_usage.keys())
        assert keys & {"prompt_tokens", "input_tokens", "completion_tokens", "output_tokens", "total_tokens"}, \
            f"用量键不符合预期: {keys}"
        print("验证结论: usage 解析成功 ✓")
    else:
        print("验证结论: 上游未返回 usage（token_usage=None）✗")


if __name__ == "__main__":
    main()
