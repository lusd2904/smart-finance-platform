/// 量化域数据模型（M3 只读）。契约依据：
/// module_quant/service/factor_qc_service.py:383-403（因子质量）
/// module_quant/service/daily_list_service.py:26-64（次日清单/信号）
/// module_quant/service/quant_service.py:294-321,365-394（扫描台账/详情）
/// module_trade/service/platform_ext_service.py:141-153（8 族权重档位）。
library;

/// 因子质量报告：GET /quant/factor/qc?market=US
class FactorQcReport {
  const FactorQcReport({
    this.ok = false,
    this.market = '',
    this.asOf = '',
    this.symbolCount = 0,
    this.message = '',
    this.items = const [],
  });

  factory FactorQcReport.fromJson(Map<String, dynamic> json) => FactorQcReport(
    ok: json['ok'] == true,
    market: (json['market'] as String?) ?? '',
    asOf: (json['asOf'] as String?) ?? '',
    symbolCount: (json['symbolCount'] as num?)?.toInt() ?? 0,
    message: (json['message'] as String?) ?? '',
    items: ((json['items'] as List<dynamic>?) ?? const [])
        .whereType<Map<String, dynamic>>()
        .map(FactorQcItem.fromJson)
        .toList(),
  );

  final bool ok;
  final String market;
  final String asOf;
  final int symbolCount;
  final String message;
  final List<FactorQcItem> items;
}

/// 单因子质量行：IC/IR 汇总统计 + 五分位收益。
class FactorQcItem {
  const FactorQcItem({
    this.factorKey = '',
    this.factorLabel = '',
    this.family = '',
    this.icMean,
    this.icStd,
    this.ir,
    this.icPositiveRatio,
    this.sampleDates = 0,
    this.quantiles = const {},
    this.spread,
    this.ok = false,
  });

  factory FactorQcItem.fromJson(Map<String, dynamic> json) => FactorQcItem(
    factorKey: (json['factorKey'] as String?) ?? '',
    factorLabel: (json['factorLabel'] as String?) ?? '',
    family: (json['family'] as String?) ?? '',
    icMean: (json['icMean'] as num?)?.toDouble(),
    icStd: (json['icStd'] as num?)?.toDouble(),
    ir: (json['ir'] as num?)?.toDouble(),
    icPositiveRatio: (json['icPositiveRatio'] as num?)?.toDouble(),
    sampleDates: (json['sampleDates'] as num?)?.toInt() ?? 0,
    // 实测载荷把 spread 混在 quantiles 里（q1..q5+spread）；剥离后仅保留分位键。
    quantiles: Map.from(_stringDoubleMap(json['quantiles']))..remove('spread'),
    spread: (json['spread'] as num?)?.toDouble(),
    ok: json['ok'] == true,
  );

  final String factorKey;
  final String factorLabel;
  final String family;
  final double? icMean;
  final double? icStd;
  final double? ir;
  final double? icPositiveRatio;
  final int sampleDates;

  /// 五分位多空收益：q1~q5（单位 %），spread = q5-q1。
  final Map<String, double?> quantiles;
  final double? spread;
  final bool ok;
}

/// 次日策略清单载荷：GET /quant/daily-list → data
class DailyListPayload {
  const DailyListPayload({this.list, this.message = ''});

  factory DailyListPayload.fromJson(Map<String, dynamic> json) =>
      DailyListPayload(
        list: json['list'] is Map<String, dynamic>
            ? DailyListInfo.fromJson(json['list'] as Map<String, dynamic>)
            : null,
        message: (json['message'] as String?) ?? '',
      );

  final DailyListInfo? list;
  final String message;
}

/// 策略清单头 + 信号条目。
class DailyListInfo {
  const DailyListInfo({
    this.listId,
    this.scanDate = '',
    this.tradeDate = '',
    this.profile = '',
    this.status = '',
    this.itemCount = 0,
    this.items = const [],
  });

  factory DailyListInfo.fromJson(Map<String, dynamic> json) => DailyListInfo(
    listId: (json['listId'] as num?)?.toInt(),
    scanDate: (json['scanDate'] as String?) ?? '',
    tradeDate: (json['tradeDate'] as String?) ?? '',
    profile: (json['profile'] as String?) ?? '',
    status: (json['status'] as String?) ?? '',
    itemCount: (json['itemCount'] as num?)?.toInt() ?? 0,
    items: ((json['items'] as List<dynamic>?) ?? const [])
        .whereType<Map<String, dynamic>>()
        .map(SignalItem.fromJson)
        .toList(),
  );

  final int? listId;
  final String scanDate;
  final String tradeDate;
  final String profile;
  final String status;
  final int itemCount;
  final List<SignalItem> items;
}

/// 单条策略信号。
class SignalItem {
  const SignalItem({
    this.itemId,
    this.symbol = '',
    this.market = '',
    this.name = '',
    this.signal = '',
    this.score,
    this.confidence,
    this.reason = '',
    this.status = '',
    this.side = '',
  });

