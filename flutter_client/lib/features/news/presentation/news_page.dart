import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/theme/app_theme.dart';
import '../../../shared/utils/format.dart';
import '../../../shared/widgets/page_header.dart';
import '../data/briefing_api.dart';
import '../data/briefing_models.dart';

/// 财经资讯流：美/港/A 市场切换 + 简报卡片流。
/// 设计依据：设计稿 §3.4.1 资讯列表 / §3.4.3 移动端信息流
/// （来源·时间 chip、加粗标题、AI 摘要引用框）；桌面宽屏双列瀑布。
class NewsPage extends ConsumerStatefulWidget {
  const NewsPage({super.key});

  @override
  ConsumerState<NewsPage> createState() => _NewsPageState();
}

class _NewsPageState extends ConsumerState<NewsPage> {
  static const _markets = {'US': '美股', 'HK': '港股', 'CN': 'A股'};

  String _market = 'US';
  int _limit = 20;
  late Future<List<BriefingItem>> _future;

  @override
  void initState() {
    super.initState();
    _future = ref.read(briefingApiProvider).briefings(market: _market, limit: _limit);
  }

  void _reload({bool refresh = false}) {
    setState(() {
      if (refresh) _limit = 20;
      _future = ref
          .read(briefingApiProvider)
          .briefings(market: _market, limit: _limit, refresh: refresh);
    });
  }

  @override
  Widget build(BuildContext context) {
    final wide = MediaQuery.sizeOf(context).width >= AppDimens.wideBreakpoint;
    return Scaffold(
      body: RefreshIndicator(
        onRefresh: () async => _reload(refresh: true),
        child: FutureBuilder<List<BriefingItem>>(
          future: _future,
          builder: (context, snap) {
            final items = snap.data;
            Widget body;
            if (snap.connectionState == ConnectionState.waiting && items == null) {
              body = const Center(child: CircularProgressIndicator());
            } else if (snap.hasError && (items == null || items.isEmpty)) {
              body = _ErrorView(error: '${snap.error}', onRetry: () => _reload());
            } else if (items == null || items.isEmpty) {
              body = const _EmptyView();
            } else {
              body = _buildList(items, wide);
            }
            return CustomScrollView(
              physics: const AlwaysScrollableScrollPhysics(),
              slivers: [
                SliverAppBar(
                  pinned: true,
                  title: PageHeader(
                    title: '财经资讯',
                    subtitle: '简报快照 $_market · ${items?.length ?? '--'} 条',
                  ),
                  actions: [
                    SegmentedButton<String>(
                      showSelectedIcon: false,
                      style: const ButtonStyle(visualDensity: VisualDensity.compact),
                      segments: [
                        for (final e in _markets.entries)
                          ButtonSegment(value: e.key, label: Text(e.value)),
                      ],
                      selected: {_market},
                      onSelectionChanged: (s) {
                        setState(() => _market = s.first);
                        _reload(refresh: true);
                      },
                    ),
                    const SizedBox(width: 12),
                  ],
                ),
                SliverToBoxAdapter(child: body),
              ],
            );
          },
        ),
      ),
    );
  }

  Widget _buildList(List<BriefingItem> items, bool wide) {
    final canLoadMore = _limit < 60 && items.length >= _limit;
    final cards = [for (final item in items) BriefingCard(item: item)];
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: AppDimens.pagePadding),
      child: Column(
        children: [
          const SizedBox(height: 8),
          if (wide)
            // 宽屏双列瀑布，降低长列表滚动距离。
            LayoutBuilder(builder: (context, c) {
              const gap = 10.0;
              final colW = (c.maxWidth - gap) / 2;
              return Wrap(
                spacing: gap,
                runSpacing: gap,
                children: [
                  for (final card in cards)
                    SizedBox(width: colW, child: card),
                ],
              );
            })
          else ...[
            for (final card in cards) ...[card, const SizedBox(height: 10)],
          ],
          if (canLoadMore)
            Padding(
              padding: const EdgeInsets.only(top: 2, bottom: 16),
              child: OutlinedButton.icon(
                onPressed: () {
                  _limit = (_limit + 20).clamp(1, 60);
                  _reload();
                },
                icon: const Icon(Icons.expand_more, size: 18),
                label: const Text('加载更多'),
              ),
            )
          else
            const SizedBox(height: 24),
        ],
      ),
    );
  }
}

