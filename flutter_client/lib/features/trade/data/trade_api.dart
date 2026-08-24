import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_client.dart';
import '../../../core/api/api_result.dart';
import 'trade_models.dart';

/// 交易域接口（M4 只读）。契约依据：module_trade/controller/trade_controller.py。
/// 安全红线：不接入 POST /trade/order、POST /trade/order/{id}/cancel、
/// POST /trade/auto/run、PUT /quant/longbridge/config 等写端点；
/// 服务端硬开关（longport_trading_enabled，默认 False）关闭时本域天然为纸面保护态。
class TradeApi {
  TradeApi(this._dio);

  final Dio _dio;

  /// 账户资产。
  Future<AccountInfo> account() async {
    final result = ApiResult.from(await _dio.get<void>('/trade/account'));
    return AccountInfo.fromJson(result.dataAsMap ?? <String, dynamic>{});
  }

  /// 持仓列表。
  Future<List<PositionItem>> positions() async {
    final result = ApiResult.from(await _dio.get<void>('/trade/positions'));
    final items = result.dataAsMap?['positions'];
    return ((items as List<dynamic>?) ?? const [])
        .whereType<Map<String, dynamic>>()
        .map(PositionItem.fromJson)
        .toList();
  }

  /// 委托列表。scope: today | history
  Future<List<OrderItem>> orders({String scope = 'today'}) async {
    final result = ApiResult.from(
      await _dio.get<void>('/trade/orders', queryParameters: {'scope': scope}),
    );
    final items = result.dataAsMap?['orders'];
    return ((items as List<dynamic>?) ?? const [])
        .whereType<Map<String, dynamic>>()
        .map(OrderItem.fromJson)
        .toList();
  }

  /// 盘口十档深度。
  Future<DepthData> depth({
    required String symbol,
    required String market,
  }) async {
    final result = ApiResult.from(
      await _dio.get<void>(
        '/trade/quote/depth',
        queryParameters: {'symbol': symbol, 'market': market},
      ),
    );
    return DepthData.fromJson(result.dataAsMap ?? <String, dynamic>{});
  }

  /// 逐笔成交（最近 count 笔）。
  Future<List<TradeTick>> trades({
    required String symbol,
    required String market,
    int count = 30,
  }) async {
    final result = ApiResult.from(
      await _dio.get<void>(
        '/trade/quote/trades',
        queryParameters: {'symbol': symbol, 'market': market, 'count': count},
      ),
    );
    final items = result.dataAsMap?['trades'];
    return ((items as List<dynamic>?) ?? const [])
        .whereType<Map<String, dynamic>>()
        .map(TradeTick.fromJson)
        .toList();
  }

  /// 自动交易状态（含护栏与近期运行/决策）。
  Future<AutoTradeStatus> autoStatus() async {
    final result = ApiResult.from(await _dio.get<void>('/trade/auto/status'));
    return AutoTradeStatus.fromJson(result.dataAsMap ?? <String, dynamic>{});
  }

  /// 风控规则列表。
  Future<List<RiskRule>> riskRules() async {
    final result = ApiResult.from(await _dio.get<void>('/trade/risk/rules'));
    return ((result.data as List<dynamic>?) ?? const [])
        .whereType<Map<String, dynamic>>()
        .map(RiskRule.fromJson)
        .toList();
  }

  /// 风控事件历史。
  Future<List<RiskEvent>> riskEvents({int limit = 50}) async {
    final result = ApiResult.from(
      await _dio.get<void>(
        '/trade/risk/events',
        queryParameters: {'limit': limit},
      ),
    );
    return ((result.data as List<dynamic>?) ?? const [])
        .whereType<Map<String, dynamic>>()
        .map(RiskEvent.fromJson)
        .toList();
  }
}

final tradeApiProvider = Provider<TradeApi>(
  (ref) => TradeApi(ref.watch(dioProvider)),
);

/// 账户 / 持仓 / 自动交易状态 / 风控 —— autoDispose。
final tradeAccountProvider = FutureProvider.autoDispose<AccountInfo>(
  (ref) => ref.read(tradeApiProvider).account(),
);

final tradePositionsProvider = FutureProvider.autoDispose<List<PositionItem>>(
  (ref) => ref.read(tradeApiProvider).positions(),
);

final tradeOrdersProvider = FutureProvider.autoDispose
    .family<List<OrderItem>, String>(
      (ref, scope) => ref.read(tradeApiProvider).orders(scope: scope),
    );

final tradeAutoStatusProvider = FutureProvider.autoDispose<AutoTradeStatus>(
  (ref) => ref.read(tradeApiProvider).autoStatus(),
);

final riskRulesProvider = FutureProvider.autoDispose<List<RiskRule>>(
  (ref) => ref.read(tradeApiProvider).riskRules(),
);

final riskEventsProvider = FutureProvider.autoDispose<List<RiskEvent>>(
  (ref) => ref.read(tradeApiProvider).riskEvents(),
);

/// 盘口/逐笔按「symbol|market」键取用。
typedef SymbolKey = String;

SymbolKey symbolKey(String symbol, String market) =>
    '${symbol.toUpperCase()}|$market';

final depthProvider = FutureProvider.autoDispose.family<DepthData, SymbolKey>((
  ref,
  key,
) {
  final parts = key.split('|');
  return ref.read(tradeApiProvider).depth(symbol: parts[0], market: parts[1]);
});

final tradesProvider = FutureProvider.autoDispose
    .family<List<TradeTick>, SymbolKey>((ref, key) {
      final parts = key.split('|');
      return ref
          .read(tradeApiProvider)
          .trades(symbol: parts[0], market: parts[1]);
    });
