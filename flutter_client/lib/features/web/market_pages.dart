import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api/api_client.dart';
import '../../core/api/ruoyi_client.dart';
import '../../core/theme/app_theme.dart';
import '../../features/kline/logic/kline_painter.dart';
import '../../features/market/data/market_api.dart';
import '../../features/market/data/market_models.dart';
import '../../shared/widgets/ruoyi_ui.dart';
import 'json_list_page.dart';

class MarketHeatPage extends ConsumerStatefulWidget {
  const MarketHeatPage({super.key, this.open});
  final OpenRoute? open;

  @override
  ConsumerState<MarketHeatPage> createState() => _MarketHeatPageState();
}

class _MarketHeatPageState extends ConsumerState<MarketHeatPage> {
  String _market = 'US';
  bool _busy = true;
  String? _error;
  HeatDailyData? _data;
  List<HeatTrendPoint> _trend = const [];

  @override
  void initState() {
    super.initState();
    Future<void>.microtask(_load);
  }

  Future<void> _load() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final api = ref.read(marketApiProvider);
      final data = await api.heatDaily(market: _market);
      final trend = await api.heatTrend(market: _market);
      if (!mounted) return;
      setState(() {
        _data = data;
        _trend = trend;
        _busy = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _busy = false;
        _error = describeApiError(e);
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final heat = _data?.heat;
    return AppPage(
      child: ListView(
        children: [
          PageHero(
            title: '市场热度',
            subtitle: '三市场指数 · 涨跌家数 · Top50',
            actions: [
              SegmentedButton<String>(
                segments: const [
                  ButtonSegment(value: 'US', label: Text('美股')),
                  ButtonSegment(value: 'HK', label: Text('港股')),
                  ButtonSegment(value: 'CN', label: Text('A股')),
                ],
                selected: {_market},
                onSelectionChanged: (s) {
                  _market = s.first;
                  _load();
                },
              ),
              OutlinedButton(onPressed: _load, child: const Text('刷新')),
            ],
          ),
          if (_error != null) ErrorBanner(_error!, onRetry: _load),
          if (_busy) const LinearProgressIndicator(minHeight: 2),
          ElCard(
            header: Text(heat?.indexName.isNotEmpty == true ? heat!.indexName : '热度摘要'),
            child: KvGrid({
              '时间': heat?.asOfTime ?? '',
              '涨跌%': heat?.indexChangePct?.toStringAsFixed(2) ?? '',
              '热度分': heat?.heatScore?.toStringAsFixed(1) ?? '',
              '上涨': '${heat?.advanceCount ?? 0}',
              '下跌': '${heat?.declineCount ?? 0}',
              '平盘': '${heat?.flatCount ?? 0}',
              '摘要': heat?.heatSummary ?? '',
            }),
          ),
          const SizedBox(height: 12),
          ElCard(
            header: const Text('近五日趋势'),
            child: _trend.isEmpty
                ? const EmptyHint('暂无趋势')
                : SizedBox(
                    height: 80,
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.end,
                      children: [
                        for (final p in _trend)
                          Expanded(
                            child: Padding(
                              padding: const EdgeInsets.symmetric(horizontal: 4),
                              child: Column(
                                children: [
                                  Expanded(
                                    child: Align(
                                      alignment: Alignment.bottomCenter,
                                      child: FractionallySizedBox(
                                        heightFactor: ((p.heatScore ?? 0) / 100).clamp(0.05, 1),
                                        child: Container(
                                          decoration: BoxDecoration(
                                            color: WebQuote.colorOf(p.heatScore ?? 0),
                                            borderRadius: BorderRadius.circular(3),
                                          ),
                                        ),
                                      ),
                                    ),
                                  ),
                                  const SizedBox(height: 4),
                                  Text(p.tradeDate, style: const TextStyle(fontSize: 10)),
                                ],
                              ),
                            ),
                          ),
                      ],
                    ),
                  ),
          ),
          const SizedBox(height: 12),
          ElCard(
            header: const Text('Top50'),
            padding: EdgeInsets.zero,
            child: AppDimens.isWide(context)
                ? SimpleTable(
                    columns: const [
                      TableCol('排名', 'rankNo'),
                      TableCol('代码', 'symbol'),
                      TableCol('名称', 'name'),
                      TableCol('涨跌%', 'changePct'),
                      TableCol('成交额', 'turnover'),
                    ],
                    rows: [
                      for (final r in _data?.top50 ?? const <TopPickRow>[])
                        {
                          'rankNo': r.rankNo,
                          'symbol': r.symbol,
                          'name': r.name,
                          'changePct': r.changePct,
                          'turnover': r.turnover,
                          'market': _market,
                        },
                    ],
                    onRowTap: (row) => widget.open?.call(
                      '/market/kline?symbol=${row['symbol']}&market=$_market',
                      title: '${row['symbol']}',
                    ),
                  )
                : Column(
                    children: [
                      for (final r in _data?.top50 ?? const <TopPickRow>[])
                        QuoteListTile(
                          rank: r.rankNo,
                          title: r.name.isEmpty ? r.symbol : r.name,
                          subtitle: r.symbol,
                          changePct: r.changePct,
                          onTap: () => widget.open?.call(
                            '/market/kline?symbol=${r.symbol}&market=$_market',
                            title: r.symbol,
                          ),
                        ),
                    ],
                  ),
          ),
        ],
      ),
    );
  }
}

