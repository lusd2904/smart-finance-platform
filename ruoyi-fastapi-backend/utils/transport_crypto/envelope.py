"""
传输层报文信封加解密

拆分自 utils/transport_crypto_util.py，负责请求信封的解密、
响应体的AES-GCM加密封装以及公钥/前端配置载荷构建。
"""

import base64
import json
import os
import time
from dataclasses import dataclass
from typing import Any

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from config.env import TransportCryptoConfig
from utils.transport_crypto.keys import TransportKeyProvider


# 通用编码辅助
def _urlsafe_b64encode(data: bytes) -> str:
    """
    将字节串编码为URL安全的Base64字符串

    :param data: 原始字节串
    :return: URL安全的Base64字符串
    """
    return base64.urlsafe_b64encode(data).decode('utf-8').rstrip('=')


def _urlsafe_b64decode(data: str) -> bytes:
    """
    将URL安全的Base64字符串解码为字节串

    :param data: URL安全的Base64字符串
    :return: 解码后的字节串
    """
    padding_length = (-len(data)) % 4
    return base64.urlsafe_b64decode(f'{data}{"=" * padding_length}'.encode())


# 传输层数据载体
@dataclass(frozen=True)
class DecryptedTransportEnvelope:
    """
    请求信封解密结果

    kid: 请求使用的密钥版本标识
    nonce: 请求随机数
    timestamp: 请求时间戳
    aes_key: 当前请求协商出的AES会话密钥
    aad: 通过校验后的AAD上下文
    plaintext: 解密得到的原始请求载荷
    """

    kid: str
    nonce: str
    timestamp: int
    aes_key: bytes
    aad: dict[str, str]
    plaintext: bytes


