import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api/api_client.dart';
import '../../core/api/ruoyi_client.dart';
import '../../shared/widgets/ruoyi_ui.dart';
import 'json_list_page.dart';

class SentimentDashboardPage extends ConsumerStatefulWidget {
  const SentimentDashboardPage({super.key});

  @override
  ConsumerState<SentimentDashboardPage> createState() =>
      _SentimentDashboardPageState();
}

class _SentimentDashboardPageState extends ConsumerState<SentimentDashboardPage> {
  bool _busy = true;
  String? _error;
  Map<String, dynamic> _stats = const {};
  Map<String, dynamic> _latest = const {};
  List<Map<String, dynamic>> _trend = const [];

  @override
  void initState() {
    super.initState();
    Future<void>.microtask(_load);
  }

  Future<void> _load() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final client = ref.read(ruoyiClientProvider);
      final stats = await client.get('/sentiment/stats');
      Map<String, dynamic> latest = const {};
      List<Map<String, dynamic>> trend = const [];
      try {
        final list = await client.get('/sentiment/analysis/list', query: {'pageNum': 1, 'pageSize': 1});
        final rows = extractRows(list);
        if (rows.isNotEmpty) latest = rows.first;
      } catch (_) {}
      try {
        final t = await client.get('/sentiment/analysis/trend');
        trend = extractRows(t, preferKeys: const ['points', 'items']);
      } catch (_) {}
      if (!mounted) return;
      setState(() {
        _stats = asMap(stats.data);
        _latest = latest;
        _trend = trend;
        _busy = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _busy = false;
        _error = describeApiError(e);
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return AppPage(
      child: ListView(
        children: [
          PageHero(
            title: '舆情大盘',
            subtitle: '中文舆情采集与大盘影响研判',
            actions: [OutlinedButton(onPressed: _load, child: const Text('刷新'))],
          ),
          if (_error != null) ErrorBanner(_error!, onRetry: _load),
          if (_busy) const LinearProgressIndicator(minHeight: 2),
          ElCard(
            header: const Text('统计'),
            child: KvGrid({
              for (final e in _stats.entries)
                if (e.value is! Map && e.value is! List) e.key: cellText(e.value),
            }),
          ),
          const SizedBox(height: 12),
          ElCard(
            header: const Text('最新研判'),
            child: _latest.isEmpty
                ? const EmptyHint('暂无研判')
                : Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(cellText(_latest['summary'] ?? _latest['content'])),
                      const SizedBox(height: 8),
                      Wrap(
                        spacing: 8,
                        children: [
                          ElTag('美 ${cellText(_latest['usDirection'] ?? _latest['usScore'])}'),
                          ElTag('港 ${cellText(_latest['hkDirection'] ?? _latest['hkScore'])}'),
                          ElTag('A ${cellText(_latest['aDirection'] ?? _latest['aScore'])}'),
                        ],
                      ),
                    ],
                  ),
          ),
          const SizedBox(height: 12),
          ElCard(
            header: const Text('趋势'),
            padding: EdgeInsets.zero,
            child: SimpleTable(
              columns: const [
                TableCol('时间', 'createTime'),
                TableCol('美股', 'usScore'),
                TableCol('港股', 'hkScore'),
                TableCol('A股', 'aScore'),
              ],
              rows: _trend,
            ),
          ),
        ],
      ),
    );
  }
}

class SentimentNewsPage extends StatelessWidget {
  const SentimentNewsPage({super.key});

  @override
  Widget build(BuildContext context) {
    return const JsonListPage(
      title: '资讯列表',
      path: '/sentiment/news/list',
      filters: [QueryField('title', '标题')],
      columns: [
        TableCol('时间', 'createTime'),
        TableCol('标题', 'title'),
        TableCol('来源', 'source'),
        TableCol('情感', 'sentiment'),
      ],
    );
  }
}

class SentimentAnalysisPage extends StatelessWidget {
  const SentimentAnalysisPage({super.key});

  @override
  Widget build(BuildContext context) {
    return const JsonListPage(
      title: '分析历史',
      path: '/sentiment/analysis/list',
      columns: [
        TableCol('时间', 'createTime'),
        TableCol('摘要', 'summary'),
        TableCol('美股', 'usDirection'),
        TableCol('港股', 'hkDirection'),
        TableCol('A股', 'aDirection'),
        TableCol('模型', 'modelName'),
      ],
    );
  }
}

