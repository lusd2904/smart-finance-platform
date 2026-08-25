import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../core/theme/app_theme.dart';
import '../../core/theme/ruoyi_tokens.dart';

typedef OpenRoute = void Function(String path, {String? title});

class AppPage extends StatelessWidget {
  const AppPage({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(16),
  });

  final Widget child;
  final EdgeInsets padding;

  @override
  Widget build(BuildContext context) {
    return ColoredBox(
      color: Theme.of(context).brightness == Brightness.dark
          ? WebTokens.contentBg
          : WebTokens.contentBgLight,
      child: Padding(padding: padding, child: child),
    );
  }
}

class ElCard extends StatelessWidget {
  const ElCard({
    super.key,
    required this.child,
    this.header,
    this.padding = const EdgeInsets.all(16),
    this.expand = false,
  });

  final Widget child;
  final Widget? header;
  final EdgeInsets padding;
  final bool expand;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final body = expand
        ? Expanded(child: Padding(padding: padding, child: child))
        : Padding(padding: padding, child: child);
    final card = Container(
      decoration: BoxDecoration(
        color: scheme.surfaceContainerLow,
        borderRadius: BorderRadius.circular(AppDimens.radiusCard),
        border: Border.all(color: scheme.outlineVariant),
      ),
      child: Material(
        type: MaterialType.transparency,
        child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (header != null)
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              decoration: BoxDecoration(
                border: Border(bottom: BorderSide(color: scheme.outlineVariant)),
              ),
              child: DefaultTextStyle(
                style: Theme.of(context).textTheme.titleSmall!.copyWith(
                      fontWeight: FontWeight.w600,
                    ),
                child: header!,
              ),
            ),
          body,
        ],
      ),
      ),
    );
    return expand ? SizedBox.expand(child: card) : card;
  }
}

class PageHero extends StatelessWidget {
  const PageHero({
    super.key,
    required this.title,
    this.subtitle,
    this.actions = const [],
  });

  final String title;
  final String? subtitle;
  final List<Widget> actions;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: Theme.of(context).textTheme.titleLarge?.copyWith(
                        fontWeight: FontWeight.w700,
                      ),
                ),
                if (subtitle != null) ...[
                  const SizedBox(height: 4),
                  Text(
                    subtitle!,
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          color: Theme.of(context).colorScheme.onSurfaceVariant,
                        ),
                  ),
                ],
              ],
            ),
          ),
          Wrap(spacing: 8, children: actions),
        ],
      ),
    );
  }
}

class ElTag extends StatelessWidget {
  const ElTag(
    this.text, {
    super.key,
    this.tone = ElTagTone.info,
  });

  final String text;
  final ElTagTone tone;

  @override
  Widget build(BuildContext context) {
    final (bg, fg) = switch (tone) {
      ElTagTone.success => (const Color(0x1A67C23A), const Color(0xFF67C23A)),
      ElTagTone.warning => (const Color(0x1AE6A23C), const Color(0xFFE6A23C)),
      ElTagTone.danger => (const Color(0x1AF56C6C), const Color(0xFFF56C6C)),
      ElTagTone.primary => (const Color(0x1A6366F1), WebTokens.primary),
      ElTagTone.info => (const Color(0x1A909399), const Color(0xFF909399)),
    };
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(4),
        border: Border.all(color: fg.withValues(alpha: 0.35)),
      ),
      child: Text(text, style: TextStyle(color: fg, fontSize: 12, height: 1.3)),
    );
  }
}

enum ElTagTone { info, success, warning, danger, primary }

class EmptyHint extends StatelessWidget {
  const EmptyHint(this.text, {super.key});
  final String text;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 48),
      child: Column(
        children: [
          Icon(Icons.inbox_outlined, size: 48, color: Theme.of(context).disabledColor),
          const SizedBox(height: 8),
          Text(text, style: TextStyle(color: Theme.of(context).disabledColor)),
        ],
      ),
    );
  }
}

class ErrorBanner extends StatelessWidget {
  const ErrorBanner(this.text, {super.key, this.onRetry});
  final String text;
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: const Color(0x14F56C6C),
        borderRadius: BorderRadius.circular(4),
        border: Border.all(color: const Color(0x33F56C6C)),
      ),
      child: Row(
        children: [
          const Icon(Icons.error_outline, size: 16, color: Color(0xFFF56C6C)),
          const SizedBox(width: 8),
          Expanded(child: Text(text, style: const TextStyle(color: Color(0xFFF56C6C)))),
          if (onRetry != null)
            TextButton(onPressed: onRetry, child: const Text('重试')),
        ],
      ),
    );
  }
}

