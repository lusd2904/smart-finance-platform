import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api/api_client.dart';
import '../../core/api/ruoyi_client.dart';
import '../../shared/widgets/ruoyi_ui.dart';
import 'json_list_page.dart';

class QuantStrategyPage extends StatelessWidget {
  const QuantStrategyPage({super.key, this.open});
  final OpenRoute? open;

  @override
  Widget build(BuildContext context) {
    return JsonListPage(
      title: '策略信号',
      subtitle: '策略运行历史',
      path: '/quant/strategy/history',
      columns: const [
        TableCol('时间', 'createTime'),
        TableCol('代码', 'symbol'),
        TableCol('市场', 'market'),
        TableCol('信号', 'signal'),
        TableCol('分数', 'score'),
        TableCol('档位', 'profile'),
      ],
      onRowTap: (row) => open?.call(
        '/market/symbol?symbol=${row['symbol']}&market=${row['market']}',
        title: cellText(row['symbol']),
      ),
    );
  }
}

class QuantFactorPage extends StatelessWidget {
  const QuantFactorPage({super.key});

  @override
  Widget build(BuildContext context) {
    return const JsonListPage(
      title: '因子分析',
      path: '/quant/factor/snapshots',
      extraQuery: {'limit': 80},
      paged: false,
      columns: [
        TableCol('代码', 'symbol'),
        TableCol('市场', 'market'),
        TableCol('分数', 'score'),
        TableCol('IC', 'ic'),
        TableCol('IR', 'ir'),
        TableCol('时间', 'asOf'),
      ],
    );
  }
}

class QuantScanRunsPage extends StatelessWidget {
  const QuantScanRunsPage({super.key, this.open});
  final OpenRoute? open;

  @override
  Widget build(BuildContext context) {
    return JsonListPage(
      title: '扫描台账',
      path: '/quant/scan-runs',
      extraQuery: const {'limit': 50},
      paged: false,
      preferKeys: const ['items'],
      columns: const [
        TableCol('周期', 'cycleId'),
        TableCol('市场', 'market'),
        TableCol('状态', 'status'),
        TableCol('数量', 'count'),
        TableCol('时间', 'createTime'),
      ],
      onRowTap: (row) => open?.call(
        '/quant/scan-result?cycleId=${row['cycleId']}',
        title: '扫描结果',
      ),
    );
  }
}

class QuantScanResultPage extends StatelessWidget {
  const QuantScanResultPage({super.key, this.cycleId});
  final String? cycleId;

  @override
  Widget build(BuildContext context) {
    if (cycleId == null || cycleId!.isEmpty) {
      return const JsonListPage(
        title: '扫描结果',
        path: '/quant/scan-runs',
        extraQuery: {'limit': 20},
        paged: false,
        preferKeys: ['items'],
      );
    }
    return JsonDetailPage(title: '扫描结果 $cycleId', path: '/quant/scan-runs/$cycleId');
  }
}

class QuantDailyListPage extends ConsumerStatefulWidget {
  const QuantDailyListPage({super.key, this.open});
  final OpenRoute? open;

  @override
  ConsumerState<QuantDailyListPage> createState() => _QuantDailyListPageState();
}

