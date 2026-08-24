import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/theme/app_theme.dart';
import '../../../shared/charts/trend_line.dart';
import '../../../shared/utils/format.dart';
import '../../../shared/widgets/stat_grid.dart';
import '../../market/data/market_api.dart';
import '../../market/data/market_models.dart';
import '../../sentiment/presentation/sentiment_page.dart' show ErrorView;
import '../data/trade_api.dart';

/// 行情看板：标的切换 + 分时线 + 盘口十档 + 逐笔成交。
/// 设计依据：设计稿 §3.6.2（1 标的行情 / 2 十档深度）；M4 只读。
/// 数据源：/trade/quote/depth、/trade/quote/trades、/market/kline(period=intraday)。
class MarketWatchPanel extends ConsumerStatefulWidget {
  const MarketWatchPanel({super.key});

  @override
  ConsumerState<MarketWatchPanel> createState() => _MarketWatchPanelState();
}

class _MarketWatchPanelState extends ConsumerState<MarketWatchPanel> {
  static const _markets = {'US': '美股', 'HK': '港股', 'CN': 'A股'};

  final _controller = TextEditingController(text: 'AAPL');
  String _market = 'US';

  late SymbolKey _key = symbolKey(_controller.text, _market);

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _apply() {
    final symbol = _controller.text.trim().toUpperCase();
    if (symbol.isEmpty) return;
    setState(() => _key = symbolKey(symbol, _market));
  }

  @override
  Widget build(BuildContext context) {
    return SectionCard(
      title: '标的行情与盘口',
      subtitle: '分时 · 十档深度 · 逐笔',
      child: Column(
        children: [
          Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _controller,
                  textCapitalization: TextCapitalization.characters,
                  decoration: InputDecoration(
                    hintText: '标的代码，如 AAPL',
                    isDense: true,
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(
                        AppDimens.radiusControl,
                      ),
                    ),
                  ),
                  onSubmitted: (_) => _apply(),
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
                onSelectionChanged: (s) {
                  setState(() => _market = s.first);
                  _apply();
                },
              ),
              const SizedBox(width: 10),
              FilledButton.tonal(onPressed: _apply, child: const Text('刷新')),
            ],
          ),
          const SizedBox(height: 12),
          _IntradayChart(key: ValueKey('kline-$_key'), symbolKey_: _key),
          const SizedBox(height: 12),
          _DepthPanel(key: ValueKey('depth-$_key'), symbolKey_: _key),
          const SizedBox(height: 12),
          _TradesPanel(key: ValueKey('trades-$_key'), symbolKey_: _key),
        ],
      ),
    );
  }
}

/// 分时：intraday 收盘价折线。
class _IntradayChart extends ConsumerStatefulWidget {
  const _IntradayChart({super.key, required this.symbolKey_});

  final SymbolKey symbolKey_;

  @override
  ConsumerState<_IntradayChart> createState() => _IntradayChartState();
}

class _IntradayChartState extends ConsumerState<_IntradayChart> {
  late Future<List<KlineBar>> _future;

  @override
  void initState() {
    super.initState();
    final parts = widget.symbolKey_.split('|');
    _future = ref
        .read(marketApiProvider)
        .kline(symbol: parts[0], market: parts[1], period: 'intraday');
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return FutureBuilder<List<KlineBar>>(
      future: _future,
      builder: (context, snap) {
        if (snap.connectionState == ConnectionState.waiting) {
          return const SizedBox(
            height: 96,
            child: Center(child: CircularProgressIndicator()),
          );
        }
        final bars = snap.data ?? const <KlineBar>[];
        if (bars.isEmpty) {
          return SizedBox(
            height: 96,
            child: Center(
              child: Text(
                '暂无分时数据（非交易时段或无缓存）',
                style: theme.textTheme.bodySmall?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              ),
            ),
          );
        }
        final closes = bars.map((b) => b.close).toList();
        final last = closes.last;
        final prevClose = bars.first.open;
        final changePct = prevClose == 0
            ? null
            : (last - prevClose) / prevClose * 100;
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.baseline,
              textBaseline: TextBaseline.alphabetic,
              children: [
                Text(
                  formatPrice(last),
                  style: AppNum.style(theme.textTheme.headlineMedium!).copyWith(
                    fontWeight: FontWeight.w700,
                    color: (changePct ?? 0) >= 0
                        ? AppColors.up
                        : AppColors.down,
                  ),
                ),
                const SizedBox(width: 8),
                Text(
                  formatPct(changePct),
                  style: AppNum.style(theme.textTheme.bodyMedium!).copyWith(
                    color: (changePct ?? 0) >= 0
                        ? AppColors.up
                        : AppColors.down,
                  ),
                ),
                const Spacer(),
                Text(
                  '分时 · ${bars.length} 根',
                  style: theme.textTheme.labelSmall?.copyWith(
                    color: theme.colorScheme.onSurfaceVariant,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 6),
            SizedBox(
              height: 96,
              width: double.infinity,
              child: TrendLine(values: closes, baselineAtZero: false),
            ),
          ],
        );
      },
    );
  }
}

/// 十档深度：卖十..卖一 在上，买一..买十 在下，挂单量背景占比条。
class _DepthPanel extends ConsumerWidget {
  const _DepthPanel({super.key, required this.symbolKey_});

