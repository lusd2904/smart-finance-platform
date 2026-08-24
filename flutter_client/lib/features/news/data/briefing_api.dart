import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_client.dart';
import '../../../core/api/api_result.dart';
import 'briefing_models.dart';

/// 财经简报流接口。契约依据：module_market/controller/market_controller.py:430-457。
/// 非标准分页：limit 控制条数（1..60），服务端异常时降级空列表。
class BriefingApi {
  BriefingApi(this._dio);

  final Dio _dio;

  Future<List<BriefingItem>> briefings({
    required String market,
    int limit = 20,
    bool refresh = false,
  }) async {
    final result = ApiResult.from(
      await _dio.get<void>('/market/finance/briefings', queryParameters: {
        'market': market,
        'limit': limit.clamp(1, 60),
        'refresh': refresh,
      }),
    );
    return BriefingFeed.fromJson(result.dataAsMap ?? <String, dynamic>{}).items;
  }
}

final briefingApiProvider = Provider<BriefingApi>((ref) => BriefingApi(ref.watch(dioProvider)));
