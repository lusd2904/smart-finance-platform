import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_client.dart';
import '../../../core/theme/app_theme.dart';
import '../../../shared/widgets/page_header.dart';
import '../../../shared/widgets/ruoyi_ui.dart';
import '../../../shared/widgets/stat_grid.dart';
import '../../sentiment/data/sentiment_api.dart';
import '../../sentiment/data/sentiment_models.dart';
import '../../sentiment/presentation/sentiment_page.dart';

/// 手机/桌面「AI研判」：对齐 Web 工作台首页的「最新舆情研判」，展示已有结论。
class AiPage extends ConsumerWidget {
  const AiPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final board = ref.watch(sentimentBoardProvider);
    return Scaffold(
      body: RefreshIndicator(
        onRefresh: () async => ref.refresh(sentimentBoardProvider.future),
        child: ListView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.only(bottom: 24),
          children: [
            const PageHeader(title: 'AI 研判', subtitle: '最新舆情研判结果'),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: AppDimens.pagePadding),
              child: board.when(
                loading: () => const SizedBox(
                  height: 240,
                  child: Center(child: CircularProgressIndicator()),
                ),
                error: (e, _) => ErrorView(
                  error: describeApiError(e),
                  onRetry: () => ref.invalidate(sentimentBoardProvider),
                ),
                data: (data) => _HomeVerdict(latest: data.latest),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _HomeVerdict extends StatelessWidget {
  const _HomeVerdict({required this.latest});
  final SentimentAnalysis? latest;

  @override
  Widget build(BuildContext context) {
    if (latest == null) {
      return const Padding(
        padding: EdgeInsets.only(top: 80),
        child: EmptyHint('暂无舆情分析，可先到舆情大盘查看采集进度'),
      );
    }
    final a = latest!;
    final theme = Theme.of(context);
    final markets = [
      ('美股', a.usDirection, a.usScore),
      ('港股', a.hkDirection, a.hkScore),
      ('A股', a.aDirection, a.aScore),
    ];
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        SectionCard(
          title: '最新舆情研判',
          subtitle: [
            if (a.modelName.isNotEmpty) a.modelName,
            if (a.createTime.isNotEmpty) a.createTime,
          ].join(' · '),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (a.summary.isNotEmpty)
                Text(a.summary, style: theme.textTheme.bodyMedium?.copyWith(height: 1.7)),
              const SizedBox(height: 14),
              Row(
                children: [
                  for (var i = 0; i < markets.length; i++) ...[
                    if (i > 0) const SizedBox(width: 8),
                    Expanded(child: _ScoreBox(name: markets[i].$1, direction: markets[i].$2, score: markets[i].$3)),
                  ],
                ],
              ),
            ],
          ),
        ),
        if (a.riskEvents.isNotEmpty) ...[
          const SizedBox(height: 12),
          RiskEventsCard(events: a.riskEvents),
        ],
      ],
    );
  }
}

class _ScoreBox extends StatelessWidget {
  const _ScoreBox({required this.name, required this.direction, required this.score});
  final String name;
  final String direction;
  final double? score;

  @override
  Widget build(BuildContext context) {
    final dir = SentimentDirection.fromRaw(direction);
    final Color bg;
    final Color border;
    final Color val;
    switch (dir) {
      case SentimentDirection.up:
        bg = AppColors.up.withValues(alpha: 0.12);
        border = AppColors.up.withValues(alpha: 0.35);
        val = AppColors.up;
      case SentimentDirection.down:
        bg = AppColors.down.withValues(alpha: 0.12);
        border = AppColors.down.withValues(alpha: 0.35);
        val = AppColors.down;
      default:
        bg = Theme.of(context).colorScheme.surfaceContainerHighest;
        border = Theme.of(context).colorScheme.outlineVariant;
        val = Theme.of(context).colorScheme.onSurface;
    }
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 8),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: border),
      ),
      child: Column(
        children: [
          Text(name, style: Theme.of(context).textTheme.labelSmall),
          const SizedBox(height: 4),
          Text(
            score == null ? '--' : score!.toStringAsFixed(0),
            style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                  fontWeight: FontWeight.w800,
                  color: val,
                  fontFeatures: AppNum.fontFeatures,
                ),
          ),
          const SizedBox(height: 2),
          Text(
            direction.isEmpty ? '暂无' : direction,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: Theme.of(context).textTheme.labelSmall,
          ),
        ],
      ),
    );
  }
}
