import base64
import hashlib

from cryptography.fernet import Fernet

from config.env import AppConfig, JwtConfig
from exceptions.exception import ServiceException


class CryptoUtil:
    """
    加解密工具类
    """

    _cipher_suite = None

    @classmethod
    def _get_cipher_suite(cls) -> Fernet:
        if cls._cipher_suite is None:
            # 优先使用独立的凭据加密密钥，与 JWT secret 解耦以便独立轮换；
            # 未配置时回退到 JWT secret 派生（兼容存量部署），但生产环境强制要求独立密钥。
            credential_key = getattr(JwtConfig, 'credential_encryption_key', '') or ''
            source = credential_key.strip() or JwtConfig.jwt_secret_key
            if AppConfig.app_env == 'prod' and not credential_key.strip():
                raise ServiceException(
                    '安全检查失败：生产环境必须配置 CREDENTIAL_ENCRYPTION_KEY（与 JWT_SECRET_KEY 独立），'
                    '用于加密库内券商凭据等敏感数据。'
                )
            # SHA256 hash (32 bytes) -> Base64 encoded (44 bytes) -> Fernet key
            key = base64.urlsafe_b64encode(hashlib.sha256(source.encode()).digest())
            cls._cipher_suite = Fernet(key)
        return cls._cipher_suite

    @classmethod
    def encrypt(cls, data: str) -> str:
        """
        加密字符串

        :param data: 明文
        :return: 密文
        """
        if not data:
            return data
        try:
            cipher_suite = cls._get_cipher_suite()
            encrypted_bytes = cipher_suite.encrypt(data.encode('utf-8'))
            return encrypted_bytes.decode('utf-8')
        except Exception as e:
            raise ServiceException('加密失败') from e

    @classmethod
    def decrypt(cls, token: str) -> str:
        """
        解密字符串

        :param token: 密文
        :return: 明文
        """
        if not token:
            return token
        try:
            cipher_suite = cls._get_cipher_suite()
            decrypted_bytes = cipher_suite.decrypt(token.encode('utf-8'))
            return decrypted_bytes.decode('utf-8')
        except Exception as e:
            raise ServiceException('解密失败') from e
