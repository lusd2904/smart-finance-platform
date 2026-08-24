import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/theme/app_theme.dart';
import '../../../shared/charts/sentiment_gauge.dart';
import '../../../shared/charts/trend_line.dart';
import '../../../shared/widgets/page_header.dart';
import '../data/sentiment_api.dart';
import '../data/sentiment_models.dart';

/// 舆情大盘（只读）：情绪仪表盘 + 三市场研判卡 + 历史走势 + 风险事件。
/// 设计依据：设计稿 §3.4.1 舆情大盘 / §3.4.3 移动端置顶仪表盘。
class SentimentPage extends ConsumerWidget {
  const SentimentPage({super.key});

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
            const PageHeader(title: '舆情大盘', subtitle: '三市场情绪综合监测'),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: AppDimens.pagePadding),
              child: board.when(
                loading: () => const SizedBox(
                  height: 240,
                  child: Center(child: CircularProgressIndicator()),
                ),
                error: (e, _) => ErrorView(error: '$e',
                    onRetry: () => ref.invalidate(sentimentBoardProvider)),
                data: (data) => _BoardBody(latest: data.latest, trend: data.trend),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _BoardBody extends StatelessWidget {
  const _BoardBody({required this.latest, required this.trend});

  final SentimentAnalysis? latest;
  final List<SentimentTrendPoint> trend;

  @override
  Widget build(BuildContext context) {
    if (latest == null) {
      return Padding(
        padding: const EdgeInsets.only(top: 120),
        child: Center(
          child: Column(
            children: [
              Icon(Icons.psychology_alt_outlined,
                  size: 48, color: Theme.of(context).colorScheme.outline),
              const SizedBox(height: 12),
              Text('服务端尚无研判数据，可稍后下拉刷新',
                  style: Theme.of(context).textTheme.bodyMedium),
            ],
          ),
        ),
      );
    }

    final wide = MediaQuery.sizeOf(context).width >= AppDimens.wideBreakpoint;
    final gauge = _GaugeCard(latest: latest!);
    final trendCard = TrendCard(trend: trend);
    Widget verdicts = Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        VerdictCard(name: '美股', directionRaw: latest!.usDirection, score: latest!.usScore, reason: latest!.usReason),
        const SizedBox(height: 8),
        VerdictCard(name: '港股', directionRaw: latest!.hkDirection, score: latest!.hkScore, reason: latest!.hkReason),
        const SizedBox(height: 8),
        VerdictCard(name: 'A股', directionRaw: latest!.aDirection, score: latest!.aScore, reason: latest!.aReason),
        if (latest!.riskEvents.isNotEmpty) ...[
          const SizedBox(height: 8),
          RiskEventsCard(events: latest!.riskEvents),
        ],
      ],
    );

    if (wide) {
      // 桌面双栏：左 38% 仪表盘+走势，右研判与风险事件。
      return Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(flex: 38, child: Column(children: [gauge, const SizedBox(height: 12), trendCard])),
          const SizedBox(width: 12),
          Expanded(flex: 62, child: verdicts),
        ],
      );
    }
    verdicts = verdicts;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        gauge,
        const SizedBox(height: 12),
        trendCard,
        const SizedBox(height: 12),
        verdicts,
      ],
    );
  }
}

class _GaugeCard extends StatelessWidget {
  const _GaugeCard({required this.latest});

  final SentimentAnalysis latest;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: scheme.surfaceContainerLow,
        borderRadius: BorderRadius.circular(AppDimens.radiusCard),
        border: Border.all(color: scheme.outlineVariant),
      ),
      child: Column(
        children: [
          SentimentGauge(score: latest.overallScore ?? 50, size: 220),
          if (latest.summary.isNotEmpty) ...[
            const SizedBox(height: 10),
            Text(
              latest.summary,
              maxLines: 4,
              overflow: TextOverflow.ellipsis,
              textAlign: TextAlign.center,
              style: theme.textTheme.bodyMedium?.copyWith(height: 1.5),
            ),
          ],
        ],
      ),
    );
  }
}

/// 单市场研判卡：名称 + 一句话理由 + 方向徽章 + 分值。
class VerdictCard extends StatelessWidget {
  const VerdictCard({
    super.key,
    required this.name,
    required this.directionRaw,
    required this.score,
    required this.reason,
  });

  final String name;
  final String directionRaw;
  final double? score;
  final String reason;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final dir = SentimentDirection.fromRaw(directionRaw);
    final dirColor = switch (dir) {
      SentimentDirection.up => AppColors.up,
      SentimentDirection.down => AppColors.down,
      _ => AppColors.flat,
    };
    return Container(
      padding: const EdgeInsets.fromLTRB(14, 12, 14, 12),
      decoration: BoxDecoration(
        color: scheme.surfaceContainerLow,
        borderRadius: BorderRadius.circular(AppDimens.radiusCard),
        border: Border.all(color: scheme.outlineVariant),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(width: 3, height: 40, color: dirColor),
          const SizedBox(width: 10),
          SizedBox(
            width: 44,
            child: Text(name, style: theme.textTheme.titleSmall),
          ),
          Expanded(
            child: Text(
              reason.isEmpty ? '暂无研判理由' : reason,
              maxLines: 3,
              overflow: TextOverflow.ellipsis,
              style: theme.textTheme.bodySmall?.copyWith(
                color: scheme.onSurfaceVariant,
                height: 1.45,
              ),
            ),
          ),
          const SizedBox(width: 10),
          DirectionBadge(direction: dir),
          if (score != null)
            Padding(
              padding: const EdgeInsets.only(left: 6),
              child: Text(
                score!.toStringAsFixed(0),
                style: AppNum.style(theme.textTheme.titleMedium!).copyWith(color: dirColor),
              ),
            ),
        ],
      ),
    );
  }
}

