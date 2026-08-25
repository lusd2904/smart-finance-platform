import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../core/gateway/gateway_controller.dart';
import '../../features/auth/logic/session_controller.dart';
import '../../shared/widgets/ruoyi_ui.dart';
import 'json_list_page.dart';

class SystemUserPage extends StatelessWidget {
  const SystemUserPage({super.key});

  @override
  Widget build(BuildContext context) {
    return const JsonListPage(
      title: '用户管理',
      path: '/system/user/list',
      filters: [
        QueryField('userName', '用户名'),
        QueryField('phonenumber', '手机号'),
        QueryField('status', '状态', options: [('正常', '0'), ('停用', '1')]),
      ],
      columns: [
        TableCol('编号', 'userId'),
        TableCol('用户名', 'userName'),
        TableCol('昵称', 'nickName'),
        TableCol('部门', 'dept.deptName'),
        TableCol('手机', 'phonenumber'),
        TableCol('状态', 'status'),
        TableCol('创建', 'createTime'),
      ],
    );
  }
}

class SystemRolePage extends StatelessWidget {
  const SystemRolePage({super.key});

  @override
  Widget build(BuildContext context) {
    return const JsonListPage(
      title: '角色管理',
      path: '/system/role/list',
      filters: [QueryField('roleName', '角色名称')],
      columns: [
        TableCol('编号', 'roleId'),
        TableCol('名称', 'roleName'),
        TableCol('权限字符', 'roleKey'),
        TableCol('排序', 'roleSort'),
        TableCol('状态', 'status'),
        TableCol('创建', 'createTime'),
      ],
    );
  }
}

class SystemMenuPage extends StatelessWidget {
  const SystemMenuPage({super.key});

  @override
  Widget build(BuildContext context) {
    return const JsonListPage(
      title: '菜单管理',
      path: '/system/menu/list',
      paged: false,
      columns: [
        TableCol('名称', 'menuName'),
        TableCol('排序', 'orderNum'),
        TableCol('路由', 'path'),
        TableCol('组件', 'component'),
        TableCol('权限', 'perms'),
        TableCol('类型', 'menuType'),
        TableCol('可见', 'visible'),
      ],
    );
  }
}

class SystemDeptPage extends StatelessWidget {
  const SystemDeptPage({super.key});

  @override
  Widget build(BuildContext context) {
    return const JsonListPage(
      title: '部门管理',
      path: '/system/dept/list',
      paged: false,
      columns: [
        TableCol('名称', 'deptName'),
        TableCol('排序', 'orderNum'),
        TableCol('负责人', 'leader'),
        TableCol('状态', 'status'),
      ],
    );
  }
}

class SystemPostPage extends StatelessWidget {
  const SystemPostPage({super.key});

  @override
  Widget build(BuildContext context) {
    return const JsonListPage(
      title: '岗位管理',
      path: '/system/post/list',
      columns: [
        TableCol('编号', 'postId'),
        TableCol('编码', 'postCode'),
        TableCol('名称', 'postName'),
        TableCol('排序', 'postSort'),
        TableCol('状态', 'status'),
      ],
    );
  }
}

class SystemDictPage extends StatelessWidget {
  const SystemDictPage({super.key});

  @override
  Widget build(BuildContext context) {
    return const JsonListPage(
      title: '字典管理',
      path: '/system/dict/type/list',
      columns: [
        TableCol('编号', 'dictId'),
        TableCol('名称', 'dictName'),
        TableCol('类型', 'dictType'),
        TableCol('状态', 'status'),
        TableCol('备注', 'remark'),
      ],
    );
  }
}

class SystemConfigPage extends StatelessWidget {
  const SystemConfigPage({super.key});

  @override
  Widget build(BuildContext context) {
    return const JsonListPage(
      title: '参数设置',
      path: '/system/config/list',
      filters: [QueryField('configKey', '参数键名'), QueryField('configName', '参数名称')],
      columns: [
        TableCol('编号', 'configId'),
        TableCol('名称', 'configName'),
        TableCol('键名', 'configKey'),
        TableCol('键值', 'configValue'),
        TableCol('系统', 'configType'),
      ],
    );
  }
}

