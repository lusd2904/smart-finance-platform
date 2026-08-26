import 'package:flutter/material.dart';

import '../api/api_result.dart';

/// 对齐后端 RouterModel / MetaModel（camelCase）。
class RouterMeta {
  const RouterMeta({this.title, this.icon, this.noCache, this.link, this.activeMenu});

  factory RouterMeta.fromJson(Map<String, dynamic>? json) {
    if (json == null) return const RouterMeta();
    return RouterMeta(
      title: json['title'] as String?,
      icon: json['icon'] as String?,
      noCache: json['noCache'] as bool?,
      link: json['link'] as String?,
      activeMenu: json['activeMenu'] as String?,
    );
  }

  final String? title;
  final String? icon;
  final bool? noCache;
  final String? link;
  final String? activeMenu;
}

class RouterNode {
  const RouterNode({
    this.name,
    this.path = '',
    this.hidden = false,
    this.redirect,
    this.component,
    this.alwaysShow,
    this.meta = const RouterMeta(),
    this.children = const [],
  });

  factory RouterNode.fromJson(Map<String, dynamic> json) => RouterNode(
        name: json['name'] as String?,
        path: (json['path'] as String?) ?? '',
        hidden: json['hidden'] as bool? ?? false,
        redirect: json['redirect'] as String?,
        component: json['component'] as String?,
        alwaysShow: json['alwaysShow'] as bool?,
        meta: RouterMeta.fromJson(asJsonMap(json['meta'])),
        children: asJsonList(json['children'])
            .whereType<Map<String, dynamic>>()
            .map(RouterNode.fromJson)
            .toList(),
      );

  final String? name;
  final String path;
  final bool hidden;
  final String? redirect;
  final String? component;
  final bool? alwaysShow;
  final RouterMeta meta;
  final List<RouterNode> children;

  bool get isLayout =>
      component == 'Layout' || component == 'ParentView' || component == 'InnerLink';

  String get title => (meta.title != null && meta.title!.isNotEmpty)
      ? meta.title!
      : (name ?? path);
}

class MenuLeaf {
  const MenuLeaf({
    required this.path,
    required this.title,
    this.icon,
    this.hidden = false,
  });

  final String path;
  final String title;
  final String? icon;
  final bool hidden;
}

String joinRoute(String parent, String child) {
  if (child.startsWith('http://') || child.startsWith('https://')) return child;
  if (child.startsWith('/')) return child;
  if (parent.isEmpty || parent == '/') return '/$child'.replaceAll('//', '/');
  final base = parent.endsWith('/') ? parent.substring(0, parent.length - 1) : parent;
  if (child.isEmpty) return base.startsWith('/') ? base : '/$base';
  return '$base/$child'.replaceAll('//', '/');
}

/// 若依后台：系统管理 / 监控 / 代码生成 / 自动分析任务。
/// Flutter 手机端与桌面端按 lustone（biz_operator）信息架构，这些入口不放。
const restrictedMenuPrefixes = <String>[
  '/system',
  '/monitor',
  '/tool',
  '/analysis',
];

bool isRestrictedMenuPath(String rawPath) {
  final path = rawPath.split('?').first;
  for (final prefix in restrictedMenuPrefixes) {
    if (path == prefix || path.startsWith('$prefix/')) return true;
  }
  return false;
}

Set<String> visibleMenuPaths(List<RouterNode> nodes) => {
      for (final leaf in flattenLeaves(nodes)) leaf.path,
    };

/// 侧栏/抽屉去掉系统管理树，只留业务菜单。
List<RouterNode> clientVisibleRouters(List<RouterNode> nodes, {String parent = ''}) {
  final out = <RouterNode>[];
  for (final node in nodes) {
    if (node.hidden) continue;
    final full = joinRoute(parent, node.path);
    if (isRestrictedMenuPath(full)) continue;
    final children = clientVisibleRouters(node.children, parent: full);
    if (node.children.isNotEmpty && children.isEmpty) continue;
    out.add(
      RouterNode(
        name: node.name,
        path: node.path,
        hidden: node.hidden,
        redirect: node.redirect,
        component: node.component,
        alwaysShow: node.alwaysShow,
        meta: node.meta,
        children: children,
      ),
    );
  }
  return out;
}

