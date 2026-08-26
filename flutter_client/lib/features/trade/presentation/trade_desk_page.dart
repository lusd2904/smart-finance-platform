import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_client.dart';
import '../../../core/theme/app_theme.dart';
import '../../../shared/widgets/page_header.dart';
import '../../../shared/widgets/quote_text.dart';
import '../../ai/data/ai_api.dart';
import '../../kline/logic/kline_painter.dart';
import '../../market/data/market_api.dart';
import '../../market/data/market_models.dart';
import '../../quant/data/quant_api.dart';
import '../data/trade_api.dart';
import '../data/trade_models.dart';

/// 交易工作台：自选 + K线 + 盘口 + 快捷下单 + 量化 + AI。
/// 对齐 Web `/trade/desk`，原生 Flutter 绘制，不嵌网页。
class TradeDeskPage extends ConsumerStatefulWidget {
  const TradeDeskPage({super.key});

  @override
  ConsumerState<TradeDeskPage> createState() => _TradeDeskPageState();
}

class _TradeDeskPageState extends ConsumerState<TradeDeskPage> {
  String _symbol = 'AAPL';
  String _market = 'US';
  String _period = 'daily';
  String _side = 'buy';
  String _orderType = 'LO';
  int _qty = 1;
  double _price = 0;
  String _status = '';
  bool _busy = false;
  List<KlineBar> _bars = const [];
  DepthData? _depth;
  List<TradeTick> _ticks = const [];
  List<OrderItem> _orders = const [];
  List<PositionItem> _positions = const [];
  AccountInfo? _account;
  Map<String, dynamic> _overview = const {};
  String _factor = '';
  String _ai = '';
  WatchlistOverview? _watch;

  static const _periods = {
    'intraday': '分时',
    'daily': '日K',
    'weekly': '周K',
    'monthly': '月K',
  };

  @override
  void initState() {
    super.initState();
    Future<void>.microtask(_reloadAll);
  }

