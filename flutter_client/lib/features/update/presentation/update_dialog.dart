
import 'package:flutter/material.dart';

import '../../../core/theme/app_theme.dart';
import '../data/update_api.dart';
import '../data/update_models.dart';

/// 升级提示弹窗：
/// - forceUpdate：barrier 不可关闭、无「稍后」，仅「立即下载」；
/// - 可选升级：可关闭，本会话不再重复弹出（由调用方持有 dismissed 标记）。
Future<void> showUpdateDialog(
  BuildContext context, {
  required UpdateCheck check,
}) async {
  await showDialog<void>(
    context: context,
    barrierDismissible: !check.forceUpdate,
    builder: (context) => PopScope(
      canPop: !check.forceUpdate,
      child: AlertDialog(
        title: const Text('发现新版本'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.baseline,
              textBaseline: TextBaseline.alphabetic,
              children: [
                Text(
                  'v${check.latestVersion}',
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    color: AppColors.brand,
                    fontFeatures: const [FontFeature.tabularFigures()],
                  ),
                ),
                const SizedBox(width: 8),
                Text(
                  '当前 v${check.currentVersion}',
                  style: Theme.of(context).textTheme.labelSmall?.copyWith(
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
                ),
              ],
            ),
            if (check.notes.isNotEmpty) ...[
              const SizedBox(height: 10),
              Text(
                check.notes,
                style: Theme.of(context).textTheme.bodySmall
                    ?.copyWith(height: 1.5),
              ),
            ],
            if (check.forceUpdate) ...[
              const SizedBox(height: 12),
              Text(
                '该版本过旧，为保障数据与交易安全需先升级后使用。',
                style: Theme.of(context).textTheme.bodySmall
                    ?.copyWith(color: AppColors.warn),
              ),
            ],
          ],
        ),
        actions: [
          if (!check.forceUpdate)
            TextButton(
              onPressed: () => Navigator.of(context).pop(),
              child: const Text('稍后再说'),
            ),
          FilledButton.icon(
            onPressed: () {
              launchDownload(check.downloadUrl);
              // 强更时留在弹窗内（未升级不可用）；弱更直接关闭。
              if (!check.forceUpdate && context.mounted) {
                Navigator.of(context).pop();
              }
            },
            icon: const Icon(Icons.download_rounded, size: 18),
            label: const Text('立即下载'),
          ),
        ],
      ),
    ),
  );
}
