"""
传输层密钥加载与RSA密钥对管理

拆分自 utils/transport_crypto_util.py，负责密钥对载体的定义、
运行配置校验以及按kid的密钥对加载与轮换兼容。
"""

import json
from dataclasses import dataclass
from threading import Lock

from cryptography.hazmat.primitives import serialization

from config.env import TransportCryptoConfig


@dataclass(frozen=True)
class TransportKeyPair:
    """
    传输层密钥对载体

    kid: 密钥版本标识
    private_key_pem: PEM格式私钥
    public_key_pem: PEM格式公钥
    """

    kid: str
    private_key_pem: str
    public_key_pem: str


# 传输层密钥管理
class TransportKeyProvider:
    """
    传输层密钥提供者
    """

    _lock = Lock()
    _key_pairs: dict[str, TransportKeyPair] | None = None
    _MIN_RSA_KEY_SIZE = 2048
    _RSA_KEY_SIZE_STEP = 256

    @classmethod
    def validate_runtime_configuration(cls) -> None:
        """
        校验传输层加解密运行配置，确保启用时显式配置密钥对

        :return: None
        """
        if not TransportCryptoConfig.transport_crypto_enabled or TransportCryptoConfig.transport_crypto_mode == 'off':
            return

        configured_private_key = cls._normalize_pem(TransportCryptoConfig.transport_crypto_private_key)
        configured_public_key = cls._normalize_pem(TransportCryptoConfig.transport_crypto_public_key)
        rsa_key_size = TransportCryptoConfig.transport_crypto_rsa_key_size

        if rsa_key_size < cls._MIN_RSA_KEY_SIZE or rsa_key_size % cls._RSA_KEY_SIZE_STEP != 0:
            raise ValueError('TRANSPORT_CRYPTO_RSA_KEY_SIZE必须大于等于2048，且为256的整数倍')

        if not configured_private_key or not configured_public_key:
            raise ValueError(
                '启用传输层加解密时，必须显式配置TRANSPORT_CRYPTO_PUBLIC_KEY和TRANSPORT_CRYPTO_PRIVATE_KEY'
            )

        private_key = serialization.load_pem_private_key(configured_private_key.encode('utf-8'), password=None)
        derived_public_key = (
            private_key.public_key()
            .public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )
            .decode('utf-8')
        )
        if cls._normalize_pem(derived_public_key) != configured_public_key:
            raise ValueError('TRANSPORT_CRYPTO_PUBLIC_KEY与TRANSPORT_CRYPTO_PRIVATE_KEY不匹配')

        if TransportCryptoConfig.transport_crypto_legacy_key_pairs:
            cls._build_legacy_key_pairs()

    @classmethod
    def get_current_key_pair(cls) -> TransportKeyPair:
        """
        获取当前启用的密钥对

        :return: 当前启用的密钥对
        """
        if cls._key_pairs is None:
            with cls._lock:
                if cls._key_pairs is None:
                    cls._key_pairs = cls._build_key_pairs()

        return cls._key_pairs[TransportCryptoConfig.transport_crypto_kid]

    @classmethod
    def get_current_kid(cls) -> str:
        """
        获取当前启用的密钥标识

        :return: 当前启用的密钥标识
        """
        return cls.get_current_key_pair().kid

    @classmethod
    def get_public_key_pem(cls, kid: str | None = None) -> str:
        """
        获取公钥PEM

        :param kid: 密钥版本标识，未传入时默认使用当前版本
        :return: PEM格式公钥字符串
        """
        return cls.get_key_pair(kid).public_key_pem

    @classmethod
    def get_private_key_pem(cls, kid: str | None = None) -> str:
        """
        获取私钥PEM

        :param kid: 密钥版本标识，未传入时默认使用当前版本
        :return: PEM格式私钥字符串
        """
        return cls.get_key_pair(kid).private_key_pem

    @classmethod
    def get_key_pair(cls, kid: str | None = None) -> TransportKeyPair:
        """
        根据kid获取密钥对，未传入时返回当前密钥对

        :param kid: 密钥版本标识，未传入时默认使用当前版本
        :return: 匹配到的密钥对
        """
        target_kid = kid or cls.get_current_kid()
        if cls._key_pairs is None:
            with cls._lock:
                if cls._key_pairs is None:
                    cls._key_pairs = cls._build_key_pairs()
        key_pair = cls._key_pairs.get(target_kid)
        if key_pair is None:
            raise ValueError('密钥版本不存在')
        return key_pair

    @classmethod
    def get_supported_kids(cls) -> tuple[str, ...]:
        """
        获取当前支持解密的全部密钥版本

        :return: 当前支持解密的密钥版本元组
        """
        if cls._key_pairs is None:
            cls.get_current_key_pair()
        return tuple(cls._key_pairs.keys())

    @classmethod
    def _build_key_pairs(cls) -> dict[str, TransportKeyPair]:
        """
        构建当前进程可用的全部密钥对映射

        :return: 以kid为键的密钥对映射
        """
        configured_private_key = cls._normalize_pem(TransportCryptoConfig.transport_crypto_private_key)
        configured_public_key = cls._normalize_pem(TransportCryptoConfig.transport_crypto_public_key)
        kid = TransportCryptoConfig.transport_crypto_kid

        if not configured_private_key or not configured_public_key:
            raise ValueError(
                '启用传输层加解密时，必须显式配置TRANSPORT_CRYPTO_PUBLIC_KEY和TRANSPORT_CRYPTO_PRIVATE_KEY'
            )

        key_pairs = {
            kid: TransportKeyPair(kid=kid, private_key_pem=configured_private_key, public_key_pem=configured_public_key)
        }
        key_pairs.update(cls._build_legacy_key_pairs())
        return key_pairs

    @classmethod
    def _build_legacy_key_pairs(cls) -> dict[str, TransportKeyPair]:
        """
        构建历史密钥对映射，用于密钥轮换窗口内的兼容解密

        :return: 以kid为键的历史密钥对映射
        """
        legacy_key_pairs: dict[str, TransportKeyPair] = {}
        configured_legacy_key_pairs = TransportCryptoConfig.transport_crypto_legacy_key_pairs
        if not configured_legacy_key_pairs:
            return legacy_key_pairs

        try:
            parsed_key_pairs = json.loads(configured_legacy_key_pairs)
        except json.JSONDecodeError as exc:
            raise ValueError('传输层历史密钥配置不是合法JSON') from exc

        if not isinstance(parsed_key_pairs, list):
            raise ValueError('传输层历史密钥配置必须是JSON数组')

        for item in parsed_key_pairs:
            if not isinstance(item, dict):
                raise ValueError('传输层历史密钥项必须是JSON对象')
            item_kid = item.get('kid')
            private_key_pem = cls._normalize_pem(item.get('privateKey') or item.get('private_key') or '')
            public_key_pem = cls._normalize_pem(item.get('publicKey') or item.get('public_key') or '')
            if not item_kid or not private_key_pem:
                raise ValueError('传输层历史密钥项必须包含kid和privateKey')
            if not public_key_pem:
                private_key = serialization.load_pem_private_key(private_key_pem.encode('utf-8'), password=None)
                public_key_pem = (
                    private_key.public_key()
                    .public_bytes(
                        encoding=serialization.Encoding.PEM,
                        format=serialization.PublicFormat.SubjectPublicKeyInfo,
                    )
                    .decode('utf-8')
                )
            legacy_key_pairs[str(item_kid)] = TransportKeyPair(
                kid=str(item_kid),
                private_key_pem=private_key_pem,
                public_key_pem=public_key_pem,
            )

        return legacy_key_pairs

    @staticmethod
    def _normalize_pem(pem_value: str) -> str:
        """
        兼容环境变量中的换行转义

        :param pem_value: 原始PEM字符串
        :return: 标准化后的PEM字符串
        """
        return pem_value.replace('\\n', '\n').strip() if pem_value else ''