class SentimentConfigPage extends StatelessWidget {
  const SentimentConfigPage({super.key});

  @override
  Widget build(BuildContext context) {
    return const JsonDetailPage(title: '舆情配置', path: '/sentiment/config');
  }
}

class AiChatPage extends ConsumerStatefulWidget {
  const AiChatPage({super.key});

  @override
  ConsumerState<AiChatPage> createState() => _AiChatPageState();
}

class _AiChatPageState extends ConsumerState<AiChatPage> {
  final _input = TextEditingController();
  bool _busy = false;
  List<Map<String, dynamic>> _sessions = const [];
  List<Map<String, dynamic>> _messages = const [];
  String? _sessionId;
  String? _error;

  @override
  void initState() {
    super.initState();
    Future<void>.microtask(_loadSessions);
  }

  @override
  void dispose() {
    _input.dispose();
    super.dispose();
  }

  Future<void> _loadSessions() async {
    try {
      final r = await ref.read(ruoyiClientProvider).get('/ai/chat/session/list');
      if (!mounted) return;
      setState(() => _sessions = extractRows(r, preferKeys: const ['sessions', 'items']));
    } catch (e) {
      if (mounted) setState(() => _error = describeApiError(e));
    }
  }

  Future<void> _open(String id) async {
    setState(() => _sessionId = id);
    try {
      final r = await ref.read(ruoyiClientProvider).get('/ai/chat/session/$id');
      final data = asMap(r.data);
      final msgs = data['messages'];
      setState(() {
        _messages = msgs is List
            ? msgs.whereType<Map<String, dynamic>>().toList()
            : extractRows(r, preferKeys: const ['messages']);
      });
    } catch (e) {
      if (mounted) setState(() => _error = describeApiError(e));
    }
  }

