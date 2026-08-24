import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:flutter_client/core/gateway/gateway_controller.dart';
import 'package:flutter_client/core/theme/app_theme.dart';
import 'package:flutter_client/features/auth/logic/session_controller.dart';
import 'package:flutter_client/features/kline/presentation/symbol_detail_page.dart';
import 'package:flutter_client/features/market/presentation/market_tab.dart';
import 'package:flutter_client/features/market/presentation/universe_page.dart';
import 'package:flutter_client/features/watchlist/presentation/watchlist_tab.dart';
import 'package:flutter_client/shared/widgets/status_dot.dart';
import 'package:flutter_client/shared/widgets/brand_logo.dart';
import 'package:flutter_client/shared/widgets/page_header.dart';
import 'package:flutter_client/shared/widgets/stat_grid.dart';

/// 自适应首页壳：
/// - 宽屏（桌面端 ≥900）：品牌侧栏（≥1200 展开）+ 内容区；
/// - 窄屏（手机）：底部导航。
/// 四个 tab：工作台 / 行情 / 自选 / 我的；IndexedStack 保活各 tab 滚动与数据状态。
class HomeShell extends ConsumerStatefulWidget {
  const HomeShell({super.key});

  @override
  ConsumerState<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends ConsumerState<HomeShell> {
  int _index = 0;
  static const _destinations = [
    (
      icon: Icons.dashboard_outlined,
      selectedIcon: Icons.dashboard,
      label: '工作台',
    ),
    (
      icon: Icons.candlestick_chart_outlined,
      selectedIcon: Icons.candlestick_chart,
      label: '行情',
    ),
    (icon: Icons.star_border, selectedIcon: Icons.star, label: '自选'),
    (icon: Icons.person_outline, selectedIcon: Icons.person, label: '我的'),
  ];

  /// 统一的标的详情入口：行情/自选等列表行点击后跳转。
  void _openSymbol(String symbol, String market, String name) {
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) =>
            SymbolDetailPage(symbol: symbol, market: market, name: name),
      ),
    );
  }

  /// 工作台快捷入口的 tab 切换。
  void _goTab(int i) => setState(() => _index = i);

  @override
  Widget build(BuildContext context) {
    final session = ref.watch(sessionController);
    final gateway = ref.watch(gatewayController);
    final wide = MediaQuery.sizeOf(context).width >= AppDimens.wideBreakpoint;

    final body = IndexedStack(
      index: _index,
      children: [
        WorkspaceTab(
          gatewayUrl: gateway.url,
          onGoTab: _goTab,
          onOpenSymbol: _openSymbol,
        ),
        MarketTab(onOpenSymbol: _openSymbol),
        WatchlistTab(onOpenSymbol: _openSymbol),
        MineTab(session: session),
      ],
    );

    if (!wide) {
      return Scaffold(
        body: body,
        bottomNavigationBar: NavigationBar(
          selectedIndex: _index,
          destinations: [
            for (final d in _destinations)
              NavigationDestination(
                icon: Icon(d.icon),
                selectedIcon: Icon(d.selectedIcon),
                label: d.label,
              ),
          ],
          onDestinationSelected: (i) => setState(() => _index = i),
        ),
      );
    }

    final extended = MediaQuery.sizeOf(context).width >= 1200;
    return Scaffold(
      body: Row(
        children: [
          _SideNav(
            index: _index,
            extended: extended,
            session: session,
            gatewayUrl: gateway.url,
            onSelect: (i) => setState(() => _index = i),
          ),
          const VerticalDivider(width: 1),
          Expanded(child: body),
        ],
      ),
    );
  }
}

/// 桌面端品牌侧栏：logo 字标 + 导航 + 底部网关状态。折叠时仅图标（带 tooltip）。
class _SideNav extends StatelessWidget {
  const _SideNav({
    required this.index,
    required this.extended,
    required this.session,
    required this.gatewayUrl,
    required this.onSelect,
  });

