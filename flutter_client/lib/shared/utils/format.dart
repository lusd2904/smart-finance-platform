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

/// 北京时间字符串（'yyyy-MM-dd HH:mm:ss' 或 'MM-dd HH:mm'）→ 相对时间文案。
/// 服务端统一发北京时间字符串；客户端按本地时钟做差，跨时区误差分钟级可接受。
String formatRelativeTime(String timeText, {DateTime? now}) {
  if (timeText.isEmpty) return '';
  final parsed = _parseLoose(timeText);
  if (parsed == null) return timeText;
  final diff = (now ?? DateTime.now()).difference(parsed);
  if (diff.inSeconds < 60) return '刚刚';
  if (diff.inMinutes < 60) return '${diff.inMinutes}分钟前';
  if (diff.inHours < 24) return '${diff.inHours}小时前';
  if (diff.inDays < 30) return '${diff.inDays}天前';
  return timeText.length > 10 ? timeText.substring(0, 10) : timeText;
}

/// 兼容 'yyyy-MM-dd HH:mm:ss' / 'yyyy-MM-dd' / 'MM-dd HH:mm'（缺省年份按当前年）。
DateTime? _parseLoose(String text) {
  final parts = text.split(RegExp(r'[ :\-]')).where((p) => p.isNotEmpty).toList();
  final n = parts.map((p) => int.tryParse(p)).toList();
  if (n.any((v) => v == null)) return null;
  try {
    if (n.length >= 6) {
      return DateTime(n[0]!, n[1]!, n[2]!, n[3]!, n[4]!, n[5]!);
    }
    if (n.length == 4 || n.length == 5) {
      // MM-dd HH:mm（趋势点格式）：补当前年。
      final now = DateTime.now();
      return DateTime(now.year, n[0]!, n[1]!, n[2]!, n[3]!);
    }
    if (n.length == 3) {
      return DateTime(n[0]!, n[1]!, n[2]!);
    }
  } catch (_) {}
  return null;
}
