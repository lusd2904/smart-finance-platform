import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_client.dart';
import '../../../shared/widgets/quote_text.dart';
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

  Future<List<KlineBar>> _load() => ref.read(marketApiProvider).kline(
        symbol: widget.symbol,
        market: widget.market,
        period: _period,
      );

  void _reload() => setState(() => _future = _load());

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(
        title: Text(widget.name == null || widget.name!.isEmpty
            ? widget.symbol
            : '${widget.name} · ${widget.symbol}'),
        actions: [
          IconButton(icon: const Icon(Icons.refresh), onPressed: _reload, tooltip: '刷新'),
        ],
      ),
      body: Column(
        children: [
          SegmentedButton<String>(
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
                        Text(describeApiError(snap.error!),
                            style: TextStyle(color: theme.colorScheme.error)),
                        const SizedBox(height: 8),
                        OutlinedButton(onPressed: _reload, child: const Text('重试')),
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
    final last = bars.last;
    final prev = bars.length >= 2 ? bars[bars.length - 2] : null;
    final changeRate = (prev != null && prev.close != 0)
        ? (last.close - prev.close) / prev.close * 100
        : null;
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          PriceText(last.close, style: Theme.of(context).textTheme.headlineMedium),
          const SizedBox(width: 12),
          PctText(changeRate, bold: true, style: Theme.of(context).textTheme.titleMedium),
          const Spacer(),
          Text(last.date, style: Theme.of(context).textTheme.bodySmall),
        ],
      ),
    );
  }
}
