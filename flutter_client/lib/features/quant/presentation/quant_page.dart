import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/theme/app_theme.dart';
import '../../../shared/charts/radar_chart.dart';
import '../../../shared/widgets/stat_grid.dart';
import '../../../shared/widgets/page_header.dart';
import '../data/quant_api.dart';
import '../data/quant_models.dart';
import '../../sentiment/presentation/sentiment_page.dart' show ErrorView;

/// 量化研究（M3 只读）：策略信号 / 8 族权重 / 因子质量(IC·IR·五分位) / 扫描台账。
/// 设计依据：设计稿 §3.5（桌面 Quant Lab 双栏、移动端卡片化信号消费）；
/// 规划文档 M3「量化核心只读链路」——不调用任何触发计算或写库的端点。
class QuantPage extends ConsumerWidget {
  const QuantPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final wide = MediaQuery.sizeOf(context).width >= AppDimens.wideBreakpoint;
    final signals = const _SignalsPanel();
    final weights = const _WeightsPanel();
    final qc = const _FactorQcPanel();
    final runs = const _ScanRunsPanel();

    Widget body;
    if (wide) {
      body = Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(
            flex: 42,
            child: Column(children: [weights, const SizedBox(height: 12), qc]),
          ),
          const SizedBox(width: 12),
          Expanded(
            flex: 58,
            child: Column(
              children: [signals, const SizedBox(height: 12), runs],
            ),
          ),
        ],
      );
    } else {
      body = Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          signals,
          const SizedBox(height: 12),
          weights,
          const SizedBox(height: 12),
          qc,
          const SizedBox(height: 12),
          runs,
        ],
      );
    }

    return Scaffold(
      body: RefreshIndicator(
        onRefresh: () async {
          ref.invalidate(quantDailyListProvider);
          ref.invalidate(quantProfilesProvider);
          ref.invalidate(quantScanRunsProvider);
        },
        child: ListView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.only(bottom: 24),
          children: [
            const PageHeader(title: '量化研究', subtitle: '只读链路 · 信号与因子质量总览'),
            Padding(
              padding: const EdgeInsets.symmetric(
                horizontal: AppDimens.pagePadding,
              ),
              child: body,
            ),
          ],
        ),
      ),
    );
  }
}

/// ───────────────────────── 策略信号 ─────────────────────────

class _SignalsPanel extends ConsumerWidget {
  const _SignalsPanel();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final payload = ref.watch(quantDailyListProvider);
    return SectionCard(
      title: '今日策略信号',
      subtitle: '次日清单 · 只读',
      padding: const EdgeInsets.fromLTRB(12, 10, 12, 4),
      child: payload.when(
        loading: () => const SizedBox(
          height: 120,
          child: Center(child: CircularProgressIndicator()),
        ),
        error: (e, _) => ErrorView(
          error: '$e',
          onRetry: () => ref.invalidate(quantDailyListProvider),
        ),
        data: (data) {
          final list = data.list;
          if (list == null || list.items.isEmpty) {
            return Padding(
              padding: const EdgeInsets.symmetric(vertical: 24),
              child: Center(
                child: Text(
                  data.message.isNotEmpty ? data.message : '暂无策略信号，待下一次扫描生成',
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
                ),
              ),
            );
          }
          return Column(
            children: [
              Align(
                alignment: Alignment.centerLeft,
                child: Text(
                  '${list.tradeDate} 交易 · 档位 ${list.profile} · ${list.itemCount} 条',
                  style: AppNum.style(Theme.of(context).textTheme.labelSmall!)
                      .copyWith(
                        color: Theme.of(context).colorScheme.onSurfaceVariant,
                      ),
                ),
              ),
              const SizedBox(height: 8),
              for (final item in list.items) ...[
                SignalCard(item: item),
                const SizedBox(height: 6),
              ],
            ],
          );
        },
      ),
    );
  }
}

/// 策略信号卡片：方向徽章 + 标的 + 一句话理由 + 评分/置信度。
class SignalCard extends StatelessWidget {
  const SignalCard({super.key, required this.item});

