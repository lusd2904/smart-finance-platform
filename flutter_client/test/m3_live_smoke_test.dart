import 'dart:io';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_client/features/quant/data/quant_api.dart';

/// M3 量化域真实链路冒烟（只读白名单）。
/// 运行方式同 m2_live_smoke_test：凭据走 SMOKE_USER / SMOKE_PASS 环境变量，
/// 缺失自动跳过；禁止把密码写进任何被 git 跟踪的文件。
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

  test('因子质量报告（US）结构可解析', () async {
    final report = await QuantApi(dio).factorQc(market: 'US');
    for (final item in report.items) {
      expect(item.factorKey, isNotEmpty);
      if (item.quantiles.isNotEmpty) {
        expect(item.quantiles.keys.every((k) => k.startsWith('q')), isTrue,
            reason: 'quantiles 应仅含 q1~q5 分位键（spread 已剥离）');
      }
    }
  });

  test('今日策略清单不抛且条目方向可判', () async {
    final payload = await QuantApi(dio).dailyList();
    if (payload.list != null) {
      for (final item in payload.list!.items) {
        expect(item.symbol, isNotEmpty);
      }
    }
  });

  test('扫描台账列表不抛', () async {
    final runs = await QuantApi(dio).scanRuns(limit: 5);
    expect(runs.length, lessThanOrEqualTo(5));
  });

  test('8 族权重三档预设可解析', () async {
    final profiles = await QuantApi(dio).strategyProfiles();
    for (final p in profiles) {
      expect(p.profileCode, isNotEmpty);
    }
  });

  test('残缺 Bearer 头归一为业务码 401（回归鉴权修复）', () async {
    final bare = Dio(BaseOptions(baseUrl: '$gateway/docker-api'));
    final resp = await bare.get<dynamic>('/quant/daily-list',
        options: Options(headers: {'Authorization': 'Bearer'}));
    final body = resp.data as Map<String, dynamic>;
    expect(body['code'], 401, reason: '残缺点位应返回 401 而非 500');
  });
}
