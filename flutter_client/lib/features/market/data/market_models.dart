/// 行情域数据模型。字段名对齐后端 camelCase 序列化（to_camel）。
/// 契约依据：module_market/controller/market_controller.py + market_vo.py。
library;

import '../../../core/api/api_result.dart';

/// 热度摘要：GET /market/heat/daily → data.heat
class HeatSummary {
  const HeatSummary({
    this.asOfTime = '',
    this.indexName = '',
    this.indexChangePct,
    this.totalTurnover,
    this.advanceCount = 0,
    this.declineCount = 0,
    this.flatCount = 0,
    this.heatScore,
    this.heatSummary = '',
    this.filterRule = '',
    this.staleHint = '',
  });

  factory HeatSummary.fromJson(Map<String, dynamic> json) => HeatSummary(
    asOfTime: (json['asOfTime'] as String?) ?? '',
    indexName: (json['indexName'] as String?) ?? '',
    indexChangePct: (json['indexChangePct'] as num?)?.toDouble(),
    totalTurnover: (json['totalTurnover'] as num?)?.toDouble(),
    advanceCount: (json['advanceCount'] as num?)?.toInt() ?? 0,
    declineCount: (json['declineCount'] as num?)?.toInt() ?? 0,
    flatCount: (json['flatCount'] as num?)?.toInt() ?? 0,
    heatScore: (json['heatScore'] as num?)?.toDouble(),
    heatSummary: (json['heatSummary'] as String?) ?? '',
    filterRule: (json['filterRule'] as String?) ?? '',
    staleHint: (json['staleHint'] as String?) ?? '',
  );

  final String asOfTime;
  final String indexName;
  final double? indexChangePct;
  final double? totalTurnover;
  final int advanceCount;
  final int declineCount;
  final int flatCount;
  final double? heatScore;
  final String heatSummary;
  final String filterRule;
  final String staleHint;
}

/// 热度 Top50 快照行：data.top50[i]
class TopPickRow {
  const TopPickRow({
    required this.rankNo,
    required this.symbol,
    required this.name,
    this.marketCap,
    this.turnover,
    this.changePct,
    this.inWatchlist = false,
  });

  factory TopPickRow.fromJson(Map<String, dynamic> json) => TopPickRow(
    rankNo: (json['rankNo'] as num?)?.toInt() ?? 0,
    symbol: (json['symbol'] as String?) ?? '',
    name: (json['name'] as String?) ?? '',
    marketCap: (json['marketCap'] as num?)?.toDouble(),
    turnover: (json['turnover'] as num?)?.toDouble(),
    changePct: (json['changePct'] as num?)?.toDouble(),
    inWatchlist: (json['inWatchlist'] as bool?) ?? false,
  );

  final int rankNo;
  final String symbol;
  final String name;
  final double? marketCap;
  final double? turnover;
  final double? changePct;
  final bool inWatchlist;
}

/// 热度日数据：data = {heat, meta, top50}
class HeatDailyData {
  const HeatDailyData({
    this.heat,
    this.top50 = const [],
    this.capFilterRule = '',
  });

  factory HeatDailyData.fromJson(Map<String, dynamic> json) {
    final meta = asJsonMap(json['meta']) ?? const <String, dynamic>{};
    return HeatDailyData(
      heat: json['heat'] is Map<String, dynamic>
          ? HeatSummary.fromJson(json['heat'] as Map<String, dynamic>)
          : null,
      top50: asJsonList(json['top50'])
          .whereType<Map<String, dynamic>>()
          .map(TopPickRow.fromJson)
          .toList(),
      capFilterRule: asString(meta['capFilterRule'] ?? meta['cap_rule']),
    );
  }

  final HeatSummary? heat;
  final List<TopPickRow> top50;
  final String capFilterRule;

  /// 当前市场的市值筛选文案（接口优先，缺省回退本地规则）。
  String filterRuleFor(String market) {
    final live = heat?.filterRule.trim() ?? '';
    if (live.isNotEmpty) return live;
    if (capFilterRule.trim().isNotEmpty) return capFilterRule.trim();
    return kHeatCapRule[market] ?? '';
  }
}

/// 热度指数条按市场展示的腾讯代码（顺序即卡片顺序）。
/// 美股条上只放标普/纳指，道琼斯放到统计卡，避免再重复一个标普。
const kHeatStripCodes = <String, List<String>>{
  'US': ['usINX', 'usIXIC'],
  'HK': ['r_hkHSI', 'r_hkHSTECH', 'r_hkHSCEI'],
  'CN': ['sh000001', 'sz399006', 'sh000688'],
};

/// 统计卡第一格：美股改道琼斯，港股恒生，A 股上证。
const kHeatStatIndex = <String, (String, String)>{
  'US': ('usDJI', '道琼斯'),
  'HK': ('r_hkHSI', '恒生指数'),
  'CN': ('sh000001', '上证指数'),
};

/// 三市场默认市值过滤（与 backend MARKET_META.cap_rule 对齐）。
const kHeatCapRule = <String, String>{
  'US': '10亿-1000亿美元',
  'HK': '100亿-1000亿港币',
  'CN': '100亿-2000亿人民币',
};