  final SymbolKey symbolKey_;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final depth = ref.watch(depthProvider(symbolKey_));
    final theme = Theme.of(context);
    return depth.when(
      loading: () => const SizedBox(
        height: 80,
        child: Center(child: CircularProgressIndicator()),
      ),
      error: (e, _) => ErrorView(
        error: '$e',
        onRetry: () => ref.invalidate(depthProvider(symbolKey_)),
      ),
      data: (data) {
        if (!data.available) {
          final reasonText = switch (data.reason) {
            'cn_no_depth' => 'A股暂不提供盘口深度',
            'circuit_open' => '长桥连接熔断中，稍后自动恢复',
            'empty' => '该标的无盘口数据',
            _ => data.message.isEmpty ? '盘口不可用' : data.message,
          };
          return SizedBox(
            height: 60,
            child: Center(
              child: Text(
                reasonText,
                style: theme.textTheme.bodySmall?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              ),
            ),
          );
        }
        var maxVolume = 1;
        for (final l in [...data.asks, ...data.bids]) {
          if ((l.volume ?? 0) > maxVolume) maxVolume = l.volume!;
        }
        // 卖盘倒序：卖十在上，卖一贴着中轴。
        final asks = data.asks.toList().reversed.toList();
        return Column(
          children: [
            for (final level in asks)
              _DepthRow(
                label: '卖${level.position}',
                price: level.price,
                volume: level.volume,
                maxVolume: maxVolume,
                color: AppColors.down,
              ),
            Container(
              margin: const EdgeInsets.symmetric(vertical: 4),
              height: 1,
              color: theme.colorScheme.outlineVariant,
            ),
            for (final level in data.bids)
              _DepthRow(
                label: '买${level.position}',
                price: level.price,
                volume: level.volume,
                maxVolume: maxVolume,
                color: AppColors.up,
              ),
          ],
        );
      },
    );
  }
}

class _DepthRow extends StatelessWidget {
  const _DepthRow({
    required this.label,
    required this.price,
    required this.volume,
    required this.maxVolume,
    required this.color,
  });

  final String label;
  final double? price;
  final int? volume;
  final int maxVolume;
  final Color color;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final ratio = ((volume ?? 0) / maxVolume).clamp(0.02, 1.0);
    return SizedBox(
      height: 20,
      child: Stack(
        alignment: Alignment.centerRight,
        children: [
          FractionallySizedBox(
            widthFactor: ratio,
            child: Container(
              decoration: BoxDecoration(
                color: color.withValues(alpha: 0.12),
                borderRadius: BorderRadius.circular(3),
              ),
            ),
          ),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 4),
            child: Row(
              children: [
                Expanded(
                  child: Text(
                    label,
                    style: AppNum.style(theme.textTheme.labelSmall!)
                        .copyWith(color: theme.colorScheme.onSurfaceVariant),
                  ),
                ),
                Expanded(
                  flex: 2,
                  child: Text(
                    formatPrice(price),
                    textAlign: TextAlign.end,
                    style: AppNum.style(theme.textTheme.labelSmall!)
                        .copyWith(color: color, fontWeight: FontWeight.w700),
                  ),
                ),
                Expanded(
                  flex: 2,
                  child: Text(
                    '${volume ?? '--'}',
                    textAlign: TextAlign.end,
                    style: AppNum.style(theme.textTheme.labelSmall!),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

/// 逐笔成交列表。
class _TradesPanel extends ConsumerWidget {
  const _TradesPanel({super.key, required this.symbolKey_});

  final SymbolKey symbolKey_;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final trades = ref.watch(tradesProvider(symbolKey_));
    final theme = Theme.of(context);
    return trades.when(
      loading: () => const SizedBox(
        height: 60,
        child: Center(child: CircularProgressIndicator()),
      ),
      error: (e, _) => ErrorView(
        error: '$e',
        onRetry: () => ref.invalidate(tradesProvider(symbolKey_)),
      ),
      data: (list) {
        if (list.isEmpty) {
          return SizedBox(
            height: 48,
            child: Center(
              child: Text(
                '暂无逐笔数据',
                style: theme.textTheme.bodySmall?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              ),
            ),
          );
        }
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              '逐笔成交 · 最近 ${list.length} 笔',
              style: theme.textTheme.labelSmall?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: 4),
            for (final t in list.take(12))
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 1),
                child: Row(
                  children: [
                    Expanded(
                      flex: 4,
                      child: Text(
                        t.time,
                        style: AppNum.style(
                          theme.textTheme.labelSmall!,
                        ).copyWith(color: theme.colorScheme.onSurfaceVariant),
                      ),
                    ),
                    Expanded(
                      flex: 3,
                      child: Text(
                        formatPrice(t.price),
                        style: AppNum.style(theme.textTheme.labelSmall!),
                      ),
                    ),
                    Expanded(
                      flex: 2,
                      child: Text(
                        '${t.volume ?? '--'}',
                        textAlign: TextAlign.end,
                        style: AppNum.style(theme.textTheme.labelSmall!),
                      ),
                    ),
                    SizedBox(
                      width: 34,
                      child: Text(
                        t.side == 'buy'
                            ? 'B'
                            : t.side == 'sell'
                            ? 'S'
                            : '·',
                        textAlign: TextAlign.end,
                        style: theme.textTheme.labelSmall?.copyWith(
                          fontWeight: FontWeight.w800,
                          color: t.side == 'buy'
                              ? AppColors.up
                              : t.side == 'sell'
                              ? AppColors.down
                              : theme.colorScheme.onSurfaceVariant,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
          ],
        );
      },
    );
  }
}
