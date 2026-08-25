import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_client.dart';
import '../../../core/api/api_result.dart';
import 'ai_models.dart';

/// AI 研判只读接口。契约依据：
/// module_market/controller/market_controller.py:396（单标的最新）
/// module_trade/controller/trade_controller.py:563-597（批量批次/明细）。
/// M2 只读：不触发 ai-analyze / ai/batch 等重任务端点。
class AiApi {
  AiApi(this._dio);

  final Dio _dio;

  /// 触发单标的 AI 研判（交易工作台用）。
  Future<Map<String, dynamic>> analyze({
    required String symbol,
    required String market,
    int days = 90,
  }) async {
    final result = ApiResult.from(
      await _dio.post<void>(
        '/market/ai/analyze',
        data: <String, dynamic>{
          'symbol': symbol,
          'market': market,
          'days': days,
        },
        options: Options(receiveTimeout: const Duration(seconds: 120)),
      ),
    );
    return result.dataAsMap ?? <String, dynamic>{'message': result.msg};
  }

  /// 单标的最新研判；无记录返回 null。
  Future<AiLatestAnalysis?> latest({required String symbol, required String market}) async {
    final result = ApiResult.from(await _dio.get<void>(
      '/market/symbols/${symbol.trim().toUpperCase()}/ai/latest',
      queryParameters: {'market': market.toUpperCase()},
    ));
    final data = result.dataAsMap;
    if (data == null || data.isEmpty) return null;
    return AiLatestAnalysis.fromJson(data);
  }

  /// 批量扫描批次历史。
  Future<List<AiBatch>> batches() async {
    final result = ApiResult.from(await _dio.get<void>('/trade/ai/batches'));
    return ((result.data as List<dynamic>?) ?? const [])
        .whereType<Map<String, dynamic>>()
        .map(AiBatch.fromJson)
        .toList();
  }

  /// 指定批次的标的明细。
  Future<List<AiBatchItem>> batchItems({required int batchId}) async {
    final result = ApiResult.from(await _dio.get<void>('/trade/ai/batches/$batchId/items'));
    return ((result.data as List<dynamic>?) ?? const [])
        .whereType<Map<String, dynamic>>()
        .map(AiBatchItem.fromJson)
        .toList();
  }
}

final aiApiProvider = Provider<AiApi>((ref) => AiApi(ref.watch(dioProvider)));

/// 批次历史列表。autoDispose。
final aiBatchesProvider =
    FutureProvider.autoDispose<List<AiBatch>>((ref) => ref.read(aiApiProvider).batches());
