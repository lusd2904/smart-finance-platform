import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/theme/app_theme.dart';
import '../../shared/widgets/quote_row.dart';
import '../auth/logic/session_controller.dart';
import '../market/data/market_api.dart';
import '../market/data/market_models.dart';
import '../market/data/market_quotes_ws.dart';
import '../market/presentation/universe_page.dart';
import '../trade/data/trade_api.dart';
import '../watchlist/logic/watchlist_providers.dart';

/// 自选盯盘首页：顶栏资产 + 搜索 + 指数迷你条 + 分组 + 富途式密排报价。
class PhoneWatchlistPage extends ConsumerStatefulWidget {
  const PhoneWatchlistPage({
    super.key,
    this.onOpenSymbol,
    this.onOpenMine,
    this.onOpenNotice,
  });

  final void Function(String symbol, String market, String name)? onOpenSymbol;
  final VoidCallback? onOpenMine;
  final VoidCallback? onOpenNotice;

  @override
  ConsumerState<PhoneWatchlistPage> createState() => _PhoneWatchlistPageState();
}

class _PhoneWatchlistPageState extends ConsumerState<PhoneWatchlistPage> {
  String _group = '全部';
  final Map<String, LiveStockQuote> _live = {};
  VoidCallback? _unsubQuotes;
  String _subSig = '';

  @override
  void dispose() {
    _unsubQuotes?.call();
    super.dispose();
  }

