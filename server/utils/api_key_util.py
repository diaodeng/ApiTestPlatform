import base64
import hashlib
import secrets

from cryptography.fernet import Fernet, InvalidToken

from config.env import JwtConfig


class ApiKeyUtil:
    """
    API Key工具类
    """

    API_KEY_PREFIX = "qtr_ak"

    @classmethod
    def generate_api_key(cls) -> tuple[str, str]:
        """
        生成新的API Key明文及其公开标识
        :param:
        :return: (key_code, api_key) 元组，key_code用于快速检索，api_key用于返回给调用方
        """
        key_code = secrets.token_hex(8)
        secret = secrets.token_urlsafe(32)
        api_key = f"{cls.API_KEY_PREFIX}_{key_code}.{secret}"
        return key_code, api_key

    @classmethod
    def extract_key_code(cls, api_key: str) -> str:
        """
        从API Key明文中提取公开标识
        :param api_key: API Key明文
        :return: API Key对应的公开标识
        :raise ValueError: 当API Key格式不合法时抛出
        """
        normalized_api_key = (api_key or "").strip()
        prefix = f"{cls.API_KEY_PREFIX}_"
        key_prefix, separator, secret = normalized_api_key.partition(".")
        if not normalized_api_key or separator != "." or not secret or not key_prefix.startswith(prefix):
            raise ValueError("API Key格式不合法")

        key_code = key_prefix[len(prefix):]
        if not key_code:
            raise ValueError("API Key格式不合法")

        return key_code

    @classmethod
    def mask_api_key(cls, api_key: str) -> str:
        """
        生成API Key掩码文本，供列表和详情展示
        :param api_key: API Key明文
        :return: 隐藏中间敏感内容后的展示文本
        """
        normalized_api_key = (api_key or "").strip()
        if len(normalized_api_key) <= 20:
            return normalized_api_key
        return f"{normalized_api_key[:12]}****{normalized_api_key[-6:]}"

    @classmethod
    def get_api_key_hash(cls, api_key: str) -> str:
        """
        计算API Key摘要值，用于接口鉴权校验
        :param api_key: API Key明文
        :return: API Key对应的SHA256摘要
        """
        return hashlib.sha256((api_key or "").encode("utf-8")).hexdigest()

    @classmethod
    def verify_api_key(cls, api_key: str, api_key_hash: str) -> bool:
        """
        校验API Key明文与数据库摘要是否一致
        :param api_key: API Key明文
        :param api_key_hash: 数据库存储的API Key摘要
        :return: 校验结果，True表示一致，False表示不一致
        """
        return secrets.compare_digest(cls.get_api_key_hash(api_key), api_key_hash or "")

    @classmethod
    def encrypt_api_key(cls, api_key: str) -> str:
        """
        对API Key明文进行加密，供后续查看时解密展示
        :param api_key: API Key明文
        :return: 加密后的密文字符串
        """
        return cls.__get_cipher().encrypt((api_key or "").encode("utf-8")).decode("utf-8")

    @classmethod
    def decrypt_api_key(cls, encrypted_api_key: str) -> str:
        """
        解密数据库中保存的API Key密文
        :param encrypted_api_key: API Key密文
        :return: 解密后的API Key明文
        :raise ValueError: 当密文无法解密时抛出
        """
        try:
            return cls.__get_cipher().decrypt((encrypted_api_key or "").encode("utf-8")).decode("utf-8")
        except InvalidToken as exc:
            raise ValueError("API Key密文解密失败") from exc

    @classmethod
    def __get_cipher(cls) -> Fernet:
        """
        构造API Key加解密使用的Fernet对象
        :param:
        :return: 基于服务端密钥派生后的Fernet对象
        """
        secret_key = (JwtConfig.jwt_secret_key or "").encode("utf-8")
        fernet_key = base64.urlsafe_b64encode(hashlib.sha256(secret_key).digest())
        return Fernet(fernet_key)
