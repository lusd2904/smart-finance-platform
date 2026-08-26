import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../gateway/gateway_store.dart';

/// JWT 持久化。手机走系统安全存储；macOS 开发签名会反复弹出钥匙串授权，
/// 桌面端改用本机偏好（与网关地址同一套 SharedPreferences）。
class TokenStore {
  TokenStore({this._storage, this._prefs});

  static const _tokenKey = 'auth.token.v1';

  final FlutterSecureStorage? _storage;
  final SharedPreferences? _prefs;
  String? _memory;

  Future<String?> read() async {
    if (_memory != null && _memory!.isNotEmpty) return _memory;
    try {
      if (_prefs != null) {
        _memory = _prefs.getString(_tokenKey);
      } else {
        _memory = await _storage?.read(key: _tokenKey);
      }
    } catch (_) {}
    return _memory;
  }

  Future<void> write(String token) async {
    _memory = token;
    try {
      if (_prefs != null) {
        await _prefs.setString(_tokenKey, token);
      } else {
        await _storage?.write(key: _tokenKey, value: token);
      }
    } catch (_) {}
  }

  Future<void> clear() async {
    _memory = null;
    try {
      if (_prefs != null) {
        await _prefs.remove(_tokenKey);
      } else {
        await _storage?.delete(key: _tokenKey);
      }
    } catch (_) {}
  }
}

final tokenStoreProvider = Provider<TokenStore>((ref) {
  final macosDesktop = !kIsWeb && defaultTargetPlatform == TargetPlatform.macOS;
  if (macosDesktop) {
    return TokenStore(prefs: ref.watch(sharedPreferencesProvider));
  }
  return TokenStore(storage: const FlutterSecureStorage());
});
