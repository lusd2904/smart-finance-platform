import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api/api_client.dart';
import '../../core/api/api_result.dart';
import '../../core/theme/app_theme.dart';

/// 子系统使用说明：GET `/common/guide/{module}`，轻量 Markdown 渲染（无 flutter_markdown）。
class GuidePage extends ConsumerStatefulWidget {
  const GuidePage({super.key, required this.module});

  static const modules = <String>{
    'market',
    'quant',
    'trade',
    'sentiment',
    'ai',
    'analysis',
  };

  final String module;

  @override
  ConsumerState<GuidePage> createState() => _GuidePageState();
}

class _GuidePageState extends ConsumerState<GuidePage> {
  late Future<String> _future;

  @override
  void initState() {
    super.initState();
    _future = _fetch();
  }

  @override
  void didUpdateWidget(covariant GuidePage oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.module != widget.module) {
      setState(() {
        _future = _fetch();
      });
    }
  }

  void _reload() {
    setState(() {
      _future = _fetch();
    });
  }

  Future<String> _fetch() async {
    final module = widget.module.trim().toLowerCase();
    if (!GuidePage.modules.contains(module)) {
      throw ApiException('不支持的使用说明');
    }
    final result = ApiResult.from(
      await ref.read(dioProvider).get<dynamic>('/common/guide/$module'),
    );
    return _markdownFrom(result);
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<String>(
      future: _future,
      builder: (context, snap) {
        if (snap.connectionState == ConnectionState.waiting) {
          return const Center(child: CircularProgressIndicator());
        }
        if (snap.hasError) {
          return _GuideStatus(
            message: describeApiError(snap.error!),
            onRetry: _reload,
          );
        }
        final markdown = snap.data ?? '';
        if (markdown.trim().isEmpty) {
          return _GuideStatus(message: '暂无使用说明', onRetry: _reload);
        }
        return ListView(
          padding: const EdgeInsets.fromLTRB(
            AppDimens.pagePadding,
            12,
            AppDimens.pagePadding,
            32,
          ),
          children: _markdownWidgets(context, markdown),
        );
      },
    );
  }
}

class _GuideStatus extends StatelessWidget {
  const _GuideStatus({required this.message, required this.onRetry});

  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              Icons.menu_book_outlined,
              size: 40,
              color: Theme.of(context).colorScheme.outline,
            ),
            const SizedBox(height: 12),
            Text(message, textAlign: TextAlign.center),
            const SizedBox(height: 16),
            FilledButton.tonalIcon(
              onPressed: onRetry,
              icon: const Icon(Icons.refresh),
              label: const Text('重试'),
            ),
          ],
        ),
      ),
    );
  }
}

String _markdownFrom(ApiResult result) {
  final data = result.data;
  if (data is String) {
    return data;
  }
  final map = asJsonMap(data);
  if (map == null) {
    return '';
  }
  for (final key in ['markdown', 'content', 'text', 'body', 'guide']) {
    final value = map[key];
    if (value is String && value.trim().isNotEmpty) {
      return value;
    }
  }
  return '';
}

final _heading = RegExp(r'^(#{1,6})\s+(.*)$');
final _numbered = RegExp(r'^(\d+)\.\s+(.*)$');

List<Widget> _markdownWidgets(BuildContext context, String markdown) {
  final theme = Theme.of(context);
  final body = theme.textTheme.bodyMedium?.copyWith(height: 1.55);
  final widgets = <Widget>[];
  var inFence = false;
  for (final raw in markdown.replaceAll('\r\n', '\n').split('\n')) {
    final trimmed = raw.trim();
    if (trimmed.startsWith('```')) {
      inFence = !inFence;
      continue;
    }
    if (inFence) {
      widgets.add(
        Padding(
          padding: const EdgeInsets.symmetric(vertical: 1),
          child: SelectableText(
            raw.isEmpty ? ' ' : raw,
            style: theme.textTheme.bodySmall?.copyWith(fontFamily: 'monospace'),
          ),
        ),
      );
      continue;
    }
    if (trimmed.startsWith('<')) {
      continue;
    }
    if (trimmed.isEmpty) {
      widgets.add(const SizedBox(height: 8));
      continue;
    }
    final heading = _heading.firstMatch(trimmed);
    if (heading != null) {
      final level = heading.group(1)!.length;
      final text = heading.group(2)!;
      final TextStyle? style;
      if (level <= 1) {
        style = theme.textTheme.titleLarge?.copyWith(
          fontWeight: FontWeight.w800,
        );
      } else if (level == 2) {
        style = theme.textTheme.titleMedium?.copyWith(
          fontWeight: FontWeight.w700,
        );
      } else {
        style = theme.textTheme.titleSmall?.copyWith(
          fontWeight: FontWeight.w700,
        );
      }
      widgets.add(
        Padding(
          padding: EdgeInsets.only(top: level <= 1 ? 8 : 16, bottom: 6),
          child: SelectableText(text, style: style),
        ),
      );
      continue;
    }
    if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
      widgets.add(
        Padding(
          padding: const EdgeInsets.only(left: 4, top: 2, bottom: 2),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('•  ', style: body),
              Expanded(
                child: SelectableText(trimmed.substring(2), style: body),
              ),
            ],
          ),
        ),
      );
      continue;
    }
    final numbered = _numbered.firstMatch(trimmed);
    if (numbered != null) {
      widgets.add(
        Padding(
          padding: const EdgeInsets.only(left: 4, top: 2, bottom: 2),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              SizedBox(
                width: 28,
                child: Text('${numbered.group(1)}. ', style: body),
              ),
              Expanded(child: SelectableText(numbered.group(2)!, style: body)),
            ],
          ),
        ),
      );
      continue;
    }
    widgets.add(
      Padding(
        padding: const EdgeInsets.symmetric(vertical: 3),
        child: SelectableText(trimmed, style: body),
      ),
    );
  }
  return widgets;
}