class SystemNoticePage extends StatelessWidget {
  const SystemNoticePage({super.key});

  @override
  Widget build(BuildContext context) {
    return const JsonListPage(
      title: '通知公告',
      path: '/system/notice/list',
      columns: [
        TableCol('编号', 'noticeId'),
        TableCol('标题', 'noticeTitle'),
        TableCol('类型', 'noticeType'),
        TableCol('状态', 'status'),
        TableCol('时间', 'createTime'),
      ],
    );
  }
}

class MonitorOnlinePage extends StatelessWidget {
  const MonitorOnlinePage({super.key});

  @override
  Widget build(BuildContext context) {
    return const JsonListPage(
      title: '在线用户',
      path: '/monitor/online/list',
      columns: [
        TableCol('会话', 'tokenId'),
        TableCol('用户', 'userName'),
        TableCol('IP', 'ipaddr'),
        TableCol('地点', 'loginLocation'),
        TableCol('浏览器', 'browser'),
        TableCol('时间', 'loginTime'),
      ],
    );
  }
}

class MonitorJobPage extends StatelessWidget {
  const MonitorJobPage({super.key, this.open});
  final OpenRoute? open;

  @override
  Widget build(BuildContext context) {
    return JsonListPage(
      title: '定时任务',
      path: '/monitor/job/list',
      columns: const [
        TableCol('编号', 'jobId'),
        TableCol('名称', 'jobName'),
        TableCol('分组', 'jobGroup'),
        TableCol('调用', 'invokeTarget'),
        TableCol('Cron', 'cronExpression'),
        TableCol('状态', 'status'),
      ],
      rowActions: (row, reload) => [
        TextButton(
          onPressed: () => open?.call(
            '/monitor/job-log?jobId=${row['jobId']}',
            title: '调度日志',
          ),
          child: const Text('日志'),
        ),
      ],
    );
  }
}

class MonitorJobLogPage extends StatelessWidget {
  const MonitorJobLogPage({super.key, this.jobId});
  final String? jobId;

  @override
  Widget build(BuildContext context) {
    return JsonListPage(
      title: '调度日志',
      path: '/monitor/jobLog/list',
      extraQuery: {if (jobId != null) 'jobId': jobId},
      columns: const [
        TableCol('编号', 'jobLogId'),
        TableCol('任务', 'jobName'),
        TableCol('分组', 'jobGroup'),
        TableCol('状态', 'status'),
        TableCol('信息', 'jobMessage'),
        TableCol('时间', 'createTime'),
      ],
    );
  }
}

class MonitorOperlogPage extends StatelessWidget {
  const MonitorOperlogPage({super.key});

  @override
  Widget build(BuildContext context) {
    return const JsonListPage(
      title: '操作日志',
      path: '/monitor/operlog/list',
      columns: [
        TableCol('编号', 'operId'),
        TableCol('标题', 'title'),
        TableCol('方法', 'method'),
        TableCol('操作人', 'operName'),
        TableCol('IP', 'operIp'),
        TableCol('状态', 'status'),
        TableCol('时间', 'operTime'),
      ],
    );
  }
}

class MonitorLoginPage extends StatelessWidget {
  const MonitorLoginPage({super.key});

  @override
  Widget build(BuildContext context) {
    return const JsonListPage(
      title: '登录日志',
      path: '/monitor/logininfor/list',
      columns: [
        TableCol('编号', 'infoId'),
        TableCol('用户', 'userName'),
        TableCol('IP', 'ipaddr'),
        TableCol('地点', 'loginLocation'),
        TableCol('状态', 'status'),
        TableCol('信息', 'msg'),
        TableCol('时间', 'loginTime'),
      ],
    );
  }
}

class MonitorServerPage extends StatelessWidget {
  const MonitorServerPage({super.key});

  @override
  Widget build(BuildContext context) {
    return const JsonDetailPage(title: '服务监控', path: '/monitor/server');
  }
}

class MonitorCachePage extends StatelessWidget {
  const MonitorCachePage({super.key});

  @override
  Widget build(BuildContext context) {
    return const JsonDetailPage(title: '缓存监控', path: '/monitor/cache');
  }
}

