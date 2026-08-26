import 'package:flutter/material.dart';

import '../../core/theme/app_theme.dart';

/// 页面统一头部：大标题 + 副题 + 尾部动作区。
/// 手机底栏已标明当前页，不再重复放标题。
class PageHeader extends StatelessWidget {
  const PageHeader({
    super.key,
    required this.title,
    this.subtitle,
    this.actions,
  });

  final String title;
  final String? subtitle;
  final List<Widget>? actions;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final phone = !AppDimens.isWide(context);
    // 手机底栏已标明当前页，不再重复放标题。
    if (phone) {
      if (actions == null || actions!.isEmpty) return const SizedBox.shrink();
      return Padding(
        padding: const EdgeInsets.fromLTRB(16, 8, 16, 4),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.end,
          children: actions!,
        ),
      );
    }
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 18, 20, 6),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: theme.textTheme.headlineSmall?.copyWith(
                    fontWeight: FontWeight.w800,
                  ),
                ),
                if (subtitle != null) ...[
                  const SizedBox(height: 3),
                  Text(
                    subtitle!,
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: theme.colorScheme.onSurfaceVariant,
                    ),
                  ),
                ],
              ],
            ),
          ),
          if (actions != null) ...[const SizedBox(width: 12), ...actions!],
        ],
      ),
    );
  }
}
