import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_client.dart';
import '../../../core/api/api_result.dart';
import 'sentiment_models.dart';

/// 舆情域接口。契约依据：module_sentiment/controller/sentiment_controller.py。
/// 客户端走登录态接口（/sentiment/widget/* 需独立 Widget Token，不适用）。
class SentimentApi {
  SentimentApi(this._dio);

  final Dio _dio;

  /// 最新大盘研判（取第一页第一条；无数据返回 null）。
  Future<SentimentAnalysis?> latestAnalysis() async {
    final result = ApiResult.from(await _dio.get<void>('/sentiment/analysis/list',
        queryParameters: {'pageNum': 1, 'pageSize': 1}));
    final rows = (result.rows ?? const []).whereType<Map<String, dynamic>>().toList();
    if (rows.isEmpty) return null;
    return SentimentAnalysis.fromJson(rows.first);
  }

  /// 近 N 次研判趋势（默认 24 条）。
  Future<List<SentimentTrendPoint>> trend({int limit = 24}) async {
    final result = ApiResult.from(
        await _dio.get<void>('/sentiment/analysis/trend', queryParameters: {'limit': limit}));
    return ((result.data as List<dynamic>?) ?? const [])
        .whereType<Map<String, dynamic>>()
        .map(SentimentTrendPoint.fromJson)
        .toList();
  }

  /// 触发一次舆情采集与分析（服务端入队，异步执行）。
  Future<void> triggerCollect() async {
    await _dio.post<void>('/sentiment/news/collect');
  }
}

final sentimentApiProvider =
    Provider<SentimentApi>((ref) => SentimentApi(ref.watch(dioProvider)));

/// 舆情看板聚合：最新研判 + 趋势。autoDispose 离开页面释放。
final sentimentBoardProvider = FutureProvider.autoDispose<({SentimentAnalysis? latest, List<SentimentTrendPoint> trend})>(
  (ref) async {
    final api = ref.read(sentimentApiProvider);
    final latest = await api.latestAnalysis();
    final trend = await api.trend();
    return (latest: latest, trend: trend);
  },
);