  final SignalItem item;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final color = item.isBuy
        ? AppColors.up
        : (item.isSell ? AppColors.down : AppColors.flat);
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: scheme.surfaceContainerLowest,
        borderRadius: BorderRadius.circular(AppDimens.radiusControl),
        border: Border.all(color: scheme.outlineVariant),
      ),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 4),
            decoration: BoxDecoration(
              color: color.withValues(alpha: 0.14),
              borderRadius: BorderRadius.circular(7),
            ),
            child: Text(
              item.isBuy ? '买入' : (item.isSell ? '卖出' : '观望'),
              style: theme.textTheme.labelMedium?.copyWith(
                color: color,
                fontWeight: FontWeight.w800,
              ),
            ),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '${item.symbol} · ${item.name.isEmpty ? item.market : item.name}',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: AppNum.style(theme.textTheme.titleSmall!),
                ),
                if (item.reason.isNotEmpty)
                  Padding(
                    padding: const EdgeInsets.only(top: 2),
                    child: Text(
                      item.reason,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: scheme.onSurfaceVariant,
                        height: 1.35,
                      ),
                    ),
                  ),
              ],
            ),
          ),
          const SizedBox(width: 10),
          Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              if (item.score != null)
                Text(
                  '评分 ${formatPct0(item.score)}',
                  style: AppNum.style(theme.textTheme.bodySmall!),
                ),
              if (item.confidence != null)
                Text(
                  '置信 ${item.confidence!.toStringAsFixed(0)}%',
                  style: AppNum.style(theme.textTheme.bodySmall!)
                      .copyWith(color: scheme.primary),
                ),
            ],
          ),
        ],
      ),
    );
  }
}

String formatPct0(double? v) => v == null ? '--' : v.toStringAsFixed(0);

/// ───────────────────────── 8 族权重 ─────────────────────────

class _WeightsPanel extends ConsumerStatefulWidget {
  const _WeightsPanel();

  @override
  ConsumerState<_WeightsPanel> createState() => _WeightsPanelState();
}

class _WeightsPanelState extends ConsumerState<_WeightsPanel> {
  String? _selectedCode;

  @override
  Widget build(BuildContext context) {
    final profiles = ref.watch(quantProfilesProvider);
    return SectionCard(
      title: '8 族权重',
      subtitle: '三档预设 · 只读展示',
      child: profiles.when(
        loading: () => const SizedBox(
          height: 180,
          child: Center(child: CircularProgressIndicator()),
        ),
        error: (e, _) => ErrorView(
          error: '$e',
          onRetry: () => ref.invalidate(quantProfilesProvider),
        ),
        data: (list) {
          if (list.isEmpty) {
            return Padding(
              padding: const EdgeInsets.symmetric(vertical: 28),
              child: Center(
                child: Text(
                  '暂无权重档位数据',
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
                ),
              ),
            );
          }
          String? boundCode;
          for (final p in list) {
            if (p.active) {
              boundCode = p.profileCode;
              break;
            }
          }
          final selectedCode = _selectedCode ?? boundCode ?? 'balanced';
          StrategyProfile current = list.first;
          for (final p in list) {
            if (p.profileCode == selectedCode) current = p;
          }
          return Column(
            children: [
              Wrap(
                spacing: 6,
                children: [
                  for (final p in list)
                    ChoiceChip(
                      label: Text(
                        p.active
                            ? '${p.profileName.isEmpty ? p.profileCode : p.profileName} · 生效'
                            : (p.profileName.isEmpty
                                  ? p.profileCode
                                  : p.profileName),
                      ),
                      selected: p.profileCode == selectedCode,
                      visualDensity: VisualDensity.compact,
                      onSelected: (_) =>
                          setState(() => _selectedCode = p.profileCode),
                    ),
                ],
              ),
              const SizedBox(height: 8),
              RadarChart(
                axes: current.radarAxes,
                values: current.radarValues,
                size: 230,
              ),
              const SizedBox(height: 6),
              Text(
                '买入阈值 ${current.buyThreshold ?? '--'} · 卖出阈值 ${current.sellThreshold ?? '--'}'
                ' · 更新于 ${current.updateTime}',
                style: AppNum.style(Theme.of(context).textTheme.labelSmall!)
                    .copyWith(
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                    ),
              ),
            ],
          );
        },
      ),
    );
  }
}

/// ───────────────────────── 因子质量 ─────────────────────────

class _FactorQcPanel extends ConsumerStatefulWidget {
  const _FactorQcPanel();

  @override
  ConsumerState<_FactorQcPanel> createState() => _FactorQcPanelState();
}

class _FactorQcPanelState extends ConsumerState<_FactorQcPanel> {
  String _market = 'US';

  static const _markets = {'US': '美股', 'HK': '港股', 'CN': 'A股'};