  Future<void> _reloadAll() async {
    setState(() => _busy = true);
    try {
      await Future.wait([
        _loadWatch(),
        _loadAccount(),
        _loadSymbol(),
        _loadOrders(),
      ]);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _loadWatch() async {
    try {
      final w = await ref.read(marketApiProvider).watchlistOverview();
      if (mounted) setState(() => _watch = w);
    } catch (_) {}
  }

  Future<void> _loadAccount() async {
    try {
      final api = ref.read(tradeApiProvider);
      final a = await api.account();
      final p = await api.positions();
      if (mounted) {
        setState(() {
          _account = a;
          _positions = p;
        });
      }
    } catch (e) {
      if (mounted) setState(() => _status = describeApiError(e));
    }
  }

  Future<void> _loadOrders() async {
    try {
      final o = await ref.read(tradeApiProvider).orders(scope: 'today');
      if (mounted) setState(() => _orders = o);
    } catch (_) {}
  }

  Future<void> _loadSymbol() async {
    _factor = '';
    _ai = '';
    await Future.wait([_loadKline(), _loadDepth(), _loadOverview()]);
  }

  Future<void> _loadKline() async {
    try {
      final bars = await ref.read(marketApiProvider).kline(
            symbol: _symbol,
            market: _market,
            period: _period,
          );
      if (mounted) {
        setState(() {
          _bars = bars;
          if (_price == 0 && bars.isNotEmpty) _price = bars.last.close;
        });
      }
    } catch (e) {
      if (mounted) setState(() => _status = describeApiError(e));
    }
  }

  Future<void> _loadDepth() async {
    try {
      final api = ref.read(tradeApiProvider);
      final d = await api.depth(symbol: _symbol, market: _market);
      final t = await api.trades(symbol: _symbol, market: _market);
      if (mounted) {
        setState(() {
          _depth = d;
          _ticks = t;
        });
      }
    } catch (_) {}
  }

  Future<void> _loadOverview() async {
    try {
      final o = await ref.read(marketApiProvider).symbolOverview(
            symbol: _symbol,
            market: _market,
          );
      if (mounted) setState(() => _overview = o);
    } catch (_) {}
  }

  Future<void> _computeFactor() async {
    setState(() => _busy = true);
    try {
      final r = await ref.read(quantApiProvider).computeFactor(
            symbol: _symbol,
            market: _market,
          );
      final score = r['score'];
      if (score is Map) {
        _factor = score.entries.map((e) => '${e.key}: ${e.value}').join('\n');
      } else {
        _factor = r.toString();
      }
    } catch (e) {
      _factor = describeApiError(e);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _runAi() async {
    setState(() => _busy = true);
    try {
      final latest = await ref.read(aiApiProvider).latest(
            symbol: _symbol,
            market: _market,
          );
      if (latest != null && latest.summaryText.isNotEmpty) {
        _ai = '${latest.recommendation} ${latest.summaryText}\n${latest.operationAdvice}';
      } else {
        final r = await ref.read(aiApiProvider).analyze(
              symbol: _symbol,
              market: _market,
            );
        _ai = (r['content'] ?? r['analysis'] ?? r['summary'] ?? r['message'] ?? r)
            .toString();
      }
    } catch (e) {
      _ai = describeApiError(e);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _submit() async {
    setState(() => _busy = true);
    try {
      final r = await ref.read(tradeApiProvider).submitOrder(
            symbol: _symbol,
            market: _market,
            side: _side,
            orderType: _orderType,
            quantity: _qty,
            price: _orderType == 'LO' ? _price : null,
          );
      _status = (r['message'] ?? r['ok'] ?? r).toString();
      await _loadOrders();
    } catch (e) {
      _status = describeApiError(e);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _cancel(String id) async {
    try {
      final r = await ref.read(tradeApiProvider).cancelOrder(id);
      if (mounted) {
        setState(() => _status = (r['message'] ?? '已提交撤单').toString());
        await _loadOrders();
      }
    } catch (e) {
      if (mounted) setState(() => _status = describeApiError(e));
    }
  }

  void _select(WatchlistItem item) {
    setState(() {
      _symbol = item.symbol;
      _market = item.market.isEmpty ? 'US' : item.market;
    });
    _loadSymbol();
  }

  @override
  Widget build(BuildContext context) {
    final wide = MediaQuery.sizeOf(context).width >= 1100;
    final last = _bars.isEmpty ? null : _bars.last.close;
    return Column(
      children: [
        PageHeader(
          title: '交易工作台',
          subtitle: '自选 · K线 · 盘口 · 快捷交易 · 量化 · AI',
          actions: [
            TextButton.icon(
              onPressed: _busy ? null : _reloadAll,
              icon: const Icon(Icons.refresh, size: 18),
              label: const Text('刷新'),
            ),
          ],
        ),
        if (_status.isNotEmpty)
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: Align(
              alignment: Alignment.centerLeft,
              child: Text(_status, style: TextStyle(color: AppColors.warn)),
            ),
          ),
        Expanded(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
            child: wide ? _desktop(last) : _mobile(last),
          ),
        ),
      ],
    );
  }

  Widget _desktop(double? last) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        SizedBox(width: 220, child: _watchPane(height: null)),
        const SizedBox(width: 8),
        Expanded(
          child: Column(
            children: [
              Expanded(flex: 3, child: _chartPane(last)),
              const SizedBox(height: 8),
              SizedBox(
                height: 220,
                child: Row(
                  children: [
                    Expanded(child: _bookPane()),
                    const SizedBox(width: 8),
                    SizedBox(width: 220, child: _ticket(last)),
                  ],
                ),
              ),
              const SizedBox(height: 8),
              SizedBox(height: 150, child: _ordersPane()),
            ],
          ),
        ),
        const SizedBox(width: 8),
        SizedBox(width: 280, child: _sidePane(last)),
      ],
    );
  }

  Widget _mobile(double? last) {
    return ListView(
      children: [
        SizedBox(height: 220, child: _watchPane(height: 220)),
        const SizedBox(height: 8),
        SizedBox(height: 280, child: _chartPane(last)),
        const SizedBox(height: 8),
        _ticket(last),
        const SizedBox(height: 8),
        SizedBox(height: 200, child: _bookPane()),
        const SizedBox(height: 8),
        SizedBox(height: 180, child: _ordersPane()),
        const SizedBox(height: 8),
        SizedBox(height: 280, child: _sidePane(last)),
      ],
    );
  }

  Widget _watchPane({double? height}) {
    final items = _watch?.items ?? const <WatchlistItem>[];
    final body = Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const ListTile(dense: true, title: Text('自选清单')),
        Expanded(
          child: ListView.builder(
            itemCount: items.length,
            itemBuilder: (_, i) {
              final it = items[i];
              final on = it.symbol == _symbol;
              return ListTile(
                dense: true,
                selected: on,
                title: Text(it.symbol),
                subtitle: Text(it.name.isEmpty ? it.market : it.name),
                trailing: PctText(it.changeRate),
                onTap: () => _select(it),
              );
            },
          ),
        ),
      ],
    );
    return Card(
      child: height == null ? body : SizedBox(height: height, child: body),
    );
  }

  Widget _chartPane(double? last) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(8),
        child: Column(
          children: [
            Wrap(
              spacing: 8,
              crossAxisAlignment: WrapCrossAlignment.center,
              children: [
                SizedBox(
                  width: 88,
                  child: TextField(
                    controller: TextEditingController(text: _symbol)
                      ..selection = TextSelection.collapsed(offset: _symbol.length),
                    decoration: const InputDecoration(isDense: true, labelText: '代码'),
                    onSubmitted: (v) {
                      setState(() => _symbol = v.trim().toUpperCase());
                      _loadSymbol();
                    },
                  ),
                ),
                SegmentedButton<String>(
                  segments: const [
                    ButtonSegment(value: 'US', label: Text('US')),
                    ButtonSegment(value: 'HK', label: Text('HK')),
                    ButtonSegment(value: 'CN', label: Text('CN')),
                  ],
                  selected: {_market},
                  onSelectionChanged: (s) {
                    setState(() => _market = s.first);
                    _loadSymbol();
                  },
                ),
                Text(
                  last == null ? '--' : last.toStringAsFixed(2),
                  style: AppNum.style(Theme.of(context).textTheme.headlineSmall!),
                ),
                SegmentedButton<String>(
                  segments: [
                    for (final e in _periods.entries)
                      ButtonSegment(value: e.key, label: Text(e.value)),
                  ],
                  selected: {_period},
                  onSelectionChanged: (s) {
                    setState(() => _period = s.first);
                    _loadKline();
                  },
                ),
              ],
            ),
            const SizedBox(height: 8),
            Expanded(
              child: _bars.isEmpty
                  ? const Center(child: Text('暂无K线'))
                  : InteractiveKlineChart(bars: _bars),
            ),
          ],
        ),
      ),
    );
  }

  Widget _bookPane() {
    final asks = (_depth?.asks ?? const <DepthLevel>[]).take(8).toList().reversed;
    final bids = (_depth?.bids ?? const <DepthLevel>[]).take(8);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(8),
        child: Row(
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  const Text('买卖盘', style: TextStyle(fontWeight: FontWeight.w700)),
                  for (final a in asks)
                    _lvl(a, AppColors.down),
                  for (final b in bids)
                    _lvl(b, AppColors.up),
                ],
              ),
            ),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  const Text('成交', style: TextStyle(fontWeight: FontWeight.w700)),
                  for (final t in _ticks.take(10))
                    Text(
                      '${t.price?.toStringAsFixed(2) ?? '--'}  ${t.volume ?? ''}',
                      style: AppNum.style(Theme.of(context).textTheme.bodySmall!),
                    ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _lvl(DepthLevel a, Color c) {
    return InkWell(
      onTap: a.price == null
          ? null
          : () => setState(() => _price = a.price!),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 1),
        child: Text(
          '${a.price?.toStringAsFixed(2) ?? '--'}   ${a.volume ?? a.size ?? ''}',
          style: TextStyle(color: c, fontSize: 12, fontFeatures: AppNum.fontFeatures),
        ),
      ),
    );
  }

  Widget _ticket(double? last) {
    final cash = _account?.availableCash;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(10),
        child: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Text('快捷交易', style: TextStyle(fontWeight: FontWeight.w700)),
            const SizedBox(height: 6),
            SegmentedButton<String>(
              segments: const [
                ButtonSegment(value: 'buy', label: Text('买')),
                ButtonSegment(value: 'sell', label: Text('卖')),
              ],
              selected: {_side},
              onSelectionChanged: (s) => setState(() => _side = s.first),
            ),
            const SizedBox(height: 6),
            SegmentedButton<String>(
              segments: const [
                ButtonSegment(value: 'LO', label: Text('限价')),
                ButtonSegment(value: 'MO', label: Text('市价')),
              ],
              selected: {_orderType},
              onSelectionChanged: (s) => setState(() => _orderType = s.first),
            ),
            TextField(
              decoration: const InputDecoration(labelText: '数量', isDense: true),
              keyboardType: TextInputType.number,
              onChanged: (v) => _qty = int.tryParse(v) ?? 1,
            ),
            if (_orderType == 'LO')
              TextField(
                decoration: InputDecoration(
                  labelText: '价格',
                  isDense: true,
                  hintText: last?.toStringAsFixed(2),
                ),
                keyboardType: const TextInputType.numberWithOptions(decimal: true),
                onChanged: (v) => _price = double.tryParse(v) ?? _price,
              ),
            Text(
              '可用 ${cash?.toStringAsFixed(2) ?? '--'} ${_account?.currency ?? ''}',
              style: Theme.of(context).textTheme.bodySmall,
            ),
            const SizedBox(height: 8),
            FilledButton(
              onPressed: _busy ? null : _submit,
              style: FilledButton.styleFrom(
                backgroundColor: _side == 'buy' ? AppColors.up : AppColors.down,
              ),
              child: Text('${_side == 'buy' ? '买入' : '卖出'} $_symbol'),
            ),
          ],
        ),
        ),
      ),
    );
  }

  Widget _ordersPane() {
    return Card(
      child: Row(
        children: [
          Expanded(
            child: ListView(
              children: [
                const ListTile(dense: true, title: Text('今日委托')),
                for (final o in _orders)
                  ListTile(
                    dense: true,
                    title: Text('${o.symbol} ${o.side} ${o.statusLabel.isEmpty ? o.status : o.statusLabel}'),
                    trailing: o.orderId == null
                        ? null
                        : TextButton(
                            onPressed: () => _cancel(o.orderId!),
                            child: const Text('撤'),
                          ),
                  ),
              ],
            ),
          ),
          const VerticalDivider(width: 1),
          Expanded(
            child: ListView(
              children: [
                const ListTile(dense: true, title: Text('持仓')),
                for (final p in _positions)
                  ListTile(
                    dense: true,
                    title: Text(p.symbol),
                    subtitle: Text('量 ${p.quantity ?? '--'}  成本 ${p.costPrice ?? '--'}'),
                    onTap: () {
                      final raw = p.symbol.split('.').first;
                      setState(() {
                        _symbol = raw;
                        _side = 'sell';
                      });
                      _loadSymbol();
                    },
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _sidePane(double? last) {
    return Card(
      child: ListView(
        padding: const EdgeInsets.all(10),
        children: [
          Text('$_symbol.$_market', style: Theme.of(context).textTheme.titleMedium),
          Text('现价 ${last?.toStringAsFixed(2) ?? '--'}'),
          const SizedBox(height: 8),
          Text(
            _overview['summary']?.toString() ??
                _overview['message']?.toString() ??
                '',
            style: Theme.of(context).textTheme.bodySmall,
          ),
          const Divider(),
          FilledButton.tonal(
            onPressed: _busy ? null : _computeFactor,
            child: const Text('计算量化因子'),
          ),
          Text(_factor.isEmpty ? '尚未计算' : _factor, style: Theme.of(context).textTheme.bodySmall),
          const SizedBox(height: 8),
          FilledButton.tonal(
            onPressed: _busy ? null : _runAi,
            child: const Text('AI 研判'),
          ),
          Text(_ai.isEmpty ? '尚未研判' : _ai, style: Theme.of(context).textTheme.bodySmall),
        ],
      ),
    );
  }
}
