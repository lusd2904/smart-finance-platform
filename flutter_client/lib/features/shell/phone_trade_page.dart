import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api/api_client.dart';
import '../../core/theme/app_theme.dart';
import '../../shared/utils/format.dart';
import '../../shared/widgets/quote_text.dart';
import '../../shared/widgets/ruoyi_ui.dart';
import '../trade/data/trade_api.dart';
import '../trade/data/trade_models.dart';
import '../trade/logic/ticket_qty.dart';

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
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Text(
                    '总资产',
                    style: TextStyle(
                      color: scheme.onSurfaceVariant,
                      fontSize: 13,
                    ),
                  ),
                  const Spacer(),
                  _CcyTap(
                    label: '港元',
                    selected: _display == 'HKD',
                    onTap: () => setState(() => _display = 'HKD'),
                  ),
                  const SizedBox(width: 12),
                  _CcyTap(
                    label: '美元',
                    selected: _display == 'USD',
                    onTap: () => setState(() => _display = 'USD'),
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
                  Expanded(
                    child: _signedKv('今日涨跌', hasDay ? daySum : null, fx.prefix),
                  ),
                  Expanded(
                    child: _signedKv('持仓盈亏', hasPnl ? pnlSum : null, fx.prefix),
                  ),
                ],
              ),
              const SizedBox(height: 10),
              _kv('可用现金', cash == null ? '--' : '${fx.prefix}${_money(cash)}'),
            ],
          ),
          const SizedBox(height: 18),
          Text(
            '持仓',
            style: Theme.of(context).textTheme.titleMedium
                ?.copyWith(fontWeight: FontWeight.w800),
          ),
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
              onTap: () => _onPosTap(p),
              onTrade: () => _openTicket(p),
            ),
          ),
          if (items.isEmpty)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 24),
              child: Text(
                '暂无持仓',
                textAlign: TextAlign.center,
                style: TextStyle(color: scheme.onSurfaceVariant),
              ),
            ),
          const SizedBox(height: 12),
          Text(
            '当日委托',
            style: Theme.of(context).textTheme.titleMedium
                ?.copyWith(fontWeight: FontWeight.w800),
          ),
          const SizedBox(height: 8),
          ...?orders.asData?.value
              .take(8)
              .map(
                (o) => ListTile(
                  contentPadding: EdgeInsets.zero,
                  title: Text('${o.side.toUpperCase()} ${o.symbol}'),
                  subtitle: Text(
                    '${o.quantity ?? '--'} @ ${formatPrice(o.price)} · ${o.statusLabel.isEmpty ? o.status : o.statusLabel}',
                  ),
                  trailing: (o.open && (o.orderId ?? '').isNotEmpty)
                      ? TextButton(
                          onPressed: () async {
                            final ok = await confirm(
                              context,
                              '撤销 ${o.symbol} 委托？',
                            );
                            if (!ok) {
                              return;
                            }
                            try {
                              final r = await ref
                                  .read(tradeApiProvider)
                                  .cancelOrder(o.orderId!);
                              if (context.mounted) {
                                toast(
                                  context,
                                  (r['message'] as String?)
                                              ?.trim()
                                              .isNotEmpty ==
                                          true
                                      ? r['message'] as String
                                      : '已提交撤单',
                                );
                              }
                              ref.invalidate(tradeOrdersProvider('today'));
                              ref.invalidate(tradePositionsProvider);
                            } catch (e) {
                              if (context.mounted) {
                                toast(
                                  context,
                                  describeApiError(e),
                                  error: true,
                                );
                              }
                            }
                          },
                          child: const Text('撤'),
                        )
                      : null,
                ),
              ),
        ],
      ),
    );
  }

  void _onPosTap(PositionItem p) {
    final open = widget.onOpenSymbol;
    if (open != null) {
      open(p.symbol, p.market, p.symbolName);
      return;
    }
    _openTicket(p);
  }

  void _openTicket(PositionItem p) {
    final last =
        ref.read(positionQuotesProvider).asData?.value[p.symbol]?.last ??
        p.last;
    showFastTicket(
      context,
      symbol: p.symbol,
      market: p.market,
      name: p.symbolName,
      last: last,
    );
  }

  static double? _totalAssets(AccountInfo? acc, UsdHkdFx fx) {
    if (acc == null) {
      return null;
    }
    if (acc.balances.isNotEmpty) {
      var sum = 0.0;
      var any = false;
      for (final b in acc.balances) {
        final v = b.netAssets ?? b.totalCash;
        if (v == null) {
          continue;
        }
        any = true;
        sum += fx.convert(v, b.currency);
      }
      return any ? sum : null;
    }
    final v = acc.netAssets ?? acc.totalCash;
    if (v == null) {
      return null;
    }
    return fx.convert(v, acc.currency.isEmpty ? 'USD' : acc.currency);
  }

  static double? _totalCash(AccountInfo? acc, UsdHkdFx fx) {
    if (acc == null) {
      return null;
    }
    if (acc.balances.isNotEmpty) {
      var sum = 0.0;
      var any = false;
      for (final b in acc.balances) {
        final v = b.availableCash ?? b.totalCash;
        if (v == null) {
          continue;
        }
        any = true;
        sum += fx.convert(v, b.currency);
      }
      return any ? sum : null;
    }
    final v = acc.availableCash ?? acc.totalCash;
    if (v == null) {
      return null;
    }
    return fx.convert(v, acc.currency.isEmpty ? 'USD' : acc.currency);
  }

  static Widget _kv(String k, String v) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(k, style: const TextStyle(fontSize: 12, color: AppColors.flat)),
        const SizedBox(height: 2),
        Text(
          v,
          style: const TextStyle(
            fontWeight: FontWeight.w700,
            fontFeatures: AppNum.fontFeatures,
          ),
        ),
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
          style: TextStyle(
            fontWeight: FontWeight.w700,
            color: color,
            fontFeatures: AppNum.fontFeatures,
          ),
        ),
      ],
    );
  }
}

