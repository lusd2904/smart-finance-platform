/// 交易域数据模型（M4 只读）。契约依据：
/// module_quant/service/longbridge/trade_client.py:62-100,188-222,289+（账户/持仓/订单）
/// module_quant/service/longbridge_quote.py:168-264（盘口十档/逐笔）
/// module_trade/service/auto_trade_service.py:98-111,135-169,216-238（自动交易状态）
/// module_trade/service/platform_ext_service.py:174-189+（风控规则/事件）。
///
/// 安全语义：后端无独立纸面下单端点——POST /trade/order 直连长桥 SDK，
/// 受服务端硬开关 longport_trading_enabled（默认 False）门禁。
/// 客户端 M4 不接入任何下单/撤单写端点，天然处于纸面保护态。
library;

/// 账户资产：GET /trade/account → data（flatten 后平铺键）
class AccountInfo {
  const AccountInfo({
    this.configured = false,
    this.message = '',
    this.currency = '',
    this.totalCash,
    this.availableCash,
    this.netAssets,
  });

  factory AccountInfo.fromJson(Map<String, dynamic> json) {
    // 实测载荷顶层只有 balances[]（多币种），平铺键可能缺省 → 从首条回退。
    final balances = (json['balances'] as List?) ?? const [];
    Map<String, dynamic> pick = const <String, dynamic>{};
    for (final raw in balances) {
      if (raw is! Map) continue;
      final row = raw.cast<String, dynamic>();
      if (pick.isEmpty) pick = row;
      if ((row['currency'] as String?)?.toUpperCase() == 'USD') {
        pick = row;
        break;
      }
    }
    return AccountInfo(
      configured: json['configured'] == true,
      message: (json['message'] as String?) ?? '',
      currency:
          (json['currency'] as String?) ?? (pick['currency'] as String?) ?? '',
      totalCash:
          (json['totalCash'] as num?)?.toDouble() ??
          (pick['totalCash'] as num?)?.toDouble(),
      availableCash:
          (json['availableCash'] as num?)?.toDouble() ??
          (pick['availableCash'] as num?)?.toDouble() ??
          (pick['totalCash'] as num?)?.toDouble(),
      netAssets:
          (json['netAssets'] as num?)?.toDouble() ??
          (pick['netAssets'] as num?)?.toDouble(),
    );
  }

  final bool configured;
  final String message;
  final String currency;
  final double? totalCash;
  final double? availableCash;
  final double? netAssets;
}

/// 持仓行：GET /trade/positions → data.positions[i]
/// 注：服务端不含现价/浮盈，需行情侧自行叠加；M4 只读展示成本口径。
class PositionItem {
  const PositionItem({
    this.symbol = '',
    this.symbolName = '',
    this.quantity,
    this.availableQuantity,
    this.costPrice,
    this.currency = '',
  });

  factory PositionItem.fromJson(Map<String, dynamic> json) => PositionItem(
    symbol: (json['symbol'] as String?) ?? '',
    symbolName: (json['symbolName'] as String?) ?? '',
    quantity: (json['quantity'] as num?)?.toDouble(),
    availableQuantity: (json['availableQuantity'] as num?)?.toDouble(),
    costPrice: (json['costPrice'] as num?)?.toDouble(),
    currency: (json['currency'] as String?) ?? '',
  );

  final String symbol;
  final String symbolName;
  final double? quantity;
  final double? availableQuantity;
  final double? costPrice;
  final String currency;
}

/// 委托单：GET /trade/orders?scope=today|history → data.orders[i]（_map_order 键）
class OrderItem {
  const OrderItem({
    this.orderId,
    this.symbol = '',
    this.stockName = '',
    this.side = '',
    this.status = '',
    this.statusLabel = '',
    this.orderType = '',
    this.quantity,
    this.price,
    this.executedQuantity,
    this.executedPrice,
    this.currency = '',
    this.submittedAt = '',
    this.open = false,
  });