  final int index;
  final bool extended;
  final SessionState session;
  final String gatewayUrl;
  final ValueChanged<int> onSelect;

  static const _items = [
    (
      icon: Icons.dashboard_outlined,
      selectedIcon: Icons.dashboard,
      label: '工作台',
    ),
    (
      icon: Icons.candlestick_chart_outlined,
      selectedIcon: Icons.candlestick_chart,
      label: '行情',
    ),
    (icon: Icons.star_border, selectedIcon: Icons.star, label: '自选'),
    (icon: Icons.person_outline, selectedIcon: Icons.person, label: '我的'),
  ];

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    return Material(
      color: scheme.surfaceContainerLow,
      child: SizedBox(
        width: extended ? AppDimens.sideNavWidth : AppDimens.sideRailWidth,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Padding(
              padding: EdgeInsets.fromLTRB(
                extended ? 16 : 12,
                18,
                extended ? 16 : 12,
                6,
              ),
              child: extended
                  ? const BrandWordmark()
                  : const Center(child: BrandMark(size: 32)),
            ),
            const SizedBox(height: 14),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 10),
              child: Column(
                children: [
                  for (var i = 0; i < _items.length; i++)
                    _SideNavItem(
                      icon: _items[i].icon,
                      selectedIcon: _items[i].selectedIcon,
                      label: _items[i].label,
                      selected: index == i,
                      extended: extended,
                      onTap: () => onSelect(i),
                    ),
                ],
              ),
            ),
            const Spacer(),
            Padding(
              padding: const EdgeInsets.all(10),
              child: Tooltip(
                message: '网关设置',
                child: InkWell(
                  borderRadius: BorderRadius.circular(AppDimens.radiusControl),
                  onTap: () => context.go('/gateway'),
                  child: Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 10,
                      vertical: 10,
                    ),
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(
                        AppDimens.radiusControl,
                      ),
                      border: Border.all(color: scheme.outlineVariant),
                    ),
                    child: Row(
                      children: [
                        StatusDot(
                          color: gatewayUrl.isEmpty
                              ? AppColors.warn
                              : AppColors.down,
                        ),
                        if (extended) ...[
                          const SizedBox(width: 8),
                          Expanded(
                            child: Text(
                              gatewayUrl.isEmpty ? '网关未配置' : '网关已连接',
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: theme.textTheme.bodySmall?.copyWith(
                                color: scheme.onSurfaceVariant,
                              ),
                            ),
                          ),
                          Icon(
                            Icons.tune,
                            size: 16,
                            color: scheme.onSurfaceVariant,
                          ),
                        ],
                      ],
                    ),
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _SideNavItem extends StatelessWidget {
  const _SideNavItem({
    required this.icon,
    required this.selectedIcon,
    required this.label,
    required this.selected,
    required this.extended,
    required this.onTap,
  });

  final IconData icon;
  final IconData selectedIcon;
  final String label;
  final bool selected;
  final bool extended;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final content = Container(
      height: 42,
      padding: const EdgeInsets.symmetric(horizontal: 11),
      margin: const EdgeInsets.only(bottom: 4),
      decoration: BoxDecoration(
        color: selected
            ? scheme.primary.withValues(alpha: 0.13)
            : Colors.transparent,
        borderRadius: BorderRadius.circular(AppDimens.radiusControl),
      ),
      child: Row(
        children: [
          Icon(
            selected ? selectedIcon : icon,
            size: 21,
            color: selected ? scheme.primary : scheme.onSurfaceVariant,
          ),
          if (extended) ...[
            const SizedBox(width: 11),
            Expanded(
              child: Text(
                label,
                maxLines: 1,
                style: theme.textTheme.bodyMedium?.copyWith(
                  fontWeight: selected ? FontWeight.w700 : FontWeight.w500,
                  color: selected ? scheme.primary : scheme.onSurfaceVariant,
                ),
              ),
            ),
          ],
        ],
      ),
    );
    final item = InkWell(
      borderRadius: BorderRadius.circular(AppDimens.radiusControl),
      onTap: onTap,
      child: content,
    );
    return extended ? item : Tooltip(message: label, child: item);
  }
}

/// 工作台：连接状态 + 快捷入口（含后续里程碑的「规划中」占位导航）。
class WorkspaceTab extends ConsumerWidget {
  const WorkspaceTab({
    super.key,
    required this.gatewayUrl,
    required this.onGoTab,
    this.onOpenSymbol,
  });

