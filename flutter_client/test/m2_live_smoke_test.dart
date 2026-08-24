import 'dart:io';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:flutter_client/features/ai/data/ai_api.dart';
import 'package:flutter_client/features/news/data/briefing_api.dart';
import 'package:flutter_client/features/notice/data/notice_api.dart';
import 'package:flutter_client/features/sentiment/data/sentiment_api.dart';

/// M2 真实链路冒烟（对本地栈跑，需有效凭据）：
/// SMOKE_GATEWAY=http://127.0.0.1:12580 \
/// SMOKE_USER=admin SMOKE_PASS='...' flutter test test/m2_live_smoke_test.dart
///
/// 凭据只从环境变量读取；SMOKE_PASS 缺失时整组跳过。
/// 禁止把密码写进本文件或任何被 git 跟踪的文件。
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
  late String token;

  setUpAll(() async {
    dio = Dio(BaseOptions(baseUrl: '$gateway/docker-api'));
    // 登录为 OAuth2 表单；token 在顶层 {code,msg,token}。
    final resp = await dio.post<dynamic>(
      '/login',
      data: FormData.fromMap({'username': user, 'password': pass}),
      options: Options(contentType: Headers.formUrlEncodedContentType),
    );
    final body = resp.data as Map<String, dynamic>;
    token = body['token'] as String? ??
        ((body['data'] as Map<String, dynamic>?)?['token'] as String?) ??
        '';
    expect(token, isNotEmpty, reason: '登录应返回 token');
    dio.options.headers['Authorization'] = 'Bearer $token';
  });

  test('简报流返回可解析条目', () async {
    final items = await BriefingApi(dio).briefings(market: 'US', limit: 5);
    for (final item in items) {
      expect(item.id, isNotEmpty);
    }
  });

  test('舆情最新研判与趋势不抛且结构正确', () async {
    final api = SentimentApi(dio);
    final latest = await api.latestAnalysis(); // 可为 null（栈上无数据）
    if (latest != null) {
      expect(latest.createTime, isNotEmpty);
    }
    final trend = await api.trend(limit: 3);
    expect(trend.length, lessThanOrEqualTo(3));
  });

  test('批量扫描批次历史不抛', () async {
    final batches = await AiApi(dio).batches();
    expect(batches, isA<List>());
  });

  test('通知列表不抛且已读字段解析', () async {
    final notices = await NoticeApi(dio).list(limit: 5);
    for (final n in notices) {
      expect(n.read, anyOf(isTrue, isFalse));
    }
  });
}
