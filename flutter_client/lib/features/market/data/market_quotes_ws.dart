import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

import '../../../core/gateway/gateway_controller.dart';
import '../../../core/storage/token_store.dart';
import '../../market/data/market_models.dart';

/// 行情指数实时通道（M5 WS 通道客户端侧）。
/// 契约依据：module_market/controller/market_ws_controller.py
/// （WS /ws/market/quotes?interval=15，开帧 {type:auth,token}，载荷与 /market/index/quotes data 一致）。
/// interval=15 避免 stampede 后端 Redis CACHE_TTL=30s。
///
/// 语义：
/// - 断线自动重连（指数退避 2s→16s 封顶），连接期间持续推送；
/// - 连接失败/未授权时流以错误结束，行情页回退到既有一次性轮询展示。

class MarketQuoteStream {
  const MarketQuoteStream({this.items = const [], this.asOf = ''});

  final List<IndexQuote> items;
  final String asOf;
}

/// 解析指数快照。quotes 通道没有 data.items，返回 null 以免冲掉指数。
MarketQuoteStream? parseMarketQuotesMessage(Object message) {
  if (message is String && (message == 'ping' || message == 'pong')) {
    return null;
  }
  final body = message is String
      ? jsonDecode(message) as Map<String, dynamic>
      : message as Map<String, dynamic>;
  if (body['channel'] == 'quotes') return null;
  final raw = body['data'];
  if (raw is! Map) return null;
  final data = raw.cast<dynamic, dynamic>();
  final items = ((data['items'] as List?) ?? const [])
      .whereType<Map>()
      .map((m) => IndexQuote.fromJson(m.cast<String, dynamic>()))
      .toList();
  return MarketQuoteStream(items: items, asOf: (data['asOf'] as String?) ?? '');
}

/// 个股最新价推送：WS channel=quotes。
class LiveStockQuote {
  const LiveStockQuote({
    required this.symbol,
    required this.market,
    this.last,
    this.changePct,
    this.quoteTime = '',
    this.source = '',
  });

  final String symbol;
  final String market;
  final double? last;
  final double? changePct;
  final String quoteTime;
  final String source;

  String get key => '${market.toUpperCase()}:${symbol.toUpperCase()}';
}

LiveStockQuote? liveStockQuoteFromJson(Map<String, dynamic> json) {
  final symbol = (json['symbol'] as String?)?.trim() ?? '';
  if (symbol.isEmpty) return null;
  final last = (json['last'] as num?)?.toDouble();
  final chg = (json['changePct'] as num?)?.toDouble() ?? (json['changeRate'] as num?)?.toDouble();
  return LiveStockQuote(
    symbol: symbol.toUpperCase(),
    market: ((json['market'] as String?) ?? 'US').toUpperCase(),
    last: last,
    changePct: chg,
    quoteTime: (json['quoteTime'] as String?) ?? '',
    source: (json['source'] as String?) ?? '',
  );
}

/// 解析个股 quotes 通道；其它帧返回 null。
List<LiveStockQuote>? parseLiveQuotesMessage(Object message) {
  if (message is String && (message == 'ping' || message == 'pong')) {
    return null;
  }
  final body = message is String
      ? jsonDecode(message) as Map<String, dynamic>
      : message as Map<String, dynamic>;
  if (body['channel'] != 'quotes') return null;
  final raw = body['quotes'];
  if (raw is! Map) return const [];
  final items = ((raw['items'] as List?) ?? const [])
      .whereType<Map>()
      .map((m) => liveStockQuoteFromJson(m.cast<String, dynamic>()))
      .whereType<LiveStockQuote>()
      .toList();
  return items;
}

WatchlistItem applyLiveQuote(WatchlistItem item, LiveStockQuote quote) {
  return item.copyWith(
    last: quote.last ?? item.last,
    changeRate: quote.changePct ?? item.changeRate,
  );
}

class _QuoteSub {
  _QuoteSub(this.pairs, this.cb);
  final List<({String symbol, String market})> pairs;
  final void Function(List<LiveStockQuote> items) cb;
}

/// 个股订阅枢纽：与指数流共用同一 WS 契约，单独连接以免改指数解析。
class StockQuotesHub {
  StockQuotesHub(this._ref);

  final Ref _ref;

  final Map<int, _QuoteSub> _subs = {};
  int _seq = 0;
  WebSocketChannel? _channel;
  var _connecting = false;
  var _disposed = false;
  Duration _backoff = const Duration(seconds: 2);

  VoidCallback subscribe(
    List<({String symbol, String market})> pairs,
    void Function(List<LiveStockQuote> items) cb,
  ) {
    final id = ++_seq;
    _subs[id] = _QuoteSub(_normalize(pairs), cb);
    unawaited(_ensureConnected());
    _sendSubscribe();
    return () {
      _subs.remove(id);
      if (_subs.isEmpty) {
        unawaited(_close());
      } else {
        _sendSubscribe();
      }
    };
  }