  void _syncQuotes(List<WatchlistItem> items) {
    final sig = items.map((i) => '${i.market}:${i.symbol}').join(',');
    if (sig == _subSig) return;
    _subSig = sig;
    _unsubQuotes?.call();
    _unsubQuotes = null;
    if (items.isEmpty) return;
    _unsubQuotes = ref.read(stockQuotesHubProvider).subscribe(
      [
        for (final it in items)
          (symbol: it.symbol, market: it.market.isEmpty ? 'US' : it.market),
      ],
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

  WatchlistItem _patched(WatchlistItem item) {
    final key =
        '${(item.market.isEmpty ? 'US' : item.market).toUpperCase()}:${item.symbol.toUpperCase()}';
    final live = _live[key];
    return live == null ? item : applyLiveQuote(item, live);
  }

  @override
  Widget build(BuildContext context) {
    final overview = ref.watch(watchlistOverviewProvider);
    return overview.when(
      loading: () => const Center(child: CircularProgressIndicator()),
      error: (e, _) => Center(
        child: TextButton(
          onPressed: () => ref.invalidate(watchlistOverviewProvider),
          child: Text('加载失败，点此重试\n$e', textAlign: TextAlign.center),
        ),
      ),
      data: (data) {
        _syncQuotes(data.items);
        final items = _group == '全部'
            ? data.items
            : data.items.where((i) => i.groups.contains(_group)).toList();
        return RefreshIndicator(
          onRefresh: () async {
            ref.invalidate(watchlistOverviewProvider);
            ref.invalidate(indexQuotesProvider);
            ref.invalidate(tradeAccountProvider);
            await ref.read(watchlistOverviewProvider.future);
          },
          child: CustomScrollView(
            slivers: [
              SliverToBoxAdapter(
                child: _TopBar(
                  onSearch: () => Navigator.of(context).push(
                    MaterialPageRoute<void>(
                      builder: (_) =>
                          UniverseBrowsePage(onOpenSymbol: widget.onOpenSymbol),
                    ),
                  ),
                  onMine: widget.onOpenMine,
                  onNotice: widget.onOpenNotice,
                ),
              ),
              const SliverToBoxAdapter(child: _IndexStrip()),
              SliverToBoxAdapter(
                child: _GroupBar(
                  selected: _group,
                  count: data.count,
                  groups: data.groups,
                  onSelect: (g) => setState(() => _group = g),
                ),
              ),
              SliverToBoxAdapter(
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
                  child: Text(
                    '共 ${data.count} · 涨 ${data.bullish} · 跌 ${data.bearish} · 平 ${data.neutral}',
                    style: TextStyle(
                      fontSize: 12,
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                    ),
                  ),
                ),
              ),
              const SliverToBoxAdapter(child: QuoteListHeader()),
              if (items.isEmpty)
                const SliverFillRemaining(
                  hasScrollBody: false,
                  child: Center(child: Text('暂无自选，点顶栏搜索添加')),
                )
              else
                SliverPadding(
                  padding: const EdgeInsets.only(bottom: 24),
                  sliver: SliverList.separated(
                    itemCount: items.length,
                    separatorBuilder: (_, _) => const Divider(height: 1),
                    itemBuilder: (_, i) {
                      final item = _patched(items[i]);
                      return QuoteListRow(
                        name: item.name.isEmpty ? item.symbol : item.name,
                        symbol: item.symbol,
                        marketLabel: _marketLabel(item.market),
                        last: item.last,
                        changePct: item.changeRate,
                        leadingExtra: _recTag(item.recommendation),
                        onTap: widget.onOpenSymbol == null
                            ? null
                            : () => widget.onOpenSymbol!(
                                items[i].symbol,
                                items[i].market,
                                items[i].name,
                              ),
                      );
                    },
                  ),
                ),
            ],
          ),
        );
      },
    );
  }
}

class _TopBar extends ConsumerWidget {
  const _TopBar({this.onSearch, this.onMine, this.onNotice});
  final VoidCallback? onSearch;
  final VoidCallback? onMine;
  final VoidCallback? onNotice;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final account = ref.watch(tradeAccountProvider).asData?.value;
    final user = ref.watch(sessionController).user;
    final name = user?.nickName ?? user?.userName ?? '';
    final scheme = Theme.of(context).colorScheme;
    final assets = account?.netAssets ?? account?.totalCash;
    final ccy = (account?.currency ?? '').toUpperCase();
    final prefix = ccy == 'CNY'
        ? '¥'
        : (ccy == 'HKD' ? 'HK\$' : (ccy.isEmpty ? '' : '\$'));

    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 8, 12, 8),
      child: Row(
        children: [
          ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 118),
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
              decoration: BoxDecoration(
                color: scheme.surfaceContainerLow,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: scheme.outlineVariant),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  FittedBox(
                    fit: BoxFit.scaleDown,
                    alignment: Alignment.centerLeft,
                    child: Text(
                      assets == null ? '--' : '$prefix${_money(assets)}',
                      maxLines: 1,
                      style: const TextStyle(
                        fontWeight: FontWeight.w800,
                        fontSize: 13,
                        fontFeatures: AppNum.fontFeatures,
                      ),
                    ),
                  ),
                  Text(
                    assets == null ? '未绑定券商' : '净资产',
                    style: TextStyle(
                      fontSize: 10,
                      color: scheme.onSurfaceVariant,
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Material(
              color: scheme.surfaceContainerLow,
              borderRadius: BorderRadius.circular(22),
              child: InkWell(
                borderRadius: BorderRadius.circular(22),
                onTap: onSearch,
                child: Padding(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 10,
                    vertical: 10,
                  ),
                  child: Row(
                    children: [
                      Icon(
                        Icons.search,
                        size: 18,
                        color: scheme.onSurfaceVariant,
                      ),
                      const SizedBox(width: 6),
                      Expanded(
                        child: Text(
                          '搜索代码或名称',
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: TextStyle(
                            color: scheme.onSurfaceVariant,
                            fontSize: 13,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
          IconButton(
            tooltip: '通知',
            visualDensity: VisualDensity.compact,
            onPressed: onNotice,
            icon: const Icon(Icons.notifications_outlined),
          ),
          GestureDetector(
            onTap: onMine,
            child: CircleAvatar(
              radius: 16,
              backgroundColor: AppColors.brand,
              child: Text(
                name.isEmpty ? 'U' : name.characters.first,
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 13,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  static String _money(double v) {
    final s = v.abs() >= 1000
        ? v
              .toStringAsFixed(2)
              .replaceAllMapped(
                RegExp(r'(\d)(?=(\d{3})+\.)'),
                (m) => '${m[1]},',
              )
        : v.toStringAsFixed(2);
    return s;
  }
}

class _IndexStrip extends ConsumerWidget {
  const _IndexStrip();

  /// WS 有指数快照时用实时流，否则回退 REST（首帧 / 断线 / 测试覆盖）。
  List<IndexQuote> _liveOrPolledIndexes(WidgetRef ref) {
    final live = ref.watch(marketQuotesStreamProvider).asData?.value.items;
    if (live != null && live.isNotEmpty) return live;
    return ref.watch(indexQuotesProvider).asData?.value ?? const <IndexQuote>[];
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final items = _liveOrPolledIndexes(ref).take(6).toList();
    if (items.isEmpty) return const SizedBox(height: 8);
    return IndexMiniStrip(
      items: [
        for (final q in items)
          (
            name: q.name.isEmpty ? q.symbol : q.name,
            last: q.last,
            changePct: q.changePct,
          ),
      ],
    );
  }
}

class _GroupBar extends StatelessWidget {
  const _GroupBar({
    required this.selected,
    required this.count,
    required this.groups,
    required this.onSelect,
  });

  final String selected;
  final int count;
  final List<({String name, int count})> groups;
  final ValueChanged<String> onSelect;

  @override
  Widget build(BuildContext context) {
    final tabs = <(String, int)>[
      ('全部', count),
      for (final g in groups) (g.name, g.count),
    ];
    return SizedBox(
      height: 40,
      child: ListView.separated(
        padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
        scrollDirection: Axis.horizontal,
        itemCount: tabs.length,
        separatorBuilder: (_, _) => const SizedBox(width: 16),
        itemBuilder: (_, i) {
          final t = tabs[i];
          final on = selected == t.$1;
          return GestureDetector(
            onTap: () => onSelect(t.$1),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.end,
              children: [
                Text(
                  t.$1,
                  style: TextStyle(
                    fontWeight: on ? FontWeight.w800 : FontWeight.w500,
                    fontSize: 15,
                    color: on
                        ? Theme.of(context).colorScheme.onSurface
                        : Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
                ),
                const SizedBox(height: 6),
                Container(
                  height: 2,
                  width: 28,
                  color: on ? AppColors.brand : Colors.transparent,
                ),
              ],
            ),
          );
        },
      ),
    );
  }
}

String _marketLabel(String m) => switch (m.toUpperCase()) {
  'US' => '美股',
  'HK' => '港股',
  'CN' => 'A股',
  _ => m,
};

Widget? _recTag(String rec) {
  if (rec.isEmpty) return null;
  final color = rec.contains('买') || rec.contains('多')
      ? AppColors.up
      : rec.contains('卖') || rec.contains('空')
      ? AppColors.down
      : AppColors.flat;
  return Container(
    padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 1),
    decoration: BoxDecoration(
      color: color.withValues(alpha: 0.14),
      borderRadius: BorderRadius.circular(4),
    ),
    child: Text(
      rec,
      maxLines: 1,
      overflow: TextOverflow.ellipsis,
      style: TextStyle(
        fontSize: 10,
        color: color,
        fontWeight: FontWeight.w700,
        height: 1.1,
      ),
    ),
  );
}
