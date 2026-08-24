import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:flutter_client/core/api/api_client.dart';
import 'package:flutter_client/core/theme/app_theme.dart';
import 'package:flutter_client/shared/widgets/auth_scaffold.dart';
import 'package:flutter_client/features/auth/data/auth_api.dart';
import 'package:flutter_client/features/auth/logic/session_controller.dart';

/// 登录页：验证码图可点击刷新；验证码关闭时自动隐藏输入框。
class LoginPage extends ConsumerStatefulWidget {
  const LoginPage({super.key});

  @override
  ConsumerState<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends ConsumerState<LoginPage> {
  final _username = TextEditingController();
  final _password = TextEditingController();
  final _code = TextEditingController();

  CaptchaData? _captcha;
  bool _loadingCaptcha = false;
  bool _submitting = false;
  bool _obscure = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _refreshCaptcha();
  }

  @override
  void dispose() {
    _username.dispose();
    _password.dispose();
    _code.dispose();
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
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _loadingCaptcha = false;
        _error = describeApiError(e);
      });
    }
  }

  Future<void> _submit() async {
    final username = _username.text.trim();
    final password = _password.text;
    if (username.isEmpty || password.isEmpty) {
      setState(() => _error = '请输入用户名和密码');
      return;
    }
    final captcha = _captcha;
    if (captcha != null &&
        captcha.captchaEnabled &&
        _code.text.trim().isEmpty) {
      setState(() => _error = '请输入验证码');
      return;
    }
    setState(() {
      _submitting = true;
      _error = null;
    });
    final error = await ref
        .read(sessionController.notifier)
        .login(
          username: username,
          password: password,
          captcha:
              captcha ??
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

  ImageProvider? get _captchaImage {
    final img = _captcha?.img ?? '';
    if (img.isEmpty) return null;
    final base64Body = img.contains(',') ? img.split(',').last : img;
    try {
      return MemoryImage(base64Decode(base64Body));
    } catch (_) {
      return null;
    }
  }

  @override
  Widget build(BuildContext context) {
    final captcha = _captcha;
    final registerEnabled = captcha?.registerEnabled ?? false;
    return AuthScaffold(
      title: '欢迎回来',
      subtitle: '登录以继续访问你的投研工作台',
      headerActions: [
        IconButton(
          tooltip: '网关设置',
          icon: const Icon(Icons.settings_ethernet),
          onPressed: () => context.go('/gateway'),
        ),
      ],
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          TextField(
            controller: _username,
            decoration: const InputDecoration(labelText: '用户名'),
            autofillHints: const [AutofillHints.username],
          ),
          const SizedBox(height: 16),
          TextField(
            controller: _password,
            obscureText: _obscure,
            decoration: InputDecoration(
              labelText: '密码',
              suffixIcon: IconButton(
                icon: Icon(_obscure ? Icons.visibility : Icons.visibility_off),
                onPressed: () => setState(() => _obscure = !_obscure),
              ),
            ),
            autofillHints: const [AutofillHints.password],
            onSubmitted: (_) => _submit(),
          ),
          if (captcha == null || captcha.captchaEnabled) ...[
            const SizedBox(height: 16),
            Row(
              crossAxisAlignment: CrossAxisAlignment.center,
              children: [
                Expanded(
                  child: TextField(
                    controller: _code,
                    decoration: const InputDecoration(labelText: '验证码'),
                    onSubmitted: (_) => _submit(),
                  ),
                ),
                const SizedBox(width: 12),
                GestureDetector(
                  onTap: _refreshCaptcha,
                  child: Container(
                    height: 42,
                    width: 124,
                    alignment: Alignment.center,
                    decoration: BoxDecoration(
                      color: Theme.of(context)
                          .colorScheme
                          .surfaceContainerLowest,
                      borderRadius: BorderRadius.circular(
                        AppDimens.radiusControl,
                      ),
                      border: Border.all(
                        color: Theme.of(context).colorScheme.outlineVariant,
                      ),
                    ),
                    child: _loadingCaptcha
                        ? const SizedBox(
                            width: 18,
                            height: 18,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : (_captchaImage != null
                              ? Image(image: _captchaImage!)
                              : Text(
                                  '点击刷新',
                                  style: Theme.of(context).textTheme.bodySmall,
                                )),
                  ),
                ),
              ],
            ),
          ],
          if (_error != null) ...[
            const SizedBox(height: 14),
            FormErrorText(_error!),
          ],
          const SizedBox(height: 22),
          FilledButton(
            onPressed: _submitting ? null : _submit,
            style: FilledButton.styleFrom(
              minimumSize: const Size.fromHeight(46),
            ),
            child: Text(_submitting ? '登录中…' : '登 录'),
          ),
          if (registerEnabled)
            Center(
              child: TextButton(
                onPressed: () => context.go('/register'),
                child: const Text('没有账号？注册'),
              ),
            ),
        ],
      ),
    );
  }
}
