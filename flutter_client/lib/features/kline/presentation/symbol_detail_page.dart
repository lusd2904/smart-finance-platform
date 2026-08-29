import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_client.dart';
import '../../../core/theme/app_theme.dart';
import '../../../shared/utils/format.dart';
import '../../../shared/widgets/quote_text.dart';
import '../../ai/data/ai_api.dart';
import '../../ai/data/ai_models.dart';
import '../../market/data/market_api.dart';
import '../../market/data/market_models.dart';
import '../../market/data/market_quotes_ws.dart';
import '../../shell/phone_trade_page.dart';
import '../../trade/data/trade_api.dart';
import '../../trade/data/trade_models.dart';
import '../../watchlist/logic/watchlist_providers.dart';
import '../logic/kline_painter.dart';

/// 反重力设计稿图 01：个股行情 + AI 研判终端。
class SymbolDetailPage extends ConsumerStatefulWidget {
  const SymbolDetailPage({
    super.key,
    required this.symbol,
    required this.market,
    this.name,
  });

  final String symbol;
  final String market;
  final String? name;

  @override
  ConsumerState<SymbolDetailPage> createState() => _SymbolDetailPageState();
}

class _Pack {
  const _Pack({
    required this.bars,
    this.overview = const {},
    this.depth,
    this.ai,
    this.news = const [],
  });
  final List<KlineBar> bars;
  final Map<String, dynamic> overview;
  final DepthData? depth;
  final AiLatestAnalysis? ai;
  final List<Map<String, dynamic>> news;
}

class _SymbolDetailPageState extends ConsumerState<SymbolDetailPage> {
  String _period = 'daily';
  bool _expanded = false;
  late Future<_Pack> _future;
  LiveStockQuote? _live;
  VoidCallback? _unsubQuotes;

  static const _periodLabels = {
    'intraday': '分时',
    'daily': '日K',
    'weekly': '周K',
    'monthly': '月K',
  };

  @override
  void initState() {
    super.initState();
    _future = _load();
    Future<void>.microtask(_bindQuotes);
  }

  @override
  void dispose() {
    _unsubQuotes?.call();
    super.dispose();
  }

  void _bindQuotes() {
    _unsubQuotes?.call();
    _unsubQuotes = ref.read(stockQuotesHubProvider).subscribe(
      [(symbol: widget.symbol, market: widget.market)],
      (quotes) {
        if (!mounted || quotes.isEmpty) return;
        setState(() => _live = quotes.first);
      },
    );
  }

  Future<_Pack> _load() async {
    final api = ref.read(marketApiProvider);
    final trade = ref.read(tradeApiProvider);
    final ai = ref.read(aiApiProvider);
    final barsF = api.kline(
      symbol: widget.symbol,
      market: widget.market,
      period: _period,
    );
    final ovF = api.symbolOverview(
      symbol: widget.symbol,
      market: widget.market,
    );
    final dpF = trade.depth(symbol: widget.symbol, market: widget.market);
    final aiF = ai.latest(symbol: widget.symbol, market: widget.market);
    final newsF = api.symbolContent(
      symbol: widget.symbol,
      market: widget.market,
    );
    final bars = await barsF;
    Map<String, dynamic> ov = const {};
    DepthData? depth;
    AiLatestAnalysis? latest;
    List<Map<String, dynamic>> news = const [];
    try {
      ov = await ovF;
    } catch (_) {}
    try {
      depth = await dpF;
    } catch (_) {}
    try {
      latest = await aiF;
    } catch (_) {}
    try {
      news = await newsF;
    } catch (_) {}
    return _Pack(
      bars: bars,
      overview: ov,
      depth: depth,
      ai: latest,
      news: news,
    );
  }

  void _reload() => setState(() => _future = _load());