class _QuantDailyListPageState extends ConsumerState<QuantDailyListPage> {
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
      final r = await ref.read(ruoyiClientProvider).get('/quant/daily-list');
      if (!mounted) return;
      setState(() {
        _data = asMap(r.data);
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

  Future<void> _scan() async {
    setState(() => _busy = true);
    try {
      await ref.read(ruoyiClientProvider).post(
            '/quant/daily-list/scan',
            data: const {},
            timeout: const Duration(seconds: 180),
          );
      await _load();
    } catch (e) {
      if (mounted) setState(() => _error = describeApiError(e));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final items = () {
      final raw = _data['items'] ?? _data['list'] ?? _data['rows'];
      if (raw is List) return raw.whereType<Map<String, dynamic>>().toList();
      return const <Map<String, dynamic>>[];
    }();
    return AppPage(
      child: Column(
        children: [
          PageHero(
            title: '次日策略清单',
            subtitle: cellText(_data['asOf'] ?? _data['tradeDate']),
            actions: [
              OutlinedButton(onPressed: _load, child: const Text('刷新')),
              FilledButton(onPressed: _busy ? null : _scan, child: const Text('重新扫描')),
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
                  TableCol('市场', 'market'),
                  TableCol('信号', 'signal'),
                  TableCol('分数', 'score'),
                  TableCol('备注', 'reason'),
                ],
                rows: items,
                onRowTap: (row) => widget.open?.call(
                  '/trade/desk?symbol=${row['symbol']}&market=${row['market']}',
                  title: '交易工作台',
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class QuantStrategyConfigPage extends ConsumerStatefulWidget {
  const QuantStrategyConfigPage({super.key, this.open});
  final OpenRoute? open;

  @override
  ConsumerState<QuantStrategyConfigPage> createState() =>
      _QuantStrategyConfigPageState();
}

class _QuantStrategyConfigPageState extends ConsumerState<QuantStrategyConfigPage> {
  bool _busy = true;
  bool _saving = false;
  String? _error;
  Map<String, dynamic> _status = const {};
  List<Map<String, dynamic>> _profiles = const [];
  double _buyRatio = 20;

  static const _families = [
    ('trend', '趋势'),
    ('priceAction', '价型'),
    ('momentum', '动量'),
    ('breakout', '突破'),
    ('volumeFlow', '量能'),
    ('reversion', '回归'),
    ('volatility', '波动'),
    ('liquidity', '流动性'),
  ];

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
      final client = ref.read(ruoyiClientProvider);
      final st = await client.get('/trade/auto/status');
      final pf = await client.get('/trade/strategy-profiles');
      final profiles = extractRows(pf);
      if (!mounted) return;
      setState(() {
        _status = asMap(st.data);
        _profiles = profiles;
        _buyRatio = ((_status['buyRatio'] as num?)?.toDouble() ?? 0.2) * 100;
        if (_buyRatio <= 1) _buyRatio = 20;
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

  Future<void> _toggle(bool on) async {
    setState(() => _saving = true);
    try {
      await ref.read(ruoyiClientProvider).put(
            '/trade/auto/settings',
            data: {
              'autoTradeEnabled': on,
              'buyRatio': _buyRatio / 100,
            },
          );
      await _load();
    } catch (e) {
      if (mounted) {
        setState(() => _error = describeApiError(e));
        toast(context, describeApiError(e), error: true);
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Future<void> _saveProfile(Map<String, dynamic> p) async {
    final code = cellText(p['profileCode'] ?? p['code']);
    try {
      await ref.read(ruoyiClientProvider).put(
            '/trade/strategy-profiles/${Uri.encodeComponent(code)}',
            data: p['config'] ?? p,
          );
      if (mounted) toast(context, '已保存 $code');
      await _load();
    } catch (e) {
      if (mounted) toast(context, describeApiError(e), error: true);
    }
  }

  @override
  Widget build(BuildContext context) {
    final configured = _status['configured'] == true;
    final enabled = _status['autoTradeEnabled'] == true;
    return AppPage(
      child: ListView(
        children: [
          PageHero(
            title: '策略配置',
            subtitle: '本登录账户的交易开关与策略档位。开关和档位互不影响其他账号。',
            actions: [OutlinedButton(onPressed: _load, child: const Text('刷新'))],
          ),
          if (_error != null) ErrorBanner(_error!, onRetry: _load),
          if (_busy) const LinearProgressIndicator(minHeight: 2),
          ElCard(
            header: Row(
              children: [
                const Expanded(child: Text('本账户自动交易')),
                ElTag(
                  configured ? '长桥 Key 已配置' : '未配置长桥 Key',
                  tone: configured ? ElTagTone.success : ElTagTone.warning,
                ),
              ],
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  configured
                      ? '打开后，本账户的定时扫描与止损会向长桥真实下单，不会只写预警。'
                      : '未配置长桥账户 Key，无法打开自动交易。请先到「量化交易 / 长桥配置」填写凭据。',
                ),
                const SizedBox(height: 12),
                SwitchListTile(
                  contentPadding: EdgeInsets.zero,
                  title: const Text('自动交易'),
                  value: enabled,
                  onChanged: _saving ? null : _toggle,
                ),
                Text('日内买入仓位 ${_buyRatio.round()}%'),
                Slider(
                  value: _buyRatio.clamp(5, 50),
                  min: 5,
                  max: 50,
                  divisions: 9,
                  label: '${_buyRatio.round()}%',
                  onChanged: (v) => setState(() => _buyRatio = v),
                  onChangeEnd: (_) => _toggle(enabled),
                ),
                TextButton(
                  onPressed: () => widget.open?.call('/quant/longbridge', title: '长桥配置'),
                  child: const Text('去长桥配置'),
                ),
              ],
            ),
          ),
          const SizedBox(height: 12),
          Wrap(
            spacing: 12,
            runSpacing: 12,
            children: [
              for (final p in _profiles)
                SizedBox(
                  width: 360,
                  child: ElCard(
                    header: Row(
                      children: [
                        Expanded(
                          child: Text(
                            '${cellText(p['profileName'])} (${cellText(p['profileCode'])})',
                          ),
                        ),
                        FilledButton(
                          onPressed: () => _saveProfile(p),
                          child: const Text('保存档位'),
                        ),
                      ],
                    ),
                    child: Column(
                      children: [
                        for (final f in _families)
                          ListTile(
                            dense: true,
                            contentPadding: EdgeInsets.zero,
                            title: Text(f.$2),
                            trailing: SizedBox(
                              width: 140,
                              child: Slider(
                                value: _weightOf(p, f.$1),
                                onChanged: (v) => setState(() => _setWeight(p, f.$1, v)),
                              ),
                            ),
                          ),
                      ],
                    ),
                  ),
                ),
            ],
          ),
        ],
      ),
    );
  }

  double _weightOf(Map<String, dynamic> p, String key) {
    final cfg = asMap(p['config']);
    final weights = asMap(cfg['weights']);
    return (weights[key] as num?)?.toDouble() ?? 0.1;
  }

  void _setWeight(Map<String, dynamic> p, String key, double v) {
    final cfg = Map<String, dynamic>.from(asMap(p['config']));
    final weights = Map<String, dynamic>.from(asMap(cfg['weights']));
    weights[key] = v;
    cfg['weights'] = weights;
    p['config'] = cfg;
  }
}

class QuantLongbridgePage extends ConsumerStatefulWidget {
  const QuantLongbridgePage({super.key});

  @override
  ConsumerState<QuantLongbridgePage> createState() => _QuantLongbridgePageState();
}

class _QuantLongbridgePageState extends ConsumerState<QuantLongbridgePage> {
  final _appKey = TextEditingController();
  final _appSecret = TextEditingController();
  final _token = TextEditingController();
  String _region = 'hk';
  bool _busy = true;
  bool _saving = false;
  String? _error;
  String? _test;
  bool _configured = false;

  @override
  void initState() {
    super.initState();
    Future<void>.microtask(_load);
  }

  @override
  void dispose() {
    _appKey.dispose();
    _appSecret.dispose();
    _token.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final r = await ref.read(ruoyiClientProvider).get('/quant/longbridge/config');
      final data = asMap(r.data);
      if (!mounted) return;
      setState(() {
        _appKey.text = cellText(data['appKey']);
        _appSecret.text = cellText(data['appSecret']);
        _token.text = cellText(data['accessToken']);
        _region = cellText(data['region']).isEmpty ? 'hk' : cellText(data['region']);
        _configured = data['configured'] == true || cellText(data['appKey']).isNotEmpty;
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

  Future<void> _save() async {
    setState(() => _saving = true);
    try {
      await ref.read(ruoyiClientProvider).put(
            '/quant/longbridge/config',
            data: {
              'appKey': _appKey.text.trim(),
              'appSecret': _appSecret.text.trim(),
              'accessToken': _token.text.trim(),
              'region': _region,
            },
          );
      if (mounted) toast(context, '已保存');
      await _load();
    } catch (e) {
      if (mounted) toast(context, describeApiError(e), error: true);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Future<void> _testConn() async {
    setState(() => _test = '测试中…');
    try {
      final r = await ref.read(ruoyiClientProvider).get('/quant/longbridge/test');
      setState(() => _test = r.data?.toString() ?? r.msg);
    } catch (e) {
      setState(() => _test = describeApiError(e));
    }
  }

  @override
  Widget build(BuildContext context) {
    return AppPage(
      child: ListView(
        children: [
          PageHero(
            title: '长桥配置',
            subtitle: '凭据按登录账号加密保存，互不可见。',
            actions: [
              ElTag(
                _configured ? '已连接' : '未连接',
                tone: _configured ? ElTagTone.success : ElTagTone.info,
              ),
            ],
          ),
          if (_error != null) ErrorBanner(_error!, onRetry: _load),
          if (_busy) const LinearProgressIndicator(minHeight: 2),
          ElCard(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 640),
              child: Column(
                children: [
                  TextField(
                    controller: _appKey,
                    decoration: const InputDecoration(labelText: 'App Key'),
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: _appSecret,
                    obscureText: true,
                    decoration: const InputDecoration(labelText: 'App Secret'),
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: _token,
                    obscureText: true,
                    decoration: const InputDecoration(labelText: 'Access Token'),
                  ),
                  const SizedBox(height: 12),
                  DropdownButtonFormField<String>(
                    initialValue: _region,
                    decoration: const InputDecoration(labelText: '地区'),
                    items: const [
                      DropdownMenuItem(value: 'cn', child: Text('中国大陆 (cn)')),
                      DropdownMenuItem(value: 'hk', child: Text('香港 (hk)')),
                      DropdownMenuItem(value: 'overseas', child: Text('海外 (overseas)')),
                    ],
                    onChanged: (v) => setState(() => _region = v ?? 'hk'),
                  ),
                  const SizedBox(height: 16),
                  Row(
                    children: [
                      FilledButton(
                        onPressed: _saving ? null : _save,
                        child: const Text('保 存'),
                      ),
                      const SizedBox(width: 8),
                      OutlinedButton(
                        onPressed: _testConn,
                        child: const Text('测试连接'),
                      ),
                    ],
                  ),
                  if (_test != null) ...[
                    const SizedBox(height: 12),
                    SelectableText(_test!),
                  ],
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class QuantAlphaPage extends StatelessWidget {
  const QuantAlphaPage({super.key});

  @override
  Widget build(BuildContext context) {
    return const JsonListPage(
      title: 'Alpha 快照',
      path: '/quant/factor/snapshots',
      extraQuery: {'limit': 80},
      paged: false,
    );
  }
}

class QuantRiskPage extends StatelessWidget {
  const QuantRiskPage({super.key});

  @override
  Widget build(BuildContext context) {
    return const JsonListPage(
      title: '风险概览',
      path: '/trade/risk/events',
      extraQuery: {'limit': 50},
      paged: false,
    );
  }
}

class QuantWatchlistPage extends StatelessWidget {
  const QuantWatchlistPage({super.key, this.open});
  final OpenRoute? open;

  @override
  Widget build(BuildContext context) {
    return JsonListPage(
      title: '量化自选池',
      path: '/quant/watchlist/list',
      columns: const [
        TableCol('代码', 'symbol'),
        TableCol('名称', 'name'),
        TableCol('市场', 'market'),
        TableCol('备注', 'note'),
      ],
      onRowTap: (row) => open?.call(
        '/market/symbol?symbol=${row['symbol']}&market=${row['market']}',
        title: cellText(row['symbol']),
      ),
    );
  }
}
