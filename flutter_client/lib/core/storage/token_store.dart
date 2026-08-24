import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// JWT 持久化。token 属敏感凭据，走系统安全存储而非明文偏好。
class TokenStore {
  TokenStore(this._storage);

  static const _tokenKey = 'auth.token.v1';

  final FlutterSecureStorage _storage;

  Future<String?> read() => _storage.read(key: _tokenKey);

  Future<void> write(String token) =>
      _storage.write(key: _tokenKey, value: token);

  Future<void> clear() => _storage.delete(key: _tokenKey);
}

final tokenStoreProvider = Provider<TokenStore>((ref) {
  // v11 起 Android 默认启用加密数据存储，无需显式 AndroidOptions。
  // macOS：数据保护钥匙串（插件默认）要求正式分发签名（Team 前缀），
  // 开发/直装构建为 ad-hoc 签会报 errSecMissingEntitlement(-34018)；
  // 故 macOS 走传统钥匙串，M5 发布工程切换正式签名后再评估。
  return TokenStore(
    const FlutterSecureStorage(
      mOptions: MacOsOptions(usesDataProtectionKeychain: false),
    ),
  );
});