class WebQuote {
  static Color colorOf(num v) {
    if (v > 0) return AppColors.up;
    if (v < 0) return AppColors.down;
    return AppColors.flat;
  }
}

class MarketBoardPage extends ConsumerStatefulWidget {
  const MarketBoardPage({super.key, this.open});
  final OpenRoute? open;

  @override
  ConsumerState<MarketBoardPage> createState() => _MarketBoardPageState();
}

class _MarketBoardPageState extends ConsumerState<MarketBoardPage> {
  String _market = 'US';
  bool _busy = false;
  String? _error;
  List<BoardQuote> _rows = const [];

  @override
  void initState() {
    super.initState();
    Future<void>.microtask(_load);
  }

  Future<void> _load() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final rows = await ref.read(marketApiProvider).boardQuotes(market: _market);
      if (!mounted) return;
      setState(() {
        _rows = rows;
        _busy = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _busy = false;
        _error = describeApiError(e);
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return AppPage(
      child: Column(
        children: [
          PageHero(
            title: '行情台',
            subtitle: '批量报价',
            actions: [
              SegmentedButton<String>(
                segments: const [
                  ButtonSegment(value: 'US', label: Text('美股')),
                  ButtonSegment(value: 'HK', label: Text('港股')),
                  ButtonSegment(value: 'CN', label: Text('A股')),
                ],
                selected: {_market},
                onSelectionChanged: (s) {
                  _market = s.first;
                  _load();
                },
              ),
              OutlinedButton(onPressed: _load, child: const Text('刷新')),
              if (widget.open != null)
                FilledButton(
                  onPressed: () => widget.open!('/trade/terminal', title: '行情交易'),
                  child: const Text('行情交易'),
                ),
            ],
          ),
          if (_error != null) ErrorBanner(_error!, onRetry: _load),
          Expanded(
            child: ElCard(
              padding: EdgeInsets.zero,
              child: SimpleTable(
                busy: _busy,
                columns: const [
                  TableCol('代码', 'symbol'),
                  TableCol('名称', 'name'),
                  TableCol('最新', 'price'),
                  TableCol('涨跌%', 'changeRate'),
                ],
                rows: [
                  for (final q in _rows)
                    {
                      'symbol': q.symbol,
                      'name': q.name,
                      'price': q.price,
                      'changeRate': q.changeRate,
                      'market': q.market.isEmpty ? _market : q.market,
                    },
                ],
                onRowTap: (row) => widget.open?.call(
                  '/market/kline?symbol=${row['symbol']}&market=${row['market']}',
                  title: '${row['symbol']} K线',
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class MarketKlinePage extends ConsumerStatefulWidget {
  const MarketKlinePage({
    super.key,
    this.symbol = 'AAPL',
    this.market = 'US',
    this.open,
  });

  final String symbol;
  final String market;
  final OpenRoute? open;

  @override
  ConsumerState<MarketKlinePage> createState() => _MarketKlinePageState();
}

class _MarketKlinePageState extends ConsumerState<MarketKlinePage> {
  late final TextEditingController _symbol;
  late String _market;
  String _period = 'daily';
  bool _busy = false;
  String? _error;
  List<KlineBar> _bars = const [];

  @override
  void initState() {
    super.initState();
    _symbol = TextEditingController(text: widget.symbol);
    _market = widget.market;
    Future<void>.microtask(_load);
  }

  @override
  void dispose() {
    _symbol.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final bars = await ref.read(marketApiProvider).kline(
            symbol: _symbol.text.trim(),
            market: _market,
            period: _period,
          );
      if (!mounted) return;
      setState(() {
        _bars = bars;
        _busy = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _busy = false;
        _error = describeApiError(e);
        _bars = const [];
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return AppPage(
      child: Column(
        children: [
          PageHero(
            title: '行情K线',
            subtitle: '${_symbol.text} · $_market · $_period',
            actions: [
              SizedBox(
                width: 140,
                child: TextField(
                  controller: _symbol,
                  decoration: const InputDecoration(labelText: '代码', isDense: true),
                  onSubmitted: (_) => _load(),
                ),
              ),
              DropdownButton<String>(
                value: _market,
                items: const [
                  DropdownMenuItem(value: 'US', child: Text('US')),
                  DropdownMenuItem(value: 'HK', child: Text('HK')),
                  DropdownMenuItem(value: 'CN', child: Text('CN')),
                ],
                onChanged: (v) {
                  _market = v ?? 'US';
                  _load();
                },
              ),
              SegmentedButton<String>(
                segments: const [
                  ButtonSegment(value: 'intraday', label: Text('分时')),
                  ButtonSegment(value: 'daily', label: Text('日K')),
                  ButtonSegment(value: 'weekly', label: Text('周K')),
                  ButtonSegment(value: 'monthly', label: Text('月K')),
                ],
                selected: {_period},
                onSelectionChanged: (s) {
                  _period = s.first;
                  _load();
                },
              ),
              FilledButton(onPressed: _load, child: const Text('查询')),
              TextButton(
                onPressed: () => widget.open?.call(
                  '/market/symbol?symbol=${_symbol.text}&market=$_market',
                  title: _symbol.text,
                ),
                child: const Text('基本信息'),
              ),
            ],
          ),
          if (_error != null) ErrorBanner(_error!, onRetry: _load),
          if (_busy) const LinearProgressIndicator(minHeight: 2),
          Expanded(
            child: ElCard(
              expand: true,
              padding: EdgeInsets.zero,
              child: _bars.isEmpty
                  ? const EmptyHint('暂无K线')
                  : InteractiveKlineChart(bars: _bars),
            ),
          ),
        ],
      ),
    );
  }
}

class MarketSymbolPage extends ConsumerStatefulWidget {
  const MarketSymbolPage({
    super.key,
    required this.symbol,
    required this.market,
    this.open,
  });
  final String symbol;
  final String market;
  final OpenRoute? open;

  @override
  ConsumerState<MarketSymbolPage> createState() => _MarketSymbolPageState();
}

class _MarketSymbolPageState extends ConsumerState<MarketSymbolPage> {
  bool _busy = true;
  String? _error;
  Map<String, dynamic> _data = const {};

  @override
  void initState() {
    super.initState();
    Future<void>.microtask(_load);
  }

  Future<void> _load() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final data = await ref.read(marketApiProvider).symbolOverview(
            symbol: widget.symbol,
            market: widget.market,
          );
      if (!mounted) return;
      setState(() {
        _data = data;
        _busy = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _busy = false;
        _error = describeApiError(e);
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final flat = <String, String>{};
    _data.forEach((k, v) {
      if (v is! Map && v is! List) flat[k] = cellText(v);
    });
    return AppPage(
      child: ListView(
        children: [
          PageHero(
            title: '${widget.symbol} 标的详情',
            subtitle: widget.market,
            actions: [
              OutlinedButton(
                onPressed: () => widget.open?.call(
                  '/market/kline?symbol=${widget.symbol}&market=${widget.market}',
                  title: '${widget.symbol} K线',
                ),
                child: const Text('K线'),
              ),
              OutlinedButton(
                onPressed: () => widget.open?.call(
                  '/trade/desk?symbol=${widget.symbol}&market=${widget.market}',
                  title: '交易工作台',
                ),
                child: const Text('交易'),
              ),
            ],
          ),
          if (_error != null) ErrorBanner(_error!, onRetry: _load),
          if (_busy) const LinearProgressIndicator(minHeight: 2),
          ElCard(child: KvGrid(flat)),
        ],
      ),
    );
  }
}

class MarketWatchlistPage extends ConsumerStatefulWidget {
  const MarketWatchlistPage({super.key, this.open});
  final OpenRoute? open;

  @override
  ConsumerState<MarketWatchlistPage> createState() => _MarketWatchlistPageState();
}

class _MarketWatchlistPageState extends ConsumerState<MarketWatchlistPage> {
  bool _busy = true;
  String? _error;
  WatchlistOverview? _data;
  String _group = '全部';
  WatchlistItem? _picked;

  @override
  void initState() {
    super.initState();
    Future<void>.microtask(_load);
  }

  Future<void> _load() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final data = await ref.read(marketApiProvider).watchlistOverview();
      if (!mounted) return;
      setState(() {
        _data = data;
        _busy = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _busy = false;
        _error = describeApiError(e);
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final all = _data?.items ?? const <WatchlistItem>[];
    final items = _group == '全部'
        ? all
        : all.where((i) => i.groups.contains(_group) || i.note.contains(_group)).toList();
    final wide = MediaQuery.sizeOf(context).width >= 900;
    final table = ElCard(
      padding: EdgeInsets.zero,
      child: SimpleTable(
        busy: _busy,
        columns: const [
          TableCol('代码', 'symbol'),
          TableCol('名称', 'name'),
          TableCol('市场', 'market'),
          TableCol('最新', 'last'),
          TableCol('涨跌%', 'changeRate'),
        ],
        rows: [
          for (final i in items)
            {
              'symbol': i.symbol,
              'name': i.name,
              'market': i.market,
              'last': i.last,
              'changeRate': i.changeRate,
              'note': i.note,
              'id': i.id,
            },
        ],
        onRowTap: (row) {
          WatchlistItem? hit;
          for (final i in all) {
            if (i.symbol == row['symbol'] && i.market == row['market']) {
              hit = i;
              break;
            }
          }
          setState(() => _picked = hit);
          widget.open?.call(
            '/market/kline?symbol=${row['symbol']}&market=${row['market']}',
            title: '${row['symbol']}',
          );
        },
      ),
    );
    return AppPage(
      child: Column(
        children: [
          PageHero(
            title: '自选清单',
            subtitle: '共 ${_data?.count ?? 0} · 涨 ${_data?.bullish ?? 0} · 跌 ${_data?.bearish ?? 0}',
            actions: [OutlinedButton(onPressed: _load, child: const Text('刷新'))],
          ),
          if (_error != null) ErrorBanner(_error!, onRetry: _load),
          Expanded(
            child: wide
                ? Row(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      SizedBox(
                        width: 200,
                        child: ElCard(
                          expand: true,
                          header: const Text('分组'),
                          child: ListView(
                            shrinkWrap: true,
                            children: [
                              ListTile(
                                dense: true,
                                selected: _group == '全部',
                                title: Text('全部 ${_data?.count ?? 0}'),
                                onTap: () => setState(() => _group = '全部'),
                              ),
                              for (final g in _data?.groups ?? const [])
                                ListTile(
                                  dense: true,
                                  selected: _group == g.name,
                                  title: Text('${g.name} ${g.count}'),
                                  onTap: () => setState(() => _group = g.name),
                                ),
                            ],
                          ),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(child: table),
                      const SizedBox(width: 12),
                      SizedBox(
                        width: 280,
                        child: ElCard(
                          expand: true,
                          header: const Text('联动看板'),
                          child: _picked == null
                              ? const EmptyHint('选中一行查看')
                              : Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(
                                      '${_picked!.symbol}  ${_picked!.name}',
                                      style: const TextStyle(fontWeight: FontWeight.w700),
                                    ),
                                    const SizedBox(height: 8),
                                    Text(
                                      '${_picked!.last ?? '--'}  ${_picked!.changeRate ?? ''}',
                                      style: AppNum.style(const TextStyle(fontSize: 22, fontWeight: FontWeight.w700)),
                                    ),
                                    const SizedBox(height: 12),
                                    Text(_picked!.summary.isEmpty ? '暂无小时级研判' : _picked!.summary),
                                    const Spacer(),
                                    FilledButton(
                                      onPressed: () => widget.open?.call(
                                        '/trade/desk?symbol=${_picked!.symbol}&market=${_picked!.market}',
                                        title: '交易工作台',
                                      ),
                                      child: const Text('去交易台'),
                                    ),
                                  ],
                                ),
                        ),
                      ),
                    ],
                  )
                : table,
          ),
        ],
      ),
    );
  }
}

class MarketStocksPage extends StatelessWidget {
  const MarketStocksPage({super.key, this.open});
  final OpenRoute? open;

  @override
  Widget build(BuildContext context) {
    return JsonListPage(
      title: '全部股票',
      path: '/market/instrument/universe',
      extraQuery: const {'enabled': '1'},
      filters: const [
        QueryField('keyword', '代码/名称'),
        QueryField('market', '市场', options: [('美股', 'US'), ('港股', 'HK'), ('A股', 'CN')]),
      ],
      columns: const [
        TableCol('代码', 'symbol'),
        TableCol('名称', 'name'),
        TableCol('市场', 'market'),
        TableCol('类型', 'securityType'),
        TableCol('状态', 'status'),
      ],
      onRowTap: (row) => open?.call(
        '/market/symbol?symbol=${row['symbol']}&market=${row['market']}',
        title: cellText(row['symbol']),
      ),
    );
  }
}

class MarketNewsPage extends StatelessWidget {
  const MarketNewsPage({super.key});

  @override
  Widget build(BuildContext context) {
    return const JsonListPage(
      title: '财经资讯',
      path: '/market/finance/briefings',
      filters: [
        QueryField('market', '市场', options: [('美股', 'US'), ('港股', 'HK'), ('A股', 'CN')]),
      ],
      columns: [
        TableCol('时间', 'generatedAt'),
        TableCol('市场', 'market'),
        TableCol('标题', 'headline'),
        TableCol('来源', 'sourceName'),
      ],
    );
  }
}

class MarketAiWorkbenchPage extends ConsumerStatefulWidget {
  const MarketAiWorkbenchPage({super.key});

  @override
  ConsumerState<MarketAiWorkbenchPage> createState() => _MarketAiWorkbenchPageState();
}

class _MarketAiWorkbenchPageState extends ConsumerState<MarketAiWorkbenchPage> {
  final _symbol = TextEditingController(text: 'AAPL');
  String _market = 'US';
  bool _busy = false;
  String _result = '';

  @override
  void dispose() {
    _symbol.dispose();
    super.dispose();
  }

  Future<void> _run() async {
    setState(() => _busy = true);
    try {
      final r = await ref.read(ruoyiClientProvider).post(
            '/market/ai/analyze',
            data: {'symbol': _symbol.text.trim(), 'market': _market, 'days': 90},
            timeout: const Duration(seconds: 120),
          );
      setState(() => _result = r.data?.toString() ?? r.msg);
    } catch (e) {
      setState(() => _result = describeApiError(e));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return AppPage(
      child: ListView(
        children: [
          const PageHero(title: 'AI 研判工作台', subtitle: '单标的研判'),
          ElCard(
            child: Wrap(
              spacing: 12,
              runSpacing: 12,
              crossAxisAlignment: WrapCrossAlignment.center,
              children: [
                SizedBox(
                  width: 160,
                  child: TextField(
                    controller: _symbol,
                    decoration: const InputDecoration(labelText: '代码'),
                  ),
                ),
                DropdownButton<String>(
                  value: _market,
                  items: const [
                    DropdownMenuItem(value: 'US', child: Text('US')),
                    DropdownMenuItem(value: 'HK', child: Text('HK')),
                    DropdownMenuItem(value: 'CN', child: Text('CN')),
                  ],
                  onChanged: (v) => setState(() => _market = v ?? 'US'),
                ),
                FilledButton(
                  onPressed: _busy ? null : _run,
                  child: Text(_busy ? '研判中…' : '开始研判'),
                ),
              ],
            ),
          ),
          const SizedBox(height: 12),
          ElCard(child: SelectableText(_result.isEmpty ? '结果将显示在这里' : _result)),
        ],
      ),
    );
  }
}

class MarketRecommendationsPage extends StatelessWidget {
  const MarketRecommendationsPage({super.key});

  @override
  Widget build(BuildContext context) {
    return const JsonListPage(
      title: '智能选股',
      path: '/market/picks/latest',
      paged: false,
      columns: [
        TableCol('代码', 'symbol'),
        TableCol('名称', 'name'),
        TableCol('市场', 'market'),
        TableCol('评分', 'score'),
        TableCol('理由', 'reason'),
      ],
    );
  }
}

class MarketReviewPage extends StatelessWidget {
  const MarketReviewPage({super.key});

  @override
  Widget build(BuildContext context) {
    return const JsonListPage(
      title: '市场分析',
      path: '/market/review/history',
      paged: false,
      columns: [
        TableCol('日期', 'tradeDate'),
        TableCol('市场', 'market'),
        TableCol('立场', 'stance'),
        TableCol('分数', 'score'),
        TableCol('摘要', 'summary'),
      ],
    );
  }
}

class MarketCoveragePage extends StatelessWidget {
  const MarketCoveragePage({super.key});

  @override
  Widget build(BuildContext context) {
    return const JsonDetailPage(title: '行情覆盖', path: '/trade/coverage');
  }
}

class MarketStockPoolPage extends StatelessWidget {
  const MarketStockPoolPage({super.key, this.open});
  final OpenRoute? open;

  @override
  Widget build(BuildContext context) {
    return JsonListPage(
      title: '标的股票池',
      path: '/market/instrument/list',
      paged: true,
      columns: const [
        TableCol('代码', 'symbol'),
        TableCol('名称', 'name'),
        TableCol('市场', 'market'),
        TableCol('分类', 'category'),
      ],
      onRowTap: (row) => open?.call(
        '/market/symbol?symbol=${row['symbol']}&market=${row['market']}',
        title: cellText(row['symbol']),
      ),
    );
  }
}