  Future<void> _send() async {
    final text = _input.text.trim();
    if (text.isEmpty) return;
    setState(() => _busy = true);
    try {
      final r = await ref.read(ruoyiClientProvider).post(
            '/ai/chat/oneshot',
            data: {'content': text, 'sessionId': _sessionId},
            timeout: const Duration(seconds: 120),
          );
      _input.clear();
      final data = asMap(r.data);
      setState(() {
        _messages = [
          ..._messages,
          {'role': 'user', 'content': text},
          {'role': 'assistant', 'content': cellText(data['content'] ?? data['answer'] ?? r.data)},
        ];
      });
      await _loadSessions();
    } catch (e) {
      if (mounted) setState(() => _error = describeApiError(e));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return AppPage(
      padding: EdgeInsets.zero,
      child: Row(
        children: [
          SizedBox(
            width: 240,
            child: Column(
              children: [
                const Padding(
                  padding: EdgeInsets.all(12),
                  child: Align(alignment: Alignment.centerLeft, child: Text('会话')),
                ),
                Expanded(
                  child: ListView(
                    children: [
                      for (final s in _sessions)
                        ListTile(
                          dense: true,
                          selected: cellText(s['sessionId'] ?? s['id']) == _sessionId,
                          title: Text(
                            cellText(s['title'] ?? s['sessionId'] ?? s['id']),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                          onTap: () => _open(cellText(s['sessionId'] ?? s['id'])),
                        ),
                    ],
                  ),
                ),
              ],
            ),
          ),
          const VerticalDivider(width: 1),
          Expanded(
            child: Column(
              children: [
                if (_error != null) ErrorBanner(_error!),
                Expanded(
                  child: ListView(
                    padding: const EdgeInsets.all(16),
                    children: [
                      for (final m in _messages)
                        Align(
                          alignment: cellText(m['role']) == 'user'
                              ? Alignment.centerRight
                              : Alignment.centerLeft,
                          child: Container(
                            margin: const EdgeInsets.only(bottom: 8),
                            padding: const EdgeInsets.all(10),
                            constraints: const BoxConstraints(maxWidth: 640),
                            decoration: BoxDecoration(
                              color: cellText(m['role']) == 'user'
                                  ? const Color(0x336366F1)
                                  : Theme.of(context).colorScheme.surfaceContainerHighest,
                              borderRadius: BorderRadius.circular(8),
                            ),
                            child: SelectableText(cellText(m['content'] ?? m['text'])),
                          ),
                        ),
                    ],
                  ),
                ),
                Padding(
                  padding: const EdgeInsets.all(12),
                  child: Row(
                    children: [
                      Expanded(
                        child: TextField(
                          controller: _input,
                          decoration: const InputDecoration(hintText: '输入问题，Enter 发送'),
                          onSubmitted: (_) => _send(),
                        ),
                      ),
                      const SizedBox(width: 8),
                      FilledButton(
                        onPressed: _busy ? null : _send,
                        child: Text(_busy ? '…' : '发送'),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class AiModelPage extends StatelessWidget {
  const AiModelPage({super.key});

  @override
  Widget build(BuildContext context) {
    return const JsonListPage(
      title: 'AI 模型',
      path: '/ai/model/list',
      columns: [
        TableCol('名称', 'modelName'),
        TableCol('编码', 'modelCode'),
        TableCol('提供方', 'provider'),
        TableCol('状态', 'status'),
      ],
    );
  }
}

class AiReqChatPage extends StatelessWidget {
  const AiReqChatPage({super.key});

  @override
  Widget build(BuildContext context) {
    return const JsonListPage(
      title: '需求沟通',
      path: '/ai/req/messages',
      paged: false,
      preferKeys: ['items', 'messages'],
    );
  }
}

class AiReqListPage extends StatelessWidget {
  const AiReqListPage({super.key});

  @override
  Widget build(BuildContext context) {
    return const JsonListPage(
      title: 'AI 需求清单',
      path: '/ai/req/items',
      paged: false,
    );
  }
}

class AiReqBotPage extends StatelessWidget {
  const AiReqBotPage({super.key});

  @override
  Widget build(BuildContext context) {
    return const JsonListPage(
      title: 'AI 机器人',
      path: '/ai/req/bots',
      paged: false,
    );
  }
}

class AnalysisJobsPage extends ConsumerStatefulWidget {
  const AnalysisJobsPage({super.key});

  @override
  ConsumerState<AnalysisJobsPage> createState() => _AnalysisJobsPageState();
}

class _AnalysisJobsPageState extends ConsumerState<AnalysisJobsPage> {
  bool _busy = true;
  String? _error;
  List<Map<String, dynamic>> _jobs = const [];

  @override
  void initState() {
    super.initState();
    Future<void>.microtask(_load);
  }

  Future<void> _load() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final r = await ref.read(ruoyiClientProvider).get('/analysis/scheduler/overview');
      if (!mounted) return;
      setState(() {
        _jobs = extractRows(r, preferKeys: const ['jobs', 'items']);
        _busy = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _busy = false;
        _error = describeApiError(e);
      });
    }
  }

  Future<void> _run(String id) async {
    try {
      await ref.read(ruoyiClientProvider).post('/analysis/scheduler/jobs/$id/run');
      if (mounted) toast(context, '已触发');
      await _load();
    } catch (e) {
      if (mounted) toast(context, describeApiError(e), error: true);
    }
  }

  @override
  Widget build(BuildContext context) {
    return AppPage(
      child: Column(
        children: [
          PageHero(
            title: '自动分析任务',
            subtitle: '任务中心（管理员）',
            actions: [OutlinedButton(onPressed: _load, child: const Text('刷新'))],
          ),
          if (_error != null) ErrorBanner(_error!, onRetry: _load),
          Expanded(
            child: ElCard(
              padding: EdgeInsets.zero,
              child: SimpleTable(
                busy: _busy,
                columns: const [
                  TableCol('任务', 'jobName'),
                  TableCol('分组', 'jobGroup'),
                  TableCol('状态', 'status'),
                  TableCol('Cron', 'cronExpression'),
                  TableCol('上次', 'lastRunTime'),
                ],
                rows: _jobs,
                rowActions: (row) => [
                  TextButton(
                    onPressed: () => _run(cellText(row['jobId'] ?? row['id'])),
                    child: const Text('立即执行'),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