const kIndexDisplayName = <String, String>{
  'usinx': '标普500',
  'usixic': '纳斯达克',
  'usdji': '道琼斯',
  'r_hkhsi': '恒生指数',
  'r_hkhstech': '恒生科技',
  'r_hkhscei': '恒生国企',
  'sh000001': '上证指数',
  'sz399006': '创业板指数',
  'sh000688': '科创板指数',
};

String indexDisplayName(IndexQuote q) =>
    kIndexDisplayName[q.symbol.toLowerCase()] ?? (q.name.isEmpty ? q.symbol : q.name);

/// 按当前市场抽出指数条，缺代码时退回该 market 字段匹配的项。
List<IndexQuote> heatStripQuotes(List<IndexQuote> all, String market) {
  final codes = kHeatStripCodes[market] ?? const <String>[];
  final byCode = <String, IndexQuote>{
    for (final q in all) q.symbol.toLowerCase(): q,
  };
  final matched = <IndexQuote>[
    for (final code in codes)
      if (byCode[code.toLowerCase()] != null) byCode[code.toLowerCase()]!,
  ];
  if (matched.isNotEmpty) return matched;
  return all
      .where((q) => q.market.toUpperCase() == market.toUpperCase())
      .toList();
}

IndexQuote? heatStatQuote(List<IndexQuote> all, String market) {
  final spec = kHeatStatIndex[market];
  if (spec == null) return null;
  final code = spec.$1.toLowerCase();
  for (final q in all) {
    if (q.symbol.toLowerCase() == code) return q;
  }
  return null;
}

/// 热度趋势点：GET /market/heat/trend → data.points[i]
class HeatTrendPoint {
  const HeatTrendPoint({
    this.tradeDate = '',
    this.indexChangePct,
    this.heatScore,
    this.totalTurnover,
  });

  factory HeatTrendPoint.fromJson(Map<String, dynamic> json) => HeatTrendPoint(
    tradeDate: (json['tradeDate'] as String?) ?? '',
    indexChangePct: (json['indexChangePct'] as num?)?.toDouble(),
    heatScore: (json['heatScore'] as num?)?.toDouble(),
    totalTurnover: (json['totalTurnover'] as num?)?.toDouble(),
  );

  final String tradeDate;
  final double? indexChangePct;
  final double? heatScore;
  final double? totalTurnover;
}

/// 盘中指数报价：GET /market/index/quotes → data.items[i]
class IndexQuote {
  const IndexQuote({
    this.symbol = '',
    this.name = '',
    this.market = '',
    this.last,
    this.changePct,
    this.quoteTime = '',
  });

  factory IndexQuote.fromJson(Map<String, dynamic> json) => IndexQuote(
    symbol: (json['symbol'] as String?) ?? '',
    name: (json['name'] as String?) ?? '',
    market: (json['market'] as String?) ?? '',
    last: (json['last'] as num?)?.toDouble(),
    changePct: (json['changePct'] as num?)?.toDouble(),
    quoteTime: (json['quoteTime'] as String?) ?? '',
  );

  final String symbol;
  final String name;
  final String market;
  final double? last;
  final double? changePct;
  final String quoteTime;
}

/// 报价板行：GET /market/board/quotes → rows|quotes[i]（最近两根日K组装的最新报价）
class BoardQuote {
  const BoardQuote({
    this.market = '',
    this.symbol = '',
    this.name = '',
    this.price,
    this.changeRate,
    this.tradeDate = '',
  });

  factory BoardQuote.fromJson(Map<String, dynamic> json) => BoardQuote(
    market: (json['market'] as String?) ?? '',
    symbol: (json['symbol'] as String?) ?? '',
    name: (json['name'] as String?) ?? '',
    price: (json['price'] as num?)?.toDouble(),
    changeRate: (json['changeRate'] as num?)?.toDouble(),
    tradeDate: (json['tradeDate'] as String?) ?? '',
  );

  /// 兼容 rows / quotes / 裸数组三种载荷形态。
  static List<BoardQuote> listFrom(dynamic payload) {
    final List<dynamic> raw = switch (payload) {
      {'rows': List l} => l,
      {'quotes': List l} => l,
      List l => l,
      _ => const [],
    };
    return raw
        .whereType<Map<String, dynamic>>()
        .map(BoardQuote.fromJson)
        .toList();
  }

  final String market;
  final String symbol;
  final String name;
  final double? price;
  final double? changeRate;
  final String tradeDate;
}

/// 全市场标的行：GET /market/instrument/universe → rows[i]
class UniverseRow {
  const UniverseRow({
    this.instrumentId,
    this.symbol = '',
    this.name = '',
    this.market = '',
    this.category = '',
  });

  factory UniverseRow.fromJson(Map<String, dynamic> json) => UniverseRow(
    instrumentId: (json['instrumentId'] as num?)?.toInt(),
    symbol: (json['symbol'] as String?) ?? '',
    name: (json['name'] as String?) ?? '',
    market: (json['market'] as String?) ?? '',
    category: (json['category'] as String?) ?? '',
  );