bool menuAllows(Set<String> allowed, String rawPath) {
  final path = rawPath.split('?').first;
  if (path.isEmpty || path == '/portal' || path == '/user/profile' || path == '/gateway') {
    return true;
  }
  // 手机/桌面不放若依系统设置，即使用户角色里有这些菜单。
  if (isRestrictedMenuPath(path)) return false;
  if (allowed.contains(path)) return true;

  // 后台首页 /index 仅当 getRouters 明确下发；加载中不闪出。
  if (path == '/index' || path == '/dashboard') {
    return allowed.contains('/index') || allowed.contains('/dashboard');
  }

  // 菜单尚未返回时，不误拦业务页。
  if (allowed.isEmpty) return true;

  final segs = path.split('/').where((s) => s.isNotEmpty).toList();
  if (segs.isEmpty) return false;
  final module = '/${segs.first}';
  return allowed.any((a) => a == module || a.startsWith('$module/'));
}

List<MenuLeaf> flattenLeaves(List<RouterNode> nodes, {String parent = ''}) {
  final out = <MenuLeaf>[];
  for (final node in nodes) {
    final full = joinRoute(parent, node.path);
    if (node.children.isNotEmpty) {
      out.addAll(flattenLeaves(node.children, parent: full));
    } else if (!node.hidden && node.path.isNotEmpty) {
      out.add(MenuLeaf(path: full, title: node.title, icon: node.meta.icon));
    }
  }
  return out;
}

String? titleOfPath(List<RouterNode> nodes, String path, {String parent = ''}) {
  for (final node in nodes) {
    final full = joinRoute(parent, node.path);
    if (full == path) return node.title;
    final nested = titleOfPath(node.children, path, parent: full);
    if (nested != null) return nested;
  }
  return null;
}

IconData ruoyiIcon(String? name) {
  switch (name) {
    case 'user':
      return Icons.person_outline;
    case 'peoples':
      return Icons.groups_outlined;
    case 'tree':
      return Icons.account_tree_outlined;
    case 'tree-table':
      return Icons.list_alt;
    case 'post':
      return Icons.badge_outlined;
    case 'dict':
      return Icons.menu_book_outlined;
    case 'edit':
      return Icons.tune;
    case 'message':
      return Icons.notifications_outlined;
    case 'log':
      return Icons.article_outlined;
    case 'monitor':
      return Icons.monitor_heart_outlined;
    case 'online':
      return Icons.sensors;
    case 'job':
      return Icons.schedule;
    case 'druid':
      return Icons.storage;
    case 'server':
      return Icons.dns_outlined;
    case 'redis':
    case 'redis-list':
      return Icons.memory;
    case 'build':
      return Icons.construction;
    case 'code':
      return Icons.code;
    case 'swagger':
      return Icons.api;
    case 'chart':
    case 'date-range':
      return Icons.candlestick_chart_outlined;
    case 'guide':
      return Icons.psychology_outlined;
    case 'money':
      return Icons.payments_outlined;
    case 'system':
      return Icons.settings_outlined;
    case 'tool':
      return Icons.build_outlined;
    case 'nested':
      return Icons.account_tree;
    case 'education':
      return Icons.school_outlined;
    case 'checkbox':
      return Icons.check_box_outlined;
    case 'international':
      return Icons.public;
    case 'list':
      return Icons.view_list_outlined;
    case 'star':
      return Icons.star_outline;
    case 'eye':
      return Icons.visibility_outlined;
    case 'example':
      return Icons.widgets_outlined;
    case 'component':
      return Icons.grid_view_outlined;
    case 'dashboard':
      return Icons.dashboard_outlined;
    case 'time-range':
      return Icons.timeline;
    case 'cascader':
      return Icons.filter_list;
    case 'skill':
      return Icons.auto_graph;
    case 'tab':
      return Icons.tab;
    case 'bug':
      return Icons.bug_report_outlined;
    case 'clipboard':
      return Icons.assignment_outlined;
    case 'people':
      return Icons.person_outline;
    case 'phone':
      return Icons.phone_iphone;
    case 'email':
      return Icons.mail_outline;
    case 'qq':
    case 'wechat':
      return Icons.chat_bubble_outline;
    default:
      return Icons.circle_outlined;
  }
}
