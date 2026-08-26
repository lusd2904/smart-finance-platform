/// AI 研判域数据模型。契约依据：
/// module_market/service/market_service.py:573-614（单标的最新研判）
/// module_trade/service/platform_ext_service.py:482-521（批量扫描批次/明细）。
library;

import '../../../core/api/api_result.dart';

/// 单标的最新 AI 研判：GET /market/symbols/{symbol}/ai/latest → data（可为 null）。
class AiLatestAnalysis {
  const AiLatestAnalysis({
    this.analysisId,
    this.symbol = '',
    this.market = '',
    this.price,
    this.recommendation = '',
    this.stance = '',
    this.confidence,
    this.summaryText = '',
    this.indicatorReview = '',
    this.sentimentReview = '',
    this.operationAdvice = '',
    this.riskWarning = '',
    this.pickScore,
    this.factorScore,
    this.signal = '',
    this.modelName = '',
    this.analysisTime = '',
  });

  factory AiLatestAnalysis.fromJson(Map<String, dynamic> json) => AiLatestAnalysis(
        analysisId: asInt(json['analysisId']),
        symbol: asString(json['symbol']),
        market: asString(json['market']),
        price: asDouble(json['price']),
        recommendation: asString(json['recommendation']),
        stance: asString(json['stance']),
        confidence: asDouble(json['confidence']),
        summaryText: asString(json['summaryText']).isEmpty
            ? asString(json['summary'])
            : asString(json['summaryText']),
        indicatorReview: asString(json['indicatorReview']),
        sentimentReview: asString(json['sentimentReview']),
        operationAdvice: asString(json['operationAdvice']).isEmpty
            ? asString(json['advice'])
            : asString(json['operationAdvice']),
        riskWarning: asString(json['riskWarning']),
        pickScore: asDouble(json['pickScore']),
        factorScore: asDouble(json['factorScore']),
        signal: asString(json['signal']),
        modelName: asString(json['modelName']),
        analysisTime: asString(json['analysisTime']),
      );

  final int? analysisId;
  final String symbol;
  final String market;
  final double? price;
  final String recommendation;
  final String stance;
  final double? confidence;
  final String summaryText;
  final String indicatorReview;
  final String sentimentReview;
  final String operationAdvice;
  final String riskWarning;
  final double? pickScore;
  final double? factorScore;
  final String signal;
  final String modelName;
  final String analysisTime;

  /// 研判方向徽章语义：看多/买入/增持类红（涨），看空/卖出/减持类绿，其余灰。
  bool get isBullish {
    final d = '$recommendation$stance'.toLowerCase();
    for (final token in const [
      '多', 'bull', 'up', '涨', '买入', '增持', 'buy', 'positive',
    ]) {
      if (d.contains(token)) return true;
    }
    return false;
  }

  bool get isBearish {
    final d = '$recommendation$stance'.toLowerCase();
    for (final token in const [
      '空', 'bear', 'down', '跌', '卖出', '减持', 'sell', 'negative',
    ]) {
      if (d.contains(token)) return true;
    }
    return false;
  }
}

/// 批量扫描批次：GET /trade/ai/batches → data[i]。
class AiBatch {
  const AiBatch({
    this.batchId,
    this.cycleId,
    this.symbolsCount = 0,
    this.successCount = 0,
    this.status = '',
    this.summary = '',
    this.createTime = '',
  });

  factory AiBatch.fromJson(Map<String, dynamic> json) => AiBatch(
        batchId: asInt(json['batchId']),
        cycleId: asInt(json['cycleId']),
        symbolsCount: asInt(json['symbolsCount']) ?? 0,
        successCount: asInt(json['successCount']) ?? 0,
        status: asString(json['status']),
        summary: asString(json['summary']),
        createTime: asString(json['createTime']),
      );

  final int? batchId;
  final int? cycleId;
  final int symbolsCount;
  final int successCount;

  /// '0' 执行中 / '1' 完成。
  final String status;
  bool get finished => status == '1';
  final String summary;
  final String createTime;
}

/// 批次内单标的研判明细：GET /trade/ai/batches/{batchId}/items → data[i]。
class AiBatchItem {
  const AiBatchItem({
    this.itemId,
    this.symbol = '',
    this.market = '',
    this.decision = '',
    this.confidence,
    this.summary = '',
    this.status = '',
    this.createTime = '',
  });

  factory AiBatchItem.fromJson(Map<String, dynamic> json) => AiBatchItem(
        itemId: asInt(json['itemId']),
        symbol: asString(json['symbol']),
        market: asString(json['market']),
        decision: asString(json['decision']),
        confidence: asDouble(json['confidence']),
        summary: asString(json['summary']),
        status: asString(json['status']),
        createTime: asString(json['createTime']),
      );

  final int? itemId;
  final String symbol;
  final String market;
  final String decision;
  final double? confidence;
  final String summary;

  /// '1' 成功 / '2' 失败。
  final String status;
  bool get succeeded => status == '1';
  final String createTime;
}
