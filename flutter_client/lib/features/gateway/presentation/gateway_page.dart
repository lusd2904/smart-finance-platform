import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:flutter_client/core/gateway/gateway_controller.dart';
import 'package:flutter_client/core/gateway/gateway_probe.dart';
import 'package:flutter_client/core/theme/app_theme.dart';
import 'package:flutter_client/shared/widgets/auth_scaffold.dart';
import 'package:flutter_client/core/gateway/gateway_config.dart';

/// 网关配置页：复刻 desktop「先探测通过，才放行登录」的语义。
/// HTTPS 探测失败时提供手动改用 http 的一键回填（绝不自动降级）。
class GatewayPage extends ConsumerStatefulWidget {
  const GatewayPage({super.key});

  @override
  ConsumerState<GatewayPage> createState() => _GatewayPageState();
}

class _GatewayPageState extends ConsumerState<GatewayPage> {
  late final TextEditingController _controller;
  bool _probing = false;
  ProbeResult? _result;
  GatewayFormatException? _formatError;

  @override
  void initState() {
    super.initState();
    final current = ref.read(gatewayController);
    _controller = TextEditingController(text: resolveStoredGateway(current.url));
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  Future<void> _probeAndEnter() async {
    setState(() {
      _probing = true;
      _result = null;
      _formatError = null;
    });
    try {
      final result = await ref
          .read(gatewayController.notifier)
          .probeAndSave(_controller.text);
      if (!mounted) return;
      setState(() {
        _result = result;
        _probing = false;
      });
      if (result.ok && mounted) context.go('/login');
    } on GatewayFormatException catch (e) {
      if (!mounted) return;
      setState(() {
        _formatError = e;
        _probing = false;
      });
    }
  }

  void _applyPreset(GatewayPreset preset) {
    setState(() {
      _controller.text = preset.url;
      _result = null;
      _formatError = null;
    });
  }

  @override
  Widget build(BuildContext context) {
    final config = ref.watch(gatewayController);
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final fallback = _result?.fallbackUrl;
    return AuthScaffold(
      title: '网关配置',
      subtitle: '探测通过后方可进入登录；可随时回来修改',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: scheme.primary.withValues(alpha: 0.07),
              borderRadius: BorderRadius.circular(AppDimens.radiusControl),
            ),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(
                  Icons.info_outline_rounded,
                  size: 16,
                  color: scheme.onSurfaceVariant,
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    '这里填写前端网关地址；后端 API 端口（19099/9099）不能当网关。',
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: scheme.onSurfaceVariant,
                    ),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: gatewayPresets
                .map(
                  (p) => ActionChip(
                    label: Text(p.label),
                    tooltip: p.hint,
                    onPressed: () => _applyPreset(p),
                  ),
                )
                .toList(),
          ),
          const SizedBox(height: 16),
          TextField(
            controller: _controller,
            decoration: InputDecoration(
              labelText: '网关地址',
              hintText: 'http://127.0.0.1:12580 或 https://your-domain',
              errorText: _formatError?.message,
            ),
            onSubmitted: (_) => _probeAndEnter(),
          ),
          if (config.lastGoodUrl != null) ...[
            const SizedBox(height: 10),
            Row(
              children: [
                Icon(
                  Icons.history_rounded,
                  size: 14,
                  color: scheme.onSurfaceVariant,
                ),
                const SizedBox(width: 5),
                Expanded(
                  child: Text(
                    '上次可用：${config.lastGoodUrl}',
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: scheme.onSurfaceVariant,
                    ),
                  ),
                ),
              ],
            ),
          ],
          if (_result != null && !_result!.ok) ...[
            const SizedBox(height: 14),
            FormErrorText(_result!.message),
            if (fallback != null) ...[
              const SizedBox(height: 12),
              OutlinedButton(
                onPressed: () => setState(() => _controller.text = fallback),
                child: Text('改用 $fallback'),
              ),
            ],
          ],
          const SizedBox(height: 24),
          FilledButton.icon(
            onPressed: _probing ? null : _probeAndEnter,
            style: FilledButton.styleFrom(
              minimumSize: const Size.fromHeight(46),
            ),
            icon: _probing
                ? const SizedBox(
                    width: 16,
                    height: 16,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.network_check),
            label: Text(_probing ? '探测中…' : '探测并进入'),
          ),
        ],
      ),
    );
  }
}
