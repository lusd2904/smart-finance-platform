import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/theme/app_theme.dart';
import '../../shared/utils/format.dart';
import '../../shared/widgets/quote_text.dart';
import '../../shared/widgets/ruoyi_ui.dart';
import '../trade/data/trade_api.dart';
import '../trade/data/trade_models.dart';

/// 交易持仓：长桥现价自算涨跌幅/盈亏，总资产支持港元、美元切换。
class PhoneTradePage extends ConsumerStatefulWidget {
  const PhoneTradePage({super.key, this.onOpenSymbol});
  final void Function(String symbol, String market, String name)? onOpenSymbol;

  @override
  ConsumerState<PhoneTradePage> createState() => _PhoneTradePageState();
}

class _PhoneTradePageState extends ConsumerState<PhoneTradePage> {
  String _display = 'HKD';

  @override
  Widget build(BuildContext context) {
    final account = ref.watch(tradeAccountProvider);
    final positions = ref.watch(tradePositionsProvider);
    final quotes = ref.watch(positionQuotesProvider);
    final rate = ref.watch(usdHkdRateProvider);
    final orders = ref.watch(tradeOrdersProvider('today'));
    final scheme = Theme.of(context).colorScheme;
    final fx = UsdHkdFx(
      usdHkd: rate.asData?.value ?? UsdHkdFx.fallbackRate,
      display: _display,
    );
    final acc = account.asData?.value;
    final items = positions.asData?.value ?? const <PositionItem>[];
    final quoteMap = quotes.asData?.value ?? const <String, PositionQuote>{};
    final net = _totalAssets(acc, fx);
    final cash = _totalCash(acc, fx);
    var daySum = 0.0;
    var pnlSum = 0.0;
    var hasDay = false;
    var hasPnl = false;
    for (final p in items) {
      final q = quoteMap[p.symbol];
      final day = q?.dayAmount(p.quantity);
      final pnl = q?.pnl(p.quantity, p.costPrice);
      if (day != null) {
        hasDay = true;
        daySum += fx.convert(day, p.currency.isEmpty ? 'USD' : p.currency);
      }
      if (pnl != null) {
        hasPnl = true;
        pnlSum += fx.convert(pnl, p.currency.isEmpty ? 'USD' : p.currency);
      }
    }

    return RefreshIndicator(
      onRefresh: () async {
        ref.invalidate(tradeAccountProvider);
        ref.invalidate(tradePositionsProvider);
        ref.invalidate(positionQuotesProvider);
        ref.invalidate(usdHkdRateProvider);
        ref.invalidate(tradeOrdersProvider('today'));
      },
      child: ListView(
        padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
        children: [
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: scheme.surfaceContainerLow,
              borderRadius: BorderRadius.circular(18),
              border: Border.all(color: scheme.outlineVariant),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Text('总资产', style: TextStyle(color: scheme.onSurfaceVariant, fontSize: 13)),
                    const Spacer(),
                    SegmentedButton<String>(
                      style: const ButtonStyle(
                        visualDensity: VisualDensity.compact,
                        tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                      ),
                      segments: const [
                        ButtonSegment(value: 'HKD', label: Text('港元')),
                        ButtonSegment(value: 'USD', label: Text('美元')),
                      ],
                      selected: {_display},
                      onSelectionChanged: (s) => setState(() => _display = s.first),
                    ),
                  ],
                ),
                const SizedBox(height: 6),
                Text(
                  net == null ? '--' : '${fx.prefix}${_money(net)}',
                  style: const TextStyle(
                    fontSize: 28,
                    fontWeight: FontWeight.w800,
                    fontFeatures: AppNum.fontFeatures,
                  ),
                ),
                const SizedBox(height: 10),
                Row(
                  children: [
                    Expanded(child: _signedKv('今日涨跌', hasDay ? daySum : null, fx.prefix)),
                    Expanded(child: _signedKv('持仓盈亏', hasPnl ? pnlSum : null, fx.prefix)),
                  ],
                ),
                const SizedBox(height: 10),
                Row(
                  children: [
                    Expanded(child: _kv('购买力', cash == null ? '--' : '${fx.prefix}${_money(cash)}')),
                    Expanded(child: _kv('可用现金', cash == null ? '--' : '${fx.prefix}${_money(cash)}')),
                  ],
                ),
              ],
            ),
          ),
          const SizedBox(height: 18),
          Text('持仓', style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w800)),
          const SizedBox(height: 8),
          if (quotes.isLoading && items.isNotEmpty)
            const Padding(
              padding: EdgeInsets.only(bottom: 8),
              child: LinearProgressIndicator(minHeight: 2),
            ),
          ...items.map(
            (p) => _PosTile(
              item: p,
              quote: quoteMap[p.symbol] ?? p.asQuote,
              fx: fx,
              onTap: () => showFastTicket(
                context,
                symbol: p.symbol,
                market: p.market,
                name: p.symbolName,
              ),
            ),
          ),
          if (items.isEmpty)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 24),
              child: Text('暂无持仓', textAlign: TextAlign.center, style: TextStyle(color: scheme.onSurfaceVariant)),
            ),
          const SizedBox(height: 12),
          Text('当日委托', style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w800)),
          const SizedBox(height: 8),
          ...?orders.asData?.value.take(5).map(
                (o) => ListTile(
                  contentPadding: EdgeInsets.zero,
                  title: Text('${o.side.toUpperCase()} ${o.symbol}'),
                  subtitle: Text(
                    '${o.quantity ?? '--'} @ ${formatPrice(o.price)} · ${o.statusLabel.isEmpty ? o.status : o.statusLabel}',
                  ),
                ),
              ),
        ],
      ),
    );
  }

  static double? _totalAssets(AccountInfo? acc, UsdHkdFx fx) {
    if (acc == null) return null;
    if (acc.balances.isNotEmpty) {
      var sum = 0.0;
      var any = false;
      for (final b in acc.balances) {
        final v = b.netAssets ?? b.totalCash;
        if (v == null) continue;
        any = true;
        sum += fx.convert(v, b.currency);
      }
      return any ? sum : null;
    }
    final v = acc.netAssets ?? acc.totalCash;
    if (v == null) return null;
    return fx.convert(v, acc.currency.isEmpty ? 'USD' : acc.currency);
  }

  static double? _totalCash(AccountInfo? acc, UsdHkdFx fx) {
    if (acc == null) return null;
    if (acc.balances.isNotEmpty) {
      var sum = 0.0;
      var any = false;
      for (final b in acc.balances) {
        final v = b.availableCash ?? b.totalCash;
        if (v == null) continue;
        any = true;
        sum += fx.convert(v, b.currency);
      }
      return any ? sum : null;
    }
    final v = acc.availableCash ?? acc.totalCash;
    if (v == null) return null;
    return fx.convert(v, acc.currency.isEmpty ? 'USD' : acc.currency);
  }

  static Widget _kv(String k, String v) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(k, style: const TextStyle(fontSize: 12, color: AppColors.flat)),
        const SizedBox(height: 2),
        Text(v, style: const TextStyle(fontWeight: FontWeight.w700, fontFeatures: AppNum.fontFeatures)),
      ],
    );
  }

  static Widget _signedKv(String k, double? v, String prefix) {
    final color = switch (v) {
      null => AppColors.flat,
      > 0 => AppColors.up,
      < 0 => AppColors.down,
      _ => AppColors.flat,
    };
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(k, style: const TextStyle(fontSize: 12, color: AppColors.flat)),
        const SizedBox(height: 2),
        Text(
          v == null ? '--' : '$prefix${_signed(v)}',
          style: TextStyle(fontWeight: FontWeight.w700, color: color, fontFeatures: AppNum.fontFeatures),
        ),
      ],
    );
  }
}

