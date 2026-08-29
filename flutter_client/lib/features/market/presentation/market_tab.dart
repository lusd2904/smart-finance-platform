import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_client.dart';
import '../../../core/theme/app_theme.dart';
import '../../../shared/utils/format.dart';
import '../../../shared/widgets/quote_row.dart';
import '../data/market_api.dart';
import '../data/market_models.dart';
import '../data/market_quotes_ws.dart';

/// 按榜单对 Top50 快照排序；返回副本，最多 50 条。null 排最后。
List<TopPickRow> sortHeatBoard(List<TopPickRow> rows, String board) {
  final copy = List<TopPickRow>.of(rows);
  switch (board) {
    case 'up':
      copy.sort((a, b) => _cmpDescNullsLast(a.changePct, b.changePct));
    case 'down':
      copy.sort((a, b) => _cmpAscNullsLast(a.changePct, b.changePct));
    case 'turnover':
      copy.sort((a, b) => _cmpDescNullsLast(a.turnover, b.turnover));
    default:
      copy.sort((a, b) => a.rankNo.compareTo(b.rankNo));
  }
  if (copy.length > 50) return copy.sublist(0, 50);
  return copy;
}

int _cmpAscNullsLast(double? a, double? b) {
  if (a == null && b == null) return 0;
  if (a == null) return 1;
  if (b == null) return -1;
  return a.compareTo(b);
}

int _cmpDescNullsLast(double? a, double? b) {
  if (a == null && b == null) return 0;
  if (a == null) return 1;
  if (b == null) return -1;
  return b.compareTo(a);
}

/// 行情 tab 首页：指数条 + 涨跌统计 + 热度/涨幅/跌幅/成交榜。
class MarketTab extends ConsumerStatefulWidget {
  const MarketTab({super.key, this.onOpenSymbol});

  /// 打开标的详情：由外层（HomeShell）统一接 SymbolDetailPage；为 null 时点击无动作。
  final void Function(String symbol, String market, String name)? onOpenSymbol;

  @override
  ConsumerState<MarketTab> createState() => _MarketTabState();
}

class _MarketTabState extends ConsumerState<MarketTab> {
  /// 市场代码 → 展示名，顺序即切换条顺序（A股 / 港股 / 美股）。
  static const _markets = {'CN': 'A股', 'HK': '港股', 'US': '美股'};

  static const _boards = {
    'heat': '热度',
    'up': '涨幅',
    'down': '跌幅',
    'turnover': '成交',
  };

  /// 当前市场，保存在本组件内；切换时重拉数据。默认 A 股。
  String _market = 'CN';

  String _board = 'heat';

  /// 主数据源：heatDaily 的本地 AsyncValue（Future + setState 管理）。
  AsyncValue<HeatDailyData> _daily = const AsyncLoading();

  List<IndexQuote> _indexes = const [];

  final Map<String, LiveStockQuote> _live = {};
  VoidCallback? _unsubQuotes;
  String _subSig = '';

  @override
  void initState() {
    super.initState();
    _loadIndexes();
    _load();
  }

  @override
  void dispose() {
    _unsubQuotes?.call();
    super.dispose();
  }

  Future<void> _loadIndexes() async {
    try {
      final items = await ref.read(marketApiProvider).indexQuotes();
      if (!mounted) return;
      setState(() => _indexes = items);
    } catch (_) {}
  }

  /// 拉取当前市场热度日数据（含 Top50 快照）。
  Future<void> _load() async {
    setState(() => _daily = const AsyncLoading());
    try {
      final data = await ref.read(marketApiProvider).heatDaily(market: _market);
      if (!mounted) return;
      setState(() => _daily = AsyncData(data));
    } catch (e, st) {
      if (!mounted) return;
      setState(() => _daily = AsyncError(e, st));
    }
  }

  /// 下拉刷新：指数条与主数据一并重拉。
  Future<void> _refresh() async {
    await Future.wait([_loadIndexes(), _load()]);
  }

