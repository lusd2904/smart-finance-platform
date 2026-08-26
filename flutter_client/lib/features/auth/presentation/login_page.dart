import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:flutter_client/core/api/api_client.dart';
import 'package:flutter_client/core/gateway/gateway_config.dart';
import 'package:flutter_client/core/gateway/gateway_controller.dart';
import 'package:flutter_client/core/gateway/gateway_probe.dart';
import 'package:flutter_client/core/gateway/gateway_store.dart';
import 'package:flutter_client/core/theme/app_theme.dart';
import 'package:flutter_client/core/theme/ruoyi_tokens.dart';
import 'package:flutter_client/features/auth/data/auth_api.dart';
import 'package:flutter_client/features/auth/logic/session_controller.dart';
import 'package:flutter_client/shared/widgets/cyber_background.dart';

/// 对齐网页 login.vue：赛博背景 + 玻璃面板 + 网关地址（客户端多出来的一项）。
class LoginPage extends ConsumerStatefulWidget {
  const LoginPage({super.key});

  @override
  ConsumerState<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends ConsumerState<LoginPage> {
  final _username = TextEditingController();
  final _password = TextEditingController();
  final _code = TextEditingController();
  final _gateway = TextEditingController();
  bool _remember = false;
  bool _obscure = true;
  bool _submitting = false;
  bool _loadingCaptcha = false;
  CaptchaData? _captcha;
  String? _error;

  static const _userKey = 'login.username';
  static const _rememberKey = 'login.remember';

  bool get _dark => ref.watch(themeModeController) != ThemeMode.light;

  @override
  void initState() {
    super.initState();
    final gw = ref.read(gatewayController).url;
    _gateway.text = resolveStoredGateway(gw);
    WidgetsBinding.instance.addPostFrameCallback((_) => _bootstrap());
  }

  Future<void> _bootstrap() async {
    final prefs = ref.read(sharedPreferencesProvider);
    if (prefs.getBool(_rememberKey) == true) {
      _remember = true;
      _username.text = prefs.getString(_userKey) ?? '';
      if (mounted) setState(() {});
    }
    final stored = ref.read(gatewayController).url;
    final resolved = resolveStoredGateway(stored);
    if (stored != resolved) {
      try {
        await ref.read(gatewayController.notifier).applyUrl(_ensureScheme(resolved));
        if (mounted) _gateway.text = resolved;
      } catch (_) {}
    } else if (stored.isEmpty) {
      try {
        await ref.read(gatewayController.notifier).applyUrl(_ensureScheme(_gateway.text));
      } catch (_) {}
    }
    await _refreshCaptcha();
  }

  String _ensureScheme(String raw) {
    final t = raw.trim();
    if (t.isEmpty) return t;
    if (t.startsWith('http://') || t.startsWith('https://')) return t;
    if (RegExp(r'^(127\.|10\.|192\.168\.|localhost)').hasMatch(t)) {
      return 'http://$t';
    }
    return 'https://$t';
  }

  @override
  void dispose() {
    _username.dispose();
    _password.dispose();
    _code.dispose();
    _gateway.dispose();
    super.dispose();
  }

  Future<void> _refreshCaptcha() async {
    setState(() => _loadingCaptcha = true);
    try {
      final captcha = await ref.read(authApiProvider).captchaImage();
      if (!mounted) return;
      setState(() {
        _captcha = captcha;
        _loadingCaptcha = false;
        _code.clear();
        _error = null;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _loadingCaptcha = false;
        _error = describeApiError(e);
      });
    }
  }

  ImageProvider? get _captchaImage {
    final img = _captcha?.img ?? '';
    if (img.isEmpty) return null;
    final body = img.contains(',') ? img.split(',').last : img;
    try {
      return MemoryImage(base64Decode(body));
    } catch (_) {
      return null;
    }
  }

  Future<void> _submit() async {
    final username = _username.text.trim();
    final password = _password.text;
    if (username.isEmpty || password.isEmpty) {
      setState(() => _error = '请输入您的账号和密码');
      return;
    }
    final captcha = _captcha;
    if (captcha != null && captcha.captchaEnabled && _code.text.trim().isEmpty) {
      setState(() => _error = '请输入验证码');
      return;
    }
    setState(() {
      _submitting = true;
      _error = null;
    });
    try {
      final gw = _ensureScheme(_gateway.text);
      if (gw.isNotEmpty) {
        await ref.read(gatewayController.notifier).applyUrl(gw);
      }
    } on GatewayFormatException catch (e) {
      if (!mounted) return;
      setState(() {
        _submitting = false;
        _error = e.message;
      });
      return;
    }
    final prefs = ref.read(sharedPreferencesProvider);
    if (_remember) {
      await prefs.setBool(_rememberKey, true);
      await prefs.setString(_userKey, username);
    } else {
      await prefs.remove(_rememberKey);
      await prefs.remove(_userKey);
    }
    final error = await ref.read(sessionController.notifier).login(
          username: username,
          password: password,
          captcha: captcha ??
              const CaptchaData(
                captchaEnabled: false,
                registerEnabled: false,
                img: '',
                uuid: '',
              ),
          code: _code.text.trim(),
        );
    if (!mounted) return;
    setState(() => _submitting = false);
    if (error != null) {
      setState(() => _error = error);
      await _refreshCaptcha();
      return;
    }
    if (mounted) context.go('/home');
  }

  @override
  Widget build(BuildContext context) {
    final dark = _dark;
    final registerEnabled = _captcha?.registerEnabled ?? false;
    final captchaOn = _captcha == null || _captcha!.captchaEnabled;
    final narrow = MediaQuery.sizeOf(context).width < 760;
    final mac = AppDimens.isMac(context);
    return Scaffold(
      body: Stack(
        fit: StackFit.expand,
        children: [
          ColoredBox(color: dark ? WebTokens.loginDark : const Color(0xFFE2E8F0)),
          CyberBackground(dark: dark),
          SafeArea(
            child: Column(
              children: [
                Padding(
                  padding: EdgeInsets.fromLTRB(
                    mac ? AppDimens.macTrafficLeft : (narrow ? 16 : 40),
                    mac ? 6 : 18,
                    narrow ? 16 : 40,
                    0,
                  ),
                  child: Row(
                    children: [
                      const Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            FittedBox(
                              fit: BoxFit.scaleDown,
                              alignment: Alignment.centerLeft,
                              child: _GlowTitle('智慧金融 · NEXUS'),
                            ),
                            SizedBox(height: 2),
                            FittedBox(
                              fit: BoxFit.scaleDown,
                              alignment: Alignment.centerLeft,
                              child: Text(
                                'QUANT · SENTIMENT · MARKET',
                                style: TextStyle(
                                  fontSize: 11,
                                  letterSpacing: 2,
                                  color: Color(0xA6E2E8F0),
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(width: 8),
                      _SkinSwitch(
                        dark: dark,
                        compact: narrow,
                        onSelect: (v) => ref.read(themeModeController.notifier).setDark(v),
                      ),
                    ],
                  ),
                ),
                Expanded(
                  child: Center(
                    child: ConstrainedBox(
                      constraints: const BoxConstraints(maxWidth: 920, maxHeight: 560),
                      child: Padding(
                        padding: EdgeInsets.all(narrow ? 12 : 24),
                        child: _GlassPanel(
                          dark: dark,
                          child: LayoutBuilder(
                            builder: (context, box) {
                              return SingleChildScrollView(
                                child: ConstrainedBox(
                                  constraints: BoxConstraints(minHeight: box.maxHeight),
                                  child: IntrinsicHeight(
                                    child: Row(
                                      children: [
                                        if (!narrow)
                                          SizedBox(
                                            width: 380,
                                            child: _BrandPane(dark: dark),
                                          ),
                                        Expanded(
                                          child: Padding(
                                            padding: EdgeInsets.fromLTRB(
                                              narrow ? 20 : 36,
                                              28,
                                              narrow ? 20 : 36,
                                              24,
                                            ),
                                            child: _form(
                                              captchaOn: captchaOn,
                                              registerEnabled: registerEnabled,
                                              dark: dark,
                                            ),
                                          ),
                                        ),
                                      ],
                                    ),
                                  ),
                                ),
                              );
                            },
                          ),
                        ),
                      ),
                    ),
                  ),
                ),
                Padding(
                  padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
                  child: FittedBox(
                    fit: BoxFit.scaleDown,
                    child: Text(
                      'Copyright © 2024-2026 insistence.tech All Rights Reserved.',
                      style: const TextStyle(fontSize: 12, color: Color(0x88E2E8F0)),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _form({
    required bool captchaOn,
    required bool registerEnabled,
    required bool dark,
  }) {
    final fill = dark ? const Color(0x33020617) : Colors.white;
    InputDecoration deco(String hint, IconData icon) => InputDecoration(
          hintText: hint,
          filled: true,
          fillColor: fill,
          prefixIcon: Icon(icon, size: 18),
          border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
        );
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(
          '智慧金融分析平台',
          style: TextStyle(
            fontSize: 22,
            fontWeight: FontWeight.w700,
            color: dark ? Colors.white : const Color(0xFF0F172A),
          ),
        ),
        const SizedBox(height: 6),
        Text(
          '欢迎登录，请输入您的账号信息',
          style: TextStyle(
            fontSize: 13,
            color: dark ? const Color(0xB3E2E8F0) : const Color(0xFF64748B),
          ),
        ),
        const SizedBox(height: 18),
        TextField(
          key: const Key('login-gateway'),
          controller: _gateway,
          decoration: deco('网关地址 ${suggestedLocalGateway()}', Icons.dns_outlined),
        ),
        const SizedBox(height: 12),
        TextField(
          key: const Key('login-username'),
          controller: _username,
          decoration: deco('账号', Icons.person_outline),
          autofillHints: const [AutofillHints.username],
        ),
        const SizedBox(height: 12),
        TextField(
          key: const Key('login-password'),
          controller: _password,
          obscureText: _obscure,
          decoration: deco('密码', Icons.lock_outline).copyWith(
            suffixIcon: IconButton(
              icon: Icon(_obscure ? Icons.visibility_outlined : Icons.visibility_off_outlined),
              onPressed: () => setState(() => _obscure = !_obscure),
            ),
          ),
          autofillHints: const [AutofillHints.password],
          onSubmitted: (_) => _submit(),
        ),
        if (captchaOn) ...[
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _code,
                  decoration: deco('验证码', Icons.verified_outlined),
                  onSubmitted: (_) => _submit(),
                ),
              ),
              const SizedBox(width: 10),
              GestureDetector(
                onTap: _refreshCaptcha,
                child: Container(
                  width: 118,
                  height: 42,
                  alignment: Alignment.center,
                  decoration: BoxDecoration(
                    color: fill,
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: const Color(0x33475569)),
                  ),
                  child: _loadingCaptcha
                      ? const SizedBox(
                          width: 16,
                          height: 16,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : (_captchaImage != null
                          ? Image(image: _captchaImage!, fit: BoxFit.fill)
                          : const Text('点击刷新', style: TextStyle(fontSize: 12))),
                ),
              ),
            ],
          ),
        ],
        const SizedBox(height: 8),
        Row(
          children: [
            Checkbox(
              value: _remember,
              onChanged: (v) => setState(() => _remember = v ?? false),
            ),
            const Text('记住密码'),
            const Spacer(),
            TextButton(
              onPressed: () => context.go('/gateway'),
              child: const Text('探测网关'),
            ),
          ],
        ),
        if (_error != null)
          Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: Text(_error!, style: const TextStyle(color: Color(0xFFF87171), fontSize: 13)),
          ),
        SizedBox(
          height: 44,
          child: FilledButton(
            key: const Key('login-submit'),
            style: FilledButton.styleFrom(
              backgroundColor: WebTokens.primary,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
            ),
            onPressed: _submitting ? null : _submit,
            child: Text(_submitting ? '登 录 中...' : '登 录'),
          ),
        ),
        if (registerEnabled)
          Align(
            alignment: Alignment.centerRight,
            child: TextButton(
              onPressed: () => context.go('/register'),
              child: const Text('立即注册'),
            ),
          ),
      ],
    );
  }
}

class _GlowTitle extends StatelessWidget {
  const _GlowTitle(this.text);
  final String text;

  @override
  Widget build(BuildContext context) {
    return ShaderMask(
      shaderCallback: (rect) => const LinearGradient(
        colors: [Color(0xFF38BDF8), Color(0xFFA78BFA), Color(0xFF34D399)],
      ).createShader(rect),
      child: Text(
        text,
        style: const TextStyle(
          fontSize: 22,
          fontWeight: FontWeight.w800,
          letterSpacing: 2,
          color: Colors.white,
        ),
      ),
    );
  }
}

class _SkinSwitch extends StatelessWidget {
  const _SkinSwitch({
    required this.dark,
    required this.onSelect,
    this.compact = false,
  });
  final bool dark;
  final bool compact;
  final ValueChanged<bool> onSelect;

  @override
  Widget build(BuildContext context) {
    Widget chip(bool value, IconData icon, String label) {
      final active = dark == value;
      return InkWell(
        onTap: () => onSelect(value),
        borderRadius: BorderRadius.circular(999),
        child: Container(
          padding: EdgeInsets.symmetric(
            horizontal: compact ? 8 : 14,
            vertical: 7,
          ),
          decoration: BoxDecoration(
            color: active ? const Color(0x2E38BDF8) : Colors.transparent,
            borderRadius: BorderRadius.circular(999),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(icon, size: 16, color: Colors.white),
              if (!compact) ...[
                const SizedBox(width: 6),
                Text(label, style: const TextStyle(color: Colors.white, fontSize: 13)),
              ],
            ],
          ),
        ),
      );
    }

    return Container(
      padding: const EdgeInsets.all(4),
      decoration: BoxDecoration(
        color: const Color(0x8C0F172A),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: const Color(0x1FFFFFFF)),
      ),
      child: Row(
        children: [
          chip(false, Icons.wb_sunny_outlined, '浅色'),
          chip(true, Icons.dark_mode_outlined, '深色'),
        ],
      ),
    );
  }
}

class _GlassPanel extends StatelessWidget {
  const _GlassPanel({required this.dark, required this.child});
  final bool dark;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(18),
      child: DecoratedBox(
        decoration: BoxDecoration(
          color: dark ? const Color(0x8C0F172A) : const Color(0xADFFFFFF),
          border: Border.all(
            color: dark ? const Color(0x1FFFFFFF) : const Color(0x14000000),
          ),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: dark ? 0.28 : 0.08),
              blurRadius: 32,
            ),
          ],
        ),
        child: child,
      ),
    );
  }
}