  final String gatewayUrl;
  final ValueChanged<int> onGoTab;

  /// 传给「全部股票」页，行点击直达标的详情；为 null 时该页点击无动作。
  final void Function(String symbol, String market, String name)? onOpenSymbol;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final session = ref.watch(sessionController);
    final name = session.user?.displayName ?? '已登录用户';

    return ListView(
      padding: const EdgeInsets.only(bottom: 24),
      children: [
        PageHeader(title: '工作台', subtitle: '连接状态与功能入口'),
        ConstrainedBox(
          constraints: const BoxConstraints(
            maxWidth: AppDimens.maxContentWidth,
          ),
          child: Padding(
            padding: const EdgeInsets.symmetric(
              horizontal: AppDimens.pagePadding,
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                _ConnectionCard(
                  gatewayUrl: gatewayUrl,
                  displayName: name,
                  roles: session.roles,
                ),
                const SizedBox(height: 14),
                SectionCard(
                  title: '快捷入口',
                  subtitle: '已上线功能直达；其余按里程碑规划中',
                  padding: const EdgeInsets.all(12),
                  child: LayoutBuilder(
                    builder: (context, constraints) {
                      final w = constraints.maxWidth;
                      final columns = w < 520 ? 3 : (w < 820 ? 4 : 5);
                      return GridView.count(
                        crossAxisCount: columns,
                        shrinkWrap: true,
                        physics: const NeverScrollableScrollPhysics(),
                        mainAxisSpacing: 8,
                        crossAxisSpacing: 8,
                        childAspectRatio: 2.5,
                        children: [
                          _EntryTile(
                            icon: Icons.candlestick_chart_rounded,
                            label: '行情看板',
                            onTap: () => onGoTab(1),
                          ),
                          _EntryTile(
                            icon: Icons.list_alt_rounded,
                            label: '全部股票',
                            onTap: () => _openUniverse(context),
                          ),
                          _EntryTile(
                            icon: Icons.star_rounded,
                            label: '我的自选',
                            onTap: () => onGoTab(2),
                          ),
                          const _EntryTile(
                            icon: Icons.feed_outlined,
                            label: '财经资讯',
                            locked: true,
                          ),
                          const _EntryTile(
                            icon: Icons.psychology_outlined,
                            label: 'AI 研判',
                            locked: true,
                          ),
                          const _EntryTile(
                            icon: Icons.notifications_outlined,
                            label: '通知中心',
                            locked: true,
                          ),
                          const _EntryTile(
                            icon: Icons.insights,
                            label: '量化研究',
                            locked: true,
                          ),
                          const _EntryTile(
                            icon: Icons.swap_horiz_rounded,
                            label: '交易台',
                            locked: true,
                          ),
                        ],
                      );
                    },
                  ),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }

  void _openUniverse(BuildContext context) {
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => UniverseBrowsePage(onOpenSymbol: onOpenSymbol),
      ),
    );
  }
}

/// 连接状态卡：网关 + 账号两行信息。
class _ConnectionCard extends StatelessWidget {
  const _ConnectionCard({
    required this.gatewayUrl,
    required this.displayName,
    required this.roles,
  });

  final String gatewayUrl;
  final String displayName;
  final List<String> roles;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    return Card(
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
        child: Column(
          children: [
            ListTile(
              dense: true,
              contentPadding: EdgeInsets.zero,
              leading: StatusDot(
                color: gatewayUrl.isEmpty ? AppColors.warn : AppColors.down,
                size: 9,
              ),
              title: Text(
                '网关 ${gatewayUrl.isEmpty ? '未配置' : '已连接'}',
                style: theme.textTheme.titleSmall?.copyWith(
                  fontWeight: FontWeight.w600,
                ),
              ),
              subtitle: Text(
                gatewayUrl.isEmpty ? '点击右侧前往配置' : gatewayUrl,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: AppNum.style(theme.textTheme.bodySmall!)
                    .copyWith(color: scheme.onSurfaceVariant),
              ),
              trailing: IconButton(
                tooltip: '网关设置',
                icon: const Icon(Icons.tune, size: 20),
                onPressed: () => context.go('/gateway'),
              ),
            ),
            Divider(height: 1, color: scheme.outlineVariant),
            ListTile(
              dense: true,
              contentPadding: EdgeInsets.zero,
              leading: CircleAvatar(
                radius: 13,
                backgroundColor: scheme.primary.withValues(alpha: 0.15),
                child: Text(
                  displayName.characters.first.toUpperCase(),
                  style: theme.textTheme.labelMedium?.copyWith(
                    color: scheme.primary,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
              title: Text(
                displayName,
                style: theme.textTheme.titleSmall?.copyWith(
                  fontWeight: FontWeight.w600,
                ),
              ),
              subtitle: roles.isEmpty
                  ? null
                  : Text(
                      '角色：${roles.join('、')}',
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: scheme.onSurfaceVariant,
                      ),
                    ),
            ),
          ],
        ),
      ),
    );
  }
}

/// 快捷入口块：locked 为真表示后续里程碑功能，置灰并提示规划节点。
class _EntryTile extends StatelessWidget {
  const _EntryTile({
    required this.icon,
    required this.label,
    this.locked = false,
    this.onTap,
  });

  final IconData icon;
  final String label;
  final bool locked;
  final VoidCallback? onTap;

  static const _milestoneHint = 'M2 资讯·AI·通知 / M3 量化 / M4 交易';

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final fg = locked
        ? scheme.onSurfaceVariant.withValues(alpha: 0.55)
        : scheme.onSurface;
    return Tooltip(
      message: locked ? _milestoneHint : '',
      triggerMode: TooltipTriggerMode.tap,
      excludeFromSemantics: !locked,
      child: InkWell(
        borderRadius: BorderRadius.circular(AppDimens.radiusCard),
        onTap: locked
            ? () => ScaffoldMessenger.of(context).showSnackBar(
                SnackBar(content: Text('$label 规划中（$_milestoneHint）')),
              )
            : onTap,
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 12),
          decoration: BoxDecoration(
            color: locked
                ? scheme.surfaceContainerHighest.withValues(alpha: 0.4)
                : scheme.surfaceContainerLowest,
            borderRadius: BorderRadius.circular(AppDimens.radiusCard),
            border: Border.all(color: scheme.outlineVariant),
          ),
          child: FittedBox(
            fit: BoxFit.scaleDown,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Icon(
                      locked ? Icons.lock_outline_rounded : icon,
                      size: 19,
                      color: locked ? fg : scheme.primary,
                    ),
                    const SizedBox(width: 6),
                    if (!locked)
                      Icon(
                        Icons.arrow_forward_ios_rounded,
                        size: 12,
                        color: scheme.onSurfaceVariant,
                      ),
                  ],
                ),
                const SizedBox(height: 6),
                Row(
                  children: [
                    Text(
                      label,
                      maxLines: 1,
                      style: theme.textTheme.bodyMedium?.copyWith(
                        fontWeight: FontWeight.w600,
                        color: fg,
                      ),
                    ),
                    if (locked) ...[
                      const SizedBox(width: 5),
                      Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 5,
                          vertical: 1,
                        ),
                        decoration: BoxDecoration(
                          borderRadius: BorderRadius.circular(5),
                          color: scheme.surfaceContainerHighest,
                        ),
                        child: Text(
                          '规划中',
                          style: theme.textTheme.labelSmall?.copyWith(
                            fontSize: 9.5,
                            color: fg,
                          ),
                        ),
                      ),
                    ],
                  ],
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// 我的：个人资料卡 + 设置分组 + 退出登录。
class MineTab extends ConsumerWidget {
  const MineTab({super.key, required this.session});

  final SessionState session;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final name = session.user?.displayName ?? '已登录用户';

    return ListView(
      padding: const EdgeInsets.only(bottom: 24),
      children: [
        PageHeader(title: '我的', subtitle: '账号与客户端设置'),
        ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 720),
          child: Padding(
            padding: const EdgeInsets.symmetric(
              horizontal: AppDimens.pagePadding,
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(18),
                    child: Row(
                      children: [
                        CircleAvatar(
                          radius: 28,
                          backgroundColor: scheme.primary.withValues(
                            alpha: 0.14,
                          ),
                          child: Text(
                            name.characters.first.toUpperCase(),
                            style: theme.textTheme.titleLarge?.copyWith(
                              color: scheme.primary,
                              fontWeight: FontWeight.w800,
                            ),
                          ),
                        ),
                        const SizedBox(width: 14),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                name,
                                style: theme.textTheme.titleMedium?.copyWith(
                                  fontWeight: FontWeight.w700,
                                ),
                              ),
                              const SizedBox(height: 5),
                              Wrap(
                                spacing: 6,
                                runSpacing: 4,
                                children: [
                                  for (final r in session.roles)
                                    Container(
                                      padding: const EdgeInsets.symmetric(
                                        horizontal: 8,
                                        vertical: 2,
                                      ),
                                      decoration: BoxDecoration(
                                        color: scheme.primary.withValues(
                                          alpha: 0.1,
                                        ),
                                        borderRadius: BorderRadius.circular(6),
                                      ),
                                      child: Text(
                                        r,
                                        style: theme.textTheme.labelSmall
                                            ?.copyWith(
                                              color: scheme.primary,
                                              fontWeight: FontWeight.w600,
                                            ),
                                      ),
                                    ),
                                  if (session.roles.isEmpty)
                                    Text(
                                      '普通用户',
                                      style: theme.textTheme.bodySmall
                                          ?.copyWith(
                                            color: scheme.onSurfaceVariant,
                                          ),
                                    ),
                                ],
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 14),
                SectionCard(
                  title: '设置',
                  padding: const EdgeInsets.symmetric(
                    horizontal: 16,
                    vertical: 6,
                  ),
                  child: Column(
                    children: [
                      ListTile(
                        dense: true,
                        contentPadding: EdgeInsets.zero,
                        leading: const Icon(Icons.settings_ethernet),
                        title: const Text('网关地址'),
                        subtitle: Text('登录后可随时修改服务器地址'),
                        trailing: const Icon(Icons.chevron_right_rounded),
                        onTap: () => context.go('/gateway'),
                      ),
                      Divider(height: 1, color: scheme.outlineVariant),
                      ListTile(
                        dense: true,
                        contentPadding: EdgeInsets.zero,
                        leading: const Icon(Icons.brightness_6_outlined),
                        title: const Text('外观'),
                        subtitle: const Text('跟随系统（浅色 / 深色）'),
                      ),
                      Divider(height: 1, color: scheme.outlineVariant),
                      ListTile(
                        dense: true,
                        contentPadding: EdgeInsets.zero,
                        leading: const Icon(Icons.info_outline_rounded),
                        title: const Text('关于'),
                        subtitle: const Text('智慧金融终端 v0.1.0'),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 14),
                OutlinedButton.icon(
                  style: OutlinedButton.styleFrom(
                    foregroundColor: scheme.error,
                  ),
                  icon: const Icon(Icons.logout_rounded, size: 18),
                  label: const Text('退出登录'),
                  onPressed: () async {
                    await ref.read(sessionController.notifier).logout();
                    if (context.mounted) context.go('/login');
                  },
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}
