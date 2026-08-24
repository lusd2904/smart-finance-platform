import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:flutter_client/core/api/api_client.dart';
import 'package:flutter_client/core/theme/app_theme.dart';
import 'package:flutter_client/features/market/data/market_api.dart';
import 'package:flutter_client/features/market/data/market_models.dart';
import 'package:flutter_client/features/watchlist/logic/watchlist_providers.dart';
import 'package:flutter_client/shared/widgets/page_header.dart';
import 'package:flutter_client/shared/widgets/stat_grid.dart';
import 'package:flutter_client/shared/widgets/quote_text.dart';

/// 自选清单 tab：概览卡 + 分组筛选 + 标的列表，宽屏左侧固定分组栏、窄屏顶部 chip 行。
class WatchlistTab extends ConsumerStatefulWidget {
  const WatchlistTab({super.key, this.onOpenSymbol});

  /// 打开标的详情回调（symbol, market, name），由外层统一接入详情页；为空时点击无动作。
  final void Function(String symbol, String market, String name)? onOpenSymbol;

  @override
  ConsumerState<WatchlistTab> createState() => _WatchlistTabState();
}

class _WatchlistTabState extends ConsumerState<WatchlistTab> {
  /// 当前选中分组名；null 表示「全部」。
  String? _selectedGroup;

