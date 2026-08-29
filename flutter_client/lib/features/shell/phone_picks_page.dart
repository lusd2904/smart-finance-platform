import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api/api_result.dart';
import '../../core/theme/app_theme.dart';
import '../../shared/widgets/quote_row.dart';
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
          final items = asJsonList(data['items'])
              .whereType<Map<String, dynamic>>()
              .toList();
          final empty = data['empty'] == true || items.isEmpty;
          return ListView(
            padding: const EdgeInsets.only(bottom: 24),
            children: [
              SizedBox(
                height: 40,
                child: Row(
                  children: [
                    for (final e in _markets.entries)
                      Expanded(
                        child: InkWell(
                          onTap: () => setState(() => _market = e.key),
                          child: Column(
                            children: [
                              Expanded(
                                child: Center(
                                  child: Text(
                                    e.value,
                                    style: TextStyle(
                                      fontSize: 14,
                                      fontWeight: _market == e.key
                                          ? FontWeight.w700
                                          : FontWeight.w500,
                                      color: _market == e.key
                                          ? AppColors.brand
                                          : scheme.onSurfaceVariant,
                                    ),
                                  ),
                                ),
                              ),
                              Container(
                                height: 2,
                                color: _market == e.key
                                    ? AppColors.brand
                                    : Colors.transparent,
                              ),
                            ],
                          ),
                        ),
                      ),
                  ],
                ),
              ),
              if ((data['tradeDate'] ?? '').toString().isNotEmpty)
                Padding(
                  padding: const EdgeInsets.fromLTRB(16, 6, 16, 0),
                  child: Text(
                    '${data['tradeDate']}',
                    style: TextStyle(
                      fontSize: 12,
                      color: scheme.onSurfaceVariant,
                    ),
                  ),
                ),
              const QuoteListHeader(),
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
                for (var i = 0; i < items.length; i++) ...[
                  const Divider(height: 1),
                  _PickRow(row: items[i], onOpen: widget.onOpenSymbol),
                ],
            ],
          );
        },
      ),
    );
  }
}

class _PickRow extends StatelessWidget {
  const _PickRow({required this.row, this.onOpen});
  final Map<String, dynamic> row;
  final void Function(String symbol, String market, String name)? onOpen;

  @override
  Widget build(BuildContext context) {
    final symbol = '${row['symbol'] ?? ''}';
    final name = '${row['name'] ?? ''}';
    final market = '${row['market'] ?? 'US'}';
    final rec = '${row['recommendation'] ?? ''}';
    final chg = (row['changePct'] as num?)?.toDouble();
    final last =
        (row['last'] as num?)?.toDouble() ?? (row['price'] as num?)?.toDouble();
    final tone = () {
      final t = rec.toLowerCase();
      if (t.contains('买') ||
          t.contains('多') ||
          t.contains('buy') ||
          t.contains('bull')) {
        return AppColors.up;
      }
      if (t.contains('卖') ||
          t.contains('空') ||
          t.contains('sell') ||
          t.contains('bear')) {
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
    Widget? tag;
    if (rec.isNotEmpty) {
      tag = Container(
        padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 1),
        decoration: BoxDecoration(
          color: tone.withValues(alpha: 0.14),
          borderRadius: BorderRadius.circular(4),
        ),
        child: Text(
          rec,
          style: TextStyle(
            fontSize: 10,
            color: tone,
            fontWeight: FontWeight.w700,
          ),
        ),
      );
    }
    return QuoteListRow(
      name: name.isEmpty ? symbol : name,
      symbol: symbol,
      marketLabel: marketLabel,
      last: last,
      changePct: chg,
      leadingExtra: tag,
      onTap: onOpen == null || symbol.isEmpty
          ? null
          : () => onOpen!(symbol, market, name),
    );
  }
}