class _CcyTap extends StatelessWidget {
  const _CcyTap({
    required this.label,
    required this.selected,
    required this.onTap,
  });
  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final muted = Theme.of(context).colorScheme.onSurfaceVariant;
    return GestureDetector(
      onTap: onTap,
      behavior: HitTestBehavior.opaque,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 2),
        child: Text(
          label,
          style: TextStyle(
            fontSize: 13,
            fontWeight: selected ? FontWeight.w800 : FontWeight.w500,
            color: selected ? AppColors.brand : muted,
          ),
        ),
      ),
    );
  }
}

class _PosTile extends StatelessWidget {
  const _PosTile({
    required this.item,
    required this.fx,
    this.quote,
    this.onTap,
    this.onTrade,
  });
  final PositionItem item;
  final PositionQuote? quote;
  final UsdHkdFx fx;
  final VoidCallback? onTap;
  final VoidCallback? onTrade;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final native = item.currency.isEmpty ? 'USD' : item.currency;
    final pct = quote?.changePct;
    final pnl = quote?.pnl(item.quantity, item.costPrice);
    final pnlShow = pnl == null ? null : fx.convert(pnl, native);
    final name = item.symbolName.isNotEmpty ? item.symbolName : item.symbol;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        children: [
          Expanded(
            child: Material(
              color: Colors.transparent,
              child: InkWell(
                onTap: onTap,
                child: Padding(
                  padding: const EdgeInsets.symmetric(vertical: 6),
                  child: Row(
                    children: [
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              name,
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: const TextStyle(
                                fontWeight: FontWeight.w800,
                                fontSize: 15,
                                height: 1.15,
                              ),
                            ),
                            const SizedBox(height: 2),
                            Text(
                              '${item.symbol} · ${item.quantity ?? '--'} 股',
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: theme.textTheme.bodySmall?.copyWith(
                                color: theme.colorScheme.onSurfaceVariant,
                                fontSize: 11,
                                height: 1.2,
                              ),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(width: 8),
                      Column(
                        crossAxisAlignment: CrossAxisAlignment.end,
                        children: [
                          PriceText(
                            quote?.last ?? item.last,
                            style: const TextStyle(
                              fontWeight: FontWeight.w800,
                              fontSize: 15,
                              fontFeatures: AppNum.fontFeatures,
                            ),
                          ),
                          PctText(pct, bold: true),
                          Text(
                            pnlShow == null
                                ? '盈亏 --'
                                : '盈亏 ${fx.prefix}${_signed(pnlShow)}',
                            style: TextStyle(
                              fontSize: 12,
                              fontWeight: FontWeight.w700,
                              color: _tone(pnlShow),
                              fontFeatures: AppNum.fontFeatures,
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
          TextButton(
            style: TextButton.styleFrom(
              visualDensity: VisualDensity.compact,
              tapTargetSize: MaterialTapTargetSize.shrinkWrap,
              padding: const EdgeInsets.symmetric(horizontal: 8),
              minimumSize: Size.zero,
            ),
            onPressed: onTrade,
            child: const Text('交易'),
          ),
        ],
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
  return v
      .toStringAsFixed(2)
      .replaceAllMapped(RegExp(r'(\d)(?=(\d{3})+\.)'), (m) => '${m[1]},');
}

String _signed(double v) {
  final abs = _money(v.abs());
  if (v > 0) {
    return '+$abs';
  }
  if (v < 0) {
    return '-$abs';
  }
  return abs;
}

/// 极速交易抽屉：限价/市价、仓位比例，提交 POST /trade/order。
Future<void> showFastTicket(
  BuildContext context, {
  required String symbol,
  required String market,
  String? name,
  String side = 'buy',
  double? price,
  double? last,
}) {
  return showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    showDragHandle: true,
    builder: (_) => _FastTicketSheet(
      symbol: symbol,
      market: market,
      name: name ?? '',
      side: side,
      price: price,
      last: last,
    ),
  );
}

class _FastTicketSheet extends ConsumerStatefulWidget {
  const _FastTicketSheet({
    required this.symbol,
    required this.market,
    required this.name,
    this.side = 'buy',
    this.price,
    this.last,
  });
  final String symbol;
  final String market;
  final String name;
  final String side;
  final double? price;
  final double? last;

  @override
  ConsumerState<_FastTicketSheet> createState() => _FastTicketSheetState();
}

class _FastTicketSheetState extends ConsumerState<_FastTicketSheet> {
  late String _side = widget.side == 'sell' ? 'sell' : 'buy';
  String _type = 'LO';
  bool _busy = false;
  late final TextEditingController _price = TextEditingController(
    text: widget.price != null
        ? widget.price!.toString()
        : (widget.last != null ? widget.last!.toString() : ''),
  );
  final _qty = TextEditingController();

  @override
  void initState() {
    super.initState();
    _price.addListener(() {
      if (mounted) {
        setState(() {});
      }
    });
  }

  @override
  void dispose() {
    _price.dispose();
    _qty.dispose();
    super.dispose();
  }

  int get _qtyN => int.tryParse(_qty.text.trim()) ?? 0;
  double? get _px => double.tryParse(_price.text.trim());

  double? get _refPrice {
    final typed = _px;
    if (typed != null && typed > 0) {
      return typed;
    }
    return widget.last;
  }

  double? _cashOf(AccountInfo? acc) {
    if (acc == null) {
      return null;
    }
    final ccy = cashCurrencyForMarket(widget.market);
    return acc.balanceOf(ccy)?.availableCash ??
        (acc.currency.toUpperCase() == ccy ? acc.availableCash : null);
  }

  double? _sellableOf(List<PositionItem> items) {
    for (final p in items) {
      if (p.symbol.toUpperCase() == widget.symbol.toUpperCase() ||
          p.quoteSymbol.toUpperCase() == widget.symbol.toUpperCase()) {
        return p.availableQuantity ?? p.quantity;
      }
    }
    return null;
  }

  void _applyPercent(int percent) {
    final acc = ref.read(tradeAccountProvider).asData?.value;
    final positions =
        ref.read(tradePositionsProvider).asData?.value ??
        const <PositionItem>[];
    final n = ticketQtyForPercent(
      percent: percent,
      side: _side,
      market: widget.market,
      price: _refPrice,
      cash: _cashOf(acc),
      sellable: _sellableOf(positions),
    );
    if (n <= 0) {
      toast(context, _side == 'sell' ? '无可卖仓位' : '购买力不足或缺少价格', error: true);
      return;
    }
    _qty.text = '$n';
    setState(() {});
  }

  Future<void> _submit() async {
    HapticFeedback.mediumImpact();
    if (_qtyN <= 0) {
      toast(context, '请输入股数', error: true);
      return;
    }
    if (_type == 'LO' && (_px == null || _px! <= 0)) {
      toast(context, '限价单请填写有效价格', error: true);
      return;
    }
    setState(() => _busy = true);
    try {
      final r = await ref
          .read(tradeApiProvider)
          .submitOrder(
            symbol: widget.symbol,
            market: widget.market,
            side: _side,
            orderType: _type,
            quantity: _qtyN,
            price: _type == 'LO' ? _px : null,
          );
      if (!mounted) {
        return;
      }
      final ok = r['ok'] == true || r['orderId'] != null;
      toast(
        context,
        (r['message'] as String?)?.trim().isNotEmpty == true
            ? r['message'] as String
            : (ok ? '已提交委托' : '下单失败'),
        error: !ok,
      );
      ref.invalidate(tradeAccountProvider);
      ref.invalidate(tradePositionsProvider);
      ref.invalidate(tradeOrdersProvider('today'));
      Navigator.pop(context);
    } catch (e) {
      if (mounted) {
        toast(context, describeApiError(e), error: true);
      }
    } finally {
      if (mounted) {
        setState(() => _busy = false);
      }
    }
  }

  String _ticketHint(int maxQty) {
    if (_side == 'sell') {
      return maxQty > 0 ? '可卖 $maxQty 股' : '无可卖仓位';
    }
    if (_refPrice == null) {
      return '填写价格后可按仓位百分比下单';
    }
    return maxQty > 0 ? '可买 $maxQty 股' : '购买力不足';
  }

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final notion = (_refPrice ?? 0) * _qtyN;
    final acc = ref.watch(tradeAccountProvider).asData?.value;
    final positions =
        ref.watch(tradePositionsProvider).asData?.value ??
        const <PositionItem>[];
    final maxQty = ticketQtyForPercent(
      percent: 100,
      side: _side,
      market: widget.market,
      price: _refPrice,
      cash: _cashOf(acc),
      sellable: _sellableOf(positions),
    );
    return Padding(
      padding: EdgeInsets.fromLTRB(
        16,
        0,
        16,
        16 + MediaQuery.viewInsetsOf(context).bottom,
      ),
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
                    keyboardType: const TextInputType.numberWithOptions(
                      decimal: true,
                    ),
                    decoration: const InputDecoration(
                      labelText: '价格',
                      isDense: true,
                    ),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: TextField(
                    controller: _qty,
                    keyboardType: TextInputType.number,
                    decoration: const InputDecoration(
                      labelText: '股数',
                      isDense: true,
                    ),
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
                    onPressed: () => _applyPercent(p),
                  ),
              ],
            ),
            const SizedBox(height: 8),
            Text(
              _ticketHint(maxQty),
              style: TextStyle(
                color: scheme.onSurfaceVariant,
                fontFeatures: AppNum.fontFeatures,
              ),
            ),
            Text(
              '名义金额 ${_money(notion)}',
              style: TextStyle(
                color: scheme.onSurfaceVariant,
                fontFeatures: AppNum.fontFeatures,
              ),
            ),
            const SizedBox(height: 14),
            FilledButton(
              style: FilledButton.styleFrom(
                backgroundColor: _side == 'buy' ? AppColors.up : AppColors.down,
                minimumSize: const Size.fromHeight(48),
              ),
              onPressed: _busy ? null : _submit,
              child: Text(
                _busy
                    ? '提交中…'
                    : (_side == 'buy' ? '极速买入 $_qtyN股' : '极速卖出 $_qtyN股'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
