import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_client.dart';
import '../../../shared/widgets/quote_text.dart';
import '../../../core/theme/app_theme.dart';
import '../../market/data/market_api.dart';
import '../../market/data/market_models.dart';
import '../logic/kline_painter.dart';

/// 标的详情页：头部报价卡 + 日/周/月 K线（自绘蜡烛图 + 成交量副图）。
/// M1 范围：period=daily/weekly/monthly；intraday 分时留待后续增强。
class SymbolDetailPage extends ConsumerStatefulWidget {
  const SymbolDetailPage({
    super.key,
    required this.symbol,
    required this.market,
    this.name,
  });

  final String symbol;
  final String market;
  final String? name;

  @override
  ConsumerState<SymbolDetailPage> createState() => _SymbolDetailPageState();
}

class _SymbolDetailPageState extends ConsumerState<SymbolDetailPage> {
  String _period = 'daily';
  late Future<List<KlineBar>> _future;

  static const _periodLabels = {'daily': '日K', 'weekly': '周K', 'monthly': '月K'};

  @override
  void initState() {
    super.initState();
    _future = _load();
  }

  Future<List<KlineBar>> _load() => ref
      .read(marketApiProvider)
      .kline(symbol: widget.symbol, market: widget.market, period: _period);

  void _reload() => setState(() => _future = _load());

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(
        title: Text(
          widget.name == null || widget.name!.isEmpty
              ? widget.symbol
              : '${widget.name} · ${widget.symbol}',
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _reload,
            tooltip: '刷新',
          ),
        ],
      ),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 4, 16, 10),
            child: Align(
              alignment: Alignment.centerLeft,
              child: SegmentedButton<String>(
                segments: [
                  for (final e in _periodLabels.entries)
                    ButtonSegment(value: e.key, label: Text(e.value)),
                ],
                selected: {_period},
                onSelectionChanged: (s) {
                  if (s.first != _period) {
                    setState(() => _period = s.first);
                    _reload();
                  }
                },
              ),
            ),
          ),
          Divider(height: 1, color: theme.colorScheme.outlineVariant),
          Expanded(
            child: FutureBuilder<List<KlineBar>>(
              future: _future,
              builder: (context, snap) {
                if (snap.connectionState != ConnectionState.done) {
                  return const Center(child: CircularProgressIndicator());
                }
                if (snap.hasError) {
                  return Center(
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Text(
                          describeApiError(snap.error!),
                          style: TextStyle(color: theme.colorScheme.error),
                        ),
                        const SizedBox(height: 8),
                        OutlinedButton(
                          onPressed: _reload,
                          child: const Text('重试'),
                        ),
                      ],
                    ),
                  );
                }
                final bars = snap.data ?? const <KlineBar>[];
                if (bars.isEmpty) {
                  return const Center(child: Text('暂无 K 线数据'));
                }
                return Column(
                  children: [
                    _QuoteHead(bars: bars),
                    Expanded(child: InteractiveKlineChart(bars: bars)),
                  ],
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}

/// 头部报价：最后一根收盘价与前一根比较得出涨跌。
class _QuoteHead extends StatelessWidget {
  const _QuoteHead({required this.bars});

  final List<KlineBar> bars;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final last = bars.last;
    final prev = bars.length >= 2 ? bars[bars.length - 2] : null;
    final changeRate = (prev != null && prev.close != 0)
        ? (last.close - prev.close) / prev.close * 100
        : null;
    final chgColor = switch (changeRate) {
      null => AppColors.flat,
      > 0 => AppColors.up,
      < 0 => AppColors.down,
      _ => AppColors.flat,
    };
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 14, 20, 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.center,
            children: [
              PriceText(last.close, style: theme.textTheme.quoteDisplay),
              const SizedBox(width: 12),
              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 10,
                  vertical: 4,
                ),
                decoration: BoxDecoration(
                  color: chgColor.withValues(alpha: 0.13),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: PctText(
                  changeRate,
                  bold: true,
                  style: theme.textTheme.titleMedium,
                ),
              ),
            ],
          ),
          const SizedBox(height: 6),
          Text(
            last.date,
            style: theme.textTheme.bodySmall?.copyWith(
              color: theme.colorScheme.onSurfaceVariant,
            ),
          ),
        ],
      ),
    );
  }
}
