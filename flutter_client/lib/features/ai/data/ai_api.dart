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

  /// 触发单标的 AI 研判：HTTP 只入队，再轮询票据并取最新落库结果。
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
        options: Options(receiveTimeout: const Duration(seconds: 20)),
      ),
    );
    final data = result.dataAsMap ?? <String, dynamic>{};
    final jobId = '${data['jobId'] ?? ''}';
    if (data['accepted'] == true || jobId.isNotEmpty) {
      if (jobId.isNotEmpty) {
        final ticket = await _pollJob(jobId);
        if ('${ticket['status']}' == 'failed') {
          return {
            'message': ticket['error'] ?? result.msg ?? '研判失败',
            ...ticket,
          };
        }
      }
      final latest = await this.latest(symbol: symbol, market: market);
      if (latest != null) {
        return {
          'recommendation': latest.recommendation,
          'stance': latest.stance,
          'confidence': latest.confidence,
          'summary': latest.summaryText,
          'operationAdvice': latest.operationAdvice,
          'modelName': latest.modelName,
          'message': result.msg,
        };
      }
      return <String, dynamic>{'message': result.msg.isNotEmpty ? result.msg : '研判已完成，请稍后刷新'};
    }
    return data.isEmpty ? <String, dynamic>{'message': result.msg} : data;
  }

  Future<Map<String, dynamic>> _pollJob(String jobId) async {
    final deadline = DateTime.now().add(const Duration(minutes: 3));
    while (DateTime.now().isBefore(deadline)) {
      try {
        final result = ApiResult.from(await _dio.get<void>('/market/jobs/$jobId'));
        final ticket = result.dataAsMap ?? <String, dynamic>{};
        final status = '${ticket['status'] ?? ''}';
        if (status == 'done' || status == 'failed') return ticket;
      } catch (_) {
        // 短暂 5xx / 票据未写入时继续等到截止
      }
      await Future<void>.delayed(const Duration(seconds: 2));
    }
    return <String, dynamic>{'status': 'failed', 'error': '任务等待超时'};
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
    var rows = asJsonList(result.data);
    if (rows.isEmpty) rows = asJsonList(result.dataAsMap?['items']);
    return rows.map(asJsonMap).whereType<Map<String, dynamic>>().map(AiBatch.fromJson).toList();
  }

  /// 指定批次的标的明细。
  Future<List<AiBatchItem>> batchItems({required int batchId}) async {
    final result = ApiResult.from(await _dio.get<void>('/trade/ai/batches/$batchId/items'));
    var rows = asJsonList(result.data);
    if (rows.isEmpty) rows = asJsonList(result.dataAsMap?['items']);
    return rows.map(asJsonMap).whereType<Map<String, dynamic>>().map(AiBatchItem.fromJson).toList();
  }
}

final aiApiProvider = Provider<AiApi>((ref) => AiApi(ref.watch(dioProvider)));

/// 批次历史列表。autoDispose。
final aiBatchesProvider =
    FutureProvider.autoDispose<List<AiBatch>>((ref) => ref.read(aiApiProvider).batches());
