import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_client.dart';
import '../../../core/theme/app_theme.dart';
import '../../../shared/utils/format.dart';
import '../../../shared/widgets/stat_grid.dart';
import '../../../shared/widgets/page_header.dart';
import '../../../shared/widgets/quote_text.dart';
import '../data/market_api.dart';
import '../data/market_models.dart';
import '../data/market_quotes_ws.dart';

/// 行情 tab 首页：市场热度看板。
/// 结构（自上而下）：市场切换 → 盘中指数条 → 统计卡行 → 热度摘要 → 热度 Top50 列表，
/// 整体支持下拉刷新。
class MarketTab extends ConsumerStatefulWidget {
  const MarketTab({super.key, this.onOpenSymbol});

  /// 打开标的详情：由外层（HomeShell）统一接 SymbolDetailPage；为 null 时点击无动作。
  final void Function(String symbol, String market, String name)? onOpenSymbol;

  @override
  ConsumerState<MarketTab> createState() => _MarketTabState();
}

class _MarketTabState extends ConsumerState<MarketTab> {
  /// 市场代码 → 展示名，顺序即切换条顺序。
  static const _markets = {'US': '美股', 'HK': '港股', 'CN': 'A股'};

  /// 当前市场，保存在本组件内；切换时重拉数据。
  String _market = 'US';

  /// 主数据源：heatDaily 的本地 AsyncValue（Future + setState 管理）。
  AsyncValue<HeatDailyData> _daily = const AsyncLoading();

  List<IndexQuote> _indexes = const [];

  @override
  void initState() {
    super.initState();
    _loadIndexes();
    _load();
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

  /// 正常内容：看板各区块 + Top50。
  Widget _buildContent(HeatDailyData data) {
    final heat = data.heat ?? const HeatSummary();
    final quotes = _liveOrPolledIndexes;
    final strip = heatStripQuotes(quotes, _market);
    final statQ = heatStatQuote(quotes, _market);
    final statPct = _market == 'US' ? statQ?.changePct : (statQ?.changePct ?? heat.indexChangePct);
    return ListView(
      padding: const EdgeInsets.only(bottom: 24),
      children: [
        const PageHeader(
          title: '行情',
          subtitle: '市场热度看板',
        ),
        Padding(
          padding: const EdgeInsets.symmetric(
            horizontal: AppDimens.pagePadding,
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              SegmentedButton<String>(
                segments: [
                  for (final e in _markets.entries)
                    ButtonSegment(value: e.key, label: Text(e.value)),
                ],
                selected: {_market},
                onSelectionChanged: (selection) {
                  final next = selection.first;
                  if (next == _market) return;
                  setState(() => _market = next);
                  _load();
                },
              ),
              const SizedBox(height: 10),
              _filterRuleBanner(context, data),
              const SizedBox(height: 12),
              _IndexStrip(items: strip),
              const SizedBox(height: 16),
              StatGrid(
                cells: [
                  StatCellData(
                    label: kHeatStatIndex[_market]?.$2 ??
                        (heat.indexName.isEmpty ? '指数涨跌' : heat.indexName),
                    value: PctText(statPct),
                  ),
                  StatCellData(
                    label: '成交额',
                    value: Text(formatAmountCn(heat.totalTurnover)),
                  ),
                  StatCellData(
                    label: '涨跌家数',
                    value: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Text(
                          '${heat.advanceCount}',
                          style: const TextStyle(color: AppColors.up),
                        ),
                        Text(
                          '/${heat.declineCount}',
                          style: const TextStyle(color: AppColors.down),
                        ),
                        Text(
                          '/${heat.flatCount}',
                          style: const TextStyle(color: AppColors.flat),
                        ),
                      ],
                    ),
                  ),
                  StatCellData(
                    label: '热度分',
                    value: Text(heat.heatScore?.toStringAsFixed(1) ?? '--'),
                  ),
                ],
              ),
              const SizedBox(height: 14),
              _summaryCard(context, heat),
              const SizedBox(height: 14),
              SectionCard(
                title: '热度 Top50',
                subtitle: '按当日热度排序 · 点击行查看 K 线详情',
                padding: const EdgeInsets.fromLTRB(8, 4, 8, 8),
                child: Column(
                  children: [
                    for (var i = 0; i < data.top50.length; i++) ...[
                      if (i > 0)
                        Divider(
                          height: 1,
                          indent: 46,
                          color: Theme.of(context).colorScheme.outlineVariant,
                        ),
                      _topRow(context, data.top50[i]),
                    ],
                  ],
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _filterRuleBanner(BuildContext context, HeatDailyData data) {
    final raw = data.filterRuleFor(_market);
    if (raw.isEmpty) return const SizedBox.shrink();
    final text = raw.contains('市值') ? raw : '市值 $raw';
    final scheme = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 9),
      decoration: BoxDecoration(
        color: scheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(AppDimens.radiusControl),
        border: Border.all(color: scheme.outlineVariant),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(Icons.filter_alt_outlined, size: 16, color: scheme.primary),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              '筛选规则：$text',
              style: Theme.of(context).textTheme.bodySmall?.copyWith(height: 1.4),
            ),
          ),
        ],
      ),
    );
  }

  /// 热度摘要卡；staleHint 非空时以警示色提示数据延迟。
  Widget _summaryCard(BuildContext context, HeatSummary heat) {
    final theme = Theme.of(context);
    return SectionCard(
      title: '今日热度',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            heat.heatSummary.isEmpty ? '暂无热度摘要' : heat.heatSummary,
            style: theme.textTheme.bodyMedium?.copyWith(height: 1.55),
          ),
          if (heat.staleHint.isNotEmpty) ...[
            const SizedBox(height: 10),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 9),
              decoration: BoxDecoration(
                color: AppColors.warn.withValues(alpha: 0.12),
                borderRadius: BorderRadius.circular(AppDimens.radiusControl),
              ),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Icon(
                    Icons.warning_amber_rounded,
                    size: 15,
                    color: AppColors.warn,
                  ),
                  const SizedBox(width: 7),
                  Expanded(
                    child: Text(
                      heat.staleHint,
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: AppColors.warn,
                      ),
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

  /// Top50 行：排名徽标 + 标的 + 涨跌幅 + 市值/成交额 + 自选星标。
  Widget _topRow(BuildContext context, TopPickRow row) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    return InkWell(
      onTap: widget.onOpenSymbol == null
          ? null
          : () => widget.onOpenSymbol!(row.symbol, _market, row.name),
      borderRadius: BorderRadius.circular(AppDimens.radiusControl),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 11),
        child: Row(
          children: [
            _rankBadge(context, row.rankNo),
            const SizedBox(width: 11),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Flexible(
                        child: Text(
                          row.symbol,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: theme.textTheme.titleSmall?.copyWith(
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                      ),
                      const SizedBox(width: 6),
                      Flexible(
                        child: Text(
                          row.name,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: theme.textTheme.bodySmall?.copyWith(
                            color: scheme.onSurfaceVariant,
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 2),
                  Text(
                    '市值 ${formatAmountCn(row.marketCap)} · 成交 ${formatAmountCn(row.turnover)}',
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: scheme.onSurfaceVariant,
                    ),
                  ),
                ],
              ),
            ),
            if (row.inWatchlist)
              const Padding(
                padding: EdgeInsets.only(left: 6),
                child: Icon(
                  Icons.star_rounded,
                  size: 17,
                  color: AppColors.warn,
                ),
              ),
            const SizedBox(width: 8),
            PctText(
              row.changePct,
              bold: true,
              style: theme.textTheme.titleSmall,
            ),
          ],
        ),
      ),
    );
  }

