import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/gateway/gateway_config.dart';
import '../../core/gateway/gateway_controller.dart';
import '../../core/menu/menu_api.dart';
import '../../core/menu/router_models.dart';
import '../../core/theme/app_theme.dart';
import '../../core/theme/ruoyi_tokens.dart';
import '../../features/auth/logic/session_controller.dart';
import '../../features/kline/presentation/symbol_detail_page.dart';
import '../../features/market/presentation/market_tab.dart';
import '../../features/sentiment/presentation/sentiment_page.dart';
import '../../shared/widgets/ruoyi_ui.dart';
import 'page_registry.dart';
import 'phone_pages.dart';
import 'phone_picks_page.dart';
import 'phone_trade_page.dart';

/// 测试/程序化打开路由（不经过侧栏点击）。
class ShellNavRequest {
  const ShellNavRequest(this.path, {this.title});
  final String path;
  final String? title;
}

final shellNavRequestProvider = StateProvider<ShellNavRequest?>((ref) => null);

class TagTab {
  const TagTab({required this.path, required this.title, this.query = const {}});
  final String path;
  final String title;
  final Map<String, String> query;

  String get key {
    if (query.isEmpty) return path;
    final q = Uri(queryParameters: query).query;
    return q.isEmpty ? path : '$path?$q';
  }
}

/// 对齐网页 layout：左侧菜单（getRouters）+ 顶栏 + 页签 + 原生内容区。
class AdminShell extends ConsumerStatefulWidget {
  const AdminShell({super.key});

  @override
  ConsumerState<AdminShell> createState() => _AdminShellState();
}

