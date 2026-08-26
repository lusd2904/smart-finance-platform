import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:webview_flutter/webview_flutter.dart';

import '../../core/gateway/gateway_controller.dart';
import '../../core/storage/token_store.dart';
import '../../core/theme/app_theme.dart';
import '../auth/logic/session_controller.dart';

/// macOS / 宽屏桌面：登录后直接打开网关里的 Web 控制台。
/// 页面、路由、样式与 Docker Web 是同一份前端，不再走 Flutter 精简页。
class DesktopWebShell extends ConsumerStatefulWidget {
  const DesktopWebShell({super.key});

  @override
  ConsumerState<DesktopWebShell> createState() => _DesktopWebShellState();
}

class _DesktopWebShellState extends ConsumerState<DesktopWebShell> {
  WebViewController? _controller;
  String? _error;
  bool _ready = false;

  @override
  void initState() {
    super.initState();
    Future<void>.microtask(_boot);
  }

  Future<void> _boot() async {
    final gateway = ref.read(gatewayController).url.trim();
    final token = await ref.read(tokenStoreProvider).read();
    if (!mounted) return;
    if (gateway.isEmpty) {
      setState(() => _error = '未配置网关');
      return;
    }
    if (token == null || token.isEmpty) {
      setState(() => _error = '未登录');
      return;
    }
    final base = gateway.replaceAll(RegExp(r'/$'), '');
    final uri = Uri.tryParse(base);
    if (uri == null || uri.host.isEmpty) {
      setState(() => _error = '网关地址无效');
      return;
    }
    try {
      final cookies = WebViewCookieManager();
      await cookies.clearCookies();
      await cookies.setCookie(
        WebViewCookie(
          name: 'Admin-Token',
          value: token,
          domain: uri.host,
          path: '/',
        ),
      );
      if (!mounted) return;
      final controller = WebViewController()
        ..setJavaScriptMode(JavaScriptMode.unrestricted)
        ..setNavigationDelegate(
          NavigationDelegate(
            onPageFinished: (url) {
              _controller?.runJavaScript(
                "document.cookie='Admin-Token=$token; path=/';",
              );
            },
            onWebResourceError: (err) {
              if (!mounted) return;
              if (!_ready) setState(() => _error = err.description);
            },
          ),
        )
        ..loadRequest(Uri.parse('$base/portal'));
      if (!mounted) return;
      setState(() {
        _controller = controller;
        _ready = true;
        _error = null;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() => _error = '$e');
    }
  }

  @override
  Widget build(BuildContext context) {
    final mac = AppDimens.isMac(context);
    final dark = Theme.of(context).brightness == Brightness.dark;
    final bar = dark ? const Color(0xFF020617) : const Color(0xFFE2E8F0);
    return Scaffold(
      backgroundColor: bar,
      body: Column(
        children: [
          if (mac)
            Container(
              height: AppDimens.macTitlebarHeight,
              color: bar,
              alignment: Alignment.centerRight,
              padding: const EdgeInsets.only(right: 10),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  IconButton(
                    tooltip: '网关',
                    visualDensity: VisualDensity.compact,
                    onPressed: () => context.go('/gateway'),
                    icon: const Icon(Icons.dns_outlined, size: 16),
                  ),
                  IconButton(
                    tooltip: '退出登录',
                    visualDensity: VisualDensity.compact,
                    onPressed: () async {
                      await ref.read(sessionController.notifier).logout();
                      if (context.mounted) context.go('/login');
                    },
                    icon: const Icon(Icons.logout, size: 16),
                  ),
                ],
              ),
            ),
          Expanded(child: _body(context)),
        ],
      ),
    );
  }

  Widget _body(BuildContext context) {
    if (_error != null && _controller == null) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
            const SizedBox(height: 12),
            FilledButton(
              onPressed: () {
                setState(() => _error = null);
                _boot();
              },
              child: const Text('重试'),
            ),
            TextButton(
              onPressed: () => context.go('/login'),
              child: const Text('返回登录'),
            ),
          ],
        ),
      );
    }
    final controller = _controller;
    if (controller == null) {
      return const Center(child: CircularProgressIndicator());
    }
    return WebViewWidget(controller: controller);
  }
}
