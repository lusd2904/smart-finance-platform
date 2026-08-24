import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:flutter_client/core/gateway/gateway_config.dart';

/// 网关配置持久化。desktop 存 userDataDir/gateway.json，这里等价存 SharedPreferences。
class GatewayStore {
  GatewayStore(this._prefs);

  static const _storageKey = 'gateway.config.v1';

  final SharedPreferences _prefs;

  GatewayConfig load() {
    final raw = _prefs.getString(_storageKey);
    if (raw == null || raw.isEmpty) return const GatewayConfig();
    try {
      return GatewayConfig.fromJson(jsonDecode(raw) as Map<String, dynamic>);
    } catch (_) {
      // 配置损坏时回到未配置态，让用户重新走探测流程。
      return const GatewayConfig();
    }
  }

  Future<void> save(GatewayConfig config) =>
      _prefs.setString(_storageKey, jsonEncode(config.toJson()));
}

/// 由 main() 注入已初始化的 SharedPreferences 实例。
final sharedPreferencesProvider = Provider<SharedPreferences>((ref) {
  throw UnimplementedError('main() 中 override');
});

final gatewayStoreProvider =
    Provider<GatewayStore>((ref) => GatewayStore(ref.watch(sharedPreferencesProvider)));
