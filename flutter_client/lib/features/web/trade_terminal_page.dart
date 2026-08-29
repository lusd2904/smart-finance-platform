import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api/api_client.dart';
import '../../core/market/market_session.dart';
import '../../core/theme/app_theme.dart';
import '../../core/theme/ruoyi_tokens.dart';
import '../../features/kline/logic/kline_painter.dart';
import '../../features/market/data/market_api.dart';
import '../../features/market/data/market_models.dart';
import '../../features/market/data/market_quotes_ws.dart';
import '../../features/trade/data/trade_api.dart';
import '../../features/trade/data/trade_models.dart';
import '../../shared/utils/format.dart';
import '../../shared/widgets/ruoyi_ui.dart';

const kTerminalAllGroup = '全部';

List<String> terminalWatchGroups(WatchlistOverview? watch) {
  final names = <String>[kTerminalAllGroup];
  final seen = <String>{kTerminalAllGroup};
  for (final g in watch?.groups ?? const []) {
    if (g.name.isNotEmpty && seen.add(g.name)) names.add(g.name);
  }
  for (final item in watch?.items ?? const []) {
    for (final g in item.groups) {
      if (g.isNotEmpty && seen.add(g)) names.add(g);
    }
    if (item.groups.isEmpty && item.note.isNotEmpty && seen.add(item.note)) {
      names.add(item.note);
    }
  }
  return names;
}

List<WatchlistItem> filterWatchlistByGroup(
  List<WatchlistItem> items,
  String group,
) {
  if (group.isEmpty || group == kTerminalAllGroup) return items;
  return items
      .where((i) => i.groups.contains(group) || i.note.contains(group))
      .toList();
}

bool watchlistContainsSymbol(
  List<WatchlistItem> items,
  String symbol,
  String market,
) {
  final m = market.isEmpty ? 'US' : market.toUpperCase();
  final s = symbol.toUpperCase();
  return items.any((i) {
    final im = i.market.isEmpty ? 'US' : i.market.toUpperCase();
    return i.symbol.toUpperCase() == s && im == m;
  });
}

/// API 时间转为北京墙上时钟再交给图轴；禁止 `toIso8601String()`（会带 Z）。
KlineBar klineBarForDisplay(KlineBar bar) {
  final date = formatBeijingTime(bar.date, withSeconds: false);
  if (date.isEmpty) return bar;
  return KlineBar(
    date: date,
    open: bar.open,
    high: bar.high,
    low: bar.low,
    close: bar.close,
    volume: bar.volume,
  );
}

List<KlineBar> klineBarsForDisplay(List<KlineBar> bars) =>
    [for (final b in bars) klineBarForDisplay(b)];

/// 分时且带时分的分钟线用收盘价折线；收盘回落日 K（无时分）仍画蜡烛。
bool terminalDrawsCloseLine(String period, List<KlineBar> bars) {
  if (period.toLowerCase() != 'intraday') return false;
  return bars.any((b) => b.date.contains(':'));
}

/// 行情交易终端：真实接口 + 顶栏美股常驻、港股/A 股按开盘显示。
class TradeTerminalPage extends ConsumerStatefulWidget {
  const TradeTerminalPage({super.key, this.sessionClock});

  final MarketSessionClock? sessionClock;

  @override
  ConsumerState<TradeTerminalPage> createState() => _TradeTerminalPageState();
}

class _TradeTerminalPageState extends ConsumerState<TradeTerminalPage> {
  String _symbol = 'AAPL';
  String _market = 'US';
  String _period = 'daily';
  String _side = 'buy';
  String _orderType = 'LO';
  String _group = kTerminalAllGroup;
  int _mobilePane = 1;
  final _qty = TextEditingController(text: '1');
  final _price = TextEditingController();
  bool _busy = false;
  bool _quantBusy = false;
  String? _error;
  String _status = '';
  List<IndexQuote> _indices = const [];
  WatchlistOverview? _watch;
  List<KlineBar> _bars = const [];
  List<PositionItem> _positions = const [];
  List<OrderItem> _orders = const [];
  AccountInfo? _account;
  AutoTradeStatus? _auto;
  DepthData? _depth;
  List<TradeTick> _ticks = const [];
  Timer? _sessionTick;
  Timer? _bookTick;
  Timer? _snapshotTick;
  Timer? _tapeDelay;
  bool _timersOn = false;
  Map<String, dynamic> _snapshot = const {};
  VoidCallback? _unsubQuotes;

  MarketSessionClock get _clock => widget.sessionClock ?? MarketSessionClock();

  @override
  void initState() {
    super.initState();
    Future<void>.microtask(_bootstrap);
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _syncTimers(TickerMode.valuesOf(context).enabled);
  }

  void _syncTimers(bool on) {
    if (on == _timersOn) return;
    _timersOn = on;
    if (!on) {
      _sessionTick?.cancel();
      _bookTick?.cancel();
      _snapshotTick?.cancel();
      _sessionTick = null;
      _bookTick = null;
      _snapshotTick = null;
      return;
    }
    _sessionTick ??= Timer.periodic(const Duration(seconds: 30), (_) {
      if (mounted) {
        setState(() {});
        unawaited(_loadKline(deferExtras: true));
      }
    });
    _bookTick ??= Timer.periodic(const Duration(seconds: 60), (_) {
      if (mounted) unawaited(_loadAccount());
    });
    _snapshotTick ??= Timer.periodic(const Duration(seconds: 90), (_) {
      if (mounted) unawaited(_loadSnapshot());
    });
  }