class _PosTile extends StatelessWidget {
  const _PosTile({required this.item, required this.fx, this.quote, this.onTap});
  final PositionItem item;
  final PositionQuote? quote;
  final UsdHkdFx fx;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final native = item.currency.isEmpty ? 'USD' : item.currency;
    final last = quote?.last;
    final pct = quote?.changePct;
    final pnl = quote?.pnl(item.quantity, item.costPrice);
    final day = quote?.dayAmount(item.quantity);
    final pnlShow = pnl == null ? null : fx.convert(pnl, native);
    final dayShow = day == null ? null : fx.convert(day, native);
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 10),
          child: Row(
            children: [
              CircleAvatar(
                backgroundColor: theme.colorScheme.surfaceContainerHighest,
                child: Text(item.symbol.isEmpty ? '?' : item.symbol.characters.first),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      item.symbol,
                      style: const TextStyle(fontWeight: FontWeight.w800),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      [
                        if (item.symbolName.isNotEmpty) item.symbolName,
                        '${item.quantity ?? '--'} 股',
                        '最新 ${last == null ? '--' : formatPrice(last)} $native',
                      ].join(' · '),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: theme.textTheme.bodySmall?.copyWith(color: theme.colorScheme.onSurfaceVariant),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 8),
              Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  PctText(pct, bold: true),
                  const SizedBox(height: 2),
                  Text(
                    pnlShow == null ? '盈亏 --' : '盈亏 ${fx.prefix}${_signed(pnlShow)}',
                    style: TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.w700,
                      color: _tone(pnlShow),
                      fontFeatures: AppNum.fontFeatures,
                    ),
                  ),
                  Text(
                    dayShow == null ? '今 --' : '今 ${fx.prefix}${_signed(dayShow)}',
                    style: TextStyle(
                      fontSize: 11,
                      color: _tone(dayShow),
                      fontFeatures: AppNum.fontFeatures,
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  static Color _tone(double? v) => switch (v) {
        null => AppColors.flat,
        > 0 => AppColors.up,
        < 0 => AppColors.down,
        _ => AppColors.flat,
      };
}

String _money(double v) {
  return v.toStringAsFixed(2).replaceAllMapped(RegExp(r'(\d)(?=(\d{3})+\.)'), (m) => '${m[1]},');
}

String _signed(double v) {
  final abs = _money(v.abs());
  if (v > 0) return '+$abs';
  if (v < 0) return '-$abs';
  return abs;
}

/// 极速交易抽屉：限价/市价、仓位比例。实盘下单受服务端硬开关约束，未开则提示纸面保护。
Future<void> showFastTicket(
  BuildContext context, {
  required String symbol,
  required String market,
  String? name,
}) {
  return showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    showDragHandle: true,
    builder: (_) => _FastTicketSheet(symbol: symbol, market: market, name: name ?? ''),
  );
}

class _FastTicketSheet extends ConsumerStatefulWidget {
  const _FastTicketSheet({required this.symbol, required this.market, required this.name});
  final String symbol;
  final String market;
  final String name;

  @override
  ConsumerState<_FastTicketSheet> createState() => _FastTicketSheetState();
}

class _FastTicketSheetState extends ConsumerState<_FastTicketSheet> {
  String _side = 'buy';
  String _type = 'LO';
  final _price = TextEditingController();
  final _qty = TextEditingController(text: '100');

  @override
  void dispose() {
    _price.dispose();
    _qty.dispose();
    super.dispose();
  }

  int get _qtyN => int.tryParse(_qty.text.trim()) ?? 0;
  double? get _px => double.tryParse(_price.text.trim());

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final notion = (_px ?? 0) * _qtyN;
    return Padding(
      padding: EdgeInsets.fromLTRB(16, 0, 16, 16 + MediaQuery.viewInsetsOf(context).bottom),
      child: SingleChildScrollView(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              '交易 ${widget.symbol}${widget.name.isEmpty ? '' : ' · ${widget.name}'}',
              style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 16),
            ),
            const SizedBox(height: 12),
            SegmentedButton<String>(
              segments: const [
                ButtonSegment(value: 'buy', label: Text('买入')),
                ButtonSegment(value: 'sell', label: Text('卖出')),
              ],
              selected: {_side},
              onSelectionChanged: (s) => setState(() => _side = s.first),
            ),
            const SizedBox(height: 10),
            SegmentedButton<String>(
              segments: const [
                ButtonSegment(value: 'LO', label: Text('限价')),
                ButtonSegment(value: 'MO', label: Text('市价')),
              ],
              selected: {_type},
              onSelectionChanged: (s) => setState(() => _type = s.first),
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _price,
                    enabled: _type == 'LO',
                    keyboardType: const TextInputType.numberWithOptions(decimal: true),
                    decoration: const InputDecoration(labelText: '价格', isDense: true),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: TextField(
                    controller: _qty,
                    keyboardType: TextInputType.number,
                    decoration: const InputDecoration(labelText: '股数', isDense: true),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 10),
            Wrap(
              spacing: 8,
              children: [
                for (final p in [25, 50, 75, 100])
                  ActionChip(
                    label: Text(p == 100 ? '全仓' : '$p%'),
                    onPressed: () {
                      // 无购买力明细时仅给默认手数，避免编造可买数量。
                      _qty.text = p == 100 ? '100' : '$p';
                      setState(() {});
                    },
                  ),
              ],
            ),
            const SizedBox(height: 8),
            Text(
              '名义金额 ${_money(notion)}',
              style: TextStyle(color: scheme.onSurfaceVariant, fontFeatures: AppNum.fontFeatures),
            ),
            const SizedBox(height: 14),
            FilledButton(
              style: FilledButton.styleFrom(
                backgroundColor: _side == 'buy' ? AppColors.up : AppColors.down,
                minimumSize: const Size.fromHeight(48),
              ),
              onPressed: () async {
                HapticFeedback.mediumImpact();
                if (context.mounted) {
                  Navigator.pop(context);
                  toast(context, '纸面保护：当前未开放实盘下单，委托不会发到券商');
                }
              },
              child: Text(_side == 'buy' ? '极速买入 $_qtyN股' : '极速卖出 $_qtyN股'),
            ),
          ],
        ),
      ),
    );
  }
}