  factory OrderItem.fromJson(Map<String, dynamic> json) => OrderItem(
    orderId: json['orderId']?.toString(),
    symbol: (json['symbol'] as String?) ?? '',
    stockName: (json['stockName'] as String?) ?? '',
    side: (json['side'] as String?) ?? '',
    status: (json['status'] as String?) ?? '',
    statusLabel: (json['statusLabel'] as String?) ?? '',
    orderType: (json['orderType'] as String?) ?? '',
    quantity: (json['quantity'] as num?)?.toDouble(),
    price: (json['price'] as num?)?.toDouble(),
    executedQuantity: (json['executedQuantity'] as num?)?.toDouble(),
    executedPrice: (json['executedPrice'] as num?)?.toDouble(),
    currency: (json['currency'] as String?) ?? '',
    submittedAt: (json['submittedAt'] as String?) ?? '',
    open: json['open'] == true,
  );

  final String? orderId;
  final String symbol;
  final String stockName;
  final String side;
  final String status;
  final String statusLabel;
  final String orderType;
  final double? quantity;
  final double? price;
  final double? executedQuantity;
  final double? executedPrice;
  final String currency;
  final String submittedAt;

  /// 在途单（未终态）：submitted/new/wait_to_new/partial_filled/wait_to_cancel。
  final bool open;

  bool get isBuy => side.toLowerCase().contains('buy') || side == 'BUY';
}

/// 盘口单档：GET /trade/quote/depth → data.asks[i]/bids[i]
class DepthLevel {
  const DepthLevel({this.position = 0, this.price, this.volume, this.size});

  factory DepthLevel.fromJson(Map<String, dynamic> json) => DepthLevel(
    position: (json['position'] as num?)?.toInt() ?? 0,
    price: (json['price'] as num?)?.toDouble(),
    volume: (json['volume'] as num?)?.toInt(),
    size: (json['size'] as num?)?.toInt(),
  );

  /// 档位序号 1~10（1 最贴近现价）。
  final int position;
  final double? price;
  final int? volume;
  final int? size;
}

/// 盘口深度载荷：A股等无深度市场返回 available=false + reason='cn_no_depth'。
class DepthData {
  const DepthData({
    this.configured = false,
    this.available = false,
    this.reason = '',
    this.message = '',
    this.asks = const [],
    this.bids = const [],
  });

  factory DepthData.fromJson(Map<String, dynamic> json) {
    List<DepthLevel> levels(dynamic raw) =>
        ((raw as List<dynamic>?) ?? const [])
            .whereType<Map<String, dynamic>>()
            .map(DepthLevel.fromJson)
            .toList();
    return DepthData(
      configured: json['configured'] == true,
      available: json['available'] == true,
      reason: (json['reason'] as String?) ?? '',
      message: (json['message'] as String?) ?? '',
      asks: levels(json['asks']),
      bids: levels(json['bids']),
    );
  }

  final bool configured;
  final bool available;
  final String reason;
  final String message;
  final List<DepthLevel> asks;
  final List<DepthLevel> bids;
}

/// 逐笔成交：GET /trade/quote/trades → data.trades[i]
class TradeTick {
  const TradeTick({this.time = '', this.price, this.volume, this.side = ''});

  factory TradeTick.fromJson(Map<String, dynamic> json) => TradeTick(
    time: (json['time'] as String?) ?? '',
    price: (json['price'] as num?)?.toDouble(),
    volume: (json['volume'] as num?)?.toInt(),
    side: (json['side'] as String?) ?? '',
  );

  final String time;
  final double? price;
  final int? volume;

  /// buy / sell / neutral
  final String side;
}

