import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/gateway/gateway_controller.dart';
import '../../core/theme/app_theme.dart';
import '../../features/auth/logic/session_controller.dart';
import '../../shared/widgets/ruoyi_ui.dart';
import 'phone_quant_page.dart';

/// 「我的」：次级入口。底栏是舆情 / 选股 / 热度 / 持仓。
class PhoneMinePage extends ConsumerWidget {
  const PhoneMinePage({super.key, this.open, this.onOpenSymbol});
  final OpenRoute? open;
  final void Function(String symbol, String market, String name)? onOpenSymbol;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final session = ref.watch(sessionController);
    final user = session.user;
    final gateway = ref.watch(gatewayController);
    final name = user?.nickName ?? user?.userName ?? '未登录';
    final scheme = Theme.of(context).colorScheme;

    void push(Widget page, {String title = '', bool wrapped = true}) {
      Navigator.of(context).push(
        MaterialPageRoute<void>(
          builder: (_) => wrapped
              ? Scaffold(appBar: AppBar(title: Text(title)), body: page)
              : page,
        ),
      );
    }

    Widget group(String title, List<Widget> children) {
      return Padding(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Padding(
              padding: const EdgeInsets.only(left: 4, bottom: 8),
              child: Text(
                title,
                style: Theme.of(context).textTheme.labelMedium?.copyWith(
                      color: scheme.onSurfaceVariant,
                    ),
              ),
            ),
            DecoratedBox(
              decoration: BoxDecoration(
                color: scheme.surfaceContainerLow,
                borderRadius: BorderRadius.circular(AppDimens.radiusCard),
                border: Border.all(color: scheme.outlineVariant),
              ),
              child: Column(children: children),
            ),
          ],
        ),
      );
    }

    Widget tile(IconData icon, String title, VoidCallback onTap, {String? subtitle}) {
      return Material(
        color: Colors.transparent,
        child: ListTile(
          leading: Icon(icon, size: 22),
          title: Text(title),
          subtitle: subtitle == null ? null : Text(subtitle, maxLines: 1, overflow: TextOverflow.ellipsis),
          trailing: const Icon(Icons.chevron_right, size: 18),
          onTap: onTap,
        ),
      );
    }

    return ListView(
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(20, 20, 20, 8),
          child: Row(
            children: [
              CircleAvatar(
                radius: 28,
                backgroundColor: AppColors.brand,
                child: Text(
                  name.isEmpty ? 'U' : name.characters.first,
                  style: const TextStyle(color: Colors.white, fontSize: 22, fontWeight: FontWeight.w700),
                ),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(name, style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w800)),
                    const SizedBox(height: 4),
                    Text(
                      user?.userName ?? '',
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(color: scheme.onSurfaceVariant),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
        group('功能', [
          tile(Icons.hub_outlined, '量化研究', () => push(PhoneQuantPage(onOpenSymbol: onOpenSymbol), title: '量化研究')),
          tile(Icons.forum_outlined, '需求沟通', () => open?.call('/ai/req-chat', title: '需求沟通')),
          tile(
            Icons.dns_outlined,
            '网关探测',
            () => context.go('/gateway'),
            subtitle: gateway.url.isEmpty ? '未配置' : gateway.url,
          ),
        ]),
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 24, 16, 32),
          child: OutlinedButton(
            style: OutlinedButton.styleFrom(
              foregroundColor: AppColors.up,
              side: const BorderSide(color: AppColors.up),
              minimumSize: const Size.fromHeight(48),
            ),
            onPressed: () async {
              final ok = await confirm(context, '确定退出登录吗？');
              if (!ok) return;
              await ref.read(sessionController.notifier).logout();
              if (context.mounted) context.go('/login');
            },
            child: const Text('退出登录'),
          ),
        ),
      ],
    );
  }
}
