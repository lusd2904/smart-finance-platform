import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:flutter_client/core/gateway/gateway_config.dart';
import 'package:flutter_client/core/gateway/gateway_probe.dart';
import 'package:flutter_client/core/gateway/gateway_store.dart';

/// 网关配置状态：内存态 + SharedPreferences 持久化。
class GatewayController extends Notifier<GatewayConfig> {
  @override
  GatewayConfig build() => ref.watch(gatewayStoreProvider).load();

  Future<void> _persist(GatewayConfig next) async {
    await ref.read(gatewayStoreProvider).save(next);
    state = next;
  }

  /// 探测通过才落盘（记录 lastGood）；失败原样返回结果，配置不动。
  Future<ProbeResult> probeAndSave(String rawUrl) async {
    final result = await probeGateway(rawUrl);
    if (!result.ok) return result;
    final origin = result.origin ?? normalizeGateway(rawUrl);
    await _persist(
      GatewayConfig(
        url: origin,
        confirmOnLaunch: state.confirmOnLaunch,
        lastGoodUrl: origin,
        lastGoodAt: DateTime.now(),
      ),
    );
    return result;
  }

  /// 登录页填写网关后直接生效，不强制探测（避免卡在探测页）。
  Future<void> applyUrl(String rawUrl) async {
    final origin = normalizeGateway(rawUrl);
    if (origin.isEmpty) {
      throw const GatewayFormatException('请填写网关地址');
    }
    await _persist(
      GatewayConfig(
        url: origin,
        confirmOnLaunch: state.confirmOnLaunch,
        lastGoodUrl: state.lastGoodUrl,
        lastGoodAt: state.lastGoodAt,
      ),
    );
  }

  Future<void> reset() => _persist(const GatewayConfig());
}

final gatewayController = NotifierProvider<GatewayController, GatewayConfig>(
  GatewayController.new,
);
