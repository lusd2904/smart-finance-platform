import 'dart:convert';
import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:flutter_client/core/api/api_client.dart';
import 'package:flutter_client/core/gateway/gateway_controller.dart';
import 'package:flutter_client/core/gateway/gateway_probe.dart';
import 'package:flutter_client/core/gateway/gateway_store.dart';
import 'package:flutter_client/core/theme/ruoyi_tokens.dart';
import 'package:flutter_client/features/auth/data/auth_api.dart';
import 'package:flutter_client/features/auth/logic/session_controller.dart';

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
    _gateway.text = gw.isEmpty ? 'http://127.0.0.1:12580' : gw;
    WidgetsBinding.instance.addPostFrameCallback((_) => _bootstrap());
  }

  Future<void> _bootstrap() async {
    final prefs = ref.read(sharedPreferencesProvider);
    if (prefs.getBool(_rememberKey) == true) {
      _remember = true;
      _username.text = prefs.getString(_userKey) ?? '';
      if (mounted) setState(() {});
    }
    if (ref.read(gatewayController).url.isEmpty) {
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
    return Scaffold(
      body: Stack(
        fit: StackFit.expand,
        children: [
          DecoratedBox(
            decoration: BoxDecoration(
              color: dark ? WebTokens.loginDark : const Color(0xFFE2E8F0),
              gradient: dark
                  ? const RadialGradient(
                      center: Alignment(-0.8, -0.6),
                      radius: 1.1,
                      colors: [Color(0x6B3B82F6), Color(0x00020617)],
                    )
                  : null,
            ),
          ),
          if (dark)
            const DecoratedBox(
              decoration: BoxDecoration(
                gradient: RadialGradient(
                  center: Alignment(0.85, 0.75),
                  radius: 0.9,
                  colors: [Color(0x669333EA), Color(0x00020617)],
                ),
              ),
            ),
          CustomPaint(painter: _CyberGridPainter(dark: dark)),
          SafeArea(
            child: Column(
              children: [
                Padding(
                  padding: const EdgeInsets.fromLTRB(40, 18, 40, 0),
                  child: Row(
                    children: [
                      const Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          _GlowTitle('智慧金融 · NEXUS'),
                          SizedBox(height: 2),
                          Text(
                            'QUANT · SENTIMENT · MARKET',
                            style: TextStyle(
                              fontSize: 11,
                              letterSpacing: 2,
                              color: Color(0xA6E2E8F0),
                            ),
                          ),
                        ],
                      ),
                      const Spacer(),
                      _SkinSwitch(
                        dark: dark,
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
                        padding: const EdgeInsets.all(24),
                        child: _GlassPanel(
                          dark: dark,
                          child: Row(
                            children: [
                              if (MediaQuery.sizeOf(context).width >= 760)
                                SizedBox(
                                  width: 380,
                                  child: _BrandPane(dark: dark),
                                ),
                              Expanded(
                                child: Padding(
                                  padding: const EdgeInsets.fromLTRB(36, 28, 36, 24),
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
                    ),
                  ),
                ),
                const Padding(
                  padding: EdgeInsets.only(bottom: 16),
                  child: Text(
                    'Copyright © 2024-2026 insistence.tech All Rights Reserved.',
                    style: TextStyle(fontSize: 12, color: Color(0x88E2E8F0)),
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
          decoration: deco('网关地址 http://127.0.0.1:12580', Icons.dns_outlined),
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
  const _SkinSwitch({required this.dark, required this.onSelect});
  final bool dark;
  final ValueChanged<bool> onSelect;

  @override
  Widget build(BuildContext context) {
    Widget chip(bool value, IconData icon, String label) {
      final active = dark == value;
      return InkWell(
        onTap: () => onSelect(value),
        borderRadius: BorderRadius.circular(999),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 7),
          decoration: BoxDecoration(
            color: active ? const Color(0x2E38BDF8) : Colors.transparent,
            borderRadius: BorderRadius.circular(999),
          ),
          child: Row(
            children: [
              Icon(icon, size: 16, color: Colors.white),
              const SizedBox(width: 6),
              Text(label, style: const TextStyle(color: Colors.white, fontSize: 13)),
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

class _CyberGridPainter extends CustomPainter {
  _CyberGridPainter({required this.dark});
  final bool dark;

  @override
  void paint(Canvas canvas, Size size) {
    final rnd = math.Random(7);
    final nodePaint = Paint()
      ..color = (dark ? const Color(0xFF38BDF8) : const Color(0xFF2563EB)).withValues(alpha: 0.35)
      ..strokeWidth = 1;
    final points = <Offset>[];
    for (var i = 0; i < 28; i++) {
      points.add(Offset(rnd.nextDouble() * size.width, rnd.nextDouble() * size.height));
    }
    for (var i = 0; i < points.length; i++) {
      for (var j = i + 1; j < points.length; j++) {
        final d = (points[i] - points[j]).distance;
        if (d < 180) {
          canvas.drawLine(
            points[i],
            points[j],
            nodePaint..color = nodePaint.color.withValues(alpha: (1 - d / 180) * 0.25),
          );
        }
      }
      canvas.drawCircle(points[i], 2.2, nodePaint..color = nodePaint.color.withValues(alpha: 0.7));
    }
  }

  @override
  bool shouldRepaint(covariant _CyberGridPainter oldDelegate) => oldDelegate.dark != dark;
}
