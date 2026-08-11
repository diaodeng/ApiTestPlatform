import json
from typing import Any

from utils.api_key_util import ApiKeyUtil


def encrypt_secret(secret: dict[str, Any]) -> str:
    """将结构化敏感凭证序列化后加密，禁止向业务配置回写明文。"""
    return ApiKeyUtil.encrypt_api_key(json.dumps(secret, ensure_ascii=False, separators=(",", ":")))


def decrypt_secret(cipher_text: str) -> dict[str, Any]:
    """解密凭证内容，损坏密文以明确错误中断调用，绝不使用空凭证覆盖旧值。"""
    raw = ApiKeyUtil.decrypt_api_key(cipher_text)
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("凭证内容格式错误，必须是对象")
    return parsed


def mask_secret(secret: dict[str, Any]) -> str:
    """构造可审计但不泄露内容的凭证摘要。"""
    keys = sorted(str(key) for key, value in secret.items() if value not in (None, "", [], {}))
    return f"已配置字段：{', '.join(keys[:6])}{' 等' if len(keys) > 6 else ''}" if keys else "未配置敏感字段"
