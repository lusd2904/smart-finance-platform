import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api/api_client.dart';
import '../../core/api/ruoyi_client.dart';
import '../../shared/widgets/ruoyi_ui.dart';

/// 通用列表页：对齐 RuoYi「查询条 + 表格 + 分页」。
class JsonListPage extends ConsumerStatefulWidget {
  const JsonListPage({
    super.key,
    required this.title,
    required this.path,
    this.subtitle,
    this.columns = const [],
    this.filters = const [],
    this.preferKeys,
    this.extraQuery = const {},
    this.pageSize = 20,
    this.paged = true,
    this.onRowTap,
    this.open,
    this.rowActions,
    this.headerActions,
    this.method = 'GET',
    this.postBody,
  });

  final String title;
  final String? subtitle;
  final String path;
  final List<TableCol> columns;
  final List<QueryField> filters;
  final List<String>? preferKeys;
  final Map<String, dynamic> extraQuery;
  final int pageSize;
  final bool paged;
  final ValueChanged<Map<String, dynamic>>? onRowTap;
  final OpenRoute? open;
  final List<Widget> Function(Map<String, dynamic> row, VoidCallback reload)? rowActions;
  final List<Widget> Function(VoidCallback reload)? headerActions;
  final String method;
  final Map<String, dynamic>? postBody;

  @override
  ConsumerState<JsonListPage> createState() => _JsonListPageState();
}

class _JsonListPageState extends ConsumerState<JsonListPage> {
  final _values = <String, String>{};
  int _page = 1;
  int _total = 0;
  bool _busy = false;
  String? _error;
  List<Map<String, dynamic>> _rows = const [];
  List<TableCol> _cols = const [];

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
      final query = <String, dynamic>{
        ...widget.extraQuery,
        ..._values,
        if (widget.paged) 'pageNum': _page,
        if (widget.paged) 'pageSize': widget.pageSize,
      };
      final client = ref.read(ruoyiClientProvider);
      final result = widget.method == 'POST'
          ? await client.post(widget.path, data: {...?widget.postBody, ...query})
          : await client.get(widget.path, query: query);
      final rows = extractRows(result, preferKeys: widget.preferKeys);
      final cols = widget.columns.isNotEmpty ? widget.columns : _autoCols(rows);
      if (!mounted) return;
      setState(() {
        _rows = rows;
        _cols = cols;
        _total = extractTotal(result, rows);
        _busy = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _busy = false;
        _error = describeApiError(e);
        _rows = const [];
      });
    }
  }

  List<TableCol> _autoCols(List<Map<String, dynamic>> rows) {
    if (rows.isEmpty) return const [];
    final keys = rows.first.keys.where((k) {
      final v = rows.first[k];
      return v is! Map && v is! List;
    }).take(8);
    return [for (final k in keys) TableCol(_label(k), k)];
  }

  String _label(String key) {
    const map = {
      'userName': '用户名',
      'nickName': '昵称',
      'userId': '编号',
      'status': '状态',
      'createTime': '创建时间',
      'updateTime': '更新时间',
      'roleName': '角色',
      'roleKey': '权限字符',
      'menuName': '菜单',
      'path': '路由',
      'component': '组件',
      'symbol': '代码',
      'name': '名称',
      'market': '市场',
      'title': '标题',
      'price': '价格',
      'qty': '数量',
      'side': '方向',
      'orderId': '订单号',
      'jobName': '任务',
      'jobGroup': '分组',
      'ipaddr': 'IP',
      'msg': '说明',
    };
    return map[key] ?? key;
  }

  @override
  Widget build(BuildContext context) {
    return AppPage(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          PageHero(
            title: widget.title,
            subtitle: widget.subtitle,
            actions: [
              OutlinedButton.icon(
                onPressed: _busy ? null : _load,
                icon: const Icon(Icons.refresh, size: 16),
                label: const Text('刷新'),
              ),
              ...?widget.headerActions?.call(_load),
            ],
          ),
          if (widget.filters.isNotEmpty) ...[
            ElCard(
              child: QueryBar(
                fields: widget.filters,
                values: _values,
                onChanged: (k, v) => setState(() => _values[k] = v),
                onSearch: () {
                  _page = 1;
                  _load();
                },
                onReset: () {
                  setState(() {
                    _values.clear();
                    _page = 1;
                  });
                  _load();
                },
              ),
            ),
            const SizedBox(height: 12),
          ],
          if (_error != null) ErrorBanner(_error!, onRetry: _load),
          Expanded(
            child: ElCard(
              expand: true,
              padding: const EdgeInsets.fromLTRB(8, 0, 8, 8),
              child: Column(
                children: [
                  Expanded(
                    child: SingleChildScrollView(
                      child: SimpleTable(
                        columns: _cols,
                        rows: _rows,
                        busy: _busy,
                        onRowTap: widget.onRowTap,
                        rowActions: widget.rowActions == null
                            ? null
                            : (row) => widget.rowActions!(row, _load),
                      ),
                    ),
                  ),
                  if (widget.paged)
                    Pager(
                      page: _page,
                      pageSize: widget.pageSize,
                      total: _total,
                      onPage: (p) {
                        _page = p;
                        _load();
                      },
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

/// 把接口返回的 JSON 对象铺成键值表，适合监控/详情。
class JsonDetailPage extends ConsumerStatefulWidget {
  const JsonDetailPage({
    super.key,
    required this.title,
    required this.path,
    this.query,
    this.subtitle,
  });

  final String title;
  final String path;
  final String? subtitle;
  final Map<String, dynamic>? query;

  @override
  ConsumerState<JsonDetailPage> createState() => _JsonDetailPageState();
}

class _JsonDetailPageState extends ConsumerState<JsonDetailPage> {
  bool _busy = true;
  String? _error;
  Map<String, dynamic> _data = const {};

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
      final result = await ref.read(ruoyiClientProvider).get(
            widget.path,
            query: widget.query,
          );
      if (!mounted) return;
      setState(() {
        _data = asMap(result.data);
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
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          PageHero(
            title: widget.title,
            subtitle: widget.subtitle,
            actions: [
              OutlinedButton.icon(
                onPressed: _busy ? null : _load,
                icon: const Icon(Icons.refresh, size: 16),
                label: const Text('刷新'),
              ),
            ],
          ),
          if (_error != null) ErrorBanner(_error!, onRetry: _load),
          Expanded(
            child: _busy
                ? const Center(child: CircularProgressIndicator())
                : ListView(
                    children: [
                      for (final e in _flatten(_data))
                        ListTile(
                          dense: true,
                          title: Text(e.$1, style: const TextStyle(fontSize: 12)),
                          subtitle: SelectableText(e.$2),
                        ),
                    ],
                  ),
          ),
        ],
      ),
    );
  }

  List<(String, String)> _flatten(Map<String, dynamic> data, [String prefix = '']) {
    final out = <(String, String)>[];
    data.forEach((k, v) {
      final key = prefix.isEmpty ? k : '$prefix.$k';
      if (v is Map<String, dynamic>) {
        out.addAll(_flatten(v, key));
      } else if (v is List) {
        out.add((key, '${v.length} 项'));
      } else {
        out.add((key, v?.toString() ?? ''));
      }
    });
    return out;
  }
}
