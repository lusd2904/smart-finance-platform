import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/theme/app_theme.dart';
import '../../../shared/utils/format.dart';
import '../../../shared/widgets/page_header.dart';
import '../data/notice_api.dart';
import '../data/notice_models.dart';
import '../../sentiment/presentation/sentiment_page.dart' show ErrorView;

/// 通知中心：应用内通知列表（30s 轮询）+ 单条/全部已读。
/// 设计依据：设计稿 §3.8 分组卡片风格；规划文档 M2「应用内轮询」。
class NoticePage extends ConsumerWidget {
  const NoticePage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final board = ref.watch(noticeBoardProvider);
    return Scaffold(
      body: RefreshIndicator(
        onRefresh: () async => ref.invalidate(noticeBoardProvider),
        child: ListView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.only(bottom: 24),
          children: [
            PageHeader(
              title: '通知中心',
              subtitle: board.value == null
                  ? '加载中…'
                  : '${board.value!.items.length} 条通知 · ${board.value!.unread} 未读',
            ),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: AppDimens.pagePadding),
              child: board.when(
                loading: () => const SizedBox(
                  height: 240,
                  child: Center(child: CircularProgressIndicator()),
                ),
                error: (e, _) => ErrorView(
                  error: '$e',
                  onRetry: () => ref.invalidate(noticeBoardProvider),
                ),
                data: (data) {
                  if (data.items.isEmpty) {
                    return Padding(
                      padding: const EdgeInsets.only(top: 120),
                      child: Center(
                        child: Column(
                          children: [
                            Icon(Icons.notifications_off_outlined,
                                size: 48,
                                color: Theme.of(context).colorScheme.outline),
                            const SizedBox(height: 12),
                            Text('暂无通知',
                                style: Theme.of(context).textTheme.bodyMedium),
                          ],
                        ),
                      ),
                    );
                  }
                  return Column(
                    children: [
                      Align(
                        alignment: Alignment.centerRight,
                        child: TextButton.icon(
                          onPressed: data.unread == 0
                              ? null
                              : () async {
                                  await ref.read(noticeApiProvider).markRead();
                                  ref.invalidate(noticeBoardProvider);
                                },
                          icon: const Icon(Icons.done_all_rounded, size: 18),
                          label: const Text('全部已读'),
                        ),
                      ),
                      const SizedBox(height: 4),
                      for (final n in data.items)
                        NoticeTile(
                          notice: n,
                          onOpen: () async {
                            if (!n.read) {
                              await ref.read(noticeApiProvider).markRead(id: n.id);
                              ref.invalidate(noticeBoardProvider);
                            }
                          },
                        ),
                    ],
                  );
                },
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// 级别 → 图标与色。告警红走主题错误色；
/// AppColors.up/down 是行情「涨/跌」专用语义，不得挪作状态色。
(Color, IconData) levelStyle(String level, ColorScheme scheme) {
  switch (level.toLowerCase()) {
    case 'success':
      return (AppColors.brand, Icons.check_circle_outline);
    case 'error':
    case 'critical':
      return (scheme.error, Icons.error_outline);
    case 'warn':
    case 'warning':
      return (AppColors.warn, Icons.warning_amber_outlined);
    default:
      return (AppColors.brand, Icons.info_outline);
  }
}

/// 通知条目：级别图标 + 分类 chip + 标题/正文 + 时间；未读加粗带点。
class NoticeTile extends StatelessWidget {
  const NoticeTile({super.key, required this.notice, this.onOpen});

  final NoticeItem notice;
  final VoidCallback? onOpen;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final (color, icon) = levelStyle(notice.level, scheme);
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: InkWell(
        borderRadius: BorderRadius.circular(AppDimens.radiusCard),
        onTap: onOpen,
        child: Container(
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            color: scheme.surfaceContainerLow,
            borderRadius: BorderRadius.circular(AppDimens.radiusCard),
            border: Border.all(color: scheme.outlineVariant),
          ),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(icon, size: 20, color: color),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        if (!notice.read)
                          Container(
                            width: 7,
                            height: 7,
                            margin: const EdgeInsets.only(right: 6),
                            decoration: BoxDecoration(
                              color: scheme.primary,
                              shape: BoxShape.circle,
                            ),
                          ),
                        Expanded(
                          child: Text(
                            notice.title,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: theme.textTheme.titleSmall?.copyWith(
                              fontWeight:
                                  notice.read ? FontWeight.w500 : FontWeight.w700,
                            ),
                          ),
                        ),
                        if (notice.category.isNotEmpty) ...[
                          const SizedBox(width: 6),
                          Container(
                            padding: const EdgeInsets.symmetric(
                                horizontal: 6, vertical: 2),
                            decoration: BoxDecoration(
                              color: scheme.surfaceContainerHighest
                                  .withValues(alpha: 0.5),
                              borderRadius: BorderRadius.circular(6),
                            ),
                            child: Text(
                              notice.category,
                              style: theme.textTheme.labelSmall,
                            ),
                          ),
                        ],
                      ],
                    ),
                    if (notice.content.isNotEmpty) ...[
                      const SizedBox(height: 4),
                      Text(
                        notice.content,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: theme.textTheme.bodySmall?.copyWith(
                          color: scheme.onSurfaceVariant,
                          height: 1.45,
                        ),
                      ),
                    ],
                    const SizedBox(height: 6),
                    Text(
                      formatRelativeTime(notice.createTime),
                      style: AppNum.style(theme.textTheme.labelSmall!).copyWith(
                        color: scheme.onSurfaceVariant,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
