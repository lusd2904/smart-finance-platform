import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_client.dart';
import '../../../core/theme/app_theme.dart';
import '../../../shared/utils/format.dart';
import '../../../shared/widgets/quote_text.dart';
import '../data/market_api.dart';
import '../data/market_models.dart';
import 'universe_page.dart';

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

  /// 盘中指数条独立请求：存为字段以便下拉刷新时重建触发 FutureBuilder 重拉。
  late Future<List<IndexQuote>> _indexFuture;

  @override
  void initState() {
    super.initState();
    _indexFuture = ref.read(marketApiProvider).indexQuotes();
    _load();
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
    setState(() {
      _indexFuture = ref.read(marketApiProvider).indexQuotes();
    });
    await _load();
  }

  @override
  Widget build(BuildContext context) {
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
          Icon(Icons.cloud_off_outlined,
              size: 48, color: Theme.of(context).colorScheme.outline),
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
    return ListView(
      padding: const EdgeInsets.fromLTRB(12, 12, 12, 24),
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
        const SizedBox(height: 12),
        Row(
          children: [
            TextButton.icon(
              onPressed: () => Navigator.of(context).push(
                MaterialPageRoute<void>(builder: (_) => const UniverseBrowsePage()),
              ),
              icon: const Icon(Icons.grid_view_outlined, size: 18),
              label: const Text('全部股票'),
            ),
          ],
        ),
        const SizedBox(height: 4),
        _IndexStrip(future: _indexFuture),
        const SizedBox(height: 12),
        LayoutBuilder(
          builder: (context, constraints) =>
              _statGrid(context, heat, constraints.maxWidth),
        ),
        const SizedBox(height: 12),
        _summaryCard(context, heat),
        const SizedBox(height: 8),
        ...data.top50.map((row) => _topRow(context, row)),
      ],
    );
  }

  /// 统计卡行：宽度 <600 两列、<900 三列、其余四列。
  Widget _statGrid(BuildContext context, HeatSummary heat, double width) {
    final columns = width >= 900 ? 4 : (width >= 600 ? 3 : 2);
    return GridView.count(
      crossAxisCount: columns,
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      mainAxisSpacing: 8,
      crossAxisSpacing: 8,
      childAspectRatio: columns == 2 ? 2.6 : 2.1,
      children: [
        _statCell(
          context,
          label: heat.indexName.isEmpty ? '指数' : heat.indexName,
          child: PctText(heat.indexChangePct,
              bold: true, style: Theme.of(context).textTheme.titleMedium),
        ),
        _statCell(
          context,
          label: '成交额',
          child: Text(formatAmountCn(heat.totalTurnover),
              style: Theme.of(context)
                  .textTheme
                  .titleMedium
                  ?.copyWith(fontWeight: FontWeight.w600)),
        ),
        _statCell(
          context,
          label: '涨跌家数',
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text('${heat.advanceCount}',
                  style: const TextStyle(color: AppColors.up)),
              Text('/${heat.declineCount}',
                  style: const TextStyle(color: AppColors.down)),
              Text('/${heat.flatCount}',
                  style: const TextStyle(color: AppColors.flat)),
            ],
          ),
        ),
        _statCell(
          context,
          label: '热度分',
          child: Text(
            heat.heatScore?.toStringAsFixed(1) ?? '--',
            style: Theme.of(context)
                .textTheme
                .titleMedium
                ?.copyWith(fontWeight: FontWeight.w600),
          ),
        ),
      ],
    );
  }

  /// 单张统计卡：小字标签 + 内容。
  Widget _statCell(
    BuildContext context, {
    required String label,
    required Widget child,
  }) {
    return Card(
      margin: EdgeInsets.zero,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(label,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: Theme.of(context)
                    .textTheme
                    .bodySmall
                    ?.copyWith(color: Theme.of(context).colorScheme.outline)),
            const SizedBox(height: 4),
            child,
          ],
        ),
      ),
    );
  }

  /// 热度摘要文本卡；staleHint 非空时以 error 色小字提示数据延迟。
  Widget _summaryCard(BuildContext context, HeatSummary heat) {
    return Card(
      margin: EdgeInsets.zero,
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.local_fire_department,
                    size: 18, color: AppColors.up),
                const SizedBox(width: 6),
                Text('今日热度',
                    style: Theme.of(context)
                        .textTheme
                        .titleSmall
                        ?.copyWith(fontWeight: FontWeight.w600)),
              ],
            ),
            const SizedBox(height: 8),
            Text(
              heat.heatSummary.isEmpty ? '暂无热度摘要' : heat.heatSummary,
              style: Theme.of(context).textTheme.bodyMedium,
            ),
            if (heat.staleHint.isNotEmpty) ...[
              const SizedBox(height: 8),
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Icon(Icons.info_outline,
                      size: 14, color: Theme.of(context).colorScheme.error),
                  const SizedBox(width: 4),
                  Expanded(
                    child: Text(
                      heat.staleHint,
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          color: Theme.of(context).colorScheme.error),
                    ),
                  ),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }

  /// Top50 行：排名徽标 + 标的 + 涨跌幅 + 市值/成交额 + 自选星标。
  Widget _topRow(BuildContext context, TopPickRow row) {
    return InkWell(
      onTap: widget.onOpenSymbol == null
          ? null
          : () => widget.onOpenSymbol!(row.symbol, _market, row.name),
      borderRadius: BorderRadius.circular(8),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 10),
        child: Row(
          children: [
            _rankBadge(context, row.rankNo),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Flexible(
                        child: Text(row.symbol,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style:
                                Theme.of(context).textTheme.titleSmall?.copyWith(
                                    fontWeight: FontWeight.w600)),
                      ),
                      const SizedBox(width: 6),
                      Flexible(
                        child: Text(row.name,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: Theme.of(context).textTheme.bodySmall?.copyWith(
                                color: Theme.of(context).colorScheme.outline)),
                      ),
                    ],
                  ),
                  const SizedBox(height: 2),
                  Text(
                    '市值 ${formatAmountCn(row.marketCap)} · 成交 ${formatAmountCn(row.turnover)}',
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: Theme.of(context).colorScheme.outline),
                  ),
                ],
              ),
            ),
            if (row.inWatchlist)
              const Padding(
                padding: EdgeInsets.only(left: 6),
                child: Icon(Icons.star, size: 16, color: Color(0xFFF5A623)),
              ),
            const SizedBox(width: 8),
            PctText(row.changePct, bold: true),
          ],
        ),
      ),
    );
  }

  /// 排名徽标：前三名用涨色高亮，其余中性底色。
  Widget _rankBadge(BuildContext context, int rankNo) {
    final top3 = rankNo > 0 && rankNo <= 3;
    return Container(
      width: 26,
      height: 26,
      alignment: Alignment.center,
      decoration: BoxDecoration(
        color: top3 ? AppColors.up.withValues(alpha: 0.12) : null,
        borderRadius: BorderRadius.circular(6),
      ),
      child: Text(
        '$rankNo',
        style: Theme.of(context).textTheme.labelMedium?.copyWith(
              fontWeight: FontWeight.w700,
              color: top3 ? AppColors.up : Theme.of(context).colorScheme.outline,
            ),
      ),
    );
  }
}

/// 盘中指数条：横向滚动卡片；加载中或空列表（非交易时段）整条隐藏。
class _IndexStrip extends StatelessWidget {
  const _IndexStrip({required this.future});

  final Future<List<IndexQuote>> future;

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<List<IndexQuote>>(
      future: future,
      builder: (context, snap) {
        final items = snap.data;
        if (items == null || items.isEmpty) return const SizedBox.shrink();
        return SizedBox(
          height: 84,
          child: ListView.separated(
            scrollDirection: Axis.horizontal,
            itemCount: items.length,
            separatorBuilder: (_, _) => const SizedBox(width: 8),
            itemBuilder: (context, i) {
              final q = items[i];
              return Container(
                width: 132,
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: Theme.of(context).colorScheme.surfaceContainerHighest,
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(
                      q.name,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: Theme.of(context)
                          .textTheme
                          .bodySmall
                          ?.copyWith(
                              color: Theme.of(context).colorScheme.outline),
                    ),
                    PriceText(q.last,
                        style: Theme.of(context)
                            .textTheme
                            .titleMedium
                            ?.copyWith(fontWeight: FontWeight.w600)),
                    PctText(q.changePct, bold: true),
                  ],
                ),
              );
            },
          ),
        );
      },
    );
  }
}