class KvGrid extends StatelessWidget {
  const KvGrid(this.entries, {super.key, this.columns = 3});
  final Map<String, String> entries;
  final int columns;

  @override
  Widget build(BuildContext context) {
    final items = entries.entries.toList();
    return Wrap(
      spacing: 16,
      runSpacing: 12,
      children: [
        for (final e in items)
          SizedBox(
            width: 220,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  e.key,
                  style: Theme.of(context).textTheme.labelSmall?.copyWith(
                        color: Theme.of(context).colorScheme.onSurfaceVariant,
                      ),
                ),
                const SizedBox(height: 2),
                Text(
                  e.value.isEmpty ? '--' : e.value,
                  style: AppNum.style(
                    Theme.of(context).textTheme.bodyMedium!.copyWith(
                          fontWeight: FontWeight.w600,
                        ),
                  ),
                ),
              ],
            ),
          ),
      ],
    );
  }
}

class SimpleTable extends StatelessWidget {
  const SimpleTable({
    super.key,
    required this.columns,
    required this.rows,
    this.onRowTap,
    this.rowActions,
    this.busy = false,
  });

  final List<TableCol> columns;
  final List<Map<String, dynamic>> rows;
  final ValueChanged<Map<String, dynamic>>? onRowTap;
  final List<Widget> Function(Map<String, dynamic> row)? rowActions;
  final bool busy;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    if (busy && rows.isEmpty) {
      return const Padding(
        padding: EdgeInsets.all(32),
        child: Center(child: CircularProgressIndicator(strokeWidth: 2)),
      );
    }
    if (rows.isEmpty) return const EmptyHint('暂无数据');
    return LayoutBuilder(
      builder: (context, c) {
        return SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          child: ConstrainedBox(
            constraints: BoxConstraints(minWidth: c.maxWidth),
            child: DataTable(
              headingRowHeight: 42,
              dataRowMinHeight: 40,
              dataRowMaxHeight: 56,
              headingRowColor: WidgetStatePropertyAll(scheme.surfaceContainerHighest),
              columns: [
                for (final col in columns)
                  DataColumn(
                    label: Text(
                      col.label,
                      style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13),
                    ),
                  ),
                if (rowActions != null) const DataColumn(label: Text('操作')),
              ],
              rows: [
                for (final row in rows)
                  DataRow(
                    onSelectChanged: onRowTap == null ? null : (_) => onRowTap!(row),
                    cells: [
                      for (final col in columns)
                        DataCell(
                          col.builder != null
                              ? col.builder!(row)
                              : Text(
                                  col.value(row),
                                  style: AppNum.style(const TextStyle(fontSize: 13)),
                                ),
                        ),
                      if (rowActions != null)
                        DataCell(Row(children: rowActions!(row))),
                    ],
                  ),
              ],
            ),
          ),
        );
      },
    );
  }
}

class TableCol {
  const TableCol(this.label, this.key, {this.builder, this.width});
  final String label;
  final String key;
  final Widget Function(Map<String, dynamic> row)? builder;
  final double? width;

  String value(Map<String, dynamic> row) {
    final v = _dig(row, key);
    if (v == null) return '';
    if (v is num) {
      if (v is int) return v.toString();
      return v.abs() >= 100 ? v.toStringAsFixed(2) : v.toStringAsFixed(4);
    }
    return v.toString();
  }

  static dynamic _dig(Map<String, dynamic> row, String key) {
    if (row.containsKey(key)) return row[key];
    if (!key.contains('.')) return null;
    dynamic cur = row;
    for (final part in key.split('.')) {
      if (cur is Map) {
        cur = cur[part];
      } else {
        return null;
      }
    }
    return cur;
  }
}

class QueryField {
  const QueryField(this.key, this.label, {this.width = 180, this.options});
  final String key;
  final String label;
  final double width;
  final List<(String label, String value)>? options;
}

class QueryBar extends StatefulWidget {
  const QueryBar({
    super.key,
    required this.fields,
    required this.values,
    required this.onChanged,
    required this.onSearch,
    this.onReset,
    this.extra = const [],
  });

  final List<QueryField> fields;
  final Map<String, String> values;
  final void Function(String key, String value) onChanged;
  final VoidCallback onSearch;
  final VoidCallback? onReset;
  final List<Widget> extra;

  @override
  State<QueryBar> createState() => _QueryBarState();
}

class _QueryBarState extends State<QueryBar> {
  final Map<String, TextEditingController> _ctrls = {};

  @override
  void initState() {
    super.initState();
    _syncControllers();
  }

  @override
  void didUpdateWidget(covariant QueryBar oldWidget) {
    super.didUpdateWidget(oldWidget);
    _syncControllers();
  }

