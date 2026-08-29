import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_client.dart';
import '../../../core/theme/app_theme.dart';
import '../../../shared/widgets/quote_row.dart';
import '../../watchlist/logic/watchlist_providers.dart';
import '../data/market_api.dart';
import '../data/market_models.dart';
import '../data/market_quotes_ws.dart';

/// 市场筛选档位：'' 表示全部市场。
const _marketFilters = <String, String>{
  '': '全部',
  'US': '美股',
  'HK': '港股',
  'CN': 'A股',
};

String _marketLabel(String market) => switch (market.toUpperCase()) {
  'US' => '美股',
  'HK' => '港股',
  'CN' => 'A股',
  _ => market,
};

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
  Timer? _searchDebounce;

  String _market = '';
  List<UniverseRow> _rows = const [];
  int _total = 0;
  int _pageNum = 1;
  bool _loading = false;
  bool _loadingMore = false;
  String? _error;
  bool _addingSymbol = false;

  final Map<String, LiveStockQuote> _live = {};
  VoidCallback? _unsubQuotes;
  String _subSig = '';

  @override
  void initState() {
    super.initState();
    // 首次进入自动加载第一页。
    _refresh();
  }

  @override
  void dispose() {
    _searchDebounce?.cancel();
    _unsubQuotes?.call();
    _keywordCtrl.dispose();
    super.dispose();
  }

  bool get _hasMore => !_loading && _rows.length < _total;

  String get _keyword {
    final text = _keywordCtrl.text.trim();
    return text;
  }

  /// 重置到第一页并重新拉取；筛选或关键字变更时调用。
  Future<void> _refresh() async {
    setState(() {
      _pageNum = 1;
      _rows = const [];
      _total = 0;
      _loading = true;
      _error = null;
    });
    try {
      final page = await ref
          .read(marketApiProvider)
          .universe(
            market: _market.isEmpty ? null : _market,
            keyword: _keyword.isEmpty ? null : _keyword,
            pageNum: 1,
            pageSize: _pageSize,
          );
      if (!mounted) return;
      setState(() {
        _rows = page.rows;
        _total = page.total;
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
            keyword: _keyword.isEmpty ? null : _keyword,
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
    _searchDebounce?.cancel();
    setState(() => _market = market);
    _refresh();
  }

  /// 输入防抖约 300ms 后搜索。
  void _onKeywordChanged(String _) {
    _searchDebounce?.cancel();
    _searchDebounce = Timer(const Duration(milliseconds: 300), () {
      if (!mounted) return;
      _refresh();
    });
  }

  /// 软键盘确认立即搜索，并取消未触发的防抖。
  void _onKeywordSubmitted(String _) {
    _searchDebounce?.cancel();
    _refresh();
  }

  /// 可见行订阅个股行情；签名不变则不重订。
  void _syncQuotes() {
    final sig = _rows.map((r) => '${r.market}:${r.symbol}').join(',');
    if (sig == _subSig) return;
    _subSig = sig;
    _unsubQuotes?.call();
    _unsubQuotes = null;
    if (_rows.isEmpty) return;
    _unsubQuotes = ref.read(stockQuotesHubProvider).subscribe(
      [
        for (final row in _rows)
          (symbol: row.symbol, market: row.market.isEmpty ? 'US' : row.market),
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

  LiveStockQuote? _liveFor(UniverseRow row) {
    final market = row.market.isEmpty ? 'US' : row.market;
    return _live['${market.toUpperCase()}:${row.symbol.toUpperCase()}'];
  }

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
    _syncQuotes();
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(12, 8, 12, 0),
          child: _buildSearchField(),
        ),
        _buildMarketTabs(),
        const QuoteListHeader(trailingWidth: 40),
        Expanded(child: _buildBody()),
      ],
    );
  }

  Widget _buildSearchField() {
    return TextField(
      controller: _keywordCtrl,
      decoration: const InputDecoration(
        hintText: '搜索代码或名称',
        prefixIcon: Icon(Icons.search),
        isDense: true,
      ),
      textInputAction: TextInputAction.search,
      onChanged: _onKeywordChanged,
      onSubmitted: _onKeywordSubmitted,
    );
  }

  /// 下划线文字档：全部 / 美股 / 港股 / A股。
  Widget _buildMarketTabs() {
    final scheme = Theme.of(context).colorScheme;
    return SizedBox(
      height: 40,
      child: Row(
        children: [
          for (final e in _marketFilters.entries)
            Expanded(
              child: InkWell(
                onTap: () => _onMarketChanged(e.key),
                child: Column(
                  children: [
                    Expanded(
                      child: Center(
                        child: Text(
                          e.value,
                          style: TextStyle(
                            fontSize: 14,
                            fontWeight: _market == e.key
                                ? FontWeight.w700
                                : FontWeight.w500,
                            color: _market == e.key
                                ? AppColors.brand
                                : scheme.onSurfaceVariant,
                          ),
                        ),
                      ),
                    ),
                    Container(
                      height: 2,
                      color: _market == e.key
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
        separatorBuilder: (_, _) => const Divider(height: 1),
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

  Widget _buildRow(UniverseRow row) {
    final live = _liveFor(row);
    return QuoteListRow(
      name: row.name.isEmpty ? row.symbol : row.name,
      symbol: row.symbol,
      marketLabel: _marketLabel(row.market),
      last: live?.last,
      changePct: live?.changePct,
      trailing: IconButton(
        tooltip: '加自选',
        visualDensity: VisualDensity.compact,
        icon: const Icon(Icons.add),
        onPressed: _addingSymbol ? null : () => _addToWatchlist(row),
      ),
      onTap: widget.onOpenSymbol == null
          ? null
          : () => widget.onOpenSymbol!(row.symbol, row.market, row.name),
    );
  }
}
