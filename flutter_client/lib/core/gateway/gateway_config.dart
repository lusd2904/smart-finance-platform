/// 未配置时的默认网关：线上前端入口。本机 Docker / 模拟器仍可在网关页手动改。
const kDefaultGateway = 'https://sfp.luapi.top';

String suggestedLocalGateway() => kDefaultGateway;

/// 模拟器环回地址在真机上不可达；当作未配置，回落到线上网关。
String resolveStoredGateway(String stored) {
  final u = stored.trim().toLowerCase();
  if (u.isEmpty || u.contains('10.0.2.2') || u.contains('10.0.3.2')) {
    return kDefaultGateway;
  }
  return stored.trim();
}

/// 网关配置（与 desktop/src/gateway.js 的 gateway.json 结构对齐）。
class GatewayConfig {
  const GatewayConfig({
    this.url = '',
    this.confirmOnLaunch = true,
    this.lastGoodUrl,
    this.lastGoodAt,
  });

  factory GatewayConfig.fromJson(Map<String, dynamic> json) => GatewayConfig(
    url: (json['url'] as String?) ?? '',
    confirmOnLaunch: (json['confirmOnLaunch'] as bool?) ?? true,
    lastGoodUrl: json['lastGoodUrl'] as String?,
    lastGoodAt: json['lastGoodAt'] == null
        ? null
        : DateTime.tryParse(json['lastGoodAt'] as String),
  );

  /// 当前生效网关地址（已规范化的 origin），空串表示未配置。
  final String url;
  final bool confirmOnLaunch;
  final String? lastGoodUrl;
  final DateTime? lastGoodAt;

  Map<String, dynamic> toJson() => {
    'url': url,
    'confirmOnLaunch': confirmOnLaunch,
    'lastGoodUrl': lastGoodUrl,
    'lastGoodAt': lastGoodAt?.toIso8601String(),
  };

  GatewayConfig copyWith({
    String? url,
    bool? confirmOnLaunch,
    String? lastGoodUrl,
    DateTime? lastGoodAt,
  }) => GatewayConfig(
    url: url ?? this.url,
    confirmOnLaunch: confirmOnLaunch ?? this.confirmOnLaunch,
    lastGoodUrl: lastGoodUrl ?? this.lastGoodUrl,
    lastGoodAt: lastGoodAt ?? this.lastGoodAt,
  );
}

/// 预设项文案与 desktop 网关配置窗一致。
class GatewayPreset {
  const GatewayPreset(this.id, this.label, this.url, this.hint);
  final String id;
  final String label;
  final String url;
  final String hint;
}

const gatewayPresets = <GatewayPreset>[
  GatewayPreset(
    'cloud',
    '线上 HTTPS',
    kDefaultGateway,
    '生产前端网关 sfp.luapi.top，业务接口走 /docker-api',
  ),
  GatewayPreset(
    'local-docker',
    '本机 Docker',
    'http://127.0.0.1:12580',
    'docker-compose.sentiment.yml 默认前端网关，已代理 /docker-api',
  ),
  GatewayPreset(
    'android-emulator',
    'Android 模拟器',
    'http://10.0.2.2:12580',
    '模拟器访问宿主机环回',
  ),
  GatewayPreset(
    'lan',
    '局域网',
    'http://192.168.1.10:12580',
    '把 IP 换成这台机器在局域网中的地址',
  ),
];
