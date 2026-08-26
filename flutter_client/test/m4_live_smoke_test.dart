import 'dart:io';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:flutter_client/features/trade/data/trade_api.dart';

/// M4 交易域真实链路冒烟（严格只读白名单）。
/// 运行方式同 m2/m3：凭据走 SMOKE_USER / SMOKE_PASS 环境变量，缺失自动跳过。
/// 禁止把密码写进任何被 git 跟踪的文件。
/// 不调用 POST /trade/order、cancel、auto/run 等写端点（实盘红线）。
void main() {
  final gateway =
      Platform.environment['SMOKE_GATEWAY'] ?? 'http://127.0.0.1:12580';
  final user = Platform.environment['SMOKE_USER'];
  final pass = Platform.environment['SMOKE_PASS'];

  if (user == null || user.isEmpty || pass == null || pass.isEmpty) {
    // ignore: avoid_print
    print('---- 跳过：未提供 SMOKE_USER / SMOKE_PASS ----');
    return;
  }

  late Dio dio;

  setUpAll(() async {
    dio = Dio(BaseOptions(baseUrl: '$gateway/docker-api'));
    final resp = await dio.post<dynamic>(
      '/login',
      data: FormData.fromMap({'username': user, 'password': pass}),
      options: Options(contentType: Headers.formUrlEncodedContentType),
    );
    final body = resp.data as Map<String, dynamic>;
    final token = body['token'] as String? ??
        ((body['data'] as Map<String, dynamic>?)?['token'] as String?) ??
        '';
    expect(token, isNotEmpty, reason: '登录应返回 token');
    dio.options.headers['Authorization'] = 'Bearer $token';
  });

  test('账户资产结构可解析', () async {
    final a = await TradeApi(dio).account();
    if (a.configured) {
      expect(a.currency, isNotEmpty);
    }
  });

  test('持仓列表不抛', () async {
    final list = await TradeApi(dio).positions();
    expect(list, isA<List>());
  });

  test('当日与历史委托不抛且状态字段存在', () async {
    final api = TradeApi(dio);
    for (final scope in ['today', 'history']) {
      for (final o in await api.orders(scope: scope)) {
        expect(o.status, isNotEmpty);
        expect(o.open, anyOf(isTrue, isFalse));
      }
    }
  });

  test('盘口深度与逐笔（A股返回 cn_no_depth 也算通过）', () async {
    final api = TradeApi(dio);
    final depth = await api.depth(symbol: 'AAPL', market: 'US');
    if (depth.available) {
      expect(depth.bids, isNotEmpty);
    } else {
      expect(depth.reason, isNotEmpty);
    }
    final trades = await api.trades(symbol: 'AAPL', market: 'US', count: 5);
    expect(trades.length, lessThanOrEqualTo(5));
  });

  test('自动交易状态：tradingEnabled 布尔', () async {
    final s = await TradeApi(dio).autoStatus();
    if (s.configured) {
      expect(s.tradingEnabled, anyOf(isTrue, isFalse));
    }
  });

  test('风控规则与事件不抛', () async {
    final api = TradeApi(dio);
    for (final r in await api.riskRules()) {
      expect(r.ruleType, isNotEmpty);
    }
    for (final e in await api.riskEvents(limit: 10)) {
      expect(e.title, isNotEmpty);
    }
  });
}
