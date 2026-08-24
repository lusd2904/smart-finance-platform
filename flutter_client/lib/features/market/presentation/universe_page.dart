import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_client.dart';
import '../../../core/theme/app_theme.dart';
import '../../watchlist/logic/watchlist_providers.dart';
import '../data/market_api.dart';
import '../data/market_models.dart';

/// 市场筛选档位：'' 表示全部市场。
const _marketFilters = <String, String>{
  '': '全部',
  'US': '美股',
  'HK': '港股',
  'CN': 'A 股',
};

/// 市场标签色块配色：与后端 market 枚举一一对应，未知市场回退中性灰。
Color _marketColor(String market) {
  switch (market.toUpperCase()) {
    case 'US':
      return const Color(0xFF409EFF);
    case 'HK':
      return const Color(0xFFE6A23C);
    case 'CN':
      return AppColors.up;
    default:
      return AppColors.flat;
  }
}

/// 全部股票分页浏览页：市场筛选 + 关键字搜索 + 分页加载。
///
/// 行点击经 [onOpenSymbol] 上抛（由 HomeShell 统一接标的详情），
/// 回调为 null 时点击无动作；加自选成功后刷新自选概览。
class UniverseBrowsePage extends ConsumerStatefulWidget {
  const UniverseBrowsePage({super.key, this.onOpenSymbol});

  /// 打开标的详情回调：(symbol, market, name)。
  final void Function(String symbol, String market, String name)? onOpenSymbol;

  @override
  ConsumerState<UniverseBrowsePage> createState() => _UniverseBrowsePageState();
}

class _UniverseBrowsePageState extends ConsumerState<UniverseBrowsePage> {
  static const int _pageSize = 50;

  final _keywordCtrl = TextEditingController();

  String _market = '';
  List<UniverseRow> _rows = const [];
  Map<String, int> _counts = const {};
  int _total = 0;
  int _pageNum = 1;
  bool _loading = false;
  bool _loadingMore = false;
  String? _error;
  bool _addingSymbol = false;

  @override
  void initState() {
    super.initState();
    // 首次进入自动加载第一页。
    _refresh();
  }

  @override
  void dispose() {
    _keywordCtrl.dispose();
    super.dispose();
  }

  bool get _hasMore => !_loading && _rows.length < _total;

  /// 重置到第一页并重新拉取；筛选或关键字变更时调用。
  Future<void> _refresh() async {
    setState(() {
      _pageNum = 1;
      _rows = const [];
      _total = 0;
      _counts = const {};
      _loading = true;
      _error = null;
    });
    try {
      final page = await ref
          .read(marketApiProvider)
          .universe(
            market: _market.isEmpty ? null : _market,
            keyword: _keywordCtrl.text.trim().isEmpty
                ? null
                : _keywordCtrl.text.trim(),
            pageNum: 1,
            pageSize: _pageSize,
          );
      if (!mounted) return;
      setState(() {
        _rows = page.rows;
        _total = page.total;
        _counts = page.counts;
        _loading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = describeApiError(e);
        _loading = false;
      });
    }
  }

