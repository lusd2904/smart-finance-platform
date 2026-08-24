import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:flutter_client/core/gateway/gateway_controller.dart';
import 'package:flutter_client/features/auth/logic/session_controller.dart';
import 'package:flutter_client/features/kline/presentation/symbol_detail_page.dart';
import 'package:flutter_client/features/market/presentation/market_tab.dart';
import 'package:flutter_client/features/watchlist/presentation/watchlist_tab.dart';

/// 自适应首页壳：宽屏（桌面端）侧栏导航 + 内容区；窄屏（手机）底部导航。
/// 四个 tab：工作台 / 行情（M1 热度看板）/ 自选 / 我的。
class HomeShell extends ConsumerStatefulWidget {
  const HomeShell({super.key});

  @override
  ConsumerState<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends ConsumerState<HomeShell> {
  int _index = 0;
  static const _destinations = [
    (icon: Icons.dashboard_outlined, selectedIcon: Icons.dashboard, label: '工作台'),
    (icon: Icons.candlestick_chart_outlined, selectedIcon: Icons.candlestick_chart, label: '行情'),
    (icon: Icons.star_border, selectedIcon: Icons.star, label: '自选'),
    (icon: Icons.person_outline, selectedIcon: Icons.person, label: '我的'),
  ];

  /// 统一的标的详情入口：行情/自选等列表行点击后跳转。
  void _openSymbol(String symbol, String market, String name) {
    Navigator.of(context).push(MaterialPageRoute<void>(
      builder: (_) => SymbolDetailPage(symbol: symbol, market: market, name: name),
    ));
  }
  @override
  Widget build(BuildContext context) {
    final session = ref.watch(sessionController);
    final gateway = ref.watch(gatewayController);
    final wide = MediaQuery.sizeOf(context).width >= 900;
    final body = switch (_index) {
      0 => _WorkspaceTab(gatewayUrl: gateway.url),
      1 => MarketTab(onOpenSymbol: _openSymbol),
      2 => WatchlistTab(onOpenSymbol: _openSymbol),
      _ => _MineTab(session: session),
    };
    if (!wide) {
      return Scaffold(
        body: body,
        bottomNavigationBar: NavigationBar(
          selectedIndex: _index,
          destinations: [
            for (final d in _destinations)
              NavigationDestination(icon: Icon(d.icon), selectedIcon: Icon(d.selectedIcon), label: d.label),
          ],
          onDestinationSelected: (i) => setState(() => _index = i),
        ),
      );
    }
    return Scaffold(
      body: Row(
        children: [
          NavigationRail(
            selectedIndex: _index,
            onDestinationSelected: (i) => setState(() => _index = i),
            extended: MediaQuery.sizeOf(context).width >= 1200,
            labelType: NavigationRailLabelType.none,
            leading: Padding(
              padding: const EdgeInsets.symmetric(vertical: 12),
              child: Icon(
                Icons.show_chart,
                color: Theme.of(context).colorScheme.primary,
                size: 32,
              ),
            ),
            destinations: [
              for (final d in _destinations)
                NavigationRailDestination(
                  icon: Icon(d.icon),
                  selectedIcon: Icon(d.selectedIcon),
                  label: Text(d.label),
                ),
            ],
          ),
          const VerticalDivider(width: 1),
          Expanded(child: body),
        ],
      ),
    );
  }
}

class _WorkspaceTab extends ConsumerWidget {
  const _WorkspaceTab({required this.gatewayUrl});

  final String gatewayUrl;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 560),
        child: Card(
          margin: const EdgeInsets.all(24),
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(children: [Icon(Icons.verified, color: theme.colorScheme.primary), const SizedBox(width: 8), Text('连接正常', style: theme.textTheme.titleMedium)]),
                const Divider(height: 24),
                ListTile(
                  dense: true,
                  contentPadding: EdgeInsets.zero,
                  leading: const Icon(Icons.settings_ethernet),
                  title: const Text('网关'),
                  subtitle: Text(gatewayUrl.isEmpty ? '未配置' : gatewayUrl),
                  trailing: IconButton(
                    icon: const Icon(Icons.edit_outlined),
                    onPressed: () => context.go('/gateway'),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _MineTab extends ConsumerWidget {
  const _MineTab({required this.session});

  final SessionState session;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    final name = session.user?.displayName ?? '已登录用户';
    return ListView(
      padding: const EdgeInsets.all(24),
      children: [
        CircleAvatar(radius: 36, child: Text(name.characters.first.toUpperCase(), style: theme.textTheme.headlineMedium)),
        const SizedBox(height: 12),
        Center(child: Text(name, style: theme.textTheme.titleMedium)),
        if (session.roles.isNotEmpty) ...[
          const SizedBox(height: 4),
          Center(child: Text('角色：${session.roles.join('、')}', style: theme.textTheme.bodySmall)),
        ],
        const SizedBox(height: 24),
        OutlinedButton.icon(
          icon: const Icon(Icons.logout),
          label: const Text('退出登录'),
          onPressed: () async {
            await ref.read(sessionController.notifier).logout();
            if (context.mounted) context.go('/login');
          },
        ),
      ],
    );
  }
}
