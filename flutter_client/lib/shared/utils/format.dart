/// 数值格式化：null 显示占位符「--」，金额自动换手亿。
library;

String formatPct(double? v) {
  if (v == null) return '--';
  final sign = v > 0 ? '+' : '';
  return '$sign${v.toStringAsFixed(2)}%';
}

String formatPrice(double? v) {
  if (v == null) return '--';
  return v.toStringAsFixed(v.abs() >= 100 ? 2 : 3);
}

/// 成交额/市值：≥1e12 万亿、≥1e8 亿、≥1e4 万，其余原值。
String formatAmountCn(double? v) {
  if (v == null || v == 0) return '--';
  if (v.abs() >= 1e12) return '${(v / 1e12).toStringAsFixed(2)}万亿';
  if (v.abs() >= 1e8) return '${(v / 1e8).toStringAsFixed(2)}亿';
  if (v.abs() >= 1e4) return '${(v / 1e4).toStringAsFixed(2)}万';
  return v.toStringAsFixed(0);
}
