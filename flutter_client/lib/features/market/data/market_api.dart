import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_client.dart';
import '../../../core/api/api_result.dart';
import 'market_models.dart';

/// 行情域接口。契约依据：module_market/controller/market_controller.py。
/// 分页参数 pageNum/pageSize；分页响应包 {rows,total}，普通包 {data}。
class MarketApi {
  MarketApi(this._dio);

  final Dio _dio;

  /// 热度日数据（含 Top50 快照）。market: US/HK/CN
  Future<HeatDailyData> heatDaily({required String market, String? tradeDate}) async {
    final result = ApiResult.from(await _dio.get<void>('/market/heat/daily', queryParameters: {
      'market': market,
      if (tradeDate != null && tradeDate.isNotEmpty) 'tradeDate': tradeDate,
    }));
    return HeatDailyData.fromJson(result.dataAsMap ?? <String, dynamic>{});
  }

  /// 近 N 日热度趋势：data.points[i]
  Future<List<HeatTrendPoint>> heatTrend({required String market, int days = 5}) async {
    final result = ApiResult.from(await _dio.get<void>('/market/heat/trend', queryParameters: {
      'market': market,
      'days': days,
    }));
    final points = result.dataAsMap?['points'];
    return ((points as List<dynamic>?) ?? const [])
        .whereType<Map<String, dynamic>>()
        .map(HeatTrendPoint.fromJson)
        .toList();
  }

  /// 盘中指数条（非交易时段返回空列表）
  Future<List<IndexQuote>> indexQuotes() async {
    final result = ApiResult.from(await _dio.get<void>('/market/index/quotes'));
    final items = result.dataAsMap?['items'];
    return ((items as List<dynamic>?) ?? const [])
        .whereType<Map<String, dynamic>>()
        .map(IndexQuote.fromJson)
        .toList();
  }

  /// 报价板批量报价（兼容 rows/quotes/裸数组载荷）
  Future<List<BoardQuote>> boardQuotes({String? market}) async {
    final response = await _dio.get<dynamic>('/market/board/quotes', queryParameters: {
      if (market != null && market.isNotEmpty) 'market': market,
    });
    // 报价板直接返回数组型载荷（可能无信封），逐层探测。
    final body = response.data;
    if (body is Map<String, dynamic>) {
      if (body.containsKey('rows') || body.containsKey('quotes')) {
        return BoardQuote.listFrom(body);
      }
      final data = body['data'];
      if (data != null) return BoardQuote.listFrom(data);
    }
    return BoardQuote.listFrom(body);
  }

  /// 全市场标的分页（强制分页）。
  Future<UniversePage> universe({
    String? market,
    String? keyword,
    int pageNum = 1,
    int pageSize = 50,
  }) async {
    final result = ApiResult.from(await _dio.get<void>('/market/instrument/universe', queryParameters: {
      if (market != null && market.isNotEmpty) 'market': market,
      if (keyword != null && keyword.isNotEmpty) 'keyword': keyword,
      'enabled': '1',
      'pageNum': pageNum,
      'pageSize': pageSize,
    }));
    return UniversePage.fromJson(result.dataAsMap ?? <String, dynamic>{});
  }

  /// K线。period: daily/weekly/monthly/intraday...
  Future<List<KlineBar>> kline({
    required String symbol,
    required String market,
    String period = 'daily',
    int limit = 250,
  }) async {
    final result = ApiResult.from(await _dio.get<void>('/market/kline', queryParameters: {
      'symbol': symbol,
      'market': market,
      'period': period,
      'start': '-$limit d',
      'stop': 'now()',
    }));
    return KlineBar.listFrom(result.dataAsMap);
  }

  /// 自选概览（含分组与最新报价）
  Future<WatchlistOverview> watchlistOverview() async {
    final result = ApiResult.from(await _dio.get<void>('/market/watchlist/overview'));
    return WatchlistOverview.fromJson(result.dataAsMap ?? <String, dynamic>{});
  }

  /// 加自选。note 即分组标签（后端按逗号拆分），可空。
  Future<void> addWatchlist({
    required String symbol,
    required String market,
    String? note,
  }) async {
    await _dio.post<void>('/market/watchlist', data: <String, dynamic>{
      'symbol': symbol,
      'market': market,
      if (note != null && note.isNotEmpty) 'note': note,
    });
  }

  /// 删自选（ids 逗号分隔）
  Future<void> deleteWatchlist(List<int> ids) async {
    await _dio.delete<void>('/market/watchlist/${ids.join(',')}');
  }
}

final marketApiProvider = Provider<MarketApi>((ref) => MarketApi(ref.watch(dioProvider)));
