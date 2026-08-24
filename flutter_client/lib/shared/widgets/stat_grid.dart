import 'package:flutter/material.dart';

import '../../core/theme/app_theme.dart';

/// 统计卡数据：标签 + 数值（任意 Widget，通常为 Text/PctText）+ 可选脚注。
class StatCellData {
  const StatCellData({required this.label, required this.value, this.hint});

  final String label;
  final Widget value;
  final String? hint;
}

/// 统计卡行：响应式列数 —— <600 两列、<900 三列、其余四列。
/// 行情看板 / 自选概览等「数字面板」场景统一用它。
class StatGrid extends StatelessWidget {
  const StatGrid({super.key, required this.cells});

  final List<StatCellData> cells;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final w = constraints.maxWidth;
        final columns = w < 600 ? 2 : (w < 900 ? 3 : 4);
        return GridView.count(
          crossAxisCount: columns,
          mainAxisSpacing: 10,
          crossAxisSpacing: 10,
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          childAspectRatio: _aspectFor(w, columns),
          children: [for (final c in cells) _StatCard(data: c)],
        );
      },
    );
  }

  /// 卡片偏扁：宽度越宽、列越多时压得越扁。
  static double _aspectFor(double width, int columns) {
    final cellWidth = (width - (columns - 1) * 10) / columns;
    return (cellWidth / 92).clamp(1.4, 2.8);
  }
}

class _StatCard extends StatelessWidget {
  const _StatCard({required this.data});

  final StatCellData data;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainerLow,
        borderRadius: BorderRadius.circular(AppDimens.radiusCard),
        border: Border.all(color: theme.colorScheme.outlineVariant),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Text(
            data.label,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: theme.textTheme.bodySmall?.copyWith(
              color: theme.colorScheme.onSurfaceVariant,
            ),
          ),
          const SizedBox(height: 5),
          FittedBox(
            fit: BoxFit.scaleDown,
            alignment: Alignment.centerLeft,
            child: DefaultTextStyle.merge(
              style:
                  AppNum.style(theme.textTheme.titleLarge ?? const TextStyle())
                      .copyWith(fontWeight: FontWeight.w700),
              child: data.value,
            ),
          ),
          if (data.hint != null) ...[
            const SizedBox(height: 3),
            Text(
              data.hint!,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: theme.textTheme.bodySmall?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
                fontSize: 11,
              ),
            ),
          ],
        ],
      ),
    );
  }
}

/// 分区卡：统一「标题 + 副题 + 尾部动作」头部与内容留白。
/// 看板区块、列表容器、表单分组一律套用，替代散落的 Card + 手写标题。
class SectionCard extends StatelessWidget {
  const SectionCard({
    super.key,
    required this.child,
    this.title,
    this.subtitle,
    this.action,
    this.padding = const EdgeInsets.all(16),
  });

  final Widget child;
  final String? title;
  final String? subtitle;
  final Widget? action;
  final EdgeInsetsGeometry padding;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Card(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (title != null)
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 14, 16, 0),
              child: Row(
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          title!,
                          style: theme.textTheme.titleMedium?.copyWith(
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                        if (subtitle != null) ...[
                          const SizedBox(height: 2),
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
                  ?action,
                ],
              ),
            ),
          Padding(padding: padding, child: child),
        ],
      ),
    );
  }
}