  @override
  Widget build(BuildContext context) {
    final titleName = widget.name == null || widget.name!.isEmpty
        ? ''
        : widget.name!;
    final watched =
        ref
            .watch(watchlistOverviewProvider)
            .asData
            ?.value
            .items
            .any(
              (i) =>
                  i.symbol.toUpperCase() == widget.symbol.toUpperCase() &&
                  i.market == widget.market,
            ) ??
        false;
    return Scaffold(
      appBar: AppBar(
        title: Column(
          children: [
            Text(
              widget.symbol,
              style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 16),
            ),
            if (titleName.isNotEmpty)
              Text(titleName, style: Theme.of(context).textTheme.bodySmall),
          ],
        ),
        centerTitle: true,
        actions: [
          IconButton(
            tooltip: watched ? '取消自选' : '加自选',
            icon: Icon(
              watched ? Icons.favorite : Icons.favorite_border,
              color: watched ? AppColors.up : null,
            ),
            onPressed: () => _toggleWatch(watched),
          ),
          IconButton(icon: const Icon(Icons.refresh), onPressed: _reload),
        ],
      ),
      body: FutureBuilder<_Pack>(
        future: _future,
        builder: (context, snap) {
          if (snap.connectionState != ConnectionState.done) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snap.hasError) {
            return Center(
              child: TextButton(
                onPressed: _reload,
                child: Text('加载失败，点此重试\n${describeApiError(snap.error!)}'),
              ),
            );
          }
          final pack = snap.data!;
          if (pack.bars.isEmpty) {
            return const Center(child: Text('暂无 K 线数据'));
          }
          return CustomScrollView(
            slivers: [
              SliverToBoxAdapter(
                child: _QuoteBlock(
                  bars: pack.bars,
                  market: widget.market,
                  live: _live,
                ),
              ),
              SliverToBoxAdapter(
                child: _MetricGrid(
                  bars: pack.bars,
                  overview: pack.overview,
                  expanded: _expanded,
                  onToggle: () => setState(() => _expanded = !_expanded),
                ),
              ),
              SliverToBoxAdapter(
                child: _PeriodBar(
                  period: _period,
                  onChanged: (p) {
                    setState(() {
                      _period = p;
                      _future = _load();
                    });
                  },
                ),
              ),
              SliverToBoxAdapter(
                child: SizedBox(
                  height: 220,
                  child: InteractiveKlineChart(bars: pack.bars),
                ),
              ),
              if (pack.depth != null && pack.depth!.available)
                SliverToBoxAdapter(
                  child: _DepthCard(
                    depth: pack.depth!,
                    onPrice: (px) => showFastTicket(
                      context,
                      symbol: widget.symbol,
                      market: widget.market,
                      name: widget.name,
                    ),
                  ),
                ),
              SliverToBoxAdapter(child: _AiCard(ai: pack.ai)),
              if (pack.news.isNotEmpty)
                SliverToBoxAdapter(child: _NewsCard(items: pack.news)),
              const SliverToBoxAdapter(child: SizedBox(height: 16)),
            ],
          );
        },
      ),
      bottomNavigationBar: SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 8),
          child: Row(
            children: [
              Expanded(
                child: FilledButton(
                  style: FilledButton.styleFrom(
                    backgroundColor: AppColors.up,
                    minimumSize: const Size.fromHeight(48),
                  ),
                  onPressed: () => showFastTicket(
                    context,
                    symbol: widget.symbol,
                    market: widget.market,
                    name: widget.name,
                  ),
                  child: Text('买入 ${widget.symbol}'),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: FilledButton(
                  style: FilledButton.styleFrom(
                    backgroundColor: AppColors.down,
                    minimumSize: const Size.fromHeight(48),
                  ),
                  onPressed: () => showFastTicket(
                    context,
                    symbol: widget.symbol,
                    market: widget.market,
                    name: widget.name,
                  ),
                  child: Text('卖出 ${widget.symbol}'),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Future<void> _toggleWatch(bool watched) async {
    final api = ref.read(marketApiProvider);
    try {
      if (watched) {
        final items =
            ref.read(watchlistOverviewProvider).asData?.value.items ?? const [];
        final hit = items.where(
          (i) =>
              i.symbol.toUpperCase() == widget.symbol.toUpperCase() &&
              i.market == widget.market &&
              i.id != null,
        );
        if (hit.isNotEmpty) {
          await api.deleteWatchlist([hit.first.id!]);
        }
      } else {
        await api.addWatchlist(symbol: widget.symbol, market: widget.market);
      }
      ref.invalidate(watchlistOverviewProvider);
    } catch (_) {}
  }
}

class _QuoteBlock extends StatelessWidget {
  const _QuoteBlock({required this.bars, required this.market, this.live});
  final List<KlineBar> bars;
  final String market;
  final LiveStockQuote? live;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final last = bars.last;
    final prev = bars.length >= 2 ? bars[bars.length - 2] : null;
    final liveLast = live?.last;
    final prevClose = prev?.close;
    final changeAmt = (liveLast != null && prevClose != null)
        ? liveLast - prevClose
        : (prev != null ? last.close - prev.close : null);
    final changeRate =
        live?.changePct ??
        ((prev != null && prev.close != 0)
            ? (last.close - prev.close) / prev.close * 100
            : null);
    final price = liveLast ?? last.close;
    final color = switch (changeRate ?? changeAmt) {
      null => AppColors.flat,
      > 0 => AppColors.up,
      < 0 => AppColors.down,
      _ => AppColors.flat,
    };
    final chgStyle = theme.textTheme.titleMedium?.copyWith(
      color: color,
      fontWeight: FontWeight.w700,
      fontFeatures: AppNum.fontFeatures,
    );
    final marketLabel = switch (market.toUpperCase()) {
      'US' => '美股',
      'HK' => '港股',
      'CN' => 'A股',
      _ => market,
    };
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 8, 20, 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              PriceText(
                price,
                style: theme.textTheme.quoteDisplay.copyWith(color: color),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Padding(
                  padding: const EdgeInsets.only(bottom: 4),
                  child: Row(
                    children: [
                      Text(formatSigned(changeAmt), style: chgStyle),
                      const SizedBox(width: 8),
                      Text(formatPct(changeRate), style: chgStyle),
                      if (live != null) ...[
                        const SizedBox(width: 8),
                        const Text(
                          'LIVE',
                          style: TextStyle(
                            fontSize: 12,
                            color: AppColors.brand,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                      ],
                    ],
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 4),
          Text(
            marketLabel,
            style: TextStyle(
              fontSize: 11,
              color: theme.colorScheme.onSurfaceVariant,
            ),
          ),
        ],
      ),
    );
  }
}

class _MetricGrid extends StatelessWidget {
  const _MetricGrid({
    required this.bars,
    required this.overview,
    required this.expanded,
    required this.onToggle,
  });
  final List<KlineBar> bars;
  final Map<String, dynamic> overview;
  final bool expanded;
  final VoidCallback onToggle;

  String _ov(List<String> keys) {
    for (final k in keys) {
      final v = overview[k];
      if (v == null) continue;
      if (v is num) {
        return v.abs() >= 1000
            ? formatAmountCn(v.toDouble())
            : formatPrice(v.toDouble());
      }
      final s = '$v';
      if (s.isNotEmpty && s != 'null') return s;
    }
    return '--';
  }

  @override
  Widget build(BuildContext context) {
    final last = bars.last;
    final prev = bars.length >= 2 ? bars[bars.length - 2] : last;
    final cells = <(String, String)>[
      ('最高', formatPrice(last.high)),
      ('最低', formatPrice(last.low)),
      ('今开', formatPrice(last.open)),
      ('昨收', formatPrice(prev.close)),
      ('成交量', formatAmountCn(last.volume)),
      ('成交额', _ov(['turnover', 'amount', 'value'])),
    ];
    if (expanded) {
      for (final extra in [
        ('市值', _ov(['marketCap', 'totalMarketCap'])),
        ('PE', _ov(['pe', 'peTtm', 'peTTM'])),
        ('PB', _ov(['pb'])),
        ('换手', _ov(['turnoverRate', 'turnoverRatio'])),
        ('振幅', _ov(['amplitude'])),
        ('均价', _ov(['avgPrice', 'vwap'])),
        ('委比', _ov(['bidAskRatio', 'weiBi'])),
        ('量比', _ov(['volumeRatio', 'liangBi'])),
        ('52周高', _ov(['week52High', 'high52w'])),
        ('52周低', _ov(['week52Low', 'low52w'])),
        ('Beta', _ov(['beta'])),
        ('股息', _ov(['dividendTtm', 'dividend'])),
      ]) {
        if (extra.$2 != '--') cells.add(extra);
      }
    }
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: Column(
        children: [
          GridView.count(
            crossAxisCount: 3,
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            childAspectRatio: 2.8,
            children: [
              for (final c in cells)
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      c.$1,
                      style: TextStyle(
                        fontSize: 11,
                        color: Theme.of(context).colorScheme.onSurfaceVariant,
                      ),
                    ),
                    Text(
                      c.$2,
                      style: const TextStyle(
                        fontSize: 13,
                        fontWeight: FontWeight.w700,
                        fontFeatures: AppNum.fontFeatures,
                      ),
                    ),
                  ],
                ),
            ],
          ),
          TextButton(
            onPressed: onToggle,
            child: Text(expanded ? '收起' : '更多行情'),
          ),
        ],
      ),
    );
  }
}