  final int? instrumentId;
  final String symbol;
  final String name;
  final String market;
  final String category;
}

/// universe 分页响应：{rows,total,counts{US,HK,CN,total}}
class UniversePage {
  const UniversePage({
    this.rows = const [],
    this.total = 0,
    this.counts = const {},
  });

  factory UniversePage.fromJson(Map<String, dynamic> json) => UniversePage(
    rows: ((json['rows'] as List<dynamic>?) ?? const [])
        .whereType<Map<String, dynamic>>()
        .map(UniverseRow.fromJson)
        .toList(),
    total: (json['total'] as num?)?.toInt() ?? 0,
    counts: ((json['counts'] as Map<String, dynamic>?) ?? const {}).map(
      (k, v) => MapEntry(k, (v as num?)?.toInt() ?? 0),
    ),
  );

  final List<UniverseRow> rows;
  final int total;
  final Map<String, int> counts;
}

/// 自选概览条目：GET /market/watchlist/overview → data.items[i]
class WatchlistItem {
  const WatchlistItem({
    this.id,
    this.symbol = '',
    this.name = '',
    this.market = '',
    this.last,
    this.changeRate,
    this.groups = const [],
    this.note = '',
    this.recommendation = '',
    this.summary = '',
    this.analysisTime = '',
  });

  factory WatchlistItem.fromJson(Map<String, dynamic> json) => WatchlistItem(
    id: (json['id'] as num?)?.toInt(),
    symbol: (json['symbol'] as String?) ?? '',
    name: (json['name'] as String?) ?? '',
    market: (json['market'] as String?) ?? '',
    last: (json['last'] as num?)?.toDouble(),
    changeRate: (json['changeRate'] as num?)?.toDouble(),
    groups: ((json['groups'] as List<dynamic>?) ?? const [])
        .whereType<String>()
        .toList(),
    note: (json['note'] as String?) ?? '',
    recommendation: (json['recommendation'] as String?) ?? '',
    summary: (json['summary'] as String?) ?? '',
    analysisTime: (json['analysisTime'] as String?) ?? '',
  );

  final int? id;
  final String symbol;
  final String name;
  final String market;
  final double? last;
  final double? changeRate;
  final List<String> groups;
  final String note;
  final String recommendation;
  final String summary;
  final String analysisTime;
}

/// 自选概览：data = {items[], count, bullish, bearish, neutral, groups[{name,count}]}
class WatchlistOverview {
  const WatchlistOverview({
    this.items = const [],
    this.count = 0,
    this.bullish = 0,
    this.bearish = 0,
    this.neutral = 0,
    this.groups = const [],
  });

  factory WatchlistOverview.fromJson(Map<String, dynamic> json) =>
      WatchlistOverview(
        items: ((json['items'] as List<dynamic>?) ?? const [])
            .whereType<Map<String, dynamic>>()
            .map(WatchlistItem.fromJson)
            .toList(),
        count: (json['count'] as num?)?.toInt() ?? 0,
        bullish: (json['bullish'] as num?)?.toInt() ?? 0,
        bearish: (json['bearish'] as num?)?.toInt() ?? 0,
        neutral: (json['neutral'] as num?)?.toInt() ?? 0,
        groups: ((json['groups'] as List<dynamic>?) ?? const [])
            .whereType<Map<String, dynamic>>()
            .map(
              (g) => (
                name: (g['name'] as String?) ?? '',
                count: (g['count'] as num?)?.toInt() ?? 0,
              ),
            )
            .toList(),
      );

  final List<WatchlistItem> items;
  final int count;
  final int bullish;
  final int bearish;
  final int neutral;
  final List<({String name, int count})> groups;
}

/// K线单根：data.klines[i]（date + OHLCV）
class KlineBar {
  const KlineBar({
    this.date = '',
    this.open = 0,
    this.high = 0,
    this.low = 0,
    this.close = 0,
    this.volume = 0,
  });

  factory KlineBar.fromJson(Map<String, dynamic> json) => KlineBar(
    date: (json['date'] ?? json['time'])?.toString() ?? '',
    open: (json['open'] as num?)?.toDouble() ?? 0,
    high: (json['high'] as num?)?.toDouble() ?? 0,
    low: (json['low'] as num?)?.toDouble() ?? 0,
    close: (json['close'] as num?)?.toDouble() ?? 0,
    volume: (json['volume'] as num?)?.toDouble() ?? 0,
  );

  static List<KlineBar> listFrom(dynamic payload) {
    final List<dynamic> raw = switch (payload) {
      {'klines': List l} => l,
      {'items': List l} => l,
      {'bars': List l} => l,
      {'list': List l} => l,
      List l => l,
      _ => const [],
    };
    return raw
        .whereType<Map<String, dynamic>>()
        .map(KlineBar.fromJson)
        .toList();
  }

  final String date;
  final double open;
  final double high;
  final double low;
  final double close;
  final double volume;

  bool get isUp => close >= open;
}
