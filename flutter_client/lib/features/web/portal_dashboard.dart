import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/api/api_client.dart';
import '../../core/api/ruoyi_client.dart';
import '../../core/menu/menu_api.dart';
import '../../core/menu/router_models.dart';
import '../../core/theme/app_theme.dart';
import '../../core/theme/ruoyi_tokens.dart';
import '../../features/auth/logic/session_controller.dart';
import '../../shared/widgets/cyber_background.dart';
import '../../shared/widgets/ruoyi_ui.dart';

class PortalPage extends ConsumerWidget {
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
        ('专业交易终端 (Pro)', '/trade/terminal'),
        ('市场热度', '/market/heat'),
        ('行情台', '/market/board'),
        ('自选清单', '/market/watchlist'),
      ],
    ),
    (
      '核心交易',
      '报价下单、持仓订单、券商通道与通知',
      '/trade/terminal',
      Icons.payments_outlined,
      [
        ('专业交易终端 (Pro)', '/trade/terminal'),
        ('行情交易', '/trade/terminal'),
        ('持仓与订单', '/trade/positions'),
        ('券商账户', '/trade/broker'),
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
      Icons.monitor_outlined,
      [
        ('工作台首页', '/index'),
        ('自动分析任务', '/analysis/jobs'),
        ('系统监控', '/monitor/job'),
      ],
    ),
  ];

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    final session = ref.watch(sessionController);
    final name = session.user?.displayName ?? '用户';
    final role = session.roles.contains('admin') ? '超级管理员' : '平台用户';
    final w = MediaQuery.sizeOf(context).width;
    final isMac = AppDimens.isMac(context);
    final allowed = visibleMenuPaths(ref.watch(routersProvider).asData?.value ?? const []);
    bool can(String path) => menuAllows(allowed, path);
    final groups = [
      for (final g in _groups)
        if (can(g.$3) || g.$5.any((l) => can(l.$2)))
          (
            g.$1,
            g.$2,
            g.$3,
            g.$4,
            [for (final l in g.$5) if (can(l.$2)) l],
          ),
    ];
    final fg = dark ? const Color(0xFFE2E8F0) : const Color(0xFF0F172A);
    final muted = dark ? const Color(0x99E2E8F0) : const Color(0xFF64748B);
    final cols = w >= 1200 ? 3 : (w >= 720 ? 2 : 1);

    Future<void> logout() async {
      final ok = await confirm(context, '确定退出登录吗？');
      if (!ok) return;
      await ref.read(sessionController.notifier).logout();
      if (context.mounted) context.go('/login');
    }

    return ColoredBox(
      color: dark ? const Color(0xFF020617) : const Color(0xFFE2E8F0),
      child: Stack(
        children: [
          Positioned.fill(child: CyberBackground(dark: dark)),
          Column(
            children: [
              Padding(
                padding: EdgeInsets.fromLTRB(
                  isMac ? AppDimens.macTrafficLeft : (w < 600 ? 16 : 40),
                  isMac ? 6 : 22,
                  w < 600 ? 16 : 40,
                  0,
                ),
                child: Row(
                  children: [
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
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
                          const SizedBox(height: 2),
                          Text(
                            'QUANT · SENTIMENT · MARKET',
                            style: TextStyle(fontSize: 11, letterSpacing: 2, color: muted),
                          ),
                        ],
                      ),
                    ),
                    _GlassChip(
                      dark: dark,
                      onTap: () => ref.read(themeModeController.notifier).toggle(),
                      child: Row(
                        children: [
                          Icon(dark ? Icons.wb_sunny_outlined : Icons.dark_mode_outlined, size: 16, color: fg),
                          const SizedBox(width: 8),
                          Text(dark ? '浅色模式' : '深色模式', style: TextStyle(fontSize: 13, color: fg)),
                        ],
                      ),
                    ),
                    const SizedBox(width: 12),
                    PopupMenuButton<String>(
                      tooltip: name,
                      onSelected: (v) {
                        if (v == 'profile') open?.call('/user/profile', title: '个人中心');
                        if (v == 'index') open?.call('/index', title: '工作台首页');
                        if (v == 'logout') logout();
                      },
                      itemBuilder: (_) => const [
                        PopupMenuItem(value: 'profile', child: Text('个人中心')),
                        PopupMenuItem(value: 'index', child: Text('工作台首页')),
                        PopupMenuItem(value: 'logout', child: Text('退出登录')),
                      ],
                      child: _GlassChip(
                        dark: dark,
                        child: Row(
                          children: [
                            CircleAvatar(
                              radius: 16,
                              backgroundColor: const Color(0xFF38BDF8),
                              child: Text(
                                name.isEmpty ? 'U' : name.characters.first,
                                style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w700),
                              ),
                            ),
                            if (w >= 720) ...[
                              const SizedBox(width: 10),
                              Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(name, style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: fg)),
                                  Text(role, style: TextStyle(fontSize: 11, color: muted)),
                                ],
                              ),
                              const SizedBox(width: 6),
                              Icon(Icons.keyboard_arrow_down, size: 16, color: muted),
                            ],
                          ],
                        ),
                      ),
                    ),
                  ],
                ),
              ),
              Expanded(
                child: Center(
                  child: ConstrainedBox(
                    constraints: const BoxConstraints(maxWidth: 1280),
                    child: ListView(
                      padding: EdgeInsets.fromLTRB(w < 600 ? 16 : 28, 28, w < 600 ? 16 : 28, 32),
                      children: [
                        Column(
                          children: [
                            Text(
                              '量化交易与 AI 研判综合指挥中心',
                              textAlign: TextAlign.center,
                              style: TextStyle(
                                fontSize: w < 720 ? 22 : 32,
                                fontWeight: FontWeight.w800,
                                letterSpacing: 3,
                                color: fg,
                              ),
                            ),
                            const SizedBox(height: 10),
                            Text(
                              'QUANTITATIVE TRADING & AI ANALYSIS COMMAND CENTER',
                              textAlign: TextAlign.center,
                              style: TextStyle(fontSize: 13, letterSpacing: 4, color: muted),
                            ),
                            const SizedBox(height: 14),
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                              decoration: BoxDecoration(
                                color: const Color(0x1438BDF8),
                                borderRadius: BorderRadius.circular(999),
                                border: Border.all(color: const Color(0x3338BDF8)),
                              ),
                              child: Row(
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  Container(
                                    width: 8,
                                    height: 8,
                                    decoration: const BoxDecoration(
                                      color: Color(0xFF39FF14),
                                      shape: BoxShape.circle,
                                      boxShadow: [BoxShadow(color: Color(0xFF39FF14), blurRadius: 8)],
                                    ),
                                  ),
                                  const SizedBox(width: 8),
                                  Text(
                                    'NEXUS AI Core Active · Influx 时序在线 · 证券级通道',
                                    style: TextStyle(fontSize: 12, color: muted),
                                  ),
                                ],
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 36),
                        LayoutBuilder(
                          builder: (context, c) {
                            final gap = 22.0;
                            final cardW = cols == 1 ? c.maxWidth : (c.maxWidth - gap * (cols - 1)) / cols;
                            return Wrap(
                              spacing: gap,
                              runSpacing: gap,
                              children: [
                                for (final g in groups)
                                  SizedBox(
                                    width: cardW,
                                    child: _ModuleCard(
                                      dark: dark,
                                      title: g.$1,
                                      desc: g.$2,
                                      icon: g.$4,
                                      links: g.$5,
                                      onEnter: () => open?.call(g.$3, title: g.$1),
                                      onLink: (p, t) => open?.call(p, title: t),
                                    ),
                                  ),
                              ],
                            );
                          },
                        ),
                        const SizedBox(height: 40),
                        Text(
                          '系统版本 V2.0 · 智慧金融分析平台',
                          textAlign: TextAlign.center,
                          style: TextStyle(fontSize: 13, letterSpacing: 1, color: muted),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _GlassChip extends StatelessWidget {
  const _GlassChip({required this.dark, required this.child, this.onTap});
  final bool dark;
  final Widget child;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final box = Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: dark ? const Color(0x8C0F172A) : const Color(0xADFFFFFF),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: dark ? const Color(0x1FFFFFFF) : const Color(0x14000000)),
      ),
      child: child,
    );
    if (onTap == null) return box;
    return Material(
      color: Colors.transparent,
      child: InkWell(onTap: onTap, borderRadius: BorderRadius.circular(999), child: box),
    );
  }
}

class _ModuleCard extends StatefulWidget {
  const _ModuleCard({
    required this.dark,
    required this.title,
    required this.desc,
    required this.icon,
    required this.links,
    required this.onEnter,
    required this.onLink,
  });

  final bool dark;
  final String title;
  final String desc;
  final IconData icon;
  final List<(String, String)> links;
  final VoidCallback onEnter;
  final void Function(String path, String title) onLink;

  @override
  State<_ModuleCard> createState() => _ModuleCardState();
}

class _ModuleCardState extends State<_ModuleCard> {
  bool _hover = false;

  @override
  Widget build(BuildContext context) {
    final dark = widget.dark;
    final fg = dark ? const Color(0xFFE2E8F0) : const Color(0xFF0F172A);
    final muted = dark ? const Color(0xB3E2E8F0) : const Color(0xFF475569);
    final accent = dark ? const Color(0xFF00C3FF) : const Color(0xFF2563EB);
    return MouseRegion(
      onEnter: (_) => setState(() => _hover = true),
      onExit: (_) => setState(() => _hover = false),
      child: AnimatedSlide(
        duration: const Duration(milliseconds: 220),
        offset: Offset(0, _hover ? -0.018 : 0),
        child: Material(
          color: Colors.transparent,
          child: InkWell(
            onTap: widget.onEnter,
            borderRadius: BorderRadius.circular(16),
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 220),
              constraints: const BoxConstraints(minHeight: 248),
              padding: const EdgeInsets.fromLTRB(22, 26, 22, 18),
              decoration: BoxDecoration(
                color: dark ? const Color(0x8C0F172A) : const Color(0xADFFFFFF),
                borderRadius: BorderRadius.circular(16),
                border: Border.all(
                  color: _hover
                      ? (dark ? const Color(0x5900F0FF) : const Color(0x732563EB))
                      : (dark ? const Color(0x1FFFFFFF) : const Color(0x14000000)),
                ),
                boxShadow: _hover
                    ? [BoxShadow(color: accent.withValues(alpha: 0.18), blurRadius: 28, offset: const Offset(0, 12))]
                    : [BoxShadow(color: Colors.black.withValues(alpha: dark ? 0.28 : 0.06), blurRadius: 18, offset: const Offset(0, 8))],
              ),
              child: Column(
                children: [
                  AnimatedContainer(
                    duration: const Duration(milliseconds: 220),
                    width: 64,
                    height: 64,
                    alignment: Alignment.center,
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(16),
                      color: _hover ? null : (dark ? const Color(0x1A00F0FF) : const Color(0x1A2563EB)),
                      gradient: _hover
                          ? const LinearGradient(colors: [Color(0xFF00C3FF), Color(0xFF6366F1)])
                          : null,
                    ),
                    child: Icon(widget.icon, size: 30, color: _hover ? Colors.white : accent),
                  ),
                  const SizedBox(height: 18),
                  Text(
                    widget.title,
                    textAlign: TextAlign.center,
                    style: TextStyle(color: fg, fontSize: 17, fontWeight: FontWeight.w700, letterSpacing: 1),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    widget.desc,
                    textAlign: TextAlign.center,
                    style: TextStyle(color: muted, fontSize: 13.5, height: 1.55),
                  ),
                  const SizedBox(height: 16),
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    alignment: WrapAlignment.center,
                    children: [
                      for (final l in widget.links)
                        InkWell(
                          onTap: () => widget.onLink(l.$2, l.$1),
                          borderRadius: BorderRadius.circular(999),
                          child: Container(
                            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                            decoration: BoxDecoration(
                              color: dark ? const Color(0x1438BDF8) : const Color(0x142563EB),
                              borderRadius: BorderRadius.circular(999),
                              border: Border.all(color: dark ? const Color(0x4738BDF8) : const Color(0x332563EB)),
                            ),
                            child: Text(l.$1, style: TextStyle(fontSize: 12, color: fg)),
                          ),
                        ),
                    ],
                  ),
                  const SizedBox(height: 14),
                  AnimatedOpacity(
                    duration: const Duration(milliseconds: 200),
                    opacity: _hover ? 1 : 0.55,
                    child: Text('进入 ${widget.title} →', style: TextStyle(color: accent, fontSize: 12, letterSpacing: 1)),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
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
                  ('行情交易', '/trade/terminal'),
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