  @override
  Widget build(BuildContext context) {
    final qc = ref.watch(factorQcProvider(_market));
    return SectionCard(
      title: '因子质量（IC · IR）',
      subtitle: '汇总统计 · 五分位多空收益',
      padding: const EdgeInsets.fromLTRB(12, 10, 12, 8),
      child: Column(
        children: [
          Align(
            alignment: Alignment.centerLeft,
            child: SegmentedButton<String>(
              showSelectedIcon: false,
              style: const ButtonStyle(visualDensity: VisualDensity.compact),
              segments: [
                for (final e in _markets.entries)
                  ButtonSegment(value: e.key, label: Text(e.value)),
              ],
              selected: {_market},
              onSelectionChanged: (s) => setState(() => _market = s.first),
            ),
          ),
          const SizedBox(height: 8),
          qc.when(
            loading: () => const SizedBox(
              height: 120,
              child: Center(child: CircularProgressIndicator()),
            ),
            error: (e, _) => ErrorView(
              error: '$e',
              onRetry: () => ref.invalidate(factorQcProvider(_market)),
            ),
            data: (report) {
              if (!report.ok && report.items.isEmpty) {
                return Padding(
                  padding: const EdgeInsets.symmetric(vertical: 20),
                  child: Text(
                    report.message.isEmpty ? '暂无因子质量数据' : report.message,
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                    ),
                  ),
                );
              }
              // 按 |IR| 降序，质量最好的排前面。
              final items = [...report.items]
                ..sort(
                  (a, b) => ((b.ir ?? 0).abs()).compareTo((a.ir ?? 0).abs()),
                );
              return Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    '截至 ${report.asOf.isEmpty ? '--' : report.asOf} · '
                    '样本 ${report.symbolCount} 标的 / ${items.length} 因子',
                    style: AppNum.style(Theme.of(context).textTheme.labelSmall!)
                        .copyWith(
                          color: Theme.of(context).colorScheme.onSurfaceVariant,
                        ),
                  ),
                  const SizedBox(height: 6),
                  for (final item in items.take(8)) ...[
                    FactorQcRow(item: item),
                    const Divider(height: 1, color: Colors.transparent),
                  ],
                ],
              );
            },
          ),
        ],
      ),
    );
  }
}

/// 单因子行：名称 + 族 | 五分位收益条 | IR / IC 数值。
class FactorQcRow extends StatelessWidget {
  const FactorQcRow({super.key, required this.item});