  List<IndexQuote> get _liveOrPolledIndexes {
    final live = ref.watch(marketQuotesStreamProvider).asData?.value.items;
    if (live != null && live.isNotEmpty) return live;
    return _indexes;
  }

  void _syncQuotes(List<TopPickRow> rows) {
    final sig = rows.map((r) => '$_market:${r.symbol}').join(',');
    if (sig == _subSig) return;
    _subSig = sig;
    _unsubQuotes?.call();
    _unsubQuotes = null;
    if (rows.isEmpty) return;
    _unsubQuotes = ref.read(stockQuotesHubProvider).subscribe(
      [for (final row in rows) (symbol: row.symbol, market: _market)],
      (quotes) {
        if (!mounted) return;
        setState(() {
          for (final q in quotes) {
            _live[q.key] = q;
          }
        });
      },
    );
  }

  LiveStockQuote? _liveFor(TopPickRow row) =>
      _live['${_market.toUpperCase()}:${row.symbol.toUpperCase()}'];

  @override
  Widget build(BuildContext context) {
    // 订阅指数 WS，供指数条/统计卡与轮询结果二选一。
    ref.watch(marketQuotesStreamProvider);
    final data = _daily.value;
    final Widget body;
    if (_daily.isLoading && data == null) {
      // 首次加载：整页转圈。
      body = const Center(child: CircularProgressIndicator());
    } else if (data == null) {
      // 加载失败且无旧数据：错误文案 + 重试。包一层可滚动容器以支持下拉刷新手势。
      body = ListView(
        children: [
          const SizedBox(height: 120),
          Icon(
            Icons.cloud_off_outlined,
            size: 48,
            color: Theme.of(context).colorScheme.outline,
          ),
          const SizedBox(height: 12),
          Text(
            describeApiError(_daily.error ?? Exception('加载失败')),
            textAlign: TextAlign.center,
            style: TextStyle(color: Theme.of(context).colorScheme.error),
          ),
          const SizedBox(height: 16),
          Center(
            child: FilledButton.tonalIcon(
              onPressed: _load,
              icon: const Icon(Icons.refresh),
              label: const Text('重试'),
            ),
          ),
        ],
      );
    } else {
      body = _buildContent(data);
    }
    return RefreshIndicator(onRefresh: _refresh, child: body);
  }

  /// 正常内容：指数条、涨跌统计、摘要、榜单。
  Widget _buildContent(HeatDailyData data) {
    _syncQuotes(data.top50);
    final heat = data.heat ?? const HeatSummary();
    final quotes = _liveOrPolledIndexes;
    final strip = heatStripQuotes(quotes, _market);
    final statQ = heatStatQuote(quotes, _market);
    final statPct = _market == 'US'
        ? statQ?.changePct
        : (statQ?.changePct ?? heat.indexChangePct);
    final ranked = sortHeatBoard(data.top50, _board);
    final marketLabel = _markets[_market] ?? _market;
    final scheme = Theme.of(context).colorScheme;
    return ListView(
      padding: const EdgeInsets.only(bottom: 24),
      children: [
        _underlineTabs(
          context,
          entries: _markets.entries,
          selected: _market,
          onSelect: (next) {
            if (next == _market) return;
            setState(() => _market = next);
            _load();
          },
        ),
        Divider(height: 1, color: scheme.outlineVariant),
        IndexMiniStrip(
          items: [
            for (final q in strip)
              (name: indexDisplayName(q), last: q.last, changePct: q.changePct),
          ],
        ),
        Divider(height: 1, color: scheme.outlineVariant),
        _heatStatsLine(heat, statPct),
        _textChipRow(
          context,
          entries: _boards.entries,
          selected: _board,
          onSelect: (next) {
            if (next == _board) return;
            setState(() => _board = next);
          },
        ),
        Divider(height: 1, color: scheme.outlineVariant),
        const QuoteListHeader(),
        for (var i = 0; i < ranked.length; i++) ...[
          Divider(height: 1, color: scheme.outlineVariant),
          QuoteListRow(
            name: ranked[i].name.isEmpty ? ranked[i].symbol : ranked[i].name,
            symbol: ranked[i].symbol,
            marketLabel: marketLabel,
            last: _liveFor(ranked[i])?.last ?? ranked[i].last,
            changePct: _liveFor(ranked[i])?.changePct ?? ranked[i].changePct,
            rank: _board == 'heat' ? ranked[i].rankNo : i + 1,
            onTap: widget.onOpenSymbol == null
                ? null
                : () => widget.onOpenSymbol!(
                    ranked[i].symbol,
                    _market,
                    ranked[i].name,
                  ),
          ),
        ],
      ],
    );
  }