class _PeriodBar extends StatelessWidget {
  const _PeriodBar({required this.period, required this.onChanged});
  final String period;
  final ValueChanged<String> onChanged;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return SizedBox(
      height: 40,
      child: Row(
        children: [
          for (final e in _SymbolDetailPageState._periodLabels.entries)
            Expanded(
              child: InkWell(
                onTap: () => onChanged(e.key),
                child: Column(
                  children: [
                    Expanded(
                      child: Center(
                        child: Text(
                          e.value,
                          style: TextStyle(
                            fontSize: 14,
                            fontWeight: period == e.key
                                ? FontWeight.w700
                                : FontWeight.w500,
                            color: period == e.key
                                ? AppColors.brand
                                : scheme.onSurfaceVariant,
                          ),
                        ),
                      ),
                    ),
                    Container(
                      height: 2,
                      color: period == e.key
                          ? AppColors.brand
                          : Colors.transparent,
                    ),
                  ],
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class _DepthCard extends StatelessWidget {
  const _DepthCard({required this.depth, this.onPrice});
  final DepthData depth;
  final ValueChanged<double>? onPrice;

  @override
  Widget build(BuildContext context) {
    final bids = depth.bids.take(4).toList();
    final asks = depth.asks.take(4).toList();
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            '盘口',
            style: TextStyle(fontWeight: FontWeight.w800, fontSize: 13),
          ),
          const SizedBox(height: 8),
          Row(
            children: [
              Expanded(child: _col('买', bids, AppColors.up, onPrice)),
              Expanded(child: _col('卖', asks, AppColors.down, onPrice)),
            ],
          ),
        ],
      ),
    );
  }

  Widget _col(
    String title,
    List<DepthLevel> rows,
    Color color,
    ValueChanged<double>? onPrice,
  ) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          title,
          style: TextStyle(
            color: color,
            fontWeight: FontWeight.w700,
            fontSize: 12,
          ),
        ),
        for (final r in rows)
          InkWell(
            onTap: r.price == null ? null : () => onPrice?.call(r.price!),
            child: Padding(
              padding: const EdgeInsets.symmetric(vertical: 2),
              child: Text(
                '${formatPrice(r.price)}  ${r.volume ?? r.size ?? '--'}',
                style: TextStyle(
                  color: color,
                  fontFeatures: AppNum.fontFeatures,
                  fontSize: 12,
                ),
              ),
            ),
          ),
      ],
    );
  }
}