  factory SignalItem.fromJson(Map<String, dynamic> json) => SignalItem(
    itemId: (json['itemId'] as num?)?.toInt(),
    symbol: (json['symbol'] as String?) ?? '',
    market: (json['market'] as String?) ?? '',
    name: (json['name'] as String?) ?? '',
    signal: (json['signal'] as String?) ?? '',
    score: (json['score'] as num?)?.toDouble(),
    confidence: (json['confidence'] as num?)?.toDouble(),
    reason: (json['reason'] as String?) ?? '',
    status: (json['status'] as String?) ?? '',
    side: (json['side'] as String?) ?? '',
  );

  final int? itemId;
  final String symbol;
  final String market;
  final String name;
  final String signal;
  final double? score;
  final double? confidence;
  final String reason;
  final String status;
  final String side;

  bool get isBuy => signal.toUpperCase().contains('BUY');
  bool get isSell => signal.toUpperCase().contains('SELL');
}

/// 扫描台账行：GET /quant/scan-runs → data.items[i]
class ScanRun {
  const ScanRun({
    this.runId,
    this.cycleId,
    this.status = '',
    this.strategyProfile = '',
    this.targetCount = 0,
    this.evaluatedCount = 0,
    this.opportunityCount = 0,
    this.submittedCount = 0,
    this.signalCount = 0,
    this.startedAt = '',
    this.finishedAt = '',
  });

  factory ScanRun.fromJson(Map<String, dynamic> json) => ScanRun(
    runId: (json['runId'] as num?)?.toInt(),
    cycleId: (json['cycleId'] as num?)?.toInt(),
    status: (json['status'] as String?) ?? '',
    strategyProfile: (json['strategyProfile'] as String?) ?? '',
    targetCount: (json['targetCount'] as num?)?.toInt() ?? 0,
    evaluatedCount: (json['evaluatedCount'] as num?)?.toInt() ?? 0,
    opportunityCount: (json['opportunityCount'] as num?)?.toInt() ?? 0,
    submittedCount: (json['submittedCount'] as num?)?.toInt() ?? 0,
    signalCount: (json['signalCount'] as num?)?.toInt() ?? 0,
    startedAt: (json['startedAt'] as String?) ?? '',
    finishedAt: (json['finishedAt'] as String?) ?? '',
  );

  final int? runId;
  final int? cycleId;
  final String status;
  final String strategyProfile;
  final int targetCount;
  final int evaluatedCount;
  final int opportunityCount;
  final int submittedCount;
  final int signalCount;
  final String startedAt;
  final String finishedAt;
}

/// 8 族权重档位：GET /trade/strategy-profiles → data[i]
class StrategyProfile {
  const StrategyProfile({
    this.profileCode = '',
    this.profileName = '',
    this.buyThreshold,
    this.sellThreshold,
    this.weights = const {},
    this.updateTime = '',
  });

  factory StrategyProfile.fromJson(Map<String, dynamic> json) {
    final config = _stringDynamicMap(json['config']);
    final rawWeights = _stringDoubleMap(config?['weights']);
    return StrategyProfile(
      profileCode: (json['profileCode'] as String?) ?? '',
      profileName: (json['profileName'] as String?) ?? '',
      buyThreshold: (config?['buyThreshold'] as num?)?.toInt(),
      sellThreshold: (config?['sellThreshold'] as num?)?.toInt(),
      weights: rawWeights,
      updateTime: (json['updateTime'] as String?) ?? '',
    );
  }

  /// conservative / balanced / aggressive
  final String profileCode;
  final String profileName;
  final int? buyThreshold;
  final int? sellThreshold;

  /// 8 族权重键：trend/priceAction/momentum/breakout/volumeFlow/reversion/volatility/liquidity
  final Map<String, double> weights;
  final String updateTime;

  static const familyLabels = <String, String>{
    'trend': '趋势',
    'priceAction': '价格形态',
    'momentum': '动量',
    'breakout': '突破',
    'volumeFlow': '量流',
    'reversion': '反转',
    'volatility': '波动',
    'liquidity': '流动性',
  };

  /// 雷达图轴标签与归一值（按最大权重归一）。
  List<String> get radarAxes =>
      weights.keys.map((k) => familyLabels[k] ?? k).toList(growable: false);

  List<double> get radarValues {
    final maxW = weights.values.fold(0.0, (m, v) => v > m ? v : m);
    if (maxW <= 0) return weights.values.map((_) => 0.0).toList();
    return weights.values.map((v) => (v / maxW).clamp(0.0, 1.0)).toList();
  }
}

/// 宽容提取嵌套 Map：服务端/测试字面量可能产生 `<dynamic, dynamic>` 键型。
Map<String, dynamic>? _stringDynamicMap(dynamic value) =>
    value is Map ? value.map((k, v) => MapEntry(k.toString(), v)) : null;

Map<String, double> _stringDoubleMap(dynamic value) {
  if (value is! Map) return const {};
  return value.map(
    (k, v) => MapEntry(k.toString(), (v as num?)?.toDouble() ?? 0.0),
  );
}