class MonitorCacheListPage extends StatelessWidget {
  const MonitorCacheListPage({super.key});

  @override
  Widget build(BuildContext context) {
    return const JsonListPage(
      title: '缓存列表',
      path: '/monitor/cache/getNames',
      paged: false,
    );
  }
}

class MonitorDruidPage extends ConsumerWidget {
  const MonitorDruidPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final gw = ref.watch(gatewayController).url;
    final url = '$gw/docker-api/druid/index.html';
    return AppPage(
      child: ElCard(
        header: const Text('数据监控 Druid'),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('原生客户端不嵌网页。本机自用可在浏览器打开 Druid 控制台：'),
            const SizedBox(height: 8),
            SelectableText(url),
            const SizedBox(height: 12),
            FilledButton(
              onPressed: () => launchUrl(Uri.parse(url)),
              child: const Text('在浏览器打开'),
            ),
          ],
        ),
      ),
    );
  }
}

class MonitorCryptoPage extends StatelessWidget {
  const MonitorCryptoPage({super.key});

  @override
  Widget build(BuildContext context) {
    return const JsonDetailPage(title: '传输加密', path: '/monitor/transportCrypto');
  }
}

class ToolGenPage extends StatelessWidget {
  const ToolGenPage({super.key});

  @override
  Widget build(BuildContext context) {
    return const JsonListPage(
      title: '代码生成',
      path: '/tool/gen/list',
      columns: [
        TableCol('表名', 'tableName'),
        TableCol('注释', 'tableComment'),
        TableCol('实体', 'className'),
        TableCol('时间', 'createTime'),
      ],
    );
  }
}

class ToolBuildPage extends StatelessWidget {
  const ToolBuildPage({super.key});

  @override
  Widget build(BuildContext context) {
    return const AppPage(
      child: ElCard(
        header: Text('表单构建'),
        child: EmptyHint('表单构建器是网页拖拽工具，原生端不提供可视化搭建。'),
      ),
    );
  }
}

class ToolSwaggerPage extends ConsumerWidget {
  const ToolSwaggerPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final gw = ref.watch(gatewayController).url;
    final url = '$gw/docker-api/docs';
    return AppPage(
      child: ElCard(
        header: const Text('系统接口'),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('OpenAPI 文档在浏览器中打开：'),
            const SizedBox(height: 8),
            SelectableText(url),
            const SizedBox(height: 12),
            FilledButton(
              onPressed: () => launchUrl(Uri.parse(url)),
              child: const Text('打开文档'),
            ),
          ],
        ),
      ),
    );
  }
}

class ProfilePage extends ConsumerWidget {
  const ProfilePage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final session = ref.watch(sessionController);
    final user = session.user;
    final gateway = ref.watch(gatewayController);
    return AppPage(
      child: ListView(
        children: [
          ElCard(
            header: const Text('账号'),
            child: KvGrid({
              '用户名': user?.userName ?? '',
              '昵称': user?.nickName ?? '',
              '角色': session.roles.join('、'),
            }),
          ),
          const SizedBox(height: 12),
          ElCard(
            header: const Text('设置'),
            padding: EdgeInsets.zero,
            child: Column(
              children: [
                ListTile(
                  leading: const Icon(Icons.dns_outlined),
                  title: const Text('网关'),
                  subtitle: Text(
                    gateway.url.isEmpty ? '未配置' : gateway.url,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: () => context.go('/gateway'),
                ),
                ListTile(
                  leading: const Icon(Icons.logout),
                  title: const Text('退出登录'),
                  onTap: () async {
                    final ok = await confirm(context, '确定退出登录吗？');
                    if (!ok) return;
                    await ref.read(sessionController.notifier).logout();
                    if (context.mounted) context.go('/login');
                  },
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class UnknownRoutePage extends StatelessWidget {
  const UnknownRoutePage(this.path, {super.key});
  final String path;

  @override
  Widget build(BuildContext context) {
    return AppPage(
      child: ElCard(
        header: const Text('页面未注册'),
        child: Text('原生客户端没有对应实现：$path'),
      ),
    );
  }
}
