import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_client.dart';
import '../../../core/api/api_result.dart';
import 'quant_models.dart';

/// 量化域只读接口（M3）。契约依据：module_quant/controller/quant_controller.py。
/// 只读白名单；compute/scan/run 等触发计算或写库的端点一律不调用。
class QuantApi {
  QuantApi(this._dio);

  final Dio _dio;

  /// 因子质量报告（IC/IR 汇总 + 五分位收益）。market: US/HK/CN
  Future<FactorQcReport> factorQc({required String market}) async {
    final result = ApiResult.from(
      await _dio.get<void>(
        '/quant/factor/qc',
        queryParameters: {'market': market},
      ),
    );
    return FactorQcReport.fromJson(result.dataAsMap ?? <String, dynamic>{});
  }

  /// 今日策略信号清单。
  Future<DailyListPayload> dailyList() async {
    final result = ApiResult.from(await _dio.get<void>('/quant/daily-list'));
    return DailyListPayload.fromJson(result.dataAsMap ?? <String, dynamic>{});
  }

  /// 扫描台账（最近 limit 条）。
  Future<List<ScanRun>> scanRuns({int limit = 20}) async {
    final result = ApiResult.from(
      await _dio.get<void>(
        '/quant/scan-runs',
        queryParameters: {'limit': limit},
      ),
    );
    final items = result.dataAsMap?['items'];
    return ((items as List<dynamic>?) ?? const [])
        .whereType<Map<String, dynamic>>()
        .map(ScanRun.fromJson)
        .toList();
  }

  /// 扫描详情（展开台账条目时懒加载）。
  Future<Map<String, dynamic>> scanRunDetail({required int cycleId}) async {
    final result = ApiResult.from(
      await _dio.get<void>('/quant/scan-runs/$cycleId'),
    );
    return result.dataAsMap ?? <String, dynamic>{};
  }

  /// 计算单标的因子打分。
  Future<Map<String, dynamic>> computeFactor({
    required String symbol,
    required String market,
    String profile = 'balanced',
  }) async {
    final result = ApiResult.from(
      await _dio.get<void>(
        '/quant/factor/compute',
        queryParameters: {
          'symbol': symbol,
          'market': market,
          'profile': profile,
        },
        options: Options(receiveTimeout: const Duration(seconds: 60)),
      ),
    );
    return result.dataAsMap ?? <String, dynamic>{};
  }

  /// 8 族权重三档预设（注意挂在 /trade 域，权限 quant:strategy:list）。
  Future<List<StrategyProfile>> strategyProfiles() async {
    final result = ApiResult.from(
      await _dio.get<void>('/trade/strategy-profiles'),
    );
    return ((result.data as List<dynamic>?) ?? const [])
        .whereType<Map<String, dynamic>>()
        .map(StrategyProfile.fromJson)
        .toList();
  }
}

/// 长桥凭据绑定态（M4 只读）：掩码回显与连通性测试。
/// 不接入 PUT /quant/longbridge/config 写端点。
extension LongbridgeReadOnly on QuantApi {
  /// 绑定态：{appKey, appSecret(掩码), accessToken(掩码), region, updateTime...}
  Future<Map<String, dynamic>> longbridgeConfig() async {
    final result = ApiResult.from(
      await _dio.get<void>('/quant/longbridge/config'),
    );
    return result.dataAsMap ?? <String, dynamic>{};
  }

  /// 连通性测试（发起外部连接但只读，不改库）。
  Future<Map<String, dynamic>> longbridgeTest() async {
    final result = ApiResult.from(
      await _dio.get<void>('/quant/longbridge/test'),
    );
    return result.dataAsMap ?? <String, dynamic>{};
  }
}

final quantApiProvider = Provider<QuantApi>(
  (ref) => QuantApi(ref.watch(dioProvider)),
);

/// 今日策略信号。
final quantDailyListProvider = FutureProvider.autoDispose<DailyListPayload>(
  (ref) => ref.read(quantApiProvider).dailyList(),
);

/// 扫描台账。
final quantScanRunsProvider = FutureProvider.autoDispose<List<ScanRun>>(
  (ref) => ref.read(quantApiProvider).scanRuns(),
);

/// 8 族权重档位。
final quantProfilesProvider = FutureProvider.autoDispose<List<StrategyProfile>>(
  (ref) => ref.read(quantApiProvider).strategyProfiles(),
);

/// 因子质量报告（按市场）。
final factorQcProvider = FutureProvider.autoDispose
    .family<FactorQcReport, String>(
      (ref, market) => ref.read(quantApiProvider).factorQc(market: market),
    );
