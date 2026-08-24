import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart' show kDebugMode;

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'core/gateway/gateway_controller.dart';
import 'core/dev/design_gallery.dart';
import 'core/theme/app_theme.dart';
import 'features/auth/logic/session_controller.dart';
import 'features/auth/presentation/login_page.dart';

import 'features/auth/presentation/register_page.dart';
import 'features/gateway/presentation/gateway_page.dart';
import 'features/home/home_shell.dart';

/// 调试/集成测试用：--dart-define=SFF_ROUTE=/gallery 直跳指定路由；发布构建固定 '/'。
const appInitialRoute = String.fromEnvironment('SFF_ROUTE', defaultValue: '/');

/// 路由守卫语义：
/// 1. 网关未配置 → 强制 /gateway（复刻 desktop「先配网关再登录」）。
/// 2. 未登录 → 除 /gateway、/login、/register 外全部回 /login。
/// 3. 已登录访问登录/注册页 → 回 /home；/gateway 任何状态都可达（对应桌面端菜单随时可改地址）。
final routerProvider = Provider<GoRouter>((ref) {
  final gateway = ref.watch(gatewayController);
  final session = ref.watch(sessionController);

  bool protected_(String loc) =>
      !((kDebugMode && loc == '/gallery')) &&
      loc != '/gateway' &&
      loc != '/login' &&
      loc != '/register';

  return GoRouter(
    initialLocation: kDebugMode ? appInitialRoute : '/',
    redirect: (context, state) {
      final loc = state.matchedLocation;
      if (gateway.url.isEmpty && loc != '/gateway') return '/gateway';
      if (gateway.url.isEmpty) return null;
      if (session.isAnonymous && protected_(loc)) return '/login';
      if (session.isAuthenticated && (loc == '/login' || loc == '/register')) {
        return '/home';
      }
      if (loc == '/') return session.isAuthenticated ? '/home' : '/login';
      return null;
    },
    routes: [
      GoRoute(path: '/', redirect: (_, _) => null),
      GoRoute(path: '/gateway', builder: (_, _) => const GatewayPage()),
      GoRoute(path: '/login', builder: (_, _) => const LoginPage()),
      GoRoute(path: '/register', builder: (_, _) => const RegisterPage()),
      GoRoute(path: '/home', builder: (_, _) => const HomeShell()),
      if (kDebugMode)
        GoRoute(path: '/gallery', builder: (_, _) => const DesignGalleryPage()),
    ],
  );
});

class SffApp extends ConsumerWidget {
  const SffApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final router = ref.watch(routerProvider);
    return MaterialApp.router(
      title: '智慧金融',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light(),
      darkTheme: AppTheme.dark(),
      themeMode: ThemeMode.system,
      routerConfig: router,
    );
  }
}