/// 简报卡片：左侧品牌色条 + 标题 + 摘要引用框 + 来源·时间行。
class BriefingCard extends StatelessWidget {
  const BriefingCard({super.key, required this.item});

  final BriefingItem item;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    return Container(
      decoration: BoxDecoration(
        color: scheme.surfaceContainerLow,
        borderRadius: BorderRadius.circular(AppDimens.radiusCard),
        border: Border.all(color: scheme.outlineVariant),
      ),
      padding: const EdgeInsets.all(14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // 标题：15sp 加粗（设计稿 §3.4.3）。
          Text(
            item.headline,
            maxLines: 3,
            overflow: TextOverflow.ellipsis,
            style: theme.textTheme.titleMedium?.copyWith(
              fontSize: 15,
              fontWeight: FontWeight.w700,
              height: 1.35,
            ),
          ),
          if (item.summary.isNotEmpty) ...[
            const SizedBox(height: 8),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: scheme.surfaceContainerHighest.withValues(alpha: 0.5),
                borderRadius: BorderRadius.circular(AppDimens.radiusControl - 2),
              ),
              child: Text(
                item.summary,
                maxLines: 4,
                overflow: TextOverflow.ellipsis,
                style: theme.textTheme.bodySmall?.copyWith(
                  color: scheme.onSurfaceVariant,
                  height: 1.4,
                ),
              ),
            ),
          ],
          const SizedBox(height: 10),
          Row(
            children: [
              Icon(Icons.public_rounded, size: 13, color: scheme.onSurfaceVariant),
              const SizedBox(width: 4),
              Expanded(
                child: Text(
                  item.sourceName.isEmpty ? '未知来源' : item.sourceName,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: scheme.onSurfaceVariant,
                  ),
                ),
              ),
              Text(
                formatRelativeTime(item.generatedAt),
                style: AppNum.style(theme.textTheme.bodySmall!).copyWith(
                  color: scheme.onSurfaceVariant,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _ErrorView extends StatelessWidget {
  const _ErrorView({required this.error, this.onRetry});

  final String error;
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(top: 120),
      child: Column(
        children: [
          Icon(Icons.cloud_off_outlined,
              size: 48, color: Theme.of(context).colorScheme.outline),
          const SizedBox(height: 12),
          Text(describeApiErrorSafe(error), textAlign: TextAlign.center),
          const SizedBox(height: 16),
          FilledButton.tonalIcon(
            onPressed: onRetry,
            icon: const Icon(Icons.refresh),
            label: const Text('重试'),
          ),
        ],
      ),
    );
  }
}

class _EmptyView extends StatelessWidget {
  const _EmptyView();

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(top: 140),
      child: Center(
        child: Column(
          children: [
            Icon(Icons.inbox_outlined, size: 48, color: Theme.of(context).colorScheme.outline),
            const SizedBox(height: 12),
            Text('暂无简报，稍后下拉刷新', style: Theme.of(context).textTheme.bodyMedium),
            const SizedBox(height: 220),
          ],
        ),
      ),
    );
  }
}

/// 错误文案兜底：非 Dio 异常直接展示摘要。
String describeApiErrorSafe(String raw) {
  if (raw.contains('timed out') || raw.contains('Timeout')) return '连接超时，请检查网关与服务状态';
  if (raw.contains('Connection refused') || raw.contains('Connection error')) {
    return '无法连接网关，请确认服务已启动';
  }
  return raw.length > 80 ? '${raw.substring(0, 80)}…' : raw;
}