  List<({String symbol, String market})> _normalize(
    List<({String symbol, String market})> pairs,
  ) {
    final seen = <String>{};
    final out = <({String symbol, String market})>[];
    for (final pair in pairs) {
      var symbol = pair.symbol.trim().toUpperCase();
      var market = pair.market.trim().isEmpty ? 'US' : pair.market.trim().toUpperCase();
      if (symbol.endsWith('.US')) {
        symbol = symbol.substring(0, symbol.length - 3);
        market = 'US';
      } else if (symbol.endsWith('.HK')) {
        symbol = symbol.substring(0, symbol.length - 3);
        market = 'HK';
      }
      if (symbol.isEmpty) continue;
      final key = '$market:$symbol';
      if (!seen.add(key)) continue;
      out.add((symbol: symbol, market: market));
      if (out.length >= 80) break;
    }
    return out;
  }

  List<Map<String, String>> _merged() {
    final seen = <String>{};
    final out = <Map<String, String>>[];
    for (final sub in _subs.values) {
      for (final pair in sub.pairs) {
        final key = '${pair.market}:${pair.symbol}';
        if (!seen.add(key)) continue;
        out.add({'symbol': pair.symbol, 'market': pair.market});
        if (out.length >= 80) return out;
      }
    }
    return out;
  }

  void _sendSubscribe() {
    final ch = _channel;
    if (ch == null || _subs.isEmpty) return;
    final symbols = _merged();
    if (symbols.isEmpty) return;
    ch.sink.add(jsonEncode({'type': 'subscribe', 'symbols': symbols}));
  }

  Future<void> _ensureConnected() async {
    if (_disposed || _connecting || _channel != null) {
      if (_channel != null) _sendSubscribe();
      return;
    }
    _connecting = true;
    try {
      await _connectLoop();
    } finally {
      _connecting = false;
    }
  }

  Future<void> _connectLoop() async {
    while (!_disposed && _subs.isNotEmpty) {
      String wsBase = '';
      TokenStore? store;
      try {
        wsBase = _ref.read(gatewayController).url;
        store = _ref.read(tokenStoreProvider);
      } catch (_) {
        return;
      }
      final tokenStore = store;
      if (tokenStore == null) return;
      final token = await tokenStore.read();
      if (token == null || token.isEmpty || wsBase.isEmpty) return;
      final wsUrl = wsBase.replaceFirst(RegExp(r'^http'), 'ws');
      final channel = WebSocketChannel.connect(
        Uri.parse('$wsUrl/docker-api/ws/market/quotes?interval=15'),
      );
      _channel = channel;
      try {
        await channel.ready;
        channel.sink.add(jsonEncode({'type': 'auth', 'token': token}));
        _backoff = const Duration(seconds: 2);
        _sendSubscribe();
        await for (final message in channel.stream) {
          if (_disposed) return;
          try {
            final items = parseLiveQuotesMessage(message);
            if (items == null || items.isEmpty) continue;
            for (final sub in _subs.values) {
              final wanted = {
                for (final p in sub.pairs) '${p.market}:${p.symbol}',
              };
              final hit = items.where((q) => wanted.contains(q.key)).toList();
              if (hit.isNotEmpty) sub.cb(hit);
            }
          } on FormatException catch (e) {
            debugPrint('[行情WS] 个股载荷解析失败: $e');
          }
        }
      } catch (_) {
        // 断线后退避重连
      } finally {
        await channel.sink.close().catchError((_) {});
        if (identical(_channel, channel)) _channel = null;
      }
      if (_disposed || _subs.isEmpty) return;
      await Future<void>.delayed(_backoff);
      _backoff = _backoff * 2 > const Duration(seconds: 16)
          ? const Duration(seconds: 16)
          : _backoff * 2;
    }
  }

  Future<void> _close() async {
    final ch = _channel;
    _channel = null;
    await ch?.sink.close().catchError((_) {});
  }

  Future<void> dispose() async {
    _disposed = true;
    _subs.clear();
    await _close();
  }
}

final stockQuotesHubProvider = Provider<StockQuotesHub>((ref) {
  final hub = StockQuotesHub(ref);
  ref.onDispose(() {
    unawaited(hub.dispose());
  });
  return hub;
});

/// 指数快照实时流：页面存活期间保持连接，断开自动重连。
final marketQuotesStreamProvider =
    StreamProvider.autoDispose<MarketQuoteStream>((ref) async* {
      final gateway = ref.watch(gatewayController);
      if (gateway.url.isEmpty) return;

      final wsBase = gateway.url.replaceFirst(RegExp(r'^http'), 'ws');
      final token = await ref.read(tokenStoreProvider).read();
      if (token == null || token.isEmpty) return;

      var backoff = const Duration(seconds: 2);
      var disposed = false;
      ref.onDispose(() => disposed = true);

      while (!disposed) {
        final channel = WebSocketChannel.connect(
          Uri.parse('$wsBase/docker-api/ws/market/quotes?interval=15'),
        );
        try {
          await channel.ready;
          channel.sink.add(jsonEncode({'type': 'auth', 'token': token}));
          backoff = const Duration(seconds: 2); // 连接成功重置退避
          await for (final message in channel.stream) {
            if (disposed) return;
            try {
              final snap = parseMarketQuotesMessage(message);
              if (snap != null) yield snap;
            } on FormatException catch (e) {
              debugPrint('[行情WS] 载荷解析失败: $e');
            }
          }
        } catch (_) {
          // 连接失败或中断 → 退避后重试。
        } finally {
          await channel.sink.close().catchError((_) {});
        }
        if (disposed) return;
        await Future<void>.delayed(backoff);
        backoff = backoff * 2 > const Duration(seconds: 16)
            ? const Duration(seconds: 16)
            : backoff * 2;
      }
    });
