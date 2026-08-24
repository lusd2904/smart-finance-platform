import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/theme/app_theme.dart';

import '../../../shared/utils/format.dart';
import '../../../shared/widgets/page_header.dart';
import '../../../shared/widgets/stat_grid.dart';
import '../data/ai_api.dart';
import '../data/ai_models.dart';

/// AI 研判（只读）：
/// - 单标的最新研判查询（输入代码 + 市场即时拉取）；
/// - 批量扫描批次历史（展开加载明细）。
/// 设计依据：设计稿 §3.7.1 AI 研判工作台 / §3.7.2 左历史右报告双模式。
/// M2 只读，不触发 ai-analyze / ai/batch 重任务端点。
class AiPage extends ConsumerWidget {
  const AiPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final batches = ref.watch(aiBatchesProvider);
    final wide = MediaQuery.sizeOf(context).width >= AppDimens.wideBreakpoint;

    final historyPanel = _BatchesPanel(batches: batches);
    final queryPanel = const _QueryPanel();

    return Scaffold(
      body: ListView(
        padding: const EdgeInsets.only(bottom: 24),
        children: [
          const PageHeader(title: 'AI 研判', subtitle: '单标的诊断与批量扫描结果查看'),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: AppDimens.pagePadding),
            child: wide
                ? Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Expanded(flex: 42, child: historyPanel),
                      const SizedBox(width: 12),
                      Expanded(flex: 58, child: queryPanel),
                    ],
                  )
                : Column(children: [queryPanel, const SizedBox(height: 12), historyPanel]),
          ),
        ],
      ),
    );
  }
}

/// ───────────────────────── 单标的查询 ─────────────────────────

class _QueryPanel extends ConsumerStatefulWidget {
  const _QueryPanel();

  @override
  ConsumerState<_QueryPanel> createState() => _QueryPanelState();
}

class _QueryPanelState extends ConsumerState<_QueryPanel> {
  static const _markets = {'US': '美股', 'HK': '港股', 'CN': 'A股'};

  final _controller = TextEditingController();
  String _market = 'US';
  bool _querying = false;
  AiLatestAnalysis? _result;
  Object? _error;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  Future<void> _query() async {
    final symbol = _controller.text.trim();
    if (symbol.isEmpty || _querying) return;
    setState(() {
      _querying = true;
      _error = null;
    });
    try {
      final r = await ref.read(aiApiProvider).latest(symbol: symbol, market: _market);
      setState(() => _result = r);
    } catch (e) {
      if (mounted) setState(() => _error = e);
    } finally {
      if (mounted) setState(() => _querying = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return SectionCard(
      title: '单标的最新研判',
      subtitle: '输入代码即时查询服务端已有结论',
      child: Column(
        children: [
          Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _controller,
                  textCapitalization: TextCapitalization.characters,
                  decoration: InputDecoration(
                    hintText: '标的代码，如 AAPL / 00700',
                    isDense: true,
                    border: OutlineInputBorder(borderRadius: BorderRadius.circular(AppDimens.radiusControl)),
                  ),
                  onSubmitted: (_) => _query(),
                ),
              ),
              const SizedBox(width: 10),
              SegmentedButton<String>(
                showSelectedIcon: false,
                style: const ButtonStyle(visualDensity: VisualDensity.compact),
                segments: [
                  for (final e in _markets.entries)
                    ButtonSegment(value: e.key, label: Text(e.value)),
                ],
                selected: {_market},
                onSelectionChanged: (s) => setState(() => _market = s.first),
              ),
              const SizedBox(width: 10),
              FilledButton.icon(
                onPressed: _querying ? null : _query,
                icon: _querying
                    ? const SizedBox(width: 14, height: 14,
                        child: CircularProgressIndicator(strokeWidth: 2))
                    : const Icon(Icons.psychology_outlined, size: 18),
                label: const Text('查询'),
              ),
            ],
          ),
          if (_error != null) ...[
            const SizedBox(height: 10),
            Text('$_error', style: TextStyle(color: theme.colorScheme.error)),
          ],
          if (_result != null) ...[
            const SizedBox(height: 12),
            AnalysisReport(analysis: _result!),
          ] else if (_error == null && !_querying) ...[
            const SizedBox(height: 8),
            Text('尚无查询结果', style: theme.textTheme.bodySmall?.copyWith(color: theme.colorScheme.onSurfaceVariant)),
          ],
        ],
      ),
    );
  }
}

/// 研判报告视图：头部结论徽章 + 分面复盘区块。
class AnalysisReport extends StatelessWidget {
  const AnalysisReport({super.key, required this.analysis});

