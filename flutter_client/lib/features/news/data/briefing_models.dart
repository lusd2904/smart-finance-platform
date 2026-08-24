/// 财经简报流数据模型。契约依据：
/// module_market/service/finance_news_service.py:58-108（get_briefings 条目字段）。
library;

/// 单条财经简报：GET /market/finance/briefings → data.data[i]
class BriefingItem {
  const BriefingItem({
    this.id = '',
    this.market = '',
    this.briefingType = '',
    this.headline = '',
    this.summary = '',
    this.sourceName = '',
    this.sourceLink = '',
    this.generatedAt = '',
  });

  factory BriefingItem.fromJson(Map<String, dynamic> json) => BriefingItem(
        market: (json['market'] as String?) ?? '',
        // 服务端实测 id 为整型（自增主键）；统一转字符串，避免 as 强转崩溃。
        id: json['id']?.toString() ?? '',
        headline: (json['headline'] as String?) ?? '',
        summary: (json['summary'] as String?) ?? '',
        sourceName: (json['sourceName'] as String?) ?? '',
        sourceLink: (json['sourceLink'] as String?) ?? '',
        generatedAt: (json['generatedAt'] as String?) ?? '',
      );

  final String id;
  final String market;
  final String briefingType;
  final String headline;
  final String summary;
  final String sourceName;
  final String sourceLink;
  final String generatedAt;
}

/// 简报流载荷。注意：该接口非标准分页包，
/// 外层 data = {success, data:[...], message, meta{market,count,limit,snapshotAt,...}}。
class BriefingFeed {
  const BriefingFeed({
    this.items = const [],
    this.snapshotAt = '',
    this.message = '',
  });

  factory BriefingFeed.fromJson(Map<String, dynamic> json) => BriefingFeed(
        items: ((json['data'] as List<dynamic>?) ?? const [])
            .whereType<Map<String, dynamic>>()
            .map(BriefingItem.fromJson)
            .toList(),
        snapshotAt: ((json['meta'] as Map<String, dynamic>?)?['snapshotAt'] as String?) ?? '',
        message: (json['message'] as String?) ?? '',
      );

  final List<BriefingItem> items;
  final String snapshotAt;

  /// 服务降级提示（采集失败时非空）。
  final String message;
}
