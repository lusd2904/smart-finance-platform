import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api/api_result.dart';
import '../../core/theme/app_theme.dart';
import '../../shared/widgets/page_header.dart';
import '../../shared/widgets/quote_text.dart';
import '../market/data/market_api.dart';

/// 智能选股：结论优先（评分 / 立场 / 建议 / 摘要），点行进 K 线。
class PhonePicksPage extends ConsumerStatefulWidget {
  const PhonePicksPage({super.key, this.onOpenSymbol});
  final void Function(String symbol, String market, String name)? onOpenSymbol;

  @override
  ConsumerState<PhonePicksPage> createState() => _PhonePicksPageState();
}

class _PhonePicksPageState extends ConsumerState<PhonePicksPage> {
  static const _markets = {'': '全部', 'US': '美股', 'HK': '港股', 'CN': 'A股'};
  String _market = '';

  @override
  Widget build(BuildContext context) {
    final async = ref.watch(picksLatestProvider(_market));
    final scheme = Theme.of(context).colorScheme;
    return RefreshIndicator(
      onRefresh: () async => ref.invalidate(picksLatestProvider(_market)),
      child: async.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => ListView(
          children: [
            const SizedBox(height: 80),
            TextButton(
              onPressed: () => ref.invalidate(picksLatestProvider(_market)),
              child: Text('加载失败，点此重试\n$e', textAlign: TextAlign.center),
            ),
          ],
        ),
        data: (data) {
          final items = asJsonList(data['items']).whereType<Map<String, dynamic>>().toList();
          final empty = data['empty'] == true || items.isEmpty;
          return ListView(
            padding: const EdgeInsets.only(bottom: 24),
            children: [
              PageHeader(
                title: '智能选股',
                subtitle: '${data['tradeDate'] ?? ''}',
              ),
              SizedBox(
                height: 44,
                child: ListView(
                  scrollDirection: Axis.horizontal,
                  padding: const EdgeInsets.fromLTRB(16, 4, 16, 8),
                  children: [
                    for (final e in _markets.entries)
                      Padding(
                        padding: const EdgeInsets.only(right: 8),
                        child: ChoiceChip(
                          label: Text(e.value),
                          selected: _market == e.key,
                          onSelected: (_) => setState(() => _market = e.key),
                        ),
                      ),
                  ],
                ),
              ),
              if (empty)
                Padding(
                  padding: const EdgeInsets.all(24),
                  child: Text(
                    '${data['message'] ?? '暂无选股单'}',
                    textAlign: TextAlign.center,
                    style: TextStyle(color: scheme.onSurfaceVariant),
                  ),
                )
              else
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 16),
                  child: Column(
                    children: [
                      for (final row in items) _PickCard(row: row, onOpen: widget.onOpenSymbol),
                    ],
                  ),
                ),
            ],
          );
        },
      ),
    );
  }
}

class _PickCard extends StatelessWidget {
  const _PickCard({required this.row, this.onOpen});
  final Map<String, dynamic> row;
  final void Function(String symbol, String market, String name)? onOpen;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final symbol = '${row['symbol'] ?? ''}';
    final name = '${row['name'] ?? ''}';
    final market = '${row['market'] ?? 'US'}';
    final rec = '${row['recommendation'] ?? ''}';
    final stance = '${row['stance'] ?? ''}';
    final summary = '${row['summary'] ?? ''}';
    final signal = '${row['signal'] ?? ''}';
    final score = (row['pickScore'] as num?)?.toDouble() ?? (row['factorScore'] as num?)?.toDouble();
    final chg = (row['changePct'] as num?)?.toDouble();
    final tone = () {
      final t = '$rec$stance$signal';
      if (t.contains('买') || t.contains('多') || t.toLowerCase().contains('buy') || t.toLowerCase().contains('bull')) {
        return AppColors.up;
      }
      if (t.contains('卖') || t.contains('空') || t.toLowerCase().contains('sell') || t.toLowerCase().contains('bear')) {
        return AppColors.down;
      }
      return AppColors.flat;
    }();
    final marketLabel = switch (market.toUpperCase()) {
      'US' => '美股',
      'HK' => '港股',
      'CN' => 'A股',
      _ => market,
    };
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Material(
        color: scheme.surfaceContainerLow,
        borderRadius: BorderRadius.circular(16),
        child: InkWell(
          borderRadius: BorderRadius.circular(16),
          onTap: onOpen == null || symbol.isEmpty
              ? null
              : () => onOpen!(symbol, market, name),
          child: Padding(
            padding: const EdgeInsets.fromLTRB(14, 12, 14, 12),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        name.isEmpty ? symbol : '$name  $symbol',
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 15),
                      ),
                    ),
                    Text(marketLabel, style: TextStyle(fontSize: 12, color: scheme.onSurfaceVariant)),
                    if (score != null) ...[
                      const SizedBox(width: 8),
                      Text(
                        score.toStringAsFixed(0),
                        style: const TextStyle(fontWeight: FontWeight.w800, fontFeatures: AppNum.fontFeatures),
                      ),
                    ],
                  ],
                ),
                const SizedBox(height: 6),
                Wrap(
                  spacing: 6,
                  runSpacing: 4,
                  children: [
                    if (rec.isNotEmpty) _tag(rec, tone),
                    if (stance.isNotEmpty && stance != rec) _tag(stance, tone),
                    if (signal.isNotEmpty) _tag(signal, scheme.onSurfaceVariant),
                    if (chg != null) PctText(chg, bold: true, style: const TextStyle(fontSize: 12)),
                  ],
                ),
                if (summary.isNotEmpty) ...[
                  const SizedBox(height: 8),
                  Text(
                    summary,
                    maxLines: 3,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(fontSize: 13, height: 1.4, color: scheme.onSurfaceVariant),
                  ),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _tag(String text, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.14),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(text, style: TextStyle(fontSize: 11, color: color, fontWeight: FontWeight.w700)),
    );
  }
}