/// 自动交易状态：GET /trade/auto/status → data
/// config 内层为 snake_case（DEFAULT_CONFIG 原样展开），guardrails 为 camelCase。
class AutoTradeStatus {
  const AutoTradeStatus({
    this.configured = false,
    this.message = '',
    this.tradingEnabled = false,
    this.autoTradeEnabled = false,
    this.submitAllowed = false,
    this.submitBlockReason = '',
    this.strategyProfile = '',
    this.maxSymbols = 0,
    this.maxDailyOrders = 0,
    this.minConfidence,
    this.requirePaper = true,
    this.todayOrdersCount = 0,
    this.maxDailyNotionalAmount = 0,
    this.todayNotionalAmount = 0,
    this.recentRuns = const [],
    this.recentDecisions = const [],
  });

  factory AutoTradeStatus.fromJson(Map<String, dynamic> json) {
    final config =
        (json['config'] as Map?)?.cast<String, dynamic>() ?? const {};
    final guardrails =
        (json['guardrails'] as Map?)?.cast<String, dynamic>() ?? const {};
    final enabled =
        json['autoTradeEnabled'] == true || json['tradingEnabled'] == true;
    return AutoTradeStatus(
      configured: json['configured'] == true,
      message: (json['message'] as String?) ?? '',
      tradingEnabled: enabled,
      autoTradeEnabled: enabled,
      submitAllowed: json['submitAllowed'] == true,
      submitBlockReason: (json['submitBlockReason'] as String?) ?? '',
      strategyProfile: (config['strategy_profile'] as String?) ?? '',
      maxSymbols: (config['max_symbols'] as num?)?.toInt() ?? 0,
      maxDailyOrders: (config['max_daily_orders'] as num?)?.toInt() ?? 0,
      minConfidence: (config['min_confidence'] as num?)?.toDouble(),
      requirePaper: config['require_paper'] != false,
      todayOrdersCount: (guardrails['todayOrdersCount'] as num?)?.toInt() ?? 0,
      maxDailyNotionalAmount:
          (guardrails['maxDailyNotionalAmount'] as num?)?.toDouble() ?? 0,
      todayNotionalAmount:
          (guardrails['todayNotionalAmount'] as num?)?.toDouble() ?? 0,
      recentRuns: ((json['recentRuns'] as List?) ?? const [])
          .whereType<Map>()
          .map((m) => AutoRun.fromJson(m.cast<String, dynamic>()))
          .toList(),
      recentDecisions: ((json['recentDecisions'] as List?) ?? const [])
          .whereType<Map>()
          .map((m) => AutoDecision.fromJson(m.cast<String, dynamic>()))
          .toList(),
    );
  }

  final bool configured;
  final String message;

  /// 服务端硬开关：false = 纸面保护态（客户端只读的根基）。
  final bool tradingEnabled;

  /// 本账户自动交易开关，与 [tradingEnabled] 同源。
  final bool autoTradeEnabled;
  final bool submitAllowed;
  final String submitBlockReason;
  final String strategyProfile;
  final int maxSymbols;
  final int maxDailyOrders;
  final double? minConfidence;
  final bool requirePaper;
  final int todayOrdersCount;
  final double maxDailyNotionalAmount;
  final double todayNotionalAmount;
  final List<AutoRun> recentRuns;
  final List<AutoDecision> recentDecisions;
}

/// 自动交易运行日志（_serialize_log 键）。
class AutoRun {
  const AutoRun({
    this.runId,
    this.cycleId,
    this.source = '',
    this.strategyProfile = '',
    this.targetCount = 0,
    this.opportunityCount = 0,
    this.submittedOrdersCount = 0,
    this.status = '',
    this.startedAt = '',
    this.finishedAt = '',
  });

  factory AutoRun.fromJson(Map<String, dynamic> json) => AutoRun(
    runId: _toInt(json['runId']),
    cycleId: _toInt(json['cycleId']),
    source: (json['source'] as String?) ?? '',
    strategyProfile: (json['strategyProfile'] as String?) ?? '',
    targetCount: _toInt(json['targetCount']) ?? 0,
    opportunityCount: _toInt(json['opportunityCount']) ?? 0,
    submittedOrdersCount: _toInt(json['submittedOrdersCount']) ?? 0,
    status: (json['status'] as String?) ?? '',
    startedAt: (json['startedAt'] as String?) ?? '',
    finishedAt: (json['finishedAt'] as String?) ?? '',
  );

