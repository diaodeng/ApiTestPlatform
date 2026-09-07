"""采集服务密码加密与脱敏工具，复用平台统一的 API Key 加密实现。"""

from utils.api_key_util import ApiKeyUtil


def encrypt_password(plain_password: str) -> str:
    """加密推送认证密码，密文落库，禁止明文存储。"""
    return ApiKeyUtil.encrypt_api_key(plain_password)


def decrypt_password(cipher_text: str) -> str:
    """解密推送认证密码；密文损坏时返回空串并交由调用方按未配置处理。"""
    if not cipher_text:
        return ""
    try:
        return ApiKeyUtil.decrypt_api_key(cipher_text)
    except Exception:
        return ""


def mask_password(plain_password: str) -> str:
    """构造可确认密码已配置但不泄露内容的掩码摘要。"""
    if not plain_password:
        return ""
    if len(plain_password) <= 4:
        return "****"
    return f"{plain_password[:2]}****{plain_password[-2:]}"