  @override
  void dispose() {
    _timersOn = false;
    _sessionTick?.cancel();
    _bookTick?.cancel();
    _snapshotTick?.cancel();
    _tapeDelay?.cancel();
    _unsubQuotes?.call();
    _qty.dispose();
    _price.dispose();
    super.dispose();
  }

  Future<void> _bootstrap() async {
    unawaited(_loadIndices());
    unawaited(_loadWatch());
    unawaited(_loadAuto());
    await _loadKline(deferExtras: true);
    if (!mounted) return;
    unawaited(_loadAccount());
    unawaited(_loadSnapshot());
    _tapeDelay?.cancel();
    _tapeDelay = Timer(const Duration(milliseconds: 400), () {
      if (mounted) unawaited(_loadTape());
    });
  }

  Future<void> _reload() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await _loadKline();
      unawaited(_loadIndices());
      unawaited(_loadAccount());
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _loadIndices() async {
    try {
      final items = await ref.read(marketApiProvider).indexQuotes();
      if (mounted) setState(() => _indices = items);
    } catch (_) {}
  }

  void _applyWatch(WatchlistOverview watch) {
    final prevSymbol = _symbol;
    final prevMarket = _market;
    final filtered = filterWatchlistByGroup(watch.items, _group);
    final pool = filtered.isNotEmpty ? filtered : watch.items;
    var symbol = _symbol;
    var market = _market;
    if (pool.isNotEmpty && !watchlistContainsSymbol(pool, symbol, market)) {
      symbol = pool.first.symbol;
      market = pool.first.market.isEmpty ? 'US' : pool.first.market;
    }
    setState(() {
      _watch = watch;
      _symbol = symbol;
      _market = market;
    });
    if (symbol != prevSymbol || market != prevMarket) {
      unawaited(_loadKline(deferExtras: true));
    }
    _syncQuoteSub();
  }

  void _syncQuoteSub() {
    _unsubQuotes?.call();
    _unsubQuotes = null;
    final items = _watch?.items ?? const <WatchlistItem>[];
    if (items.isEmpty) return;
    final hub = ref.read(stockQuotesHubProvider);
    _unsubQuotes = hub.subscribe(
      [
        for (final it in items)
          (symbol: it.symbol, market: it.market.isEmpty ? 'US' : it.market),
      ],
      (quotes) {
        if (!mounted || _watch == null || quotes.isEmpty) return;
        var next = _watch!.items;
        for (final q in quotes) {
          next = [
            for (final it in next)
              if (it.symbol.toUpperCase() == q.symbol &&
                  (it.market.isEmpty ? 'US' : it.market.toUpperCase()) == q.market)
                applyLiveQuote(it, q)
              else
                it,
          ];
        }
        setState(() => _watch = _watch!.copyWithItems(next));
      },
    );
  }

  Future<void> _loadWatch() async {
    try {
      final rows = await ref.read(marketApiProvider).watchlistRows();
      if (mounted && rows.isNotEmpty) {
        _applyWatch(WatchlistOverview(items: rows, count: rows.length));
      }
    } catch (_) {}
    try {
      final w = await ref.read(marketApiProvider).watchlistOverview();
      if (!mounted || w.items.isEmpty) return;
      _applyWatch(w);
    } catch (_) {}
  }

  Future<void> _loadAuto() async {
    try {
      final s = await ref.read(tradeApiProvider).getAutoTradeStatus();
      if (mounted) setState(() => _auto = s);
    } catch (_) {}
  }

  Future<void> _toggleQuant(bool on) async {
    if (_auto?.configured != true || _quantBusy) return;
    setState(() => _quantBusy = true);
    try {
      final s = await ref.read(tradeApiProvider).saveAutoTradeSettings(
            autoTradeEnabled: on,
          );
      if (mounted) setState(() => _auto = s);
    } catch (e) {
      if (mounted) setState(() => _status = describeApiError(e));
    } finally {
      if (mounted) setState(() => _quantBusy = false);
    }
  }

  void _setGroup(String group) {
    if (group == _group) return;
    final items = filterWatchlistByGroup(_watch?.items ?? const [], group);
    final pick = items.isNotEmpty ? items.first : null;
    setState(() {
      _group = group;
      if (pick != null) {
        _symbol = pick.symbol;
        _market = pick.market.isEmpty ? 'US' : pick.market;
      }
    });
    if (pick != null) unawaited(_loadSymbol());
  }

  void _openSymbol(String symbol, String market) {
    setState(() {
      _symbol = symbol;
      _market = market.isEmpty ? 'US' : market;
    });
    unawaited(_loadSymbol());
  }

  Future<void> _loadAccount() async {
    try {
      final api = ref.read(tradeApiProvider);
      final a = await api.account();
      final p = await api.positions();
      final o = await api.orders(scope: 'today');
      if (mounted) {
        setState(() {
          _account = a;
          _positions = p;
          _orders = o;
        });
      }
    } catch (_) {}
  }