/// 方向徽章：利多红 / 利空绿 / 中性灰。
class DirectionBadge extends StatelessWidget {
  const DirectionBadge({super.key, required this.direction});

  final SentimentDirection direction;

  @override
  Widget build(BuildContext context) {
    final color = switch (direction) {
      SentimentDirection.up => AppColors.up,
      SentimentDirection.down => AppColors.down,
      SentimentDirection.flat || SentimentDirection.unknown => AppColors.flat,
    };
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.14),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Text(
        direction.label,
        style: Theme.of(context).textTheme.labelSmall?.copyWith(
              color: color,
              fontWeight: FontWeight.w700,
            ),
      ),
    );
  }
}

class RiskEventsCard extends StatelessWidget {
  const RiskEventsCard({super.key, required this.events});

  final List<String> events;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppColors.warn.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(AppDimens.radiusCard),
        border: Border.all(color: AppColors.warn.withValues(alpha: 0.35)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.warning_amber_rounded, size: 16, color: AppColors.warn),
              const SizedBox(width: 6),
              Text('风险事件', style: theme.textTheme.titleSmall),
            ],
          ),
          const SizedBox(height: 8),
          for (final e in events.take(5))
            Padding(
              padding: const EdgeInsets.only(top: 4),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('· ', style: TextStyle(color: AppColors.warn)),
                  Expanded(
                    child: Text(e, style: theme.textTheme.bodySmall?.copyWith(height: 1.4)),
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }
}

/// 研判走势卡：美/港/A 药丸切换单序列折线。
class TrendCard extends StatefulWidget {
  const TrendCard({super.key, required this.trend});

  final List<SentimentTrendPoint> trend;

  @override
  State<TrendCard> createState() => _TrendCardState();
}

class _TrendCardState extends State<TrendCard> {
  String _market = 'US';

  static const _labels = {'US': '美股', 'HK': '港股', 'CN': 'A股'};
  static const _colors = {'US': AppColors.brand, 'HK': AppColors.warn, 'CN': AppColors.up};

  List<double> get _values {
    double? pick(SentimentTrendPoint p) =>
        switch (_market) {'US' => p.usScore, 'HK' => p.hkScore, _ => p.aScore};
    return [for (final p in widget.trend) if (pick(p) != null) pick(p)!];
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: scheme.surfaceContainerLow,
        borderRadius: BorderRadius.circular(AppDimens.radiusCard),
        border: Border.all(color: scheme.outlineVariant),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text('近 ${widget.trend.length} 次研判走势',
                    style: theme.textTheme.titleSmall),
              ),
              for (final key in _labels.keys) ...[
                _Pill(
                  label: _labels[key]!,
                  selected: _market == key,
                  color: _colors[key]!,
                  onTap: () => setState(() => _market = key),
                ),
                const SizedBox(width: 6),
              ],
            ],
          ),
          const SizedBox(height: 12),
          SizedBox(
            height: 96,
            width: double.infinity,
            child: TrendLine(values: _values, color: _colors[_market]),
          ),
        ],
      ),
    );
  }
}

class _Pill extends StatelessWidget {
  const _Pill({
    required this.label,
    required this.selected,
    required this.onTap,
    required this.color,
  });

  final String label;
  final bool selected;
  final Color color;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return InkWell(
      borderRadius: BorderRadius.circular(999),
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
        decoration: BoxDecoration(
          color: selected ? color.withValues(alpha: 0.15) : Colors.transparent,
          borderRadius: BorderRadius.circular(999),
          border: Border.all(color: selected ? color : theme.colorScheme.outlineVariant),
        ),
        child: Text(
          label,
          style: theme.textTheme.labelSmall?.copyWith(
            fontWeight: FontWeight.w600,
            color: selected ? color : theme.colorScheme.onSurfaceVariant,
          ),
        ),
      ),
    );
  }
}

/// 页面级错误视图：图标 + 文案 + 重试。资讯/AI/通知页复用。
class ErrorView extends StatelessWidget {
  const ErrorView({super.key, required this.error, this.onRetry});

  final String error;
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 60),
      child: Column(
        children: [
          Icon(Icons.cloud_off_outlined, size: 48, color: Theme.of(context).colorScheme.outline),
          const SizedBox(height: 12),
          Text(error, textAlign: TextAlign.center,
              style: TextStyle(color: Theme.of(context).colorScheme.error)),
          const SizedBox(height: 16),
          FilledButton.tonalIcon(
            onPressed: onRetry,
            icon: const Icon(Icons.refresh),
            label: const Text('重试'),
          ),
        ],
      ),
    );
  }
}