  final int? runId;
  final int? cycleId;
  final String source;
  final String strategyProfile;
  final int targetCount;
  final int opportunityCount;
  final int submittedOrdersCount;
  final String status;
  final String startedAt;
  final String finishedAt;
}

/// 自动交易决策明细（_serialize_decision 键）。
class AutoDecision {
  const AutoDecision({
    this.decisionId,
    this.symbol = '',
    this.market = '',
    this.side = '',
    this.quantity,
    this.price,
    this.confidence,
    this.status = '',
    this.reason = '',
    this.createTime = '',
  });

  factory AutoDecision.fromJson(Map<String, dynamic> json) => AutoDecision(
    decisionId: _toInt(json['decisionId']),
    symbol: (json['symbol'] as String?) ?? '',
    market: (json['market'] as String?) ?? '',
    side: (json['side'] as String?) ?? '',
    quantity: _toInt(json['quantity']),
    price: _toDouble(json['price']),
    confidence: _toDouble(json['confidence']),
    status: (json['status'] as String?) ?? '',
    reason: (json['reason'] as String?) ?? '',
    createTime: (json['createTime'] as String?) ?? '',
  );

  final int? decisionId;
  final String symbol;
  final String market;
  final String side;
  final int? quantity;
  final double? price;
  final double? confidence;
  final String status;
  final String reason;
  final String createTime;
}

/// 风控规则：GET /trade/risk/rules → data[i]
class RiskRule {
  const RiskRule({
    this.ruleId,
    this.ruleName = '',
    this.ruleType = '',
    this.symbol = '',
    this.threshold,
    this.enabled = false,
    this.remark = '',
  });

  factory RiskRule.fromJson(Map<String, dynamic> json) => RiskRule(
    ruleId: (json['ruleId'] as num?)?.toInt(),
    ruleName: (json['ruleName'] as String?) ?? '',
    ruleType: (json['ruleType'] as String?) ?? '',
    symbol: (json['symbol'] as String?) ?? '',
    threshold: (json['threshold'] as num?)?.toDouble(),
    enabled: json['enabled'] == '1' || json['enabled'] == true,
    remark: (json['remark'] as String?) ?? '',
  );

  final int? ruleId;
  final String ruleName;
  final String ruleType;
  final String symbol;
  final double? threshold;
  final bool enabled;
  final String remark;
}

/// 风控事件：GET /trade/risk/events → data[i]
class RiskEvent {
  const RiskEvent({
    this.eventId,
    this.eventLevel = '',
    this.title = '',
    this.content = '',
    this.symbol = '',
    this.handled = false,
    this.reviewStatusLabel = '',
    this.createTime = '',
  });

  factory RiskEvent.fromJson(Map<String, dynamic> json) => RiskEvent(
    eventId: (json['eventId'] as num?)?.toInt(),
    eventLevel: (json['eventLevel'] as String?) ?? '',
    title: (json['title'] as String?) ?? '',
    content: (json['content'] as String?) ?? '',
    symbol: (json['symbol'] as String?) ?? '',
    handled: json['handled'] == true,
    reviewStatusLabel: (json['reviewStatusLabel'] as String?) ?? '',
    createTime: (json['createTime'] as String?) ?? '',
  );

  final int? eventId;
  final String eventLevel;
  final String title;
  final String content;
  final String symbol;
  final bool handled;
  final String reviewStatusLabel;
  final String createTime;
}

/// 宽容数值转换：服务端部分计数字段（SDK 透传）可能以字符串返回。
int? _toInt(dynamic value) =>
    value is num ? value.toInt() : int.tryParse('$value');

double? _toDouble(dynamic value) =>
    value is num ? value.toDouble() : double.tryParse('$value');