  @override
  Widget build(BuildContext context) {
    final overviewAsync = ref.watch(watchlistOverviewProvider);
    return overviewAsync.when(
      loading: () => const Center(child: CircularProgressIndicator()),
      error: (error, _) => _buildError(error),
      data: (overview) {
        // 按选中分组过滤列表（全部时不过滤）。
        final items = _selectedGroup == null
            ? overview.items
            : overview.items
                  .where((it) => it.groups.contains(_selectedGroup))
                  .toList();
        // 宽屏：左 220px 分组栏 + 右列表；窄屏：概览卡下横向 chip 行。
        return Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const PageHeader(title: '自选', subtitle: '分组跟踪与倾向概览'),
            Expanded(
              child: LayoutBuilder(
                builder: (context, constraints) {
                  final wide = constraints.maxWidth > 1000;
                  final content = wide
                      ? Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            SizedBox(
                              width: 220,
                              child: _buildGroupPanel(overview),
                            ),
                            const VerticalDivider(width: 1),
                            Expanded(
                              child: items.isEmpty
                                  ? _buildEmpty(
                                      items.isEmpty && overview.items.isEmpty,
                                    )
                                  : _buildItemList(items),
                            ),
                          ],
                        )
                      : Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            _buildOverviewCards(overview),
                            _buildGroupChipBar(overview),
                            Expanded(
                              child: items.isEmpty
                                  ? _buildEmpty(overview.items.isEmpty)
                                  : _buildItemList(items),
                            ),
                          ],
                        );
                  if (!wide) return content;
                  // 宽屏时概览卡横跨顶部，下方左右分栏。
                  return Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      _buildOverviewCards(overview),
                      Expanded(child: content),
                    ],
                  );
                },
              ),
            ),
          ],
        );
      },
    );
  }

  /// 错误态：可读文案 + 重试。
  Widget _buildError(Object error) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(describeApiError(error), textAlign: TextAlign.center),
            const SizedBox(height: 12),
            FilledButton.tonalIcon(
              onPressed: () => ref.invalidate(watchlistOverviewProvider),
              icon: const Icon(Icons.refresh),
              label: const Text('重试'),
            ),
          ],
        ),
      ),
    );
  }

  /// 空态引导文案。overall 为真表示整个自选为空，否则只是当前分组为空。
  Widget _buildEmpty(bool overall) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.star_border, size: 48, color: Theme.of(context).hintColor),
          const SizedBox(height: 8),
          Text(
            overall ? '暂无自选标的，去行情页点击「加自选」开始跟踪吧' : '该分组下暂无自选标的',
            style: TextStyle(color: Theme.of(context).hintColor),
          ),
        ],
      ),
    );
  }

  /// 概览卡行：自选数量 / 偏多 / 偏空 / 中性。
  Widget _buildOverviewCards(WatchlistOverview overview) {
    final cards = [
      (label: '自选数量', value: overview.count, color: AppColors.flat),
      (label: '偏多', value: overview.bullish, color: AppColors.up),
      (label: '偏空', value: overview.bearish, color: AppColors.down),
      (label: '中性', value: overview.neutral, color: AppColors.flat),
    ];
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: AppDimens.pagePadding),
      child: StatGrid(
        cells: [
          for (final c in cards)
            StatCellData(
              label: c.label,
              value: Text('${c.value}', style: TextStyle(color: c.color)),
            ),
        ],
      ),
    );
  }

  /// 窄屏顶部分组 chip 行：「全部」+ 各分组（name + count）。
  Widget _buildGroupChipBar(WatchlistOverview overview) {
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      padding: const EdgeInsets.fromLTRB(12, 12, 12, 0),
      child: Row(
        children: [
          Padding(
            padding: const EdgeInsets.only(right: 8),
            child: ChoiceChip(
              label: Text('全部 ${overview.count}'),
              selected: _selectedGroup == null,
              onSelected: (_) => setState(() => _selectedGroup = null),
            ),
          ),
          for (final g in overview.groups)
            Padding(
              padding: const EdgeInsets.only(right: 8),
              child: ChoiceChip(
                label: Text('${g.name} ${g.count}'),
                selected: _selectedGroup == g.name,
                onSelected: (_) => setState(() => _selectedGroup = g.name),
              ),
            ),
        ],
      ),
    );
  }

  /// 宽屏左侧固定分组栏。
  Widget _buildGroupPanel(WatchlistOverview overview) {
    return Material(
      color: Theme.of(context).colorScheme.surface,
      child: ListView(
        padding: const EdgeInsets.symmetric(vertical: 8),
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 4),
            child: Text(
              '分组',
              style: TextStyle(
                fontSize: 12,
                color: Theme.of(context).hintColor,
              ),
            ),
          ),
          _buildGroupTile(
            '全部',
            overview.count,
            _selectedGroup == null,
            () => setState(() => _selectedGroup = null),
          ),
          for (final g in overview.groups)
            _buildGroupTile(
              g.name,
              g.count,
              _selectedGroup == g.name,
              () => setState(() => _selectedGroup = g.name),
            ),
        ],
      ),
    );
  }

  /// 分组栏单行选项。
  Widget _buildGroupTile(
    String name,
    int count,
    bool selected,
    VoidCallback onTap,
  ) {
    final scheme = Theme.of(context).colorScheme;
    return InkWell(
      onTap: onTap,
      child: Container(
        margin: const EdgeInsets.symmetric(horizontal: 8),
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 9),
        decoration: BoxDecoration(
          color: selected ? scheme.primary.withValues(alpha: 0.12) : null,
          borderRadius: BorderRadius.circular(AppDimens.radiusControl),
        ),
        child: Row(
          children: [
            Expanded(
              child: Text(
                name,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(
                  fontWeight: selected ? FontWeight.w600 : null,
                  color: selected ? scheme.primary : null,
                ),
              ),
            ),
            Text(
              '$count',
              style: TextStyle(
                fontSize: 12,
                color: Theme.of(context).hintColor,
              ),
            ),
          ],
        ),
      ),
    );
  }

  /// 自选标的列表。
  Widget _buildItemList(List<WatchlistItem> items) {
    return ListView.separated(
      padding: const EdgeInsets.all(12),
      itemCount: items.length,
      separatorBuilder: (_, _) => const SizedBox(height: 8),
      itemBuilder: (context, index) => _buildItemCard(items[index]),
    );
  }

  /// 单个自选卡片：名称报价 + 分组 chips + 推荐标签 + 删除按钮。
  Widget _buildItemCard(WatchlistItem item) {
    final hintColor = Theme.of(context).hintColor;
    return Card(
      margin: EdgeInsets.zero,
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: widget.onOpenSymbol == null || item.symbol.isEmpty
            ? null
            : () => widget.onOpenSymbol!(item.symbol, item.market, item.name),
        child: Padding(
          padding: const EdgeInsets.fromLTRB(12, 10, 4, 10),
          child: Row(
            children: [
              // 名称区：symbol + name。
              Expanded(
                flex: 3,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      item.name.isEmpty ? item.symbol : item.name,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(fontWeight: FontWeight.w600),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      item.symbol +
                          (item.market.isEmpty ? '' : ' · ${item.market}'),
                      style: TextStyle(fontSize: 12, color: hintColor),
                    ),
                    // 分组小号 chip（最多展示 3 个）。
                    if (item.groups.isNotEmpty)
                      Padding(
                        padding: const EdgeInsets.only(top: 4),
                        child: Wrap(
                          spacing: 4,
                          runSpacing: 2,
                          children: [
                            for (final g in item.groups.take(3))
                              Container(
                                padding: const EdgeInsets.symmetric(
                                  horizontal: 6,
                                  vertical: 1,
                                ),
                                decoration: BoxDecoration(
                                  color: Theme.of(context)
                                      .colorScheme
                                      .surfaceContainerHighest,
                                  borderRadius: BorderRadius.circular(4),
                                ),
                                child: Text(
                                  g,
                                  style: TextStyle(
                                    fontSize: 10,
                                    color: hintColor,
                                  ),
                                ),
                              ),
                          ],
                        ),
                      ),
                  ],
                ),
              ),
              // 报价区：最新价 + 涨跌幅。
              Expanded(
                flex: 2,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    PriceText(item.last),
                    const SizedBox(height: 2),
                    PctText(item.changeRate),
                  ],
                ),
              ),
              // 推荐标签：含买/多红、含卖/空绿、其他灰。
              if (item.recommendation.isNotEmpty)
                Padding(
                  padding: const EdgeInsets.only(left: 8),
                  child: _buildRecommendationTag(item.recommendation),
                ),
              // 删除按钮。
              IconButton(
                tooltip: '删除自选',
                icon: const Icon(Icons.delete_outline),
                onPressed: () => _confirmDelete(item),
              ),
            ],
          ),
        ),
      ),
    );
  }

  /// 推荐结论色块标签：含'买'/'多'→红、含'卖'/'空'→绿、其余灰。
  Widget _buildRecommendationTag(String text) {
    final color = switch (text) {
      _ when text.contains('买') || text.contains('多') => AppColors.up,
      _ when text.contains('卖') || text.contains('空') => AppColors.down,
      _ => AppColors.flat,
    };
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(
        text,
        maxLines: 1,
        overflow: TextOverflow.ellipsis,
        style: TextStyle(fontSize: 11, color: color),
      ),
    );
  }

  /// 删除确认对话框 → 删自选 → 刷新概览 + SnackBar 提示。
  Future<void> _confirmDelete(WatchlistItem item) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('删除自选'),
        content: Text(
          '确定将「${item.name.isEmpty ? item.symbol : item.name}」移出自选吗？',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('取消'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('删除'),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;
    final id = item.id;
    try {
      if (id == null) throw StateError('缺少自选记录 id');
      await ref.read(marketApiProvider).deleteWatchlist([id]);
      ref.invalidate(watchlistOverviewProvider);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('已移除自选：${item.name.isEmpty ? item.symbol : item.name}'),
        ),
      );
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(describeApiError(e))));
    }
  }
}