  final AiLatestAnalysis analysis;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final badgeColor = analysis.isBullish
        ? AppColors.up
        : analysis.isBearish
            ? AppColors.down
            : AppColors.flat;

    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: scheme.surfaceContainerLowest,
        borderRadius: BorderRadius.circular(AppDimens.radiusControl),
        border: Border.all(color: scheme.outlineVariant),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // 头部：代码 · 市场 · 价格 | 结论徽章 · 置信度。
          Row(
            children: [
              Expanded(
                child: Text(
                  '${analysis.symbol} · ${analysis.market}',
                  style: theme.textTheme.titleMedium,
                ),
              ),
              if (analysis.price != null)
                Text(
                  formatPrice(analysis.price),
                  style: AppNum.style(theme.textTheme.titleMedium!).copyWith(fontWeight: FontWeight.w700),
                ),
            ],
          ),
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            runSpacing: 6,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                  color: badgeColor.withValues(alpha: 0.14),
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Text(
                  analysis.recommendation.isEmpty ? '暂无结论' : analysis.recommendation,
                  style: theme.textTheme.labelMedium?.copyWith(color: badgeColor, fontWeight: FontWeight.w700),
                ),
              ),
              if (analysis.confidence != null)
                Text(
                  '置信度 ${analysis.confidence!.toStringAsFixed(0)}%',
                  style: AppNum.style(theme.textTheme.bodySmall!),
                ),
              if (analysis.signal.isNotEmpty)
                Text(
                  '信号 ${analysis.signal}',
                  style: theme.textTheme.bodySmall?.copyWith(color: scheme.onSurfaceVariant),
                ),
            ],
          ),
          if (analysis.summaryText.isNotEmpty)
            _block(context, icon: Icons.summarize_outlined, title: '综合结论', body: analysis.summaryText),
          if (analysis.indicatorReview.isNotEmpty)
            _block(context, icon: Icons.candlestick_chart_outlined, title: '技术面复盘', body: analysis.indicatorReview),
          if (analysis.sentimentReview.isNotEmpty)
            _block(context, icon: Icons.forum_outlined, title: '舆情面复盘', body: analysis.sentimentReview),
          if (analysis.operationAdvice.isNotEmpty)
            _block(context, icon: Icons.checklist_outlined, title: '操作建议', body: analysis.operationAdvice),
          if (analysis.riskWarning.isNotEmpty)
            _block(context, icon: Icons.warning_amber_outlined, title: '风险提示', body: analysis.riskWarning),
          const SizedBox(height: 10),
          Text(
            '${analysis.modelName} · ${analysis.analysisTime}',
            style: AppNum.style(theme.textTheme.labelSmall!).copyWith(color: scheme.onSurfaceVariant),
          ),
        ],
      ),
    );
  }

  Widget _block(BuildContext context, {required IconData icon, required String title, required String body}) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    return Padding(
      padding: const EdgeInsets.only(top: 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(icon, size: 15, color: scheme.primary),
              const SizedBox(width: 5),
              Text(title, style: theme.textTheme.labelLarge),
            ],
          ),
          const SizedBox(height: 4),
          Text(body, style: theme.textTheme.bodySmall?.copyWith(height: 1.55)),
        ],
      ),
    );
  }
}

/// ───────────────────────── 批量扫描历史 ─────────────────────────

class _BatchesPanel extends ConsumerWidget {
  const _BatchesPanel({required this.batches});

  final AsyncValue<List<AiBatch>> batches;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return SectionCard(
      title: '批量扫描历史',
      subtitle: '按批次查看标的分析明细',
      padding: const EdgeInsets.fromLTRB(12, 10, 12, 4),
      child: batches.when(
        loading: () => const SizedBox(
          height: 120,
          child: Center(child: CircularProgressIndicator()),
        ),
        error: (e, _) => Padding(
          padding: const EdgeInsets.symmetric(vertical: 24),
          child: Column(
            children: [
              Text('$e', textAlign: TextAlign.center,
                  style: TextStyle(color: Theme.of(context).colorScheme.error)),
              const SizedBox(height: 12),
              OutlinedButton.icon(
                onPressed: () => ref.invalidate(aiBatchesProvider),
                icon: const Icon(Icons.refresh, size: 18),
                label: const Text('重试'),
              ),
            ],
          ),
        ),
        data: (list) {
          if (list.isEmpty) {
            return Padding(
              padding: const EdgeInsets.symmetric(vertical: 28),
              child: Center(
                child: Text('暂无批量扫描记录',
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: Theme.of(context).colorScheme.onSurfaceVariant)),
              ),
            );
          }
          return Column(
            children: [
              for (final b in list) BatchTile(batch: b),
            ],
          );
        },
      ),
    );
  }
}