  Widget _heatStatsLine(HeatSummary heat, double? statPct) {
    final indexName =
        kHeatStatIndex[_market]?.$2 ??
        (heat.indexName.isEmpty ? '指数' : heat.indexName);
    final scheme = Theme.of(context).colorScheme;
    const base = TextStyle(fontSize: 12, height: 1.2);
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 6, 16, 2),
      child: Text.rich(
        TextSpan(
          style: base.copyWith(color: scheme.onSurface),
          children: [
            const TextSpan(text: '涨 '),
            TextSpan(
              text: '${heat.advanceCount}',
              style: const TextStyle(
                color: AppColors.up,
                fontFeatures: AppNum.fontFeatures,
              ),
            ),
            const TextSpan(text: ' 跌 '),
            TextSpan(
              text: '${heat.declineCount}',
              style: const TextStyle(
                color: AppColors.down,
                fontFeatures: AppNum.fontFeatures,
              ),
            ),
            const TextSpan(text: ' 平 '),
            TextSpan(
              text: '${heat.flatCount}',
              style: const TextStyle(
                color: AppColors.flat,
                fontFeatures: AppNum.fontFeatures,
              ),
            ),
            TextSpan(text: ' · 成交 ${formatAmountCn(heat.totalTurnover)}'),
            TextSpan(text: ' · $indexName ${formatPct(statPct)}'),
            if (heat.staleHint.isNotEmpty)
              TextSpan(
                text: ' · ${heat.staleHint}',
                style: const TextStyle(color: AppColors.warn),
              ),
          ],
        ),
        maxLines: 1,
        overflow: TextOverflow.ellipsis,
      ),
    );
  }

  /// 热度/涨幅/跌幅/成交：紧凑文字按钮，无下划线、无填充底。
  Widget _textChipRow(
    BuildContext context, {
    required Iterable<MapEntry<String, String>> entries,
    required String selected,
    required ValueChanged<String> onSelect,
  }) {
    final scheme = Theme.of(context).colorScheme;
    return SizedBox(
      height: 32,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 8),
        child: Row(
          children: [
            for (final e in entries)
              InkWell(
                onTap: () => onSelect(e.key),
                child: Padding(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 10,
                    vertical: 6,
                  ),
                  child: Text(
                    e.value,
                    style: TextStyle(
                      fontSize: 13,
                      fontWeight: selected == e.key
                          ? FontWeight.w700
                          : FontWeight.w500,
                      color: selected == e.key
                          ? AppColors.brand
                          : scheme.onSurfaceVariant,
                    ),
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }

  Widget _underlineTabs(
    BuildContext context, {
    required Iterable<MapEntry<String, String>> entries,
    required String selected,
    required ValueChanged<String> onSelect,
  }) {
    final scheme = Theme.of(context).colorScheme;
    return SizedBox(
      height: 40,
      child: Row(
        children: [
          for (final e in entries)
            Expanded(
              child: InkWell(
                onTap: () => onSelect(e.key),
                child: Column(
                  children: [
                    Expanded(
                      child: Center(
                        child: Text(
                          e.value,
                          style: TextStyle(
                            fontSize: 14,
                            fontWeight: selected == e.key
                                ? FontWeight.w700
                                : FontWeight.w500,
                            color: selected == e.key
                                ? AppColors.brand
                                : scheme.onSurfaceVariant,
                          ),
                        ),
                      ),
                    ),
                    Container(
                      height: 2,
                      color: selected == e.key
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
