import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:flutter_client/core/api/api_client.dart';
import 'package:flutter_client/features/auth/data/auth_api.dart';

/// 注册页：仅在服务端开启 registerEnabled 时从登录页可达。
class RegisterPage extends ConsumerStatefulWidget {
  const RegisterPage({super.key});

  @override
  ConsumerState<RegisterPage> createState() => _RegisterPageState();
}

class _RegisterPageState extends ConsumerState<RegisterPage> {
  final _username = TextEditingController();
  final _password = TextEditingController();
  final _confirm = TextEditingController();
  final _code = TextEditingController();

  CaptchaData? _captcha;
  String? _error;
  bool _submitting = false;

  @override
  void initState() {
    super.initState();
    () async {
      try {
        await ref.read(authApiProvider).captchaImage().then((c) {
          if (mounted) setState(() => _captcha = c);
        });
      } catch (_) {
        // 注册页验证码加载失败不阻断表单展示，提交时由服务端校验。
      }
    }();
  }

  @override
  void dispose() {
    _username.dispose();
    _password.dispose();
    _confirm.dispose();
    _code.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final username = _username.text.trim();
    final password = _password.text;
    if (username.isEmpty || password.isEmpty) {
      setState(() => _error = '请输入用户名和密码');
      return;
    }
    if (password != _confirm.text) {
      setState(() => _error = '两次输入的密码不一致');
      return;
    }
    setState(() {
      _submitting = true;
      _error = null;
    });
    try {
      await ref.read(authApiProvider).register(
            username: username,
            password: password,
            confirmPassword: _confirm.text,
            code: _code.text.trim(),
            uuid: _captcha?.uuid,
          );
      if (!mounted) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(const SnackBar(content: Text('注册成功，请登录')));
      context.go('/login');
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = describeApiError(e);
        _submitting = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('注册')),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 420),
          child: ListView(
            padding: const EdgeInsets.all(24),
            shrinkWrap: true,
            children: [
              TextField(controller: _username, decoration: const InputDecoration(labelText: '用户名')),
              const SizedBox(height: 16),
              TextField(controller: _password, obscureText: true, decoration: const InputDecoration(labelText: '密码')),
              const SizedBox(height: 16),
              TextField(
                  controller: _confirm,
                  obscureText: true,
                  decoration: const InputDecoration(labelText: '确认密码')),
              if (_captcha?.captchaEnabled ?? false) ...[
                const SizedBox(height: 16),
                TextField(controller: _code, decoration: const InputDecoration(labelText: '验证码')),
              ],
              if (_error != null) ...[
                const SizedBox(height: 12),
                Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
              ],
              const SizedBox(height: 20),
              FilledButton(
                onPressed: _submitting ? null : _submit,
                child: Text(_submitting ? '提交中…' : '注 册'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
