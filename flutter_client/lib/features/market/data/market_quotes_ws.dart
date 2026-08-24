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
/// （WS /ws/market/quotes?token=&interval=，载荷与 /market/index/quotes data 一致）。
///
/// 语义：
/// - 断线自动重连（指数退避 2s→16s 封顶），连接期间持续推送；
/// - 连接失败/未授权时流以错误结束，行情页回退到既有一次性轮询展示。

class MarketQuoteStream {
  const MarketQuoteStream({this.items = const [], this.asOf = ''});

  final List<IndexQuote> items;
  final String asOf;
}

MarketQuoteStream _parseSnapshot(Object message) {
  final body = message is String
      ? jsonDecode(message) as Map<String, dynamic>
      : message as Map<String, dynamic>;
  final data = (body['data'] ?? const {}) as Map<dynamic, dynamic>;
  final items = ((data['items'] as List?) ?? const [])
      .whereType<Map>()
      .map((m) => IndexQuote.fromJson(m.cast<String, dynamic>()))
      .toList();
  return MarketQuoteStream(items: items, asOf: (data['asOf'] as String?) ?? '');
}

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
          Uri.parse(
            '$wsBase/docker-api/ws/market/quotes?token=$token&interval=5',
          ),
        );
        try {
          await channel.ready;
          backoff = const Duration(seconds: 2); // 连接成功重置退避
          await for (final message in channel.stream) {
            if (disposed) return;
            try {
              yield _parseSnapshot(message);
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