  Future<void> _loadKline({bool deferExtras = false}) async {
    try {
      final route = resolveTerminalKline(
        market: _market,
        period: _period,
        clock: _clock,
      );
      final List<KlineBar> bars;
      if (route.useQuote) {
        final data = await ref.read(tradeApiProvider).quoteKline(
              symbol: _symbol,
              market: _market,
              period: route.period,
              limit: route.limit,
            );
        bars = klineBarsForDisplay(KlineBar.listFrom(data));
      } else {
        bars = klineBarsForDisplay(
          await ref.read(marketApiProvider).kline(
                symbol: _symbol,
                market: _market,
                period: route.period,
                limit: route.limit,
              ),
        );
      }
      if (mounted) {
        setState(() {
          _bars = bars;
          if (_price.text.isEmpty && bars.isNotEmpty) {
            _price.text = bars.last.close.toStringAsFixed(2);
          }
        });
      }
      if (!deferExtras) {
        unawaited(_loadTape());
        unawaited(_loadSnapshot());
      }
    } catch (e) {
      if (mounted) setState(() => _status = describeApiError(e));
    }
  }

  Future<void> _loadSnapshot() async {
    try {
      final snap = await ref.read(tradeApiProvider).quoteSnapshot(
            symbol: _symbol,
            market: _market,
          );
      if (mounted && snap.isNotEmpty) setState(() => _snapshot = snap);
    } catch (_) {}
  }

  Future<void> _loadTape() async {
    try {
      final trade = ref.read(tradeApiProvider);
      final depth = await trade.depth(symbol: _symbol, market: _market);
      final ticks = await trade.trades(symbol: _symbol, market: _market, count: 20);
      if (mounted) {
        setState(() {
          _depth = depth;
          _ticks = ticks;
        });
      }
    } catch (_) {}
  }

  Future<void> _loadSymbol() async {
    await _loadKline();
  }

  List<IndexQuote> get _visibleIndices {
    final clock = _clock;
    final live = _indices.where((q) {
      final m = q.market.isEmpty ? 'US' : q.market.toUpperCase();
      return clock.of(m).showChip;
    }).toList();
    final hasUs = live.any(
      (q) => (q.market.isEmpty ? 'US' : q.market.toUpperCase()) == 'US',
    );
    if (hasUs) return live;
    return [
      const IndexQuote(symbol: 'usIXIC', name: '纳斯达克', market: 'US'),
      const IndexQuote(symbol: 'usINX', name: '标普500', market: 'US'),
      ...live,
    ];
  }

