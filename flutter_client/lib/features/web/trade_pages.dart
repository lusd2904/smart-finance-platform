import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api/api_client.dart';
import '../../core/api/ruoyi_client.dart';
import '../../features/trade/presentation/trade_desk_page.dart';
import '../../shared/widgets/ruoyi_ui.dart';
import 'json_list_page.dart';

class TradeDeskHost extends StatelessWidget {
  const TradeDeskHost({super.key});

  @override
  Widget build(BuildContext context) {
    return const TradeDeskPage();
  }
}

class TradeTradingPage extends ConsumerStatefulWidget {
  const TradeTradingPage({super.key, this.symbol = 'AAPL', this.market = 'US'});
  final String symbol;
  final String market;

  @override
  ConsumerState<TradeTradingPage> createState() => _TradeTradingPageState();
}

class _TradeTradingPageState extends ConsumerState<TradeTradingPage> {
  late final TextEditingController _symbol;
  late String _market;
  final _qty = TextEditingController(text: '1');
  final _price = TextEditingController();
  String _side = 'buy';
  String _type = 'LO';
  bool _busy = false;
  String? _error;
  Map<String, dynamic> _account = const {};
  List<Map<String, dynamic>> _positions = const [];
  List<Map<String, dynamic>> _orders = const [];
  Map<String, dynamic> _depth = const {};
  Map<String, dynamic> _kline = const {};

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
    _qty.dispose();
    _price.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final client = ref.read(ruoyiClientProvider);
      final acc = await client.get('/trade/account');
      final pos = await client.get('/trade/positions');
      final ord = await client.get('/trade/orders', query: {'scope': 'today'});
      Map<String, dynamic> depth = const {};
      Map<String, dynamic> kline = const {};
      try {
        depth = asMap(
          (await client.get(
            '/trade/quote/depth',
            query: {'symbol': _symbol.text.trim(), 'market': _market},
          )).data,
        );
      } catch (_) {}
      try {
        kline = asMap(
          (await client.get(
            '/trade/quote/kline',
            query: {
              'symbol': _symbol.text.trim(),
              'market': _market,
              'period': 'daily',
              'limit': 80,
            },
          )).data,
        );
      } catch (_) {}
      if (!mounted) return;
      setState(() {
        _account = asMap(acc.data);
        _positions = extractRows(pos, preferKeys: const ['positions']);
        _orders = extractRows(ord, preferKeys: const ['orders']);
        _depth = depth;
        _kline = kline;
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

  Future<void> _submit() async {
    final ok = await confirm(
      context,
      '确认${_side == 'buy' ? '买入' : '卖出'} ${_symbol.text} ${_qty.text} 股？',
    );
    if (!ok) return;
    setState(() => _busy = true);
    try {
      await ref
          .read(ruoyiClientProvider)
          .post(
            '/trade/order',
            data: {
              'symbol': _symbol.text.trim(),
              'market': _market,
              'side': _side,
              'orderType': _type,
              'quantity': int.tryParse(_qty.text) ?? 1,
              if (_type == 'LO') 'price': num.tryParse(_price.text),
            },
            timeout: const Duration(seconds: 60),
          );
      if (mounted) toast(context, '已提交委托');
      await _load();
    } catch (e) {
      if (mounted) toast(context, describeApiError(e), error: true);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _cancel(String id) async {
    try {
      await ref
          .read(ruoyiClientProvider)
          .post('/trade/order/${Uri.encodeComponent(id)}/cancel');
      await _load();
    } catch (e) {
      if (mounted) toast(context, describeApiError(e), error: true);
    }
  }

  @override
  Widget build(BuildContext context) {
    final quote = asMap(_kline['quote']);
    final last = cellText(quote['last'] ?? quote['price'] ?? _kline['last']);
    return AppPage(
      child: ListView(
        children: [
          PageHero(
            title: '交易台',
            subtitle: '报价 · K线 · 买卖盘 · 下单 · 委托（长桥）',
            actions: [
              OutlinedButton(onPressed: _load, child: const Text('刷新全部')),
            ],
          ),
          if (_error != null) ErrorBanner(_error!, onRetry: _load),
          if (_busy) const LinearProgressIndicator(minHeight: 2),
          ElCard(
            child: Wrap(
              spacing: 16,
              runSpacing: 8,
              crossAxisAlignment: WrapCrossAlignment.center,
              children: [
                SizedBox(
                  width: 140,
                  child: TextField(
                    controller: _symbol,
                    decoration: const InputDecoration(labelText: '代码'),
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
                Text(
                  last.isEmpty ? '--' : last,
                  style: const TextStyle(
                    fontSize: 28,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                Text(cellText(quote['changeRate'] ?? quote['changePct'])),
              ],
            ),
          ),
          const SizedBox(height: 12),
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: ElCard(
                  header: const Text('买卖盘'),
                  padding: EdgeInsets.zero,
                  child: SimpleTable(
                    columns: const [
                      TableCol('方向', 'side'),
                      TableCol('价格', 'price'),
                      TableCol('数量', 'volume'),
                    ],
                    rows: [
                      for (final r in _book('asks')) {...r, 'side': '卖'},
                      for (final r in _book('bids')) {...r, 'side': '买'},
                    ],
                  ),
                ),
              ),
              const SizedBox(width: 12),
              SizedBox(
                width: 280,
                child: ElCard(
                  header: const Text('快捷下单'),
                  child: Column(
                    children: [
                      SegmentedButton<String>(
                        segments: const [
                          ButtonSegment(value: 'buy', label: Text('买入')),
                          ButtonSegment(value: 'sell', label: Text('卖出')),
                        ],
                        selected: {_side},
                        onSelectionChanged: (s) =>
                            setState(() => _side = s.first),
                      ),
                      const SizedBox(height: 8),
                      DropdownButtonFormField<String>(
                        initialValue: _type,
                        decoration: const InputDecoration(labelText: '类型'),
                        items: const [
                          DropdownMenuItem(value: 'LO', child: Text('限价 LO')),
                          DropdownMenuItem(value: 'MO', child: Text('市价 MO')),
                        ],
                        onChanged: (v) => setState(() => _type = v ?? 'LO'),
                      ),
                      const SizedBox(height: 8),
                      TextField(
                        controller: _qty,
                        decoration: const InputDecoration(labelText: '数量'),
                      ),
                      if (_type == 'LO') ...[
                        const SizedBox(height: 8),
                        TextField(
                          controller: _price,
                          decoration: const InputDecoration(labelText: '价格'),
                        ),
                      ],
                      const SizedBox(height: 12),
                      SizedBox(
                        width: double.infinity,
                        child: FilledButton(
                          onPressed: _busy ? null : _submit,
                          child: const Text('提交委托'),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          ElCard(
            header: const Text('账户'),
            child: KvGrid({
              '净资产': cellText(
                _account['netAsset'] ?? _account['equity'] ?? _account['total'],
              ),
              '现金': cellText(_account['cash'] ?? _account['available']),
              '币种': cellText(_account['currency']),
            }),
          ),
          const SizedBox(height: 12),
          ElCard(
            header: const Text('持仓'),
            padding: EdgeInsets.zero,
            child: SimpleTable(
              columns: const [
                TableCol('代码', 'symbol'),
                TableCol('数量', 'quantity'),
                TableCol('市值', 'marketValue'),
                TableCol('盈亏', 'unrealizedPnl'),
              ],
              rows: _positions,
            ),
          ),
          const SizedBox(height: 12),
          ElCard(
            header: const Text('今日委托'),
            padding: EdgeInsets.zero,
            child: SimpleTable(
              columns: const [
                TableCol('订单', 'orderId'),
                TableCol('代码', 'symbol'),
                TableCol('方向', 'side'),
                TableCol('数量', 'quantity'),
                TableCol('状态', 'status'),
              ],
              rows: _orders,
              rowActions: (row) => [
                TextButton(
                  onPressed: () =>
                      _cancel(cellText(row['orderId'] ?? row['id'])),
                  child: const Text('撤单'),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  List<Map<String, dynamic>> _book(String key) {
    final raw = _depth[key];
    if (raw is List) return raw.whereType<Map<String, dynamic>>().toList();
    return const [];
  }
}

class TradePositionsPage extends StatelessWidget {
  const TradePositionsPage({super.key, this.open});
  final OpenRoute? open;

  @override
  Widget build(BuildContext context) {
    return JsonListPage(
      title: '持仓',
      path: '/trade/positions',
      paged: false,
      preferKeys: const ['positions'],
      columns: const [
        TableCol('代码', 'symbol'),
        TableCol('名称', 'name'),
        TableCol('数量', 'quantity'),
        TableCol('成本', 'costPrice'),
        TableCol('现价', 'last'),
        TableCol('市值', 'marketValue'),
        TableCol('盈亏', 'unrealizedPnl'),
      ],
      onRowTap: (row) => open?.call(
        '/trade/terminal?symbol=${row['symbol']}&market=${row['market']}',
        title: '交易台',
      ),
    );
  }
}

class TradeOrdersPage extends StatelessWidget {
  const TradeOrdersPage({super.key});

  @override
  Widget build(BuildContext context) {
    return const JsonListPage(
      title: '订单',
      path: '/trade/orders',
      extraQuery: {'scope': 'today'},
      paged: false,
      preferKeys: ['orders'],
      columns: [
        TableCol('订单号', 'orderId'),
        TableCol('代码', 'symbol'),
        TableCol('方向', 'side'),
        TableCol('类型', 'orderType'),
        TableCol('数量', 'quantity'),
        TableCol('价格', 'price'),
        TableCol('状态', 'status'),
        TableCol('时间', 'submittedAt'),
      ],
    );
  }
}

class TradeBrokerPage extends StatelessWidget {
  const TradeBrokerPage({super.key, this.open});
  final OpenRoute? open;

  @override
  Widget build(BuildContext context) {
    return JsonDetailPage(
      title: '券商账户',
      subtitle: '长桥账户资产',
      path: '/trade/account',
    );
  }
}

class TradeRiskPage extends StatelessWidget {
  const TradeRiskPage({super.key});

  @override
  Widget build(BuildContext context) {
    return const JsonListPage(
      title: '风控管理',
      path: '/trade/risk/rules',
      paged: false,
      columns: [
        TableCol('名称', 'name'),
        TableCol('类型', 'ruleType'),
        TableCol('状态', 'status'),
        TableCol('阈值', 'threshold'),
        TableCol('更新', 'updateTime'),
      ],
    );
  }
}

class TradeRiskReviewPage extends StatelessWidget {
  const TradeRiskReviewPage({super.key});

  @override
  Widget build(BuildContext context) {
    return const JsonListPage(
      title: '风险复核',
      path: '/trade/risk/events',
      extraQuery: {'limit': 80},
      paged: false,
    );
  }
}

class TradeBacktestPage extends ConsumerStatefulWidget {
  const TradeBacktestPage({super.key});

  @override
  ConsumerState<TradeBacktestPage> createState() => _TradeBacktestPageState();
}

class _TradeBacktestPageState extends ConsumerState<TradeBacktestPage> {
  final _symbol = TextEditingController(text: 'AAPL');
  bool _busy = false;
  List<Map<String, dynamic>> _rows = const [];
  String? _error;

  @override
  void initState() {
    super.initState();
    Future<void>.microtask(_list);
  }

  @override
  void dispose() {
    _symbol.dispose();
    super.dispose();
  }

  Future<void> _list() async {
    try {
      final r = await ref.read(ruoyiClientProvider).get('/trade/backtest/list');
      if (mounted) setState(() => _rows = extractRows(r));
    } catch (e) {
      if (mounted) setState(() => _error = describeApiError(e));
    }
  }

  Future<void> _run() async {
    setState(() => _busy = true);
    try {
      await ref
          .read(ruoyiClientProvider)
          .post(
            '/trade/backtest/run',
            data: {'symbol': _symbol.text.trim(), 'market': 'US'},
            timeout: const Duration(seconds: 120),
          );
      await _list();
    } catch (e) {
      if (mounted) setState(() => _error = describeApiError(e));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return AppPage(
      child: Column(
        children: [
          PageHero(
            title: '策略回测',
            subtitle: '8 族因子信号，只看当前登录账户',
            actions: [
              SizedBox(
                width: 140,
                child: TextField(
                  controller: _symbol,
                  decoration: const InputDecoration(labelText: '代码'),
                ),
              ),
              FilledButton(
                onPressed: _busy ? null : _run,
                child: Text(_busy ? '回测中…' : '运行回测'),
              ),
            ],
          ),
          if (_error != null) ErrorBanner(_error!, onRetry: _list),
          Expanded(
            child: ElCard(
              padding: EdgeInsets.zero,
              child: SimpleTable(
                columns: const [
                  TableCol('编号', 'id'),
                  TableCol('代码', 'symbol'),
                  TableCol('策略', 'strategy'),
                  TableCol('收益', 'returnPct'),
                  TableCol('回撤', 'maxDrawdown'),
                  TableCol('时间', 'createTime'),
                ],
                rows: _rows,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class TradeNotificationsPage extends StatelessWidget {
  const TradeNotificationsPage({super.key});

  @override
  Widget build(BuildContext context) {
    return const JsonListPage(
      title: '通知中心',
      path: '/trade/notifications',
      extraQuery: {'limit': 50},
      paged: false,
      columns: [
        TableCol('时间', 'createTime'),
        TableCol('标题', 'title'),
        TableCol('内容', 'content'),
        TableCol('已读', 'read'),
      ],
    );
  }
}

class TradeAiRunsPage extends StatelessWidget {
  const TradeAiRunsPage({super.key});

  @override
  Widget build(BuildContext context) {
    return const JsonListPage(
      title: 'AI 交易台账',
      path: '/trade/ai-trade-runs',
      extraQuery: {'limit': 30},
      paged: false,
    );
  }
}

class TradeFeishuPage extends ConsumerStatefulWidget {
  const TradeFeishuPage({super.key});

  @override
  ConsumerState<TradeFeishuPage> createState() => _TradeFeishuPageState();
}

class _TradeFeishuPageState extends ConsumerState<TradeFeishuPage> {
  final _webhook = TextEditingController();
  final _secret = TextEditingController();
  bool _busy = false;
  String? _msg;

  @override
  void initState() {
    super.initState();
    Future<void>.microtask(_load);
  }

  @override
  void dispose() {
    _webhook.dispose();
    _secret.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    try {
      final r = await ref.read(ruoyiClientProvider).get('/trade/feishu/config');
      final d = asMap(r.data);
      _webhook.text = cellText(d['webhook']);
      _secret.text = cellText(d['secret']);
      if (mounted) setState(() {});
    } catch (e) {
      if (mounted) setState(() => _msg = describeApiError(e));
    }
  }

  Future<void> _save() async {
    setState(() => _busy = true);
    try {
      await ref
          .read(ruoyiClientProvider)
          .put(
            '/trade/feishu/config',
            data: {
              'webhook': _webhook.text.trim(),
              'secret': _secret.text.trim(),
            },
          );
      setState(() => _msg = '已保存');
    } catch (e) {
      setState(() => _msg = describeApiError(e));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return AppPage(
      child: ListView(
        children: [
          const PageHero(title: '飞书推送', subtitle: 'Webhook 机器人'),
          ElCard(
            child: Column(
              children: [
                TextField(
                  controller: _webhook,
                  decoration: const InputDecoration(labelText: 'Webhook'),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: _secret,
                  decoration: const InputDecoration(labelText: 'Secret'),
                ),
                const SizedBox(height: 16),
                FilledButton(
                  onPressed: _busy ? null : _save,
                  child: const Text('保存'),
                ),
                if (_msg != null)
                  Padding(
                    padding: const EdgeInsets.only(top: 8),
                    child: Text(_msg!),
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