  /// 排名徽标：前三名品牌色圆底高亮，其余中性。
  Widget _rankBadge(BuildContext context, int rankNo) {
    final top3 = rankNo > 0 && rankNo <= 3;
    final scheme = Theme.of(context).colorScheme;
    return Container(
      width: 26,
      height: 26,
      alignment: Alignment.center,
      decoration: BoxDecoration(
        color: top3
            ? scheme.primary.withValues(alpha: 0.14)
            : scheme.surfaceContainerHighest,
        shape: BoxShape.circle,
      ),
      child: Text(
        '$rankNo',
        style: Theme.of(context).textTheme.labelMedium?.copyWith(
          fontWeight: FontWeight.w800,
          fontFeatures: AppNum.fontFeatures,
          color: top3 ? scheme.primary : scheme.onSurfaceVariant,
        ),
      ),
    );
  }
}

/// 当前市场指数条。空列表（该市场暂无报价）整条隐藏。
class _IndexStrip extends StatelessWidget {
  const _IndexStrip({required this.items});

  final List<IndexQuote> items;

  @override
  Widget build(BuildContext context) {
    if (items.isEmpty) return const SizedBox.shrink();
    return LayoutBuilder(
      builder: (context, constraints) {
        const gap = 10.0;
        final n = items.length;
        final cols = n <= 2 ? n : 2;
        final cellW = cols <= 1
            ? constraints.maxWidth
            : (constraints.maxWidth - gap * (cols - 1)) / cols;
        return Wrap(
          spacing: gap,
          runSpacing: gap,
          children: [
            for (final q in items)
              SizedBox(
                width: cellW,
                child: _indexCard(context, q),
              ),
          ],
        );
      },
    );
  }

  Widget _indexCard(BuildContext context, IndexQuote q) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 12),
      decoration: BoxDecoration(
        color: scheme.surfaceContainerLow,
        borderRadius: BorderRadius.circular(AppDimens.radiusCard),
        border: Border.all(color: scheme.outlineVariant),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            indexDisplayName(q),
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: theme.textTheme.bodySmall?.copyWith(
              color: scheme.onSurfaceVariant,
            ),
          ),
          const SizedBox(height: 5),
          FittedBox(
            fit: BoxFit.scaleDown,
            alignment: Alignment.centerLeft,
            child: PriceText(
              q.last,
              style: theme.textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w700),
            ),
          ),
          const SizedBox(height: 2),
          PctText(q.changePct, bold: true),
        ],
      ),
    );
  }
}
