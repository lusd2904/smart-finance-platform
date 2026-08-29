import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_client.dart';
import '../../../core/api/api_result.dart';
import 'trade_models.dart';

/// 交易域接口。契约依据：module_trade/controller/trade_controller.py。
class TradeApi {
  TradeApi(this._dio);

  final Dio _dio;

  /// 账户资产。
  Future<AccountInfo> account() async {
    final result = ApiResult.from(
      await _dio.get<void>(
        '/trade/account',
        options: Options(receiveTimeout: const Duration(seconds: 15)),
      ),
    );
    return AccountInfo.fromJson(result.dataAsMap ?? <String, dynamic>{});
  }

  /// 持仓列表。
  Future<List<PositionItem>> positions() async {
    final result = ApiResult.from(await _dio.get<void>('/trade/positions'));
    return asJsonList(result.dataAsMap?['positions'])
        .whereType<Map<String, dynamic>>()
        .map(PositionItem.fromJson)
        .toList();
  }

  /// 委托列表。scope: today | history
  Future<List<OrderItem>> orders({String scope = 'today'}) async {
    final result = ApiResult.from(
      await _dio.get<void>('/trade/orders', queryParameters: {'scope': scope}),
    );
    return asJsonList(result.dataAsMap?['orders'])
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
        options: Options(receiveTimeout: const Duration(seconds: 15)),
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
        options: Options(receiveTimeout: const Duration(seconds: 15)),
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

  Future<AutoTradeStatus> getAutoTradeStatus() => autoStatus();

  /// 紧急停机。PUT /trade/halt
  Future<Map<String, dynamic>> setHalt({required bool halted, String reason = ''}) async {
    final result = ApiResult.from(
      await _dio.put<void>(
        '/trade/halt',
        data: <String, dynamic>{'halted': halted, 'reason': reason},
      ),
    );
    return result.dataAsMap ?? <String, dynamic>{'halted': halted};
  }

  /// 保存本账户自动交易开关。PUT /trade/auto/settings
  Future<AutoTradeStatus> saveAutoTradeSettings({
    required bool autoTradeEnabled,
    double? dailyBuyRatio,
  }) async {
    final result = ApiResult.from(
      await _dio.put<void>(
        '/trade/auto/settings',
        data: <String, dynamic>{
          'autoTradeEnabled': autoTradeEnabled,
          'dailyBuyRatio': ?dailyBuyRatio,
        },
      ),
    );
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

  /// 交易侧 K 线（长桥/时序库，含 quote）。
  Future<Map<String, dynamic>> quoteKline({
    required String symbol,
    required String market,
    String period = 'daily',
    int limit = 200,
  }) async {
    final result = ApiResult.from(
      await _dio.get<void>(
        '/trade/quote/kline',
        queryParameters: {
          'symbol': symbol,
          'market': market,
          'period': period,
          'limit': limit,
        },
        options: Options(receiveTimeout: const Duration(seconds: 60)),
      ),
    );
    return result.dataAsMap ?? <String, dynamic>{};
  }

  /// 长桥补缺快照：估值/换手/量比/市值。库里已有字段由页面保留。
  Future<Map<String, dynamic>> quoteSnapshot({
    required String symbol,
    required String market,
  }) async {
    final result = ApiResult.from(
      await _dio.get<void>(
        '/trade/quote/snapshot',
        queryParameters: {'symbol': symbol, 'market': market},
        options: Options(receiveTimeout: const Duration(seconds: 20)),
      ),
    );
    return result.dataAsMap ?? <String, dynamic>{};
  }

  Future<PositionQuote> positionQuote({required String symbol, required String market}) async {
    final data = await quoteSnapshot(symbol: symbol, market: market);
    final nested = asJsonMap(data['quote']) ?? const <String, dynamic>{};
    return PositionQuote(
      last: asDouble(data['last'] ?? data['lastDone'] ?? nested['last'] ?? nested['lastDone']),
      prevClose: asDouble(data['prevClose'] ?? nested['prevClose']),
    );
  }

  /// 长桥批量实时行情：GET /trade/quote/realtime
  Future<List<Map<String, dynamic>>> realtimeQuotes(List<String> symbols) async {
    final codes = symbols.map((s) => s.trim()).where((s) => s.isNotEmpty).toList();
    if (codes.isEmpty) return const [];
    final result = ApiResult.from(
      await _dio.get<void>(
        '/trade/quote/realtime',
        queryParameters: {'symbols': codes.join(',')},
        options: Options(receiveTimeout: const Duration(seconds: 20)),
      ),
    );
    return asJsonList(result.dataAsMap?['quotes']).whereType<Map<String, dynamic>>().toList();
  }

  Future<Map<String, PositionQuote>> quotesFor(List<PositionItem> items) async {
    final out = <String, PositionQuote>{
      for (final p in items)
        if (p.asQuote != null) p.symbol: p.asQuote!,
    };
    final missing = items.where((p) => out[p.symbol] == null).toList();
    if (missing.isEmpty) return out;
    try {
      final rows = await realtimeQuotes([
        for (final p in missing) p.symbol.contains('.') ? p.symbol : '${p.quoteSymbol}.${p.market}',
      ]);
      for (final p in missing) {
        final hit = _matchQuote(rows, p);
        if (hit == null) continue;
        out[p.symbol] = PositionQuote(
          last: asDouble(hit['lastDone'] ?? hit['last']),
          prevClose: asDouble(hit['prevClose']),
        );
      }
    } catch (_) {
      await Future.wait(missing.map((p) async {
        try {
          final raw = p.symbol.contains('.') ? p.symbol : p.quoteSymbol;
          out[p.symbol] = await positionQuote(symbol: raw, market: p.market);
        } catch (_) {}
      }));
    }
    return out;
  }

  static Map<String, dynamic>? _matchQuote(List<Map<String, dynamic>> rows, PositionItem p) {
    final want = <String>{
      p.symbol.toUpperCase(),
      p.quoteSymbol.toUpperCase(),
      '${p.quoteSymbol}.${p.market}'.toUpperCase(),
    };
    for (final row in rows) {
      final sym = asString(row['symbol']).toUpperCase();
      if (want.contains(sym) || want.contains(sym.split('.').first)) return row;
    }
    return null;
  }

  /// 美元兑港元。取不到时返回 null，由页面回退。
  Future<double?> usdHkdRate() async {
    try {
      final rows = await realtimeQuotes(const ['USDHKD']);
      final last = asDouble(rows.isEmpty ? null : (rows.first['lastDone'] ?? rows.first['last']));
      if (last == null || last <= 0) return null;
      return last < 1 ? 1 / last : last;
    } catch (_) {
      return null;
    }
  }

  /// 快捷下单。服务端按本账户自动交易开关与长桥凭据决定是否真实提交。
  Future<Map<String, dynamic>> submitOrder({
    required String symbol,
    required String market,
    required String side,
    required String orderType,
    required int quantity,
    double? price,
  }) async {
    final result = ApiResult.from(
      await _dio.post<void>(
        '/trade/order',
        data: <String, dynamic>{
          'symbol': symbol,
          'market': market,
          'side': side,
          'orderType': orderType,
          'quantity': quantity,
          'price': ?price,
        },
        options: Options(receiveTimeout: const Duration(seconds: 60)),
      ),
    );
    return result.dataAsMap ?? <String, dynamic>{'message': result.msg};
  }

  /// 撤单。
  Future<Map<String, dynamic>> cancelOrder(String orderId) async {
    final result = ApiResult.from(
      await _dio.post<void>('/trade/order/${Uri.encodeComponent(orderId)}/cancel'),
    );
    return result.dataAsMap ?? <String, dynamic>{'message': result.msg};
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

/// 持仓现价：优先用 /trade/positions 已叠加的长桥行情，缺的再批量补。
final positionQuotesProvider =
    FutureProvider.autoDispose<Map<String, PositionQuote>>((ref) async {
  final items = await ref.watch(tradePositionsProvider.future);
  if (items.isEmpty) return const {};
  return ref.read(tradeApiProvider).quotesFor(items);
});

/// 美元兑港元；取不到时用联系汇率中枢。
final usdHkdRateProvider = FutureProvider.autoDispose<double>((ref) async {
  return await ref.read(tradeApiProvider).usdHkdRate() ?? UsdHkdFx.fallbackRate;
});

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