class _BrandPane extends StatelessWidget {
  const _BrandPane({required this.dark});
  final bool dark;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: const BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [Color(0x1F38BDF8), Color(0x2E6366F1)],
        ),
        border: Border(right: BorderSide(color: Color(0x1AFFFFFF))),
      ),
      child: Padding(
        padding: const EdgeInsets.fromLTRB(40, 48, 40, 40),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              width: 56,
              height: 56,
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(16),
                gradient: const LinearGradient(
                  colors: [Color(0xFF00C3FF), Color(0xFF6366F1)],
                ),
                boxShadow: const [
                  BoxShadow(color: Color(0x5900C3FF), blurRadius: 22, offset: Offset(0, 6)),
                ],
              ),
              child: const Icon(Icons.candlestick_chart, color: Colors.white, size: 28),
            ),
            const SizedBox(height: 26),
            Text(
              '智慧金融分析平台',
              style: TextStyle(
                fontSize: 24,
                fontWeight: FontWeight.w700,
                letterSpacing: 2,
                color: dark ? Colors.white : const Color(0xFF0F172A),
              ),
            ),
            const SizedBox(height: 10),
            Text(
              '全市场行情 · 舆情共振 · 智能量化 · 纸面交易',
              style: TextStyle(
                fontSize: 14,
                color: dark ? const Color(0xB3E2E8F0) : const Color(0xFF475569),
              ),
            ),
          ],
        ),
      ),
    );
  }
}


