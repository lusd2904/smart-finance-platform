import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_client.dart';
import '../../../core/api/api_result.dart';
import '../../../core/api/ruoyi_client.dart';
import '../../../core/theme/app_theme.dart';

/// 需求沟通：对话气泡 + 发送，对齐网页 req-chat（不是消息列表表格）。
class AiReqChatPage extends ConsumerStatefulWidget {
  const AiReqChatPage({super.key});

  @override
  ConsumerState<AiReqChatPage> createState() => _AiReqChatPageState();
}

class _AiReqChatPageState extends ConsumerState<AiReqChatPage> {
  final _draft = TextEditingController();
  final _scroll = ScrollController();
  final _jobs = <String, String>{};
  List<Map<String, dynamic>> _messages = const [];
  bool _loading = true;
  bool _sending = false;
  String? _error;
  String _hint = '';
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    Future<void>.microtask(() => _load(silent: false));
    _timer = Timer.periodic(const Duration(seconds: 3), (_) => _tick());
  }

  @override
  void dispose() {
    _timer?.cancel();
    _draft.dispose();
    _scroll.dispose();
    super.dispose();
  }

  RuoyiClient get _client => ref.read(ruoyiClientProvider);

  Future<void> _load({required bool silent}) async {
    if (!silent && mounted) {
      setState(() {
        _loading = true;
        _error = null;
      });
    }
    try {
      final result = await _client.get('/ai/req/messages', query: {'limit': 200});
      final items = asJsonList(result.dataAsMap?['items']).whereType<Map<String, dynamic>>().toList();
      if (!mounted) return;
      setState(() {
        _messages = items;
        _loading = false;
        _error = null;
      });
      _jumpBottom();
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        if (!silent) _error = describeApiError(e);
      });
    }
  }

  Future<void> _tick() async {
    if (_jobs.isEmpty) return;
    for (final id in [..._jobs.keys]) {
      try {
        final result = await _client.get('/ai/req/jobs/$id');
        final ticket = result.dataAsMap ?? const <String, dynamic>{};
        final status = asString(ticket['status']);
        if (status == 'done' || status == 'failed') {
          _jobs.remove(id);
        }
      } catch (_) {
        _jobs.remove(id);
      }
    }
    if (!mounted) return;
    setState(() => _hint = _jobs.isEmpty ? '' : (_jobs.values.first));
    await _load(silent: true);
  }

  void _jumpBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!_scroll.hasClients) return;
      _scroll.jumpTo(_scroll.position.maxScrollExtent);
    });
  }

  Future<void> _send() async {
    final content = _draft.text.trim();
    if (content.isEmpty || _sending) return;
    _draft.clear();
    setState(() => _sending = true);
    try {
      final result = await _client.post('/ai/req/messages', data: {'content': content});
      final data = result.dataAsMap ?? const <String, dynamic>{};
      final userMsg = asJsonMap(data['userMessage']);
      final aiMsg = asJsonMap(data['aiMessage']);
      setState(() {
        if (userMsg != null) _messages = [..._messages, userMsg];
        if (aiMsg != null) _messages = [..._messages, aiMsg];
        final jobId = asString(data['jobId']);
        if (jobId.isNotEmpty || data['accepted'] == true) {
          final id = jobId.isEmpty ? 'pending-${DateTime.now().millisecondsSinceEpoch}' : jobId;
          _jobs[id] = '已发送，机器人正在回复';
          _hint = '已发送，机器人正在回复';
        }
      });
      _jumpBottom();
    } catch (e) {
      if (_draft.text.trim().isEmpty) _draft.text = content;
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(describeApiError(e))));
      }
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    return Column(
      children: [
        if (_hint.isNotEmpty)
          Container(
            width: double.infinity,
            color: scheme.surfaceContainerHighest,
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            child: Text(_hint, style: theme.textTheme.bodySmall?.copyWith(color: scheme.onSurfaceVariant)),
          ),
        Expanded(
          child: _loading
              ? const Center(child: CircularProgressIndicator())
              : _error != null
                  ? Center(
                      child: Padding(
                        padding: const EdgeInsets.all(24),
                        child: Column(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Text(_error!, textAlign: TextAlign.center, style: TextStyle(color: scheme.error)),
                            const SizedBox(height: 12),
                            OutlinedButton(onPressed: () => _load(silent: false), child: const Text('重试')),
                          ],
                        ),
                      ),
                    )
                  : _messages.isEmpty
                      ? Center(
                          child: Text(
                            '还没有消息，先说明要做的需求',
                            style: theme.textTheme.bodyMedium?.copyWith(color: scheme.onSurfaceVariant),
                          ),
                        )
                      : ListView.builder(
                          controller: _scroll,
                          padding: const EdgeInsets.fromLTRB(12, 12, 12, 8),
                          itemCount: _messages.length,
                          itemBuilder: (_, i) => _Bubble(msg: _messages[i]),
                        ),
        ),
        SafeArea(
          top: false,
          child: Padding(
            padding: const EdgeInsets.fromLTRB(12, 8, 12, 10),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                Expanded(
                  child: TextField(
                    controller: _draft,
                    minLines: 1,
                    maxLines: 4,
                    textInputAction: TextInputAction.send,
                    onSubmitted: (_) => _send(),
                    decoration: InputDecoration(
                      hintText: '输入需求讨论…',
                      isDense: true,
                      contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(AppDimens.radiusControl)),
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                FilledButton(
                  onPressed: _sending ? null : _send,
                  style: FilledButton.styleFrom(
                    minimumSize: const Size(72, 44),
                    padding: const EdgeInsets.symmetric(horizontal: 16),
                  ),
                  child: _sending
                      ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                      : const Text('发送'),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}

class _Bubble extends StatelessWidget {
  const _Bubble({required this.msg});
  final Map<String, dynamic> msg;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final role = asString(msg['role']);
    final mine = role == 'user';
    final name = asString(msg['nickName']).isEmpty ? asString(msg['userName']) : asString(msg['nickName']);
    final time = asString(msg['createTime']);
    final content = asString(msg['content']);
    return Align(
      alignment: mine ? Alignment.centerRight : Alignment.centerLeft,
      child: ConstrainedBox(
        constraints: BoxConstraints(maxWidth: MediaQuery.sizeOf(context).width * 0.78),
        child: Container(
          margin: const EdgeInsets.only(bottom: 10),
          padding: const EdgeInsets.fromLTRB(12, 8, 12, 10),
          decoration: BoxDecoration(
            color: mine ? scheme.primaryContainer : scheme.surfaceContainerHighest,
            borderRadius: BorderRadius.circular(14),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                time.isEmpty ? name : '$name  $time',
                style: theme.textTheme.labelSmall?.copyWith(color: scheme.onSurfaceVariant),
              ),
              const SizedBox(height: 4),
              Text(content, style: theme.textTheme.bodyMedium?.copyWith(height: 1.55)),
            ],
          ),
        ),
      ),
    );
  }
}