  /// 追加下一页；失败仅提示，不打断已有列表。
  Future<void> _loadMore() async {
    if (_loadingMore || !_hasMore) return;
    setState(() => _loadingMore = true);
    try {
      final next = _pageNum + 1;
      final page = await ref
          .read(marketApiProvider)
          .universe(
            market: _market.isEmpty ? null : _market,
            keyword: _keywordCtrl.text.trim().isEmpty
                ? null
                : _keywordCtrl.text.trim(),
            pageNum: next,
            pageSize: _pageSize,
          );
      if (!mounted) return;
      setState(() {
        // 简单按 symbol+market 去重，避免服务端翻页抖动产生重复行。
        final seen = _rows.map((r) => '${r.market}:${r.symbol}').toSet();
        _rows = [
          ..._rows,
          ...page.rows.where((r) => seen.add('${r.market}:${r.symbol}')),
        ];
        _total = page.total;
        _counts = page.counts;
        _pageNum = next;
        _loadingMore = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() => _loadingMore = false);
      ScaffoldMessenger.of(context)
        ..hideCurrentSnackBar()
        ..showSnackBar(
          SnackBar(content: Text('加载更多失败：${describeApiError(e)}')),
        );
    }
  }

  /// 切换市场筛选并重置到第一页。
  void _onMarketChanged(String market) {
    if (market == _market) return;
    setState(() => _market = market);
    _refresh();
  }

  /// 关键字提交（软键盘确认）触发搜索并重置到第一页。
  void _onKeywordSubmitted(String _) => _refresh();

  /// 加自选：成功后刷新自选概览并提示。
  Future<void> _addToWatchlist(UniverseRow row) async {
    if (_addingSymbol) return;
    setState(() => _addingSymbol = true);
    try {
      await ref
          .read(marketApiProvider)
          .addWatchlist(symbol: row.symbol, market: row.market);
      ref.invalidate(watchlistOverviewProvider);
      if (!mounted) return;
      ScaffoldMessenger.of(context)
        ..hideCurrentSnackBar()
        ..showSnackBar(SnackBar(content: Text('已加自选：${row.name}')));
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context)
        ..hideCurrentSnackBar()
        ..showSnackBar(SnackBar(content: Text('加自选失败：${describeApiError(e)}')));
    } finally {
      if (mounted) setState(() => _addingSymbol = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(12, 8, 12, 0),
          child: _buildToolbar(),
        ),
        Padding(
          padding: const EdgeInsets.fromLTRB(12, 8, 12, 4),
          child: _buildCountCards(),
        ),
        Expanded(child: _buildBody()),
      ],
    );
  }

  /// 顶部工具行：市场筛选 SegmentedButton + 关键字搜索框。
  Widget _buildToolbar() {
    return Row(
      children: [
        SegmentedButton<String>(
          segments: [
            for (final e in _marketFilters.entries)
              ButtonSegment(value: e.key, label: Text(e.value)),
          ],
          selected: {_market},
          showSelectedIcon: false,
          onSelectionChanged: (s) => _onMarketChanged(s.first),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: TextField(
            controller: _keywordCtrl,
            decoration: const InputDecoration(
              hintText: '搜索代码 / 名称',
              prefixIcon: Icon(Icons.search),
            ),
            textInputAction: TextInputAction.search,
            onSubmitted: _onKeywordSubmitted,
          ),
        ),
      ],
    );
  }

  /// 计数卡行：US / HK / CN / total 四张小卡。
  Widget _buildCountCards() {
    return Row(
      children: [
        _countCard('美股', _counts['US'] ?? 0),
        const SizedBox(width: 8),
        _countCard('港股', _counts['HK'] ?? 0),
        const SizedBox(width: 8),
        _countCard('A股', _counts['CN'] ?? 0),
        const SizedBox(width: 8),
        _countCard('合计', _counts['total'] ?? _total),
      ],
    );
  }

  Widget _countCard(String label, int count) {
    final scheme = Theme.of(context).colorScheme;
    return Expanded(
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 8),
        decoration: BoxDecoration(
          color: scheme.surfaceContainerHighest.withValues(alpha: 0.5),
          borderRadius: BorderRadius.circular(10),
        ),
        child: Column(
          children: [
            Text(
              label,
              style: Theme.of(context).textTheme.labelSmall
                  ?.copyWith(color: scheme.onSurfaceVariant),
            ),
            const SizedBox(height: 2),
            Text(
              '$count',
              style: Theme.of(context).textTheme.titleMedium
                  ?.copyWith(fontWeight: FontWeight.bold),
            ),
          ],
        ),
      ),
    );
  }

  /// 主体：首屏错误态 / 加载态 / 标的列表 + 底部「加载更多」。
  Widget _buildBody() {
    if (_loading) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_error != null) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(_error!, textAlign: TextAlign.center),
            const SizedBox(height: 12),
            OutlinedButton.icon(
              onPressed: _refresh,
              icon: const Icon(Icons.refresh),
              label: const Text('重试'),
            ),
          ],
        ),
      );
    }
    if (_rows.isEmpty) {
      return const Center(child: Text('暂无数据'));
    }
    return RefreshIndicator(
      onRefresh: _refresh,
      child: ListView.separated(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.only(bottom: 16),
        itemCount: _rows.length + (_hasMore ? 1 : 0),
        separatorBuilder: (_, _) => Divider(
          height: 1,
          indent: 12,
          endIndent: 12,
          color: Colors.grey.shade300,
        ),
        itemBuilder: (context, index) {
          // 列表末尾放「加载更多」，total 用尽即隐藏。
          if (index == _rows.length) {
            return Padding(
              padding: const EdgeInsets.symmetric(vertical: 12),
              child: Center(
                child: _loadingMore
                    ? const SizedBox(
                        width: 22,
                        height: 22,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : OutlinedButton(
                        onPressed: _loadMore,
                        child: const Text('加载更多'),
                      ),
              ),
            );
          }
          return _buildRow(_rows[index]);
        },
      ),
    );
  }

  /// 单行：市场色块 + symbol/name + category 小字 + 行尾「加自选」。
  Widget _buildRow(UniverseRow row) {
    final scheme = Theme.of(context).colorScheme;
    return InkWell(
      onTap: widget.onOpenSymbol == null
          ? null
          : () => widget.onOpenSymbol!(row.symbol, row.market, row.name),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        child: Row(
          children: [
            // 市场标签色块
            Container(
              width: 34,
              height: 20,
              alignment: Alignment.center,
              decoration: BoxDecoration(
                color: _marketColor(row.market),
                borderRadius: BorderRadius.circular(4),
              ),
              child: Text(
                row.market.toUpperCase(),
                maxLines: 1,
                overflow: TextOverflow.clip,
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 10,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text.rich(
                    TextSpan(
                      children: [
                        TextSpan(
                          text: row.symbol,
                          style: const TextStyle(fontWeight: FontWeight.w600),
                        ),
                        const TextSpan(text: '  '),
                        TextSpan(text: row.name),
                      ],
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                  if (row.category.isNotEmpty)
                    Text(
                      row.category,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: Theme.of(context).textTheme.labelSmall
                          ?.copyWith(color: scheme.onSurfaceVariant),
                    ),
                ],
              ),
            ),
            IconButton(
              tooltip: '加自选',
              icon: const Icon(Icons.push_pin_outlined),
              onPressed: _addingSymbol ? null : () => _addToWatchlist(row),
            ),
          ],
        ),
      ),
    );
  }
}