  Future<void> _submit() async {
    final qty = int.tryParse(_qty.text.trim()) ?? 0;
    if (qty <= 0) {
      setState(() => _status = '请输入数量');
      return;
    }
    final ok = await confirm(
      context,
      '确认${_side == 'buy' ? '买入' : '卖出'} $_symbol $qty 股？',
    );
    if (!ok) return;
    setState(() => _busy = true);
    try {
      final r = await ref.read(tradeApiProvider).submitOrder(
            symbol: _symbol,
            market: _market,
            side: _side,
            orderType: _orderType,
            quantity: qty,
            price: _orderType == 'LO' ? double.tryParse(_price.text) : null,
          );
      setState(() => _status = (r['message'] ?? r['ok'] ?? r).toString());
      await _loadAccount();
    } catch (e) {
      setState(() => _status = describeApiError(e));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _cancel(String id) async {
    if (id.isEmpty) return;
    try {
      final r = await ref.read(tradeApiProvider).cancelOrder(id);
      if (mounted) {
        setState(() => _status = (r['message'] ?? '已提交撤单').toString());
        await _loadAccount();
      }
    } catch (e) {
      if (mounted) setState(() => _status = describeApiError(e));
    }
  }

  void _pick(WatchlistItem item) {
    _openSymbol(item.symbol, item.market.isEmpty ? 'US' : item.market);
  }

  @override
  Widget build(BuildContext context) {
    ref.listen(marketQuotesStreamProvider, (prev, next) {
      final items = next.asData?.value.items;
      if (items == null || !mounted) return;
      setState(() => _indices = items);
    });
    final scheme = Theme.of(context).colorScheme;
    return ColoredBox(
      color: Theme.of(context).brightness == Brightness.dark
          ? WebTokens.contentBg
          : WebTokens.contentBgLight,
      child: Column(
        children: [
          _IndexStrip(
            indices: _visibleIndices,
            clock: _clock,
            trailing: _topTrailing(),
          ),
          if (_status.isNotEmpty)
            Padding(
              padding: const EdgeInsets.fromLTRB(12, 6, 12, 0),
              child: Align(
                alignment: Alignment.centerLeft,
                child: Text(_status, style: TextStyle(color: AppColors.warn, fontSize: 12)),
              ),
            ),
          if (_error != null) Padding(padding: const EdgeInsets.all(8), child: ErrorBanner(_error!)),
          Expanded(
            child: Padding(
              padding: const EdgeInsets.all(8),
              child: AppDimens.isWide(context)
                  ? Row(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        SizedBox(width: 240, child: _watchPane()),
                        const SizedBox(width: 8),
                        Expanded(child: _chartPane()),
                        const SizedBox(width: 8),
                        SizedBox(width: 300, child: _orderPane(scheme)),
                      ],
                    )
                  : Column(
                      children: [
                        SegmentedButton<int>(
                          segments: const [
                            ButtonSegment(value: 0, label: Text('自选')),
                            ButtonSegment(value: 1, label: Text('K线')),
                            ButtonSegment(value: 2, label: Text('交易')),
                          ],
                          selected: {_mobilePane},
                          onSelectionChanged: (s) => setState(() => _mobilePane = s.first),
                        ),
                        const SizedBox(height: 8),
                        Expanded(
                          child: switch (_mobilePane) {
                            0 => _watchPane(),
                            2 => _orderPane(scheme),
                            _ => _chartPane(),
                          },
                        ),
                      ],
                    ),
            ),
          ),
          SizedBox(height: AppDimens.isWide(context) ? 150 : 120, child: _bottomPane()),
        ],
      ),
    );
  }

  Widget _topTrailing() {
    final scheme = Theme.of(context).colorScheme;
    final live = _account?.configured == true;
    final quantConfigured = _auto?.configured == true;
    final quantOn = _auto?.autoTradeEnabled == true;
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        _InstrumentSearch(
          onSearch: (kw) async {
            if (kw.trim().isEmpty) return const <UniverseRow>[];
            try {
              final page = await ref.read(marketApiProvider).universe(
                    keyword: kw.trim(),
                    pageSize: 20,
                  );
              return page.rows;
            } catch (_) {
              return const <UniverseRow>[];
            }
          },
          onSelect: (row) => _openSymbol(row.symbol, row.market),
        ),
        const SizedBox(width: 8),
        Text(
          '可用 ${_account?.availableCash?.toStringAsFixed(2) ?? '--'} ${_account?.currency ?? ''}',
          style: TextStyle(color: scheme.onSurfaceVariant, fontSize: 11),
        ),
        const SizedBox(width: 8),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
          decoration: BoxDecoration(
            color: live ? const Color(0x1A16A34A) : scheme.surfaceContainerHighest,
            borderRadius: BorderRadius.circular(4),
          ),
          child: Text(
            live ? 'LIVE' : 'SIM',
            style: TextStyle(
              fontSize: 11,
              fontWeight: FontWeight.w700,
              color: live ? const Color(0xFF16A34A) : scheme.outline,
            ),
          ),
        ),
        const SizedBox(width: 6),
        Tooltip(
          message: quantConfigured ? '本账户自动交易' : '未配置长桥 Key，无法打开量化',
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                '量化',
                style: TextStyle(
                  fontSize: 12,
                  color: quantConfigured ? scheme.onSurface : scheme.outline,
                ),
              ),
              Switch.adaptive(
                key: const Key('terminal-quant-switch'),
                value: quantOn,
                onChanged: (quantConfigured && !_quantBusy) ? _toggleQuant : null,
                materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
              ),
            ],
          ),
        ),
        IconButton(
          tooltip: '刷新',
          onPressed: _busy ? null : _reload,
          icon: const Icon(Icons.refresh, size: 18),
        ),
      ],
    );
  }

  Widget _watchPane() {
    final items = filterWatchlistByGroup(
      _watch?.items ?? const <WatchlistItem>[],
      _group,
    );
    return ElCard(
      expand: true,
      header: Row(
        children: [
          Expanded(child: Text('自选 ${items.length}')),
          DropdownButtonHideUnderline(
            child: DropdownButton<String>(
              key: const Key('terminal-group'),
              value: terminalWatchGroups(_watch).contains(_group)
                  ? _group
                  : kTerminalAllGroup,
              isDense: true,
              items: [
                for (final g in terminalWatchGroups(_watch))
                  DropdownMenuItem(
                    value: g,
                    child: Text(g == kTerminalAllGroup ? '全部自选' : g),
                  ),
              ],
              onChanged: (v) {
                if (v != null) _setGroup(v);
              },
            ),
          ),
        ],
      ),
      padding: EdgeInsets.zero,
      child: ListView.builder(
        itemCount: items.length,
        itemBuilder: (_, i) {
          final it = items[i];
          final on = it.symbol == _symbol;
          final chg = it.changeRate ?? 0;
          return ListTile(
            dense: true,
            selected: on,
            title: Text(it.symbol),
            subtitle: Text(it.name.isEmpty ? it.market : it.name),
            trailing: Text(
              '${chg >= 0 ? '+' : ''}${chg.toStringAsFixed(2)}%',
              style: TextStyle(color: chg >= 0 ? AppColors.up : AppColors.down, fontSize: 12),
            ),
            onTap: () => _pick(it),
          );
        },
      ),
    );
  }

  Widget _chartPane() {
    return ElCard(
      expand: true,
      padding: const EdgeInsets.all(8),
      child: Column(
        children: [
          Row(
            children: [
              Text('$_symbol.$_market', style: const TextStyle(fontWeight: FontWeight.w700)),
              const SizedBox(width: 8),
              Expanded(
                child: SingleChildScrollView(
                  scrollDirection: Axis.horizontal,
                  child: Row(
                    children: [
                      for (final p in const [
                        ('intraday', '分时'),
                        ('m5', '5分'),
                        ('daily', '日K'),
                        ('weekly', '周K'),
                        ('monthly', '月K'),
                      ])
                        Padding(
                          padding: const EdgeInsets.only(left: 4),
                          child: ChoiceChip(
                            label: Text(p.$2, style: const TextStyle(fontSize: 12)),
                            selected: _period == p.$1,
                            visualDensity: VisualDensity.compact,
                            onSelected: (_) {
                              setState(() => _period = p.$1);
                              _loadSymbol();
                            },
                          ),
                        ),
                    ],
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 6),
          _quoteMetrics(),
          const SizedBox(height: 8),
          Expanded(
            child: _bars.isEmpty
                ? const EmptyHint('暂无K线')
                : terminalDrawsCloseLine(_period, _bars)
                    ? _CloseLineChart(
                        key: const Key('terminal-intraday-line'),
                        bars: _bars,
                      )
                    : InteractiveKlineChart(bars: _bars),
          ),
        ],
      ),
    );
  }

  Widget _orderPane(ColorScheme scheme) {
    final bids = _depth?.bids.take(5).toList() ?? const <DepthLevel>[];
    final asks = _depth?.asks.take(5).toList() ?? const <DepthLevel>[];
    return ElCard(
      expand: true,
      header: const Text('快捷下单'),
      child: ListView(
        children: [
          if (_account?.configured != true)
            const Padding(
              padding: EdgeInsets.only(bottom: 8),
              child: Text('长桥未配置时下单会被服务端拒绝', style: TextStyle(fontSize: 12)),
            ),
          if (asks.isNotEmpty || bids.isNotEmpty) ...[
            Text('盘口', style: TextStyle(color: scheme.onSurfaceVariant, fontSize: 12)),
            for (final a in asks.reversed)
              _bookRow(false, a),
            for (final b in bids)
              _bookRow(true, b),
            const SizedBox(height: 8),
          ],
          SegmentedButton<String>(
            segments: const [
              ButtonSegment(value: 'buy', label: Text('买入')),
              ButtonSegment(value: 'sell', label: Text('卖出')),
            ],
            selected: {_side},
            onSelectionChanged: (s) => setState(() => _side = s.first),
          ),
          const SizedBox(height: 8),
          SegmentedButton<String>(
            segments: const [
              ButtonSegment(value: 'LO', label: Text('限价')),
              ButtonSegment(value: 'MO', label: Text('市价')),
            ],
            selected: {_orderType},
            onSelectionChanged: (s) => setState(() => _orderType = s.first),
          ),
          const SizedBox(height: 8),
          TextField(
            controller: _qty,
            decoration: const InputDecoration(labelText: '数量'),
            keyboardType: TextInputType.number,
          ),
          if (_orderType == 'LO') ...[
            const SizedBox(height: 8),
            TextField(
              controller: _price,
              decoration: const InputDecoration(labelText: '价格'),
            ),
          ],
          const SizedBox(height: 8),
          Text(
            '可用 ${_account?.availableCash?.toStringAsFixed(2) ?? '--'} ${_account?.currency ?? ''}',
            style: TextStyle(color: scheme.onSurfaceVariant, fontSize: 12),
          ),
          if (_snapshot['available'] == true)
            Padding(
              padding: const EdgeInsets.only(top: 6),
              child: Text(
                [
                  if (_snapshot['peTtm'] != null) 'PE(TTM) ${_fmtSnap(_snapshot['peTtm'])}',
                  if (_snapshot['peStatic'] != null) 'PE(静) ${_fmtSnap(_snapshot['peStatic'])}',
                  if (_snapshot['peDynamic'] != null) 'PE(动) ${_fmtSnap(_snapshot['peDynamic'])}',
                  if (_snapshot['pb'] != null) 'PB ${_fmtSnap(_snapshot['pb'], digits: 3)}',
                  if (_snapshot['marketCap'] != null) '市值 ${_fmtCap(_snapshot['marketCap'])}',
                  if (_snapshot['turnoverRate'] != null) '换手 ${_fmtPct(_snapshot['turnoverRate'])}',
                  if (_snapshot['volumeRatio'] != null) '量比 ${_fmtSnap(_snapshot['volumeRatio'])}',
                  if (_snapshot['amplitude'] != null) '振幅 ${_fmtPct(_snapshot['amplitude'])}',
                  if (_snapshot['high52'] != null) '52w ${_fmtSnap(_snapshot['low52'])}-${_fmtSnap(_snapshot['high52'])}',
                  if (_snapshot['historyHigh'] != null) '史高 ${_fmtSnap(_snapshot['historyHigh'])}',
                  if (_snapshot['historyLow'] != null) '史低 ${_fmtSnap(_snapshot['historyLow'])}',
                  if (_snapshot['dividendYield'] != null) '股息率 ${_fmtPct(_snapshot['dividendYield'])}',
                  if (_snapshot['lotSize'] != null) '每手 ${_snapshot['lotSize']}',
                  if (_snapshot['beta'] != null) 'Beta ${_fmtSnap(_snapshot['beta'], digits: 3)}',
                ].join('  '),
                style: TextStyle(color: scheme.onSurfaceVariant, fontSize: 11),
              ),
            ),
          const SizedBox(height: 12),
          FilledButton(
            onPressed: _busy ? null : _submit,
            style: FilledButton.styleFrom(
              backgroundColor: _side == 'buy' ? AppColors.up : AppColors.down,
            ),
            child: Text('${_side == 'buy' ? '买入' : '卖出'} $_symbol'),
          ),
          if (_ticks.isNotEmpty) ...[
            const SizedBox(height: 12),
            Text('逐笔', style: TextStyle(color: scheme.onSurfaceVariant, fontSize: 12)),
            for (final t in _ticks.take(6))
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 2),
                child: Text(
                  '${formatBeijingTime(t.time, withSeconds: false)}  ${t.price?.toStringAsFixed(2) ?? '--'}  ${t.volume ?? 0}',
                  style: TextStyle(
                    fontSize: 11,
                    color: t.side.toLowerCase().contains('sell') ? AppColors.down : AppColors.up,
                  ),
                ),
              ),
          ],
        ],
      ),
    );
  }

  (String, String) _splitBrokerSymbol(String raw) {
    final text = raw.trim();
    final m = RegExp(r'^(.*)\.(US|HK|SH|SZ|CN)$', caseSensitive: false).firstMatch(text);
    if (m == null) return (text, _market.isEmpty ? 'US' : _market);
    final suffix = m.group(2)!.toUpperCase();
    final market = (suffix == 'SH' || suffix == 'SZ') ? 'CN' : suffix;
    return (m.group(1)!, market);
  }

  Widget _quoteMetrics() {
    final lastBar = _bars.isNotEmpty ? _bars.last : null;
    final prevBar = _bars.length > 1 ? _bars[_bars.length - 2] : null;
    String cell(String label, String value) => '$label $value';
    final open = _snapshot['open'] ?? lastBar?.open;
    final high = _snapshot['high'] ?? lastBar?.high;
    final low = _snapshot['low'] ?? lastBar?.low;
    final prev = _snapshot['prevClose'] ?? prevBar?.close;
    final vol = _snapshot['volume'] ?? lastBar?.volume;
    final items = [
      cell('今开', _fmtSnap(open, digits: 3)),
      cell('最高', _fmtSnap(high, digits: 3)),
      cell('最低', _fmtSnap(low, digits: 3)),
      cell('昨收', _fmtSnap(prev, digits: 3)),
      cell('成交量', _fmtCap(vol)),
      cell('成交额', _fmtCap(_snapshot['turnover'])),
      cell('换手率', _fmtPct(_snapshot['turnoverRate'])),
      cell('振幅', _fmtPct(_snapshot['amplitude'])),
      cell('量比', _fmtSnap(_snapshot['volumeRatio'])),
      cell('市盈率(TTM)', _fmtSnap(_snapshot['peTtm'])),
      cell('市净率 PB', _fmtSnap(_snapshot['pb'], digits: 3)),
      cell('总市值', _fmtCap(_snapshot['marketCap'])),
    ];
    return Wrap(
      spacing: 12,
      runSpacing: 4,
      children: [
        for (final t in items)
          Text(t, style: const TextStyle(fontSize: 11)),
      ],
    );
  }

  String _fmtSnap(dynamic v, {int digits = 2}) {
    if (v == null) return '--';
    final n = v is num ? v.toDouble() : double.tryParse('$v');
    if (n == null) return '$v';
    return n.toStringAsFixed(digits);
  }

  String _fmtPct(dynamic v) {
    if (v == null) return '--';
    final n = v is num ? v.toDouble() : double.tryParse('$v');
    if (n == null) return '$v';
    final p = n.abs() < 0.05 ? n * 100 : n;
    return '${p.toStringAsFixed(2)}%';
  }

  String _fmtCap(dynamic v) {
    if (v == null) return '--';
    final n = v is num ? v.toDouble() : double.tryParse('$v');
    if (n == null || n <= 0) return '--';
    if (n >= 1e12) return '${(n / 1e12).toStringAsFixed(2)}万亿';
    if (n >= 1e8) return '${(n / 1e8).toStringAsFixed(2)}亿';
    if (n >= 1e4) return '${(n / 1e4).toStringAsFixed(2)}万';
    return n.toStringAsFixed(0);
  }

  Widget _bookRow(bool bid, DepthLevel lv) {
    final color = bid ? AppColors.up : AppColors.down;
    return InkWell(
      onTap: lv.price == null
          ? null
          : () => setState(() => _price.text = lv.price!.toStringAsFixed(2)),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 2),
        child: Row(
          children: [
            SizedBox(
              width: 28,
              child: Text(bid ? '买' : '卖', style: TextStyle(color: color, fontSize: 11)),
            ),
            Expanded(
              child: Text(
                lv.price?.toStringAsFixed(2) ?? '--',
                style: TextStyle(color: color, fontSize: 12, fontWeight: FontWeight.w600),
              ),
            ),
            Text('${lv.volume ?? lv.size ?? 0}', style: const TextStyle(fontSize: 11)),
          ],
        ),
      ),
    );
  }

  Widget _bottomPane() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(8, 0, 8, 8),
      child: Row(
        children: [
          Expanded(
            child: ElCard(
              expand: true,
              header: const Text('当日委托'),
              padding: EdgeInsets.zero,
              child: ListView(
                children: [
                  for (final o in _orders)
                    ListTile(
                      dense: true,
                      title: Text('${o.symbol} ${o.side} ${o.quantity ?? 0}'),
                      subtitle: Text('${o.status}  ${o.orderId ?? ''}'),
                      trailing: TextButton(
                        onPressed: (o.orderId == null || o.orderId!.isEmpty)
                            ? null
                            : () => _cancel(o.orderId!),
                        child: const Text('撤'),
                      ),
                    ),
                  if (_orders.isEmpty) const EmptyHint('暂无委托'),
                ],
              ),
            ),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: ElCard(
              expand: true,
              header: const Text('持仓'),
              padding: EdgeInsets.zero,
              child: ListView(
                children: [
                  for (final p in _positions)
                    ListTile(
                      dense: true,
                      title: Text(p.symbol),
                      subtitle: Text('${p.quantity ?? 0} 股 · 成本 ${p.costPrice ?? '--'}'),
                      onTap: () {
                        final parsed = _splitBrokerSymbol(p.symbol);
                        _openSymbol(parsed.$1, parsed.$2);
                      },
                    ),
                  if (_positions.isEmpty) const EmptyHint('暂无持仓'),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _IndexStrip extends StatelessWidget {
  const _IndexStrip({
    required this.indices,
    required this.clock,
    this.trailing,
  });

  final List<IndexQuote> indices;
  final MarketSessionClock clock;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    final chips = indices.isEmpty
        ? ['US', 'HK', 'CN']
            .map(clock.of)
            .where((s) => s.showChip)
            .map(
              (s) => _chip(
                context,
                title: s.label,
                price: '--',
                chg: null,
              ),
            )
        : indices.where((q) {
            final m = q.market.isEmpty ? 'US' : q.market;
            return clock.of(m).showChip;
          }).map((q) {
            final session = clock.of(q.market.isEmpty ? 'US' : q.market);
            final chg = q.changePct;
            return _chip(
              context,
              title: '${q.name.isEmpty ? q.symbol : q.name} ${session.sessionName}',
              price: q.last?.toStringAsFixed(2) ?? '--',
              chg: chg,
            );
          });
    return Material(
      color: Theme.of(context).colorScheme.surfaceContainerLow,
      child: SizedBox(
        height: 52,
        child: Row(
          children: [
            const SizedBox(width: 10),
            Expanded(
              child: ListView(
                scrollDirection: Axis.horizontal,
                children: [
                  for (final c in chips) ...[c, const SizedBox(width: 8)],
                ],
              ),
            ),
            if (trailing != null)
              Flexible(
                child: SingleChildScrollView(
                  scrollDirection: Axis.horizontal,
                  child: trailing!,
                ),
              ),
          ],
        ),
      ),
    );
  }

  Widget _chip(BuildContext context, {required String title, required String price, double? chg}) {
    final color = chg == null
        ? Theme.of(context).colorScheme.onSurface
        : (chg >= 0 ? AppColors.up : AppColors.down);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: Theme.of(context).colorScheme.outlineVariant),
      ),
      child: Row(
        children: [
          Text(title, style: const TextStyle(fontSize: 12)),
          const SizedBox(width: 8),
          Text(price, style: TextStyle(color: color, fontWeight: FontWeight.w700, fontSize: 13)),
          if (chg != null) ...[
            const SizedBox(width: 4),
            Text(
              '${chg >= 0 ? '+' : ''}${chg.toStringAsFixed(2)}%',
              style: TextStyle(color: color, fontSize: 12),
            ),
          ],
        ],
      ),
    );
  }
}

class _InstrumentSearch extends StatefulWidget {
  const _InstrumentSearch({required this.onSearch, required this.onSelect});

  final Future<List<UniverseRow>> Function(String keyword) onSearch;
  final ValueChanged<UniverseRow> onSelect;

  @override
  State<_InstrumentSearch> createState() => _InstrumentSearchState();
}

class _InstrumentSearchState extends State<_InstrumentSearch> {
  final _controller = TextEditingController();
  final _link = LayerLink();
  final _portal = OverlayPortalController();
  Timer? _debounce;
  String _query = '';
  List<UniverseRow> _opts = const [];

  @override
  void dispose() {
    _debounce?.cancel();
    _controller.dispose();
    super.dispose();
  }

  void _schedule(String raw) {
    final q = raw.trim();
    _query = q;
    _debounce?.cancel();
    if (q.isEmpty) {
      setState(() => _opts = const []);
      _portal.hide();
      return;
    }
    _debounce = Timer(const Duration(milliseconds: 280), () async {
      final rows = await widget.onSearch(q);
      if (!mounted || _query != q) return;
      setState(() => _opts = rows);
      if (rows.isEmpty) {
        _portal.hide();
      } else {
        _portal.show();
      }
    });
  }

  void _pick(UniverseRow row) {
    widget.onSelect(row);
    _controller.clear();
    _query = '';
    setState(() => _opts = const []);
    _portal.hide();
  }

  @override
  Widget build(BuildContext context) {
    return OverlayPortal(
      controller: _portal,
      overlayChildBuilder: (context) {
        return Positioned.fill(
          child: Stack(
            children: [
              Positioned.fill(
                child: GestureDetector(
                  behavior: HitTestBehavior.translucent,
                  onTap: _portal.hide,
                ),
              ),
              CompositedTransformFollower(
                link: _link,
                showWhenUnlinked: false,
                targetAnchor: Alignment.bottomLeft,
                followerAnchor: Alignment.topLeft,
                child: Material(
                  elevation: 6,
                  borderRadius: BorderRadius.circular(8),
                  child: ConstrainedBox(
                    constraints: const BoxConstraints(maxHeight: 260, maxWidth: 280),
                    child: ListView(
                      padding: EdgeInsets.zero,
                      shrinkWrap: true,
                      children: [
                        for (final o in _opts)
                          ListTile(
                            dense: true,
                            title: Text(o.symbol),
                            subtitle: Text(o.name.isEmpty ? o.market : o.name),
                            trailing: Text(o.market, style: const TextStyle(fontSize: 11)),
                            onTap: () => _pick(o),
                          ),
                      ],
                    ),
                  ),
                ),
              ),
            ],
          ),
        );
      },
      child: CompositedTransformTarget(
        link: _link,
        child: SizedBox(
          width: 220,
          child: TextField(
            key: const Key('terminal-search'),
            controller: _controller,
            style: const TextStyle(fontSize: 12),
            onChanged: _schedule,
            decoration: const InputDecoration(
              hintText: '搜索代码 / 名称',
              isDense: true,
              prefixIcon: Icon(Icons.search, size: 16),
              prefixIconConstraints: BoxConstraints(minWidth: 32, minHeight: 32),
              border: OutlineInputBorder(),
              contentPadding: EdgeInsets.symmetric(horizontal: 8, vertical: 8),
            ),
          ),
        ),
      ),
    );
  }
}

/// 分时：收盘价折线（覆盖夜盘/盘前/盘后全序列），轴标签为北京时间。
class _CloseLineChart extends StatelessWidget {
  const _CloseLineChart({super.key, required this.bars});

  final List<KlineBar> bars;

  @override
  Widget build(BuildContext context) {
    return CustomPaint(
      painter: _CloseLinePainter(bars: bars),
      child: const SizedBox.expand(),
    );
  }
}

class _CloseLinePainter extends CustomPainter {
  _CloseLinePainter({required this.bars});

  final List<KlineBar> bars;

  static const _volumeRatio = 0.3;
  static const _gapRatio = 0.02;

  @override
  void paint(Canvas canvas, Size size) {
    if (bars.isEmpty || size.width <= 0 || size.height <= 0) return;

    final chartHeight = size.height * (1 - _gapRatio);
    final mainH = chartHeight * (1 - _volumeRatio);
    final volTop = chartHeight * (1 - _volumeRatio) + size.height * _gapRatio;
    final volH = size.height - volTop;

    var lo = bars.first.close;
    var hi = bars.first.close;
    var maxVol = bars.first.volume;
    for (final b in bars) {
      if (b.close < lo) lo = b.close;
      if (b.close > hi) hi = b.close;
      if (b.volume > maxVol) maxVol = b.volume;
    }
    if (hi <= lo) hi = lo + 1;
    final pad = (hi - lo) * 0.05;
    lo -= pad;
    hi += pad;
    if (maxVol <= 0) maxVol = 1;

    double priceY(double p) => mainH - (p - lo) / (hi - lo) * mainH;
    double volY(double v) => volTop + volH - v / maxVol * volH;
    double xAt(int i) {
      if (bars.length <= 1) return size.width / 2;
      return size.width * i / (bars.length - 1);
    }

    final gridPaint = Paint()
      ..color = const Color(0x22808080)
      ..strokeWidth = 0.5;
    final tp = TextPainter(textDirection: TextDirection.ltr);
    for (var g = 0; g <= 3; g++) {
      final t = g / 3;
      final y = mainH * t;
      canvas.drawLine(Offset(0, y), Offset(size.width, y), gridPaint);
      final price = hi - (hi - lo) * t;
      tp.text = TextSpan(
        text: price.toStringAsFixed(2),
        style: const TextStyle(fontSize: 9, color: Color(0xFF8D8D99)),
      );
      tp.layout();
      tp.paint(canvas, Offset(size.width - tp.width - 2, y - tp.height - 1));
    }

    final slot = bars.length <= 1 ? size.width : size.width / (bars.length - 1);
    final barW = (slot * 0.6).clamp(1.0, 6.0);
    for (var i = 0; i < bars.length; i++) {
      final b = bars[i];
      final prev = i == 0 ? b.close : bars[i - 1].close;
      final color = b.close >= prev ? AppColors.up : AppColors.down;
      final cx = xAt(i);
      canvas.drawRect(
        Rect.fromLTWH(cx - barW / 2, volY(b.volume), barW, volTop + volH - volY(b.volume)),
        Paint()..color = color.withValues(alpha: 0.6),
      );
    }

    final path = Path();
    for (var i = 0; i < bars.length; i++) {
      final p = Offset(xAt(i), priceY(bars[i].close));
      i == 0 ? path.moveTo(p.dx, p.dy) : path.lineTo(p.dx, p.dy);
    }
    if (bars.length == 1) {
      canvas.drawCircle(
        Offset(xAt(0), priceY(bars.first.close)),
        2.5,
        Paint()..color = const Color(0xFF409EFF),
      );
    } else {
      final fill = Path.from(path)
        ..lineTo(size.width, mainH)
        ..lineTo(0, mainH)
        ..close();
      canvas.drawPath(
        fill,
        Paint()
          ..shader = LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [
              const Color(0xFF409EFF).withValues(alpha: 0.22),
              const Color(0xFF409EFF).withValues(alpha: 0.01),
            ],
          ).createShader(Rect.fromLTWH(0, 0, size.width, mainH)),
      );
      canvas.drawPath(
        path,
        Paint()
          ..color = const Color(0xFF409EFF)
          ..strokeWidth = 1.6
          ..style = PaintingStyle.stroke
          ..strokeJoin = StrokeJoin.round,
      );
    }

    tp.text = TextSpan(
      text: formatBeijingChartLabel(bars.first.date),
      style: const TextStyle(fontSize: 9, color: Color(0xFF8D8D99)),
    );
    tp.layout();
    tp.paint(canvas, Offset(2, size.height - tp.height));

    tp.text = TextSpan(
      text: formatBeijingChartLabel(bars.last.date),
      style: const TextStyle(fontSize: 9, color: Color(0xFF8D8D99)),
    );
    tp.layout();
    tp.paint(canvas, Offset(size.width - tp.width - 2, size.height - tp.height));
  }

  @override
  bool shouldRepaint(_CloseLinePainter oldDelegate) =>
      identical(oldDelegate.bars, bars) == false;
}