  final FactorQcItem item;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final irColor = (item.ir ?? 0) >= 0 ? AppColors.up : AppColors.down;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        children: [
          Expanded(
            flex: 5,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  item.factorLabel.isEmpty ? item.factorKey : item.factorLabel,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: theme.textTheme.bodyMedium?.copyWith(
                    fontWeight: FontWeight.w600,
                  ),
                ),
                Text(
                  '${item.family} · ${item.sampleDates}日样本',
                  style: AppNum.style(theme.textTheme.labelSmall!)
                      .copyWith(color: scheme.onSurfaceVariant),
                ),
              ],
            ),
          ),
          Expanded(flex: 4, child: QuantileBars(quantiles: item.quantiles)),
          SizedBox(
            width: 86,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                Text(
                  'IR ${(item.ir ?? 0).toStringAsFixed(2)}',
                  style: AppNum.style(theme.textTheme.bodyMedium!)
                      .copyWith(color: irColor, fontWeight: FontWeight.w700),
                ),
                Text(
                  'IC ${(item.icMean ?? 0).toStringAsFixed(3)}',
                  style: AppNum.style(theme.textTheme.labelSmall!)
                      .copyWith(color: scheme.onSurfaceVariant),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

/// 五分位收益迷你条形组：q1~q5，正红负绿，宽度按最大绝对值归一。
class QuantileBars extends StatelessWidget {
  const QuantileBars({super.key, required this.quantiles});

  final Map<String, double?> quantiles;

  @override
  Widget build(BuildContext context) {
    final keys = ['q1', 'q2', 'q3', 'q4', 'q5'];
    var maxAbs = 0.0;
    for (final k in keys) {
      final v = quantiles[k] ?? 0;
      if (v.abs() > maxAbs) maxAbs = v.abs();
    }
    final theme = Theme.of(context);
    if (maxAbs <= 0) {
      return Text(
        '--',
        style: theme.textTheme.labelSmall?.copyWith(
          color: theme.colorScheme.onSurfaceVariant,
        ),
      );
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        for (final k in keys)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 1),
            child: Row(
              children: [
                SizedBox(
                  width: 16,
                  child: Text(
                    k,
                    style: theme.textTheme.labelSmall?.copyWith(fontSize: 9),
                  ),
                ),
                Expanded(
                  child: Stack(
                    alignment: Alignment.centerLeft,
                    children: [
                      FractionallySizedBox(
                        widthFactor: ((quantiles[k] ?? 0).abs() / maxAbs).clamp(
                          0.02,
                          1.0,
                        ),
                        child: Container(
                          height: 5,
                          decoration: BoxDecoration(
                            color: (quantiles[k] ?? 0) >= 0
                                ? AppColors.up.withValues(alpha: 0.75)
                                : AppColors.down.withValues(alpha: 0.75),
                            borderRadius: BorderRadius.circular(3),
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
      ],
    );
  }
}

/// ───────────────────────── 扫描台账 ─────────────────────────

class _ScanRunsPanel extends ConsumerWidget {
  const _ScanRunsPanel();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final runs = ref.watch(quantScanRunsProvider);
    return SectionCard(
      title: '扫描台账',
      subtitle: '最近执行记录 · 点击展开明细',
      padding: const EdgeInsets.fromLTRB(12, 10, 12, 4),
      child: runs.when(
        loading: () => const SizedBox(
          height: 120,
          child: Center(child: CircularProgressIndicator()),
        ),
        error: (e, _) => ErrorView(
          error: '$e',
          onRetry: () => ref.invalidate(quantScanRunsProvider),
        ),
        data: (list) {
          if (list.isEmpty) {
            return Padding(
              padding: const EdgeInsets.symmetric(vertical: 24),
              child: Center(
                child: Text(
                  '暂无扫描记录',
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
                ),
              ),
            );
          }
          return Column(
            children: [for (final r in list.take(15)) ScanRunTile(run: r)],
          );
        },
      ),
    );
  }
}

/// 台账条目：展开时懒加载详情摘要。
class ScanRunTile extends ConsumerStatefulWidget {
  const ScanRunTile({super.key, required this.run});

  final ScanRun run;

  @override
  ConsumerState<ScanRunTile> createState() => _ScanRunTileState();
}

class _ScanRunTileState extends ConsumerState<ScanRunTile> {
  Map<String, dynamic>? _detail;
  bool _loading = false;

  Future<void> _loadDetail() async {
    if (_detail != null || _loading || widget.run.cycleId == null) return;
    setState(() => _loading = true);
    try {
      final d = await ref
          .read(quantApiProvider)
          .scanRunDetail(cycleId: widget.run.cycleId!);
      if (mounted) setState(() => _detail = d);
    } catch (_) {
      // 详情加载失败不阻塞列表；保持可重试（再次折叠展开）。
      if (mounted) setState(() => _detail = {});
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final r = widget.run;
    final finished = r.status == 'completed';
    return ExpansionTile(
      tilePadding: EdgeInsets.zero,
      childrenPadding: const EdgeInsets.only(bottom: 8),
      onExpansionChanged: (open) {
        if (open) _loadDetail();
      },
      title: Text(
        '${r.startedAt} · ${r.strategyProfile.isEmpty ? '默认档位' : r.strategyProfile}',
        style: AppNum.style(theme.textTheme.titleSmall!),
      ),
      subtitle: Text(
        '标的 ${r.targetCount} · 机会 ${r.opportunityCount} · 信号 ${r.signalCount} · 提交 ${r.submittedCount}',
        style: AppNum.style(theme.textTheme.bodySmall!)
            .copyWith(color: scheme.onSurfaceVariant),
      ),
      trailing: Chip(
        visualDensity: VisualDensity.compact,
        label: Text(
          finished ? '完成' : r.status,
          style: theme.textTheme.labelSmall,
        ),
        backgroundColor: scheme.surfaceContainerHighest.withValues(alpha: 0.5),
      ),
      children: [
        if (_loading) const LinearProgressIndicator(minHeight: 2),
        if (_detail == null)
          Text(
            '展开加载明细…',
            style: theme.textTheme.bodySmall?.copyWith(
              color: scheme.onSurfaceVariant,
            ),
          )
        else if (_detail!.isEmpty)
          Text(
            '明细加载失败',
            style: theme.textTheme.bodySmall?.copyWith(color: scheme.error),
          )
        else ...[
          for (final entry in _detail!.entries.take(6))
            if (entry.value is! List && entry.value is! Map)
              Padding(
                padding: const EdgeInsets.only(bottom: 2),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(
                      entry.key,
                      style: theme.textTheme.labelSmall?.copyWith(
                        color: scheme.onSurfaceVariant,
                      ),
                    ),
                    Text(
                      '${entry.value}',
                      style: AppNum.style(theme.textTheme.labelSmall!),
                    ),
                  ],
                ),
              ),
        ],
      ],
    );
  }
}