# 传输层加解密核心能力
class TransportCryptoUtil:
    """
    传输层加解密工具
    """

    _ENVELOPE_VERSION = '1'
    _RESPONSE_ENVELOPE_ALGORITHM = 'AES_256_GCM'
    _REQUIRED_ENVELOPE_FIELDS = ('kid', 'ts', 'nonce', 'ek', 'iv', 'ct', 'aad')

    @classmethod
    def get_response_envelope_algorithm(cls) -> str:
        """
        获取响应信封算法标识

        :return: 响应信封算法标识
        """
        return cls._RESPONSE_ENVELOPE_ALGORITHM

    @classmethod
    def decrypt_envelope(
        cls,
        envelope: dict[str, Any],
        expected_method: str,
        expected_path: str,
    ) -> DecryptedTransportEnvelope:
        """
        解密请求信封

        :param envelope: 请求加密信封
        :param expected_method: 当前请求预期HTTP方法
        :param expected_path: 当前请求预期路径
        :return: 解密后的请求信封对象
        """
        cls._validate_envelope(envelope)
        kid = str(envelope['kid'])
        aad = cls._extract_and_validate_aad(envelope, expected_method, expected_path)
        aes_key = cls.decrypt_request_key(envelope)
        iv = _urlsafe_b64decode(str(envelope['iv']))
        ciphertext = _urlsafe_b64decode(str(envelope['ct']))
        plaintext = AESGCM(aes_key).decrypt(iv, ciphertext, cls._build_aad_bytes(aad))

        return DecryptedTransportEnvelope(
            kid=kid,
            nonce=str(envelope['nonce']),
            timestamp=int(envelope['ts']),
            aes_key=aes_key,
            aad=aad,
            plaintext=plaintext,
        )

    @classmethod
    def decrypt_request_key(cls, envelope: dict[str, Any]) -> bytes:
        """
        仅解出请求中的AES会话密钥，用于异常场景构造加密错误响应

        :param envelope: 请求加密信封
        :return: 请求协商出的AES会话密钥
        """
        kid = str(envelope['kid'])
        private_key_pem = TransportKeyProvider.get_private_key_pem(kid)
        private_key = serialization.load_pem_private_key(private_key_pem.encode('utf-8'), password=None)
        encrypted_key = _urlsafe_b64decode(str(envelope['ek']))
        return private_key.decrypt(
            encrypted_key,
            padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None),
        )

    @classmethod
    def encrypt_response_body(
        cls,
        aes_key: bytes,
        payload: bytes,
        kid: str,
        method: str,
        path: str,
    ) -> bytes:
        """
        使用请求协商出的AES密钥加密响应体

        :param aes_key: 请求协商出的AES会话密钥
        :param payload: 需要加密的响应体字节串
        :param kid: 当前使用的密钥版本标识
        :param method: 当前HTTP请求方法
        :param path: 当前HTTP请求路径
        :return: 加密后的响应体字节串
        """
        iv = os.urandom(12)
        aad = {'method': method.upper(), 'path': path, 'direction': 'response'}
        ciphertext = AESGCM(aes_key).encrypt(iv, payload, cls._build_aad_bytes(aad))
        encrypted_payload = {
            'v': cls._ENVELOPE_VERSION,
            'kid': kid,
            'alg': cls._RESPONSE_ENVELOPE_ALGORITHM,
            'aad': aad,
            'iv': _urlsafe_b64encode(iv),
            'ct': _urlsafe_b64encode(ciphertext),
        }
        return json.dumps(encrypted_payload, ensure_ascii=False).encode('utf-8')

    @classmethod
    def decode_query_envelope(cls, encrypted_query: str) -> dict[str, Any]:
        """
        解码查询参数中的加密信封

        :param encrypted_query: 查询参数中的加密信封字符串
        :return: 解码后的信封字典
        """
        decoded_query = _urlsafe_b64decode(encrypted_query).decode('utf-8')
        return json.loads(decoded_query)

    @classmethod
    def build_public_key_payload(cls) -> dict[str, Any]:
        """
        构建公钥下发载荷

        :return: 公钥下发载荷字典
        """
        return {
            'kid': TransportKeyProvider.get_current_kid(),
            'envelopeVersion': cls._ENVELOPE_VERSION,
            'alg': TransportCryptoConfig.transport_crypto_algorithm,
            'publicKey': TransportKeyProvider.get_public_key_pem(),
            'supportedKids': TransportKeyProvider.get_supported_kids(),
            'expireAt': int(time.time()) + TransportCryptoConfig.transport_crypto_public_key_ttl_seconds,
        }

    @classmethod
    def build_frontend_config_payload(cls) -> dict[str, Any]:
        """
        构建前端传输层加解密运行配置载荷

        :return: 前端传输层加解密运行配置载荷字典
        """
        transport_crypto_active = (
            TransportCryptoConfig.transport_crypto_enabled and TransportCryptoConfig.transport_crypto_mode != 'off'
        )
        return {
            'transportCryptoEnabled': TransportCryptoConfig.transport_crypto_enabled,
            'transportCryptoMode': TransportCryptoConfig.transport_crypto_mode,
            'transportCryptoActive': transport_crypto_active,
            'envelopeVersion': cls._ENVELOPE_VERSION,
            'publicKeyUrl': '/transport/crypto/public-key',
            'requestEnvelopeAlgorithm': TransportCryptoConfig.transport_crypto_algorithm,
            'responseEnvelopeAlgorithm': cls.get_response_envelope_algorithm(),
            'enabledPaths': cls._split_paths(TransportCryptoConfig.transport_crypto_enabled_paths),
            'requiredPaths': cls._split_paths(TransportCryptoConfig.transport_crypto_required_paths),
            'excludePaths': cls._split_paths(TransportCryptoConfig.transport_crypto_exclude_paths),
            'maxEncryptedGetUrlLength': TransportCryptoConfig.transport_crypto_max_get_url_length,
            'configExpireAt': int(time.time()) + TransportCryptoConfig.transport_crypto_frontend_config_ttl_seconds,
        }

    @classmethod
    def _validate_envelope(cls, envelope: dict[str, Any]) -> None:
        """
        校验请求加密信封的结构、协议版本与算法是否有效

        :param envelope: 请求加密信封
        :return: None
        """
        if not isinstance(envelope, dict):
            raise ValueError('加密请求信封格式不合法')

        missing_fields = [field_name for field_name in cls._REQUIRED_ENVELOPE_FIELDS if not envelope.get(field_name)]
        if missing_fields:
            raise ValueError(f'加密请求缺少必要字段: {",".join(missing_fields)}')

        if str(envelope.get('v', '')) != cls._ENVELOPE_VERSION:
            raise ValueError('加密请求协议版本不受支持')

        if str(envelope.get('alg', '')) != TransportCryptoConfig.transport_crypto_algorithm:
            raise ValueError('加密请求算法不受支持')

    @classmethod
    def _extract_and_validate_aad(
        cls,
        envelope: dict[str, Any],
        expected_method: str,
        expected_path: str,
    ) -> dict[str, str]:
        """
        提取并校验请求AAD，确保密文与当前接口绑定

        :param envelope: 请求加密信封
        :param expected_method: 当前请求预期HTTP方法
        :param expected_path: 当前请求预期路径
        :return: 归一化后的AAD字典
        """
        aad = envelope.get('aad')
        if not isinstance(aad, dict):
            raise ValueError('加密请求缺少合法的aad')

        method = str(aad.get('method', '')).upper()
        path = str(aad.get('path', ''))
        if method != expected_method.upper() or path != expected_path:
            raise ValueError('加密请求的method/path与当前接口不匹配')

        return {'method': method, 'path': path}

    @staticmethod
    def _build_aad_bytes(aad: dict[str, str]) -> bytes:
        """
        将AAD字典序列化为AES-GCM additionalData所需字节串

        :param aad: AAD字典
        :return: 序列化后的AAD字节串
        """
        return json.dumps(aad, ensure_ascii=False, separators=(',', ':')).encode('utf-8')

    @staticmethod
    def _split_paths(path_value: str) -> list[str]:
        """
        将逗号分隔的路径配置拆分为列表

        :param path_value: 原始路径配置
        :return: 路径列表
        """
        return [path.strip() for path in path_value.split(',') if path.strip()]
