/// 极速单仓位：A 股 100 股一手，港美 1 股。不按板手（港股每票不同）估算。
int lotSizeForMarket(String market) => market.toUpperCase() == 'CN' ? 100 : 1;

String cashCurrencyForMarket(String market) => switch (market.toUpperCase()) {
  'CN' => 'CNY',
  'HK' => 'HKD',
  _ => 'USD',
};

/// 按购买力 / 可卖数量把 25/50/75/100% 落成股数。
///
/// 买入：`floor(cash / price / lot) * lot` 再按百分比向下取整到手数。
/// 卖出：可卖 × 百分比，A 股再向下取整到 100。
/// 缺价格、现金或可卖时返回 0，由 UI 提示，不编造手数。
int ticketQtyForPercent({
  required int percent,
  required String side,
  required String market,
  double? price,
  double? cash,
  double? sellable,
}) {
  if (percent <= 0) {
    return 0;
  }
  final lot = lotSizeForMarket(market);
  final pct = percent.clamp(1, 100);
  if (side == 'sell') {
    final avail = sellable ?? 0;
    if (avail <= 0) {
      return 0;
    }
    final raw = (avail * pct / 100).floor();
    if (lot <= 1) {
      return raw;
    }
    return (raw ~/ lot) * lot;
  }
  if (price == null || price <= 0 || cash == null || cash <= 0) {
    return 0;
  }
  final maxShares = (cash / price / lot).floor() * lot;
  if (maxShares <= 0) {
    return 0;
  }
  return ((maxShares / lot) * pct / 100).floor() * lot;
}