class _AiCard extends StatelessWidget {
  const _AiCard({this.ai});
  final AiLatestAnalysis? ai;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final score = ai?.confidence ?? ai?.pickScore ?? ai?.factorScore;
    final scoreColor = ai?.isBullish == true
        ? AppColors.up
        : ai?.isBearish == true
        ? AppColors.down
        : AppColors.flat;
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 8),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  ai?.modelName.isNotEmpty == true
                      ? 'AI 研判 · ${ai!.modelName}'
                      : 'AI 研判',
                  style: const TextStyle(
                    fontWeight: FontWeight.w800,
                    fontSize: 13,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  ai == null
                      ? '暂无该标的研判'
                      : [
                          if (ai!.recommendation.isNotEmpty) ai!.recommendation,
                          if (ai!.stance.isNotEmpty) ai!.stance,
                          if (ai!.summaryText.isNotEmpty) ai!.summaryText,
                        ].join(' · '),
                  maxLines: 3,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                    color: scheme.onSurfaceVariant,
                    fontSize: 13,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(width: 12),
          Text(
            score == null
                ? '--'
                : (score <= 1
                      ? (score * 100).toStringAsFixed(0)
                      : score.toStringAsFixed(0)),
            style: TextStyle(
              fontWeight: FontWeight.w800,
              fontSize: 22,
              fontFeatures: AppNum.fontFeatures,
              color: scoreColor,
            ),
          ),
        ],
      ),
    );
  }
}

class _NewsCard extends StatelessWidget {
  const _NewsCard({required this.items});
  final List<Map<String, dynamic>> items;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            '资讯',
            style: TextStyle(fontWeight: FontWeight.w800, fontSize: 13),
          ),
          const SizedBox(height: 6),
          for (var i = 0; i < (items.length < 8 ? items.length : 8); i++) ...[
            if (i > 0) Divider(height: 1, color: scheme.outlineVariant),
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 8),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    '${items[i]['title'] ?? ''}',
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      fontWeight: FontWeight.w600,
                      fontSize: 13,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    [
                      if ((items[i]['sourceName'] ?? '').toString().isNotEmpty)
                        items[i]['sourceName'],
                      if ((items[i]['publishedAt'] ?? '').toString().isNotEmpty)
                        items[i]['publishedAt'],
                    ].join(' · '),
                    style: TextStyle(
                      color: scheme.onSurfaceVariant,
                      fontSize: 11,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }
}