class _AdminShellState extends ConsumerState<AdminShell> {
  bool _sidebarOpen = true;
  int _phoneTab = 0;
  bool _phoneBootstrapped = false;
  final List<TagTab> _tags = [
    const TagTab(path: '/portal', title: '工作台'),
  ];
  int _active = 0;
  final Map<String, Widget> _cache = {};
  final Map<int, Widget> _phoneRoots = {};

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_phoneBootstrapped) return;
    _phoneBootstrapped = true;
    if (!AppDimens.isWide(context)) {
      _tags
        ..clear()
        ..add(const TagTab(path: '/sentiment/dashboard', title: '舆情'));
      _phoneTab = 0;
      _active = 0;
      _cache.clear();
    }
  }

  void _openSymbol(String symbol, String market, String name) {
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => SymbolDetailPage(symbol: symbol, market: market, name: name),
      ),
    );
  }

  void _open(String raw, {String? title}) {
    final uri = Uri.parse(raw);
    final path = uri.path.isEmpty ? raw.split('?').first : uri.path;
    final query = Map<String, String>.from(uri.queryParameters);
    if (!AppDimens.isWide(context) &&
        (path == '/market/kline' || path == '/market/symbol' || path == '/market/tradingview')) {
      _openSymbol(
        query['symbol'] ?? 'AAPL',
        query['market'] ?? 'US',
        title ?? query['symbol'] ?? '',
      );
      return;
    }
    final tab = TagTab(
      path: path,
      title: title ?? defaultTitleFor(path),
      query: query,
    );
    final idx = _tags.indexWhere((t) => t.key == tab.key);
    setState(() {
      if (idx >= 0) {
        _active = idx;
      } else {
        _tags.add(tab);
        _active = _tags.length - 1;
      }
    });
  }

  void _close(int i) {
    if (_tags.length <= 1) return;
    setState(() {
      final removed = _tags.removeAt(i);
      _cache.remove(removed.key);
      if (_active >= _tags.length) _active = _tags.length - 1;
      if (_active < 0) _active = 0;
    });
  }

  Widget _pageOf(TagTab tab) {
    final allowed = visibleMenuPaths(ref.read(routersProvider).asData?.value ?? const []);
    return _cache.putIfAbsent(
      tab.key,
      () => buildNativePage(tab.path, tab.query, _open, allowed: allowed),
    );
  }

  @override
  Widget build(BuildContext context) {
    ref.listen<ShellNavRequest?>(shellNavRequestProvider, (prev, next) {
      if (next == null) return;
      _open(next.path, title: next.title);
    });

    final routers = ref.watch(routersProvider);
    final session = ref.watch(sessionController);
    final gateway = ref.watch(gatewayController);
    final dark = ref.watch(themeModeController) != ThemeMode.light;
    final current = _tags[_active];
    final wide = AppDimens.isWide(context);
    final menu = clientVisibleRouters(routers.asData?.value ?? const <RouterNode>[]);
    final stack = ColoredBox(
      color: Theme.of(context).brightness == Brightness.dark
          ? WebTokens.contentBg
          : WebTokens.contentBgLight,
      child: IndexedStack(
        index: _active,
        children: [for (final t in _tags) _pageOf(t)],
      ),
    );

    Future<void> logout() async {
      final ok = await confirm(context, '确定退出登录吗？');
      if (!ok) return;
      await ref.read(sessionController.notifier).logout();
      if (context.mounted) context.go('/login');
    }

    return CallbackShortcuts(
      bindings: {
        const SingleActivator(LogicalKeyboardKey.backslash, meta: true): () {
          if (wide) setState(() => _sidebarOpen = !_sidebarOpen);
        },
        const SingleActivator(LogicalKeyboardKey.keyR, meta: true): () {},
        const SingleActivator(LogicalKeyboardKey.keyK, meta: true): () {
          _open('/market/stocks', title: '全部股票');
        },
      },
      child: Focus(
        autofocus: true,
        child: wide
            ? _desktopScaffold(
                menu: menu,
                loading: routers.isLoading,
                current: current,
                session: session,
                gateway: gateway,
                dark: dark,
                stack: stack,
                logout: logout,
              )
            : _phoneScaffold(
                menu: menu,
                loading: routers.isLoading,
                current: current,
                dark: dark,
                stack: stack,
                logout: logout,
              ),
      ),
    );
  }

  Widget _desktopScaffold({
    required List<RouterNode> menu,
    required bool loading,
    required TagTab current,
    required SessionState session,
    required GatewayConfig gateway,
    required bool dark,
    required Widget stack,
    required Future<void> Function() logout,
  }) {
    final isMac = AppDimens.isMac(context);
    // 对齐网页：/portal 是独立全屏指挥中心，不套侧栏 + 顶栏 + 页签。
    if (current.path == '/portal') {
      return Scaffold(body: stack);
    }
    return Scaffold(
      body: SafeArea(
        top: !isMac,
        child: Row(
          children: [
            _Sidebar(
              open: _sidebarOpen,
              routers: menu,
              loading: loading,
              currentPath: current.path,
              onSelect: (path, title) => _open(path, title: title),
              onLogo: () => _open('/portal', title: '子系统门户'),
            ),
            Expanded(
              child: Column(
                children: [
                  _Navbar(
                    title: current.title,
                    nickName: session.user?.displayName ?? '',
                    gateway: gateway.url,
                    dark: dark,
                    sidebarOpen: _sidebarOpen,
                    onToggleSide: () => setState(() => _sidebarOpen = !_sidebarOpen),
                    onPortal: () => _open('/portal', title: '子系统门户'),
                    onIndex: menuAllows(visibleMenuPaths(menu), '/index')
                        ? () => _open('/index', title: '工作台首页')
                        : null,
                    onProfile: () => _open('/user/profile', title: '个人中心'),
                    onGateway: () => context.go('/gateway'),
                    onTheme: () => ref.read(themeModeController.notifier).toggle(),
                    onLogout: logout,
                  ),
                  _TagsBar(
                    tags: _tags,
                    active: _active,
                    onSelect: (i) => setState(() => _active = i),
                    onClose: _close,
                  ),
                  Expanded(child: stack),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  static const _phoneTabs = <(String path, String title, IconData icon)>[
    ('/sentiment/dashboard', '舆情', Icons.analytics_outlined),
    ('/market/recommendations', '选股', Icons.auto_awesome),
    ('/market/heat', '热度', Icons.candlestick_chart_outlined),
    ('/trade/positions', '持仓', Icons.account_balance_wallet_outlined),
    ('/user/profile', '我的', Icons.person_outline),
  ];

  bool _isPhoneRoot(String path) => _phoneTabs.any((t) => t.$1 == path);

  Widget _phoneRootAt(int index) {
    return _phoneRoots.putIfAbsent(index, () {
      switch (index) {
        case 0:
          return const SentimentPage();
        case 1:
          return PhonePicksPage(onOpenSymbol: _openSymbol);
        case 2:
          return MarketTab(onOpenSymbol: _openSymbol);
        case 3:
          return PhoneTradePage(onOpenSymbol: _openSymbol);
        default:
          return PhoneMinePage(open: _open, onOpenSymbol: _openSymbol);
      }
    });
  }

  Widget _phoneScaffold({
    required List<RouterNode> menu,
    required bool loading,
    required TagTab current,
    required bool dark,
    required Widget stack,
    required Future<void> Function() logout,
  }) {
    final root = _isPhoneRoot(current.path);
    return Scaffold(
      appBar: root
          ? null
          : AppBar(
              leading: IconButton(
                tooltip: '返回',
                icon: const Icon(Icons.arrow_back_ios_new, size: 18),
                onPressed: () {
                  if (_tags.length > 1) _close(_active);
                },
              ),
              title: Text(
                current.title,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
            ),
      body: SafeArea(
        bottom: false,
        child: root
            ? IndexedStack(
                index: _phoneTab.clamp(0, _phoneTabs.length - 1),
                children: [
                  for (var i = 0; i < _phoneTabs.length; i++)
                    _phoneTab == i || _phoneRoots.containsKey(i)
                        ? _phoneRootAt(i)
                        : const SizedBox.shrink(),
                ],
              )
            : stack,
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _phoneTab.clamp(0, _phoneTabs.length - 1),
        onDestinationSelected: (i) {
          final tab = _phoneTabs[i];
          setState(() {
            _phoneTab = i;
            _tags
              ..clear()
              ..add(TagTab(path: tab.$1, title: tab.$2));
            _active = 0;
          });
        },
        destinations: [
          for (final t in _phoneTabs)
            NavigationDestination(icon: Icon(t.$3), label: t.$2),
        ],
      ),
    );
  }
}

class _Sidebar extends StatelessWidget {
  const _Sidebar({
    required this.open,
    required this.routers,
    required this.loading,
    required this.currentPath,
    required this.onSelect,
    required this.onLogo,
    this.fill = false,
  });

  final bool open;
  final bool fill;
  final List<RouterNode> routers;
  final bool loading;
  final String currentPath;
  final void Function(String path, String title) onSelect;
  final VoidCallback onLogo;

  @override
  Widget build(BuildContext context) {
    return AnimatedContainer(
      duration: const Duration(milliseconds: 180),
      width: fill ? double.infinity : (open ? WebTokens.sidebarWidth : WebTokens.sidebarCollapsed),
      color: WebTokens.sidebarBg,
      child: Material(
        color: Colors.transparent,
        child: Column(
        children: [
          InkWell(
            onTap: onLogo,
            child: SizedBox(
              height: AppDimens.isMac(context) ? 52 : WebTokens.navbarHeight,
              child: Padding(
                padding: EdgeInsets.only(left: AppDimens.isMac(context) && open ? 72 : 0),
                child: Center(
                  child: Text(
                    open ? '智慧金融分析平台' : (AppDimens.isMac(context) ? '' : '智'),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      color: Colors.white,
                      fontWeight: FontWeight.w700,
                      fontSize: 14,
                    ),
                  ),
                ),
              ),
            ),
          ),
          Expanded(
            child: loading
                ? const Center(
                    child: SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                    ),
                  )
                : ListView(
                    padding: const EdgeInsets.symmetric(vertical: 6),
                    children: [
                      _leaf(
                        icon: Icons.grid_view_outlined,
                        title: '工作台',
                        path: '/portal',
                        selected: currentPath == '/portal',
                      ),
                      if (menuAllows(visibleMenuPaths(routers), '/index'))
                        _leaf(
                          icon: Icons.dashboard_outlined,
                          title: '工作台首页',
                          path: '/index',
                          selected: currentPath == '/index',
                        ),
                      for (final node in routers.where((n) => !n.hidden))
                        _Node(
                          node: node,
                          parent: '',
                          open: open,
                          currentPath: currentPath,
                          onSelect: onSelect,
                        ),
                    ],
                  ),
          ),
        ],
      ),
      ),
    );
  }

  Widget _leaf({
    required IconData icon,
    required String title,
    required String path,
    required bool selected,
  }) {
    return InkWell(
      onTap: () => onSelect(path, title),
      child: Container(
        height: 42,
        padding: EdgeInsets.symmetric(horizontal: open ? 16 : 0),
        color: selected ? WebTokens.sidebarHover : Colors.transparent,
        child: Row(
          mainAxisAlignment: open ? MainAxisAlignment.start : MainAxisAlignment.center,
          children: [
            Icon(icon, size: 16, color: selected ? WebTokens.sidebarActive : WebTokens.sidebarText),
            if (open) ...[
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  title,
                  style: TextStyle(
                    color: selected ? WebTokens.sidebarActive : WebTokens.sidebarText,
                    fontSize: 14,
                  ),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _Node extends StatelessWidget {
  const _Node({
    required this.node,
    required this.parent,
    required this.open,
    required this.currentPath,
    required this.onSelect,
  });

  final RouterNode node;
  final String parent;
  final bool open;
  final String currentPath;
  final void Function(String path, String title) onSelect;

  @override
  Widget build(BuildContext context) {
    final full = joinRoute(parent, node.path);
    final visibleChildren = node.children.where((c) => !c.hidden).toList();
    if (visibleChildren.isEmpty) {
      final selected = currentPath == full;
      return InkWell(
        onTap: () => onSelect(full, node.title),
        child: Container(
          height: 42,
          padding: EdgeInsets.only(left: open ? 16 : 0),
          color: selected ? WebTokens.sidebarHover : Colors.transparent,
          child: Row(
            mainAxisAlignment: open ? MainAxisAlignment.start : MainAxisAlignment.center,
            children: [
              Icon(
                ruoyiIcon(node.meta.icon),
                size: 16,
                color: selected ? WebTokens.sidebarActive : WebTokens.sidebarText,
              ),
              if (open) ...[
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    node.title,
                    style: TextStyle(
                      color: selected ? WebTokens.sidebarActive : WebTokens.sidebarText,
                      fontSize: 14,
                    ),
                  ),
                ),
              ],
            ],
          ),
        ),
      );
    }
    final childSelected = visibleChildren.any((c) {
      final p = joinRoute(full, c.path);
      return currentPath == p || currentPath.startsWith('$p/');
    });
    return Material(
      color: Colors.transparent,
      child: Theme(
      data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
      child: ExpansionTile(
        initiallyExpanded: childSelected,
        leading: Icon(ruoyiIcon(node.meta.icon), size: 16, color: WebTokens.sidebarText),
        title: open
            ? Text(node.title, style: const TextStyle(color: WebTokens.sidebarText, fontSize: 14))
            : const SizedBox.shrink(),
        iconColor: WebTokens.sidebarText,
        collapsedIconColor: WebTokens.sidebarText,
        tilePadding: EdgeInsets.symmetric(horizontal: open ? 8 : 0),
        childrenPadding: EdgeInsets.only(left: open ? 12 : 0),
        backgroundColor: WebTokens.sidebarSub,
        collapsedBackgroundColor: Colors.transparent,
        children: [
          for (final c in visibleChildren)
            _Node(
              node: c,
              parent: full,
              open: open,
              currentPath: currentPath,
              onSelect: onSelect,
            ),
        ],
      ),
      ),
    );
  }
}

class _Navbar extends StatelessWidget {
  const _Navbar({
    required this.title,
    required this.nickName,
    required this.gateway,
    required this.dark,
    required this.sidebarOpen,
    required this.onToggleSide,
    required this.onPortal,
    required this.onIndex,
    required this.onProfile,
    required this.onGateway,
    required this.onTheme,
    required this.onLogout,
  });

  final String title;
  final String nickName;
  final String gateway;
  final bool dark;
  final bool sidebarOpen;
  final VoidCallback onToggleSide;
  final VoidCallback onPortal;
  final VoidCallback? onIndex;
  final VoidCallback onProfile;
  final VoidCallback onGateway;
  final VoidCallback onTheme;
  final VoidCallback onLogout;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: AppDimens.isMac(context) ? 52 : WebTokens.navbarHeight,
      padding: const EdgeInsets.symmetric(horizontal: 8),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surfaceContainerLowest,
        border: Border(
          bottom: BorderSide(color: Theme.of(context).colorScheme.outlineVariant),
        ),
      ),
      child: Row(
        children: [
          IconButton(
            tooltip: '折叠菜单',
            onPressed: onToggleSide,
            icon: Icon(sidebarOpen ? Icons.menu_open : Icons.menu),
          ),
          Expanded(
            child: Text(
              title,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(fontWeight: FontWeight.w600),
            ),
          ),
          IconButton(tooltip: '子系统门户', onPressed: onPortal, icon: const Icon(Icons.grid_view_outlined)),
          if (onIndex != null)
            IconButton(tooltip: '工作台首页', onPressed: onIndex, icon: const Icon(Icons.home_outlined)),
          IconButton(
            tooltip: dark ? '浅色' : '深色',
            onPressed: onTheme,
            icon: Icon(dark ? Icons.wb_sunny_outlined : Icons.dark_mode_outlined),
          ),
          IconButton(tooltip: '网关', onPressed: onGateway, icon: const Icon(Icons.dns_outlined)),
          PopupMenuButton<String>(
            tooltip: nickName,
            onSelected: (v) {
              if (v == 'profile') onProfile();
              if (v == 'logout') onLogout();
            },
            itemBuilder: (_) => const [
              PopupMenuItem(value: 'profile', child: Text('个人中心')),
              PopupMenuItem(value: 'logout', child: Text('退出登录')),
            ],
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 8),
              child: Row(
                children: [
                  CircleAvatar(
                    radius: 12,
                    backgroundColor: WebTokens.primary,
                    child: Text(
                      nickName.isEmpty ? 'U' : nickName.characters.first,
                      style: const TextStyle(color: Colors.white, fontSize: 12),
                    ),
                  ),
                  const SizedBox(width: 6),
                  ConstrainedBox(
                    constraints: const BoxConstraints(maxWidth: 96),
                    child: Text(
                      nickName,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                  const Icon(Icons.expand_more, size: 16),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _TagsBar extends StatelessWidget {
  const _TagsBar({
    required this.tags,
    required this.active,
    required this.onSelect,
    required this.onClose,
  });

  final List<TagTab> tags;
  final int active;
  final ValueChanged<int> onSelect;
  final ValueChanged<int> onClose;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      height: WebTokens.tagsHeight,
      color: scheme.surfaceContainerLow,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 8),
        itemCount: tags.length,
        separatorBuilder: (_, _) => const SizedBox(width: 4),
        itemBuilder: (context, i) {
          final selected = i == active;
          return InkWell(
            onTap: () => onSelect(i),
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 10),
              alignment: Alignment.center,
              decoration: BoxDecoration(
                color: selected ? scheme.surfaceContainerLowest : Colors.transparent,
                border: Border(
                  bottom: BorderSide(
                    color: selected ? WebTokens.primary : Colors.transparent,
                    width: 2,
                  ),
                ),
              ),
              child: Row(
                children: [
                  Text(tags[i].title, style: TextStyle(fontSize: 12, color: selected ? WebTokens.primary : null)),
                  if (tags.length > 1) ...[
                    const SizedBox(width: 4),
                    GestureDetector(
                      onTap: () => onClose(i),
                      child: const Icon(Icons.close, size: 12),
                    ),
                  ],
                ],
              ),
            ),
          );
        },
      ),
    );
  }
}