/// 批次条目：展开时懒加载明细列表。
class BatchTile extends ConsumerStatefulWidget {
  const BatchTile({super.key, required this.batch});

  final AiBatch batch;

  @override
  ConsumerState<BatchTile> createState() => _BatchTileState();
}

class _BatchTileState extends ConsumerState<BatchTile> {
  List<AiBatchItem>? _items;
  Object? _error;
  bool _loading = false;

  Future<void> _loadItems() async {
    if (_items != null || _loading || widget.batch.batchId == null) return;
    setState(() => _loading = true);
    try {
      final items =
          await ref.read(aiApiProvider).batchItems(batchId: widget.batch.batchId!);
      if (mounted) setState(() => _items = items);
    } catch (e) {
      if (mounted) setState(() => _error = e);
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final b = widget.batch;
    return ExpansionTile(
      tilePadding: EdgeInsets.zero,
      childrenPadding: const EdgeInsets.only(bottom: 8),
      onExpansionChanged: (open) {
        if (open) _loadItems();
      },
      title: Text(
        '批次 #${b.batchId ?? '--'}',
        style: AppNum.style(theme.textTheme.titleSmall!),
      ),
      subtitle: Text(
        '${b.createTime} · 标的 ${b.symbolsCount} · 成功 ${b.successCount}',
        style: AppNum.style(theme.textTheme.bodySmall!).copyWith(color: scheme.onSurfaceVariant),
      ),
      trailing: Chip(
        visualDensity: VisualDensity.compact,
        avatar: Icon(
          b.finished ? Icons.check_circle_outline : Icons.timelapse,
          size: 14,
          color: b.finished ? AppColors.down : AppColors.warn,
        ),
        label: Text(b.finished ? '完成' : '执行中',
            style: theme.textTheme.labelSmall),
        backgroundColor: scheme.surfaceContainerHighest.withValues(alpha: 0.5),
      ),
      children: [
        if (_loading) const LinearProgressIndicator(minHeight: 2),
        if (_error != null)
          Text('$_error', style: TextStyle(color: scheme.error, fontSize: 12))
        else if (_items == null)
          Text('展开加载明细…',
              style: theme.textTheme.bodySmall?.copyWith(color: scheme.onSurfaceVariant))
        else if (_items!.isEmpty)
          Text('该批次无明细数据',
              style: theme.textTheme.bodySmall?.copyWith(color: scheme.onSurfaceVariant))
        else
          ...[for (final item in _items!) _BatchItemRow(item: item)],
      ],
    );
  }
}

class _BatchItemRow extends StatelessWidget {
  const _BatchItemRow({required this.item});

  final AiBatchItem item;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final bullish = item.decision.toLowerCase().contains('bull') ||
        item.decision.contains('多') ||
        item.decision.contains('涨');
    final bearish = item.decision.toLowerCase().contains('bear') ||
        item.decision.contains('空') ||
        item.decision.contains('跌');
    final color = !item.succeeded
        ? AppColors.flat
        : bullish
            ? AppColors.up
            : bearish
                ? AppColors.down
                : AppColors.brand;
    return Container(
      margin: const EdgeInsets.only(bottom: 6),
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: scheme.surfaceContainerLowest,
        borderRadius: BorderRadius.circular(AppDimens.radiusControl - 2),
        border: Border.all(color: scheme.outlineVariant),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 92,
            child: Text(
              '${item.symbol} · ${item.market}',
              style: AppNum.style(theme.textTheme.bodyMedium!)
                  .copyWith(fontWeight: FontWeight.w600),
            ),
          ),
          Expanded(
            child: Text(
              item.summary.isEmpty ? (item.succeeded ? '无摘要' : '分析失败') : item.summary,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: theme.textTheme.bodySmall?.copyWith(color: scheme.onSurfaceVariant),
            ),
          ),
          const SizedBox(width: 8),
          Text(
            item.decision.isEmpty
                ? (item.succeeded ? '--' : '失败')
                : item.decision,
            style: theme.textTheme.labelMedium?.copyWith(color: color, fontWeight: FontWeight.w700),
          ),
          if (item.confidence != null)
            SizedBox(
              width: 44,
              child: Text(
                ' ${item.confidence!.toStringAsFixed(0)}%',
                textAlign: TextAlign.right,
                style: AppNum.style(theme.textTheme.labelSmall!),
              ),
            ),
        ],
      ),
    );
  }
}
