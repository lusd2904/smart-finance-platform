/// 舆情域数据模型。契约依据：
/// module_sentiment/entity/vo/sentiment_vo.py + service/sentiment_service.py。
library;

import 'dart:convert';

/// 情绪方向：LLM 原文经归一化后的三值。
/// 归一规则镜像后端 _normalize_direction（sentiment_service.py:233-241）。
enum SentimentDirection {
  up('利多'),
  down('利空'),
  flat('中性'),
  unknown('未知');

  const SentimentDirection(this.label);
  final String label;

  static SentimentDirection fromRaw(String? raw) {
    if (raw == null || raw.isEmpty) return unknown;
    final d = raw.toLowerCase();
    for (final token in const ['多', 'bull', 'up', '涨', 'positive']) {
      if (d.contains(token)) return up;
    }
    for (final token in const ['空', 'bear', 'down', '跌', 'negative']) {
      if (d.contains(token)) return down;
    }
    return flat;
  }
}

/// 后端舆情影响分约为 [-10, 10]；手机仪表盘固定 0–100。
/// |raw|≤10 时线性映射：-10→0、0→50、10→100；已是百分制则原样使用。
double? sentimentIndexTo100(double? raw) {
  if (raw == null) return null;
  if (raw >= -10 && raw <= 10) {
    return ((raw + 10) * 5).clamp(0, 100);
  }
  return raw.clamp(0, 100);
}

/// 大盘综合研判记录：GET /sentiment/analysis/list → rows[i]（取用字段子集）。
class SentimentAnalysis {
  const SentimentAnalysis({
    this.analysisId,
    this.newsCount = 0,
    this.summary = '',
    this.usDirection = '',
    this.usScore,
    this.usReason = '',
    this.hkDirection = '',
    this.hkScore,
    this.hkReason = '',
    this.aDirection = '',
    this.aScore,
    this.aReason = '',
    this.riskEvents = const [],
    this.modelName = '',
    this.createTime = '',
  });

  factory SentimentAnalysis.fromJson(Map<String, dynamic> json) => SentimentAnalysis(
        analysisId: (json['analysisId'] as num?)?.toInt(),
        newsCount: (json['newsCount'] as num?)?.toInt() ?? 0,
        summary: (json['summary'] as String?) ?? '',
        usDirection: (json['usDirection'] as String?) ?? '',
        usScore: sentimentIndexTo100((json['usScore'] as num?)?.toDouble()),
        usReason: (json['usReason'] as String?) ?? '',
        hkDirection: (json['hkDirection'] as String?) ?? '',
        hkScore: sentimentIndexTo100((json['hkScore'] as num?)?.toDouble()),
        hkReason: (json['hkReason'] as String?) ?? '',
        aDirection: (json['aDirection'] as String?) ?? '',
        aScore: sentimentIndexTo100((json['aScore'] as num?)?.toDouble()),
        aReason: (json['aReason'] as String?) ?? '',
        riskEvents: _parseRiskEvents(json['riskEvents']),
        modelName: (json['modelName'] as String?) ?? '',
        createTime: (json['createTime'] as String?) ?? '',
      );

  final int? analysisId;
  final int newsCount;
  final String summary;

  /// 三市场方向原文与展示分值（已映射到 0~100）。
  final String usDirection;
  final double? usScore;
  final String usReason;
  final String hkDirection;
  final double? hkScore;
  final String hkReason;
  final String aDirection;
  final double? aScore;
  final String aReason;
  final List<String> riskEvents;
  final String modelName;
  final String createTime;

  /// 综合分：三市场均分；全空返回 null。
  double? get overallScore {
    final scores = [usScore, hkScore, aScore].whereType<double>().toList();
    if (scores.isEmpty) return null;
    return scores.reduce((a, b) => a + b) / scores.length;
  }

  /// 列表接口常把 riskEvents 存成 JSON 字符串，看板接口才是数组。
  static List<String> _parseRiskEvents(dynamic raw) {
    if (raw == null) return const [];
    if (raw is List) {
      return raw.map((e) => e.toString()).where((e) => e.isNotEmpty).toList();
    }
    final text = raw.toString().trim();
    if (text.isEmpty) return const [];
    if (text.startsWith('[')) {
      try {
        final parsed = jsonDecode(text);
        if (parsed is List) {
          return parsed.map((e) => e.toString()).where((e) => e.isNotEmpty).toList();
        }
      } catch (_) {}
    }
    return text
        .split(RegExp(r'[\n;；]'))
        .map((e) => e.trim())
        .where((e) => e.isNotEmpty)
        .toList();
  }

  /// 综合方向：三市场归一方向的多数票，平票回退中性。
  SentimentDirection get overallDirection {
    final votes = [
      SentimentDirection.fromRaw(usDirection),
      SentimentDirection.fromRaw(hkDirection),
      SentimentDirection.fromRaw(aDirection),
    ];
    final ups = votes.where((v) => v == SentimentDirection.up).length;
    final downs = votes.where((v) => v == SentimentDirection.down).length;
    if (ups > downs && ups >= 2) return SentimentDirection.up;
    if (downs > ups && downs >= 2) return SentimentDirection.down;
    return SentimentDirection.flat;
  }
}

/// 舆情趋势点：GET /sentiment/analysis/trend → data[i]（createTime 已格式化为 MM-dd HH:mm）。
class SentimentTrendPoint {
  const SentimentTrendPoint({
    this.createTime = '',
    this.usScore,
    this.hkScore,
    this.aScore,
  });

  factory SentimentTrendPoint.fromJson(Map<String, dynamic> json) =>
      SentimentTrendPoint(
        createTime: (json['createTime'] as String?) ?? '',
        usScore: sentimentIndexTo100((json['usScore'] as num?)?.toDouble()),
        hkScore: sentimentIndexTo100((json['hkScore'] as num?)?.toDouble()),
        aScore: sentimentIndexTo100((json['aScore'] as num?)?.toDouble()),
      );

  final String createTime;
  final double? usScore;
  final double? hkScore;
  final double? aScore;
}
