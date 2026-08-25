import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api/api_client.dart';
import '../../core/api/ruoyi_client.dart';
import '../../core/theme/ruoyi_tokens.dart';
import '../../shared/widgets/ruoyi_ui.dart';

class PortalPage extends StatelessWidget {
  const PortalPage({super.key, this.open});
  final OpenRoute? open;

  static const _groups = [
    (
      '舆情与 AI 研判',
      '中文舆情采集、大盘影响研判与统一模型对话',
      '/sentiment/dashboard',
      Icons.analytics_outlined,
      [
        ('舆情 AI 大盘', '/sentiment/dashboard'),
        ('AI 研判工作台', '/market/ai-workbench'),
        ('AI 助手', '/ai/chat'),
      ],
    ),
    (
      '行情中心',
      '市场热度、报价台、自选与财经资讯',
      '/market/heat',
      Icons.candlestick_chart_outlined,
      [
        ('行情交易', '/trade/terminal'),
        ('市场热度', '/market/heat'),
        ('行情台', '/market/board'),
        ('自选清单', '/market/watchlist'),
      ],
    ),
    (
      '核心交易',
      '报价下单、持仓订单、券商通道与通知',
      '/trade/trading',
      Icons.payments_outlined,
      [
        ('行情交易', '/trade/terminal'),
        ('核心交易台', '/trade/trading'),
        ('持仓与订单', '/trade/positions'),
        ('券商账户', '/trade/broker'),
        ('通知中心', '/trade/notifications'),
      ],
    ),
    (
      '量化策略',
      '多因子信号、档位阈值与 Influx 回测',
      '/quant/strategy',
      Icons.auto_graph,
      [
        ('量化策略中心', '/quant/strategy'),
        ('Alpha 快照', '/quant/alpha-snapshot'),
        ('策略配置', '/quant/strategy-config'),
        ('策略回测', '/trade/backtest'),
      ],
    ),
    (
      '风控管理',
      '规则、扫描与风险事件',
      '/trade/risk',
      Icons.warning_amber_outlined,
      [
        ('风控管理', '/trade/risk'),
        ('风险复核', '/trade/risk-review'),
      ],
    ),
    (
      '平台工作台',
      '业务总览、行情快照与系统监控',
      '/index',
      Icons.monitor_heart_outlined,
      [
        ('工作台首页', '/index'),
        ('自动分析任务', '/analysis/jobs'),
        ('系统监控', '/monitor/job'),
      ],
    ),
  ];

  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    final w = MediaQuery.sizeOf(context).width;
    final pad = w < 600 ? 16.0 : 32.0;
    final cardW = w < 720 ? w - pad * 2 : 360.0;
    return ColoredBox(
      color: dark ? WebTokens.loginDark : const Color(0xFFE2E8F0),
      child: CustomPaint(
        painter: _PortalGlow(dark: dark),
        child: ListView(
          padding: EdgeInsets.fromLTRB(pad, w < 600 ? 16 : 28, pad, 24),
          children: [
            ShaderMask(
              shaderCallback: (r) => const LinearGradient(
                colors: [Color(0xFF38BDF8), Color(0xFFA78BFA), Color(0xFF34D399)],
              ).createShader(r),
              child: const Text(
                '智慧金融 · NEXUS',
                style: TextStyle(
                  fontSize: 22,
                  fontWeight: FontWeight.w800,
                  letterSpacing: 2,
                  color: Colors.white,
                ),
              ),
            ),
            const SizedBox(height: 18),
            Text(
              '量化交易与 AI 研判综合指挥中心',
              style: TextStyle(
                fontSize: w < 600 ? 22 : 28,
                fontWeight: FontWeight.w800,
                color: dark ? Colors.white : const Color(0xFF0F172A),
              ),
            ),
            const SizedBox(height: 6),
            Text(
              'QUANTITATIVE TRADING & AI ANALYSIS COMMAND CENTER',
              style: TextStyle(
                letterSpacing: 2,
                fontSize: 12,
                color: dark ? const Color(0x99E2E8F0) : const Color(0xFF64748B),
              ),
            ),
            const SizedBox(height: 16),
            if (w < 720) ...[
              GridView.count(
                crossAxisCount: 4,
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                mainAxisSpacing: 8,
                crossAxisSpacing: 8,
                childAspectRatio: 0.9,
                children: [
                  _Shortcut('行情', Icons.candlestick_chart_outlined, () => open?.call('/market/heat', title: '行情')),
                  _Shortcut('自选', Icons.star_outline, () => open?.call('/market/watchlist', title: '自选')),
                  _Shortcut('选股', Icons.auto_awesome, () => open?.call('/market/recommendations', title: '智能选股')),
                  _Shortcut('交易', Icons.payments_outlined, () => open?.call('/trade/terminal', title: '交易')),
                  _Shortcut('持仓', Icons.account_balance_wallet_outlined, () => open?.call('/trade/positions', title: '持仓')),
                  _Shortcut('量化', Icons.auto_graph, () => open?.call('/quant/strategy', title: '量化')),
                  _Shortcut('舆情', Icons.analytics_outlined, () => open?.call('/sentiment/dashboard', title: '舆情')),
                  _Shortcut('AI', Icons.psychology_outlined, () => open?.call('/market/ai-workbench', title: 'AI 研判')),
                ],
              ),
              const SizedBox(height: 16),
            ],
            Wrap(
              spacing: 16,
              runSpacing: 16,
              children: [
                for (final g in _groups)
                  SizedBox(
                    width: cardW,
                    child: _ModuleCard(
                      title: g.$1,
                      desc: g.$2,
                      icon: g.$4,
                      links: g.$5,
                      onEnter: () => open?.call(g.$3, title: g.$1),
                      onLink: (p, t) => open?.call(p, title: t),
                    ),
                  ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _Shortcut extends StatelessWidget {
  const _Shortcut(this.label, this.icon, this.onTap);
  final String label;
  final IconData icon;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(12),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              color: const Color(0x33409EFF),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Icon(icon, color: const Color(0xFF38BDF8), size: 22),
          ),
          const SizedBox(height: 6),
          Text(label, style: const TextStyle(fontSize: 11, color: Color(0xFFE2E8F0))),
        ],
      ),
    );
  }
}

class _ModuleCard extends StatelessWidget {
  const _ModuleCard({
    required this.title,
    required this.desc,
    required this.icon,
    required this.links,
    required this.onEnter,
    required this.onLink,
  });

  final String title;
  final String desc;
  final IconData icon;
  final List<(String, String)> links;
  final VoidCallback onEnter;
  final void Function(String path, String title) onLink;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: const Color(0x8C0F172A),
      borderRadius: BorderRadius.circular(16),
      child: InkWell(
        onTap: onEnter,
        borderRadius: BorderRadius.circular(16),
        child: Container(
          padding: const EdgeInsets.all(18),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: const Color(0x1FFFFFFF)),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(icon, color: const Color(0xFF38BDF8), size: 28),
              const SizedBox(height: 12),
              Text(
                title,
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 18,
                  fontWeight: FontWeight.w700,
                ),
              ),
              const SizedBox(height: 6),
              Text(desc, style: const TextStyle(color: Color(0xB3E2E8F0), fontSize: 13)),
              const SizedBox(height: 12),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  for (final l in links)
                    TextButton(
                      onPressed: () => onLink(l.$2, l.$1),
                      child: Text(l.$1),
                    ),
                ],
              ),
              Align(
                alignment: Alignment.centerRight,
                child: Text(
                  '进入 $title →',
                  style: const TextStyle(color: Color(0xFF38BDF8), fontSize: 13),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _PortalGlow extends CustomPainter {
  _PortalGlow({required this.dark});
  final bool dark;

  @override
  void paint(Canvas canvas, Size size) {
    final p = Paint()..color = const Color(0x3338BDF8);
    canvas.drawCircle(Offset(size.width * 0.15, 80), 120, p);
    canvas.drawCircle(
      Offset(size.width * 0.85, size.height * 0.7),
      160,
      Paint()..color = const Color(0x339333EA),
    );
  }

  @override
  bool shouldRepaint(covariant _PortalGlow oldDelegate) => oldDelegate.dark != dark;
}

class DashboardPage extends ConsumerStatefulWidget {
  const DashboardPage({super.key, this.open});
  final OpenRoute? open;

  @override
  ConsumerState<DashboardPage> createState() => _DashboardPageState();
}

class _DashboardPageState extends ConsumerState<DashboardPage> {
  bool _busy = true;
  String? _error;
  Map<String, dynamic> _summary = const {};
  List<Map<String, dynamic>> _reviews = const [];

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
      final summary = await client.get('/dashboard/summary');
      List<Map<String, dynamic>> reviews = const [];
      try {
        final r = await client.get('/market/review/latest');
        reviews = extractRows(r, preferKeys: const ['items', 'reviews']);
        if (reviews.isEmpty) {
          final data = asMap(r.data);
          if (data.isNotEmpty && data.containsKey('market')) reviews = [data];
        }
      } catch (_) {}
      if (!mounted) return;
      setState(() {
        _summary = asMap(summary.data);
        _reviews = reviews;
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
    final asset = asMap(_summary['asset']);
    final heat = asMap(_summary['heat']);
    final sentiment = asMap(_summary['sentiment']);
    final quotes = _asRows(_summary['quotes']);
    final briefings = _asRows(_summary['briefings']);
    final health = asMap(_summary['health']);
    return AppPage(
      child: ListView(
        children: [
          PageHero(
            title: '工作台首页',
            subtitle: '业务总览 · 行情快照 · 系统状态',
            actions: [
              OutlinedButton.icon(
                onPressed: _busy ? null : _load,
                icon: const Icon(Icons.refresh, size: 16),
                label: const Text('刷新'),
              ),
            ],
          ),
          if (_error != null) ErrorBanner(_error!, onRetry: _load),
          if (_busy) const LinearProgressIndicator(minHeight: 2),
          ElCard(
            header: const Text('资产'),
            child: KvGrid({
              '总资产': cellText(asset['total'] ?? asset['netAsset'] ?? asset['equity']),
              '现金': cellText(asset['cash'] ?? asset['available']),
              '持仓市值': cellText(asset['marketValue'] ?? asset['positionValue']),
              '当日盈亏': cellText(asset['pnl'] ?? asset['dayPnl']),
            }),
          ),
          const SizedBox(height: 12),
          ElCard(
            header: Row(
              children: [
                const Expanded(child: Text('市场分析')),
                TextButton(
                  onPressed: () => widget.open?.call('/market/review', title: '市场分析'),
                  child: const Text('历史记录'),
                ),
              ],
            ),
            child: _reviews.isEmpty
                ? const EmptyHint('暂无收盘复盘')
                : Wrap(
                    spacing: 12,
                    runSpacing: 12,
                    children: [
                      for (final r in _reviews)
                        SizedBox(
                          width: 280,
                          child: InkWell(
                            onTap: () => widget.open?.call('/market/review', title: '市场分析'),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Row(
                                  children: [
                                    Text(
                                      cellText(r['marketLabel'] ?? r['market']),
                                      style: const TextStyle(fontWeight: FontWeight.w700),
                                    ),
                                    const Spacer(),
                                    ElTag(
                                      cellText(r['stance'] ?? '待分析'),
                                      tone: ElTagTone.primary,
                                    ),
                                  ],
                                ),
                                Text(
                                  '${cellText(r['tradeDate'])} · 温度 ${cellText(r['score'])}',
                                  style: Theme.of(context).textTheme.bodySmall,
                                ),
                                const SizedBox(height: 6),
                                Text(cellText(r['summary'])),
                              ],
                            ),
                          ),
                        ),
                    ],
                  ),
          ),
          const SizedBox(height: 12),
          ElCard(
            header: const Text('快捷导航'),
            child: Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                for (final e in [
                  ('行情台', '/market/board'),
                  ('行情交易', '/trade/terminal'),
                  ('自选', '/market/watchlist'),
                  ('交易工作台', '/trade/desk'),
                  ('策略配置', '/quant/strategy-config'),
                  ('舆情大盘', '/sentiment/dashboard'),
                  ('AI 对话', '/ai/chat'),
                ])
                  OutlinedButton(
                    onPressed: () => widget.open?.call(e.$2, title: e.$1),
                    child: Text(e.$1),
                  ),
              ],
            ),
          ),
          const SizedBox(height: 12),
          ElCard(
            header: const Text('AI 研判'),
            child: Text(
              cellText(
                sentiment['summary'] ?? sentiment['verdict'] ?? sentiment['content'] ?? '暂无',
              ),
            ),
          ),
          const SizedBox(height: 12),
          ElCard(
            header: const Text('市场热度'),
            child: KvGrid({
              '摘要': cellText(heat['heatSummary'] ?? heat['summary']),
              '分数': cellText(heat['heatScore'] ?? heat['score']),
              '上涨': cellText(heat['advanceCount']),
              '下跌': cellText(heat['declineCount']),
            }),
          ),
          const SizedBox(height: 12),
          ElCard(
            header: const Text('简报'),
            padding: EdgeInsets.zero,
            child: SimpleTable(
              columns: const [
                TableCol('时间', 'generatedAt'),
                TableCol('标题', 'headline'),
                TableCol('市场', 'market'),
              ],
              rows: briefings.take(8).toList(),
            ),
          ),
          const SizedBox(height: 12),
          ElCard(
            header: const Text('报价'),
            padding: EdgeInsets.zero,
            child: SimpleTable(
              columns: const [
                TableCol('代码', 'symbol'),
                TableCol('名称', 'name'),
                TableCol('最新', 'last'),
                TableCol('涨跌%', 'changePct'),
              ],
              rows: quotes.take(12).toList(),
            ),
          ),
          const SizedBox(height: 12),
          ElCard(
            header: const Text('系统健康'),
            child: KvGrid({
              for (final e in health.entries)
                if (e.value is! Map && e.value is! List) e.key: cellText(e.value),
            }),
          ),
        ],
      ),
    );
  }

}

List<Map<String, dynamic>> _asRows(dynamic raw) {
  if (raw is List) return raw.whereType<Map<String, dynamic>>().toList();
  if (raw is Map<String, dynamic>) {
    for (final k in ['items', 'quotes', 'list', 'rows']) {
      final v = raw[k];
      if (v is List) return v.whereType<Map<String, dynamic>>().toList();
    }
  }
  return const [];
}