  void _syncControllers() {
    final keys = widget.fields.where((f) => f.options == null).map((f) => f.key).toSet();
    for (final k in keys) {
      final text = widget.values[k] ?? '';
      final existing = _ctrls[k];
      if (existing == null) {
        _ctrls[k] = TextEditingController(text: text);
      } else if (existing.text != text) {
        existing.value = TextEditingValue(
          text: text,
          selection: TextSelection.collapsed(offset: text.length),
        );
      }
    }
    for (final stale in _ctrls.keys.where((k) => !keys.contains(k)).toList()) {
      _ctrls.remove(stale)?.dispose();
    }
  }

  @override
  void dispose() {
    for (final c in _ctrls.values) {
      c.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Wrap(
      spacing: 12,
      runSpacing: 10,
      crossAxisAlignment: WrapCrossAlignment.center,
      children: [
        for (final f in widget.fields)
          SizedBox(
            width: f.width,
            child: f.options == null
                ? TextField(
                    controller: _ctrls[f.key],
                    decoration: InputDecoration(labelText: f.label, isDense: true),
                    onChanged: (v) => widget.onChanged(f.key, v),
                    onSubmitted: (_) => widget.onSearch(),
                  )
                : DropdownButtonFormField<String>(
                    key: ValueKey('qb-${f.key}-${widget.values[f.key] ?? ''}'),
                    initialValue: (widget.values[f.key]?.isEmpty ?? true)
                        ? ''
                        : widget.values[f.key],
                    decoration: InputDecoration(labelText: f.label, isDense: true),
                    items: [
                      const DropdownMenuItem(value: '', child: Text('全部')),
                      for (final o in f.options!)
                        DropdownMenuItem(value: o.$2, child: Text(o.$1)),
                    ],
                    onChanged: (v) => widget.onChanged(f.key, v ?? ''),
                  ),
          ),
        FilledButton.icon(
          onPressed: widget.onSearch,
          icon: const Icon(Icons.search, size: 16),
          label: const Text('搜索'),
        ),
        if (widget.onReset != null)
          OutlinedButton(onPressed: widget.onReset, child: const Text('重置')),
        ...widget.extra,
      ],
    );
  }
}

class Pager extends StatelessWidget {
  const Pager({
    super.key,
    required this.page,
    required this.pageSize,
    required this.total,
    required this.onPage,
  });

  final int page;
  final int pageSize;
  final int total;
  final ValueChanged<int> onPage;

  @override
  Widget build(BuildContext context) {
    final pages = (total / pageSize).ceil().clamp(1, 9999);
    return Padding(
      padding: const EdgeInsets.only(top: 12),
      child: Row(
        children: [
          Text('共 $total 条', style: Theme.of(context).textTheme.bodySmall),
          const Spacer(),
          IconButton(
            onPressed: page > 1 ? () => onPage(page - 1) : null,
            icon: const Icon(Icons.chevron_left),
          ),
          Text('$page / $pages'),
          IconButton(
            onPressed: page < pages ? () => onPage(page + 1) : null,
            icon: const Icon(Icons.chevron_right),
          ),
        ],
      ),
    );
  }
}

Future<void> toast(BuildContext context, String msg, {bool error = false}) {
  final messenger = ScaffoldMessenger.maybeOf(context);
  messenger?.hideCurrentSnackBar();
  messenger?.showSnackBar(
    SnackBar(
      content: Text(msg),
      backgroundColor: error ? const Color(0xFFF56C6C) : null,
    ),
  );
  return Future.value();
}

Future<bool> confirm(BuildContext context, String message, {String title = '提示'}) async {
  final ok = await showDialog<bool>(
    context: context,
    builder: (ctx) => AlertDialog(
      title: Text(title),
      content: Text(message),
      actions: [
        TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('取消')),
        FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('确定')),
      ],
    ),
  );
  return ok == true;
}

class NumberBox extends StatelessWidget {
  const NumberBox({
    super.key,
    required this.value,
    required this.onChanged,
    this.min = 0,
    this.max = 999999,
    this.step = 1,
    this.width = 110,
  });

  final num value;
  final ValueChanged<num> onChanged;
  final num min;
  final num max;
  final num step;
  final double width;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: width,
      child: TextField(
        controller: TextEditingController(text: value.toString())
          ..selection = TextSelection.collapsed(offset: value.toString().length),
        keyboardType: TextInputType.number,
        inputFormatters: [FilteringTextInputFormatter.allow(RegExp(r'[0-9.\-]'))],
        decoration: const InputDecoration(isDense: true),
        onSubmitted: (v) {
          final n = num.tryParse(v) ?? value;
          onChanged(n.clamp(min, max));
        },
      ),
    );
  }
}
