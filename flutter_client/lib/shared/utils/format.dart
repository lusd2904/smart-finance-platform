/// 数值格式化：null 显示占位符「--」，金额自动换手亿。
library;

final _tzSuffix = RegExp(r'[zZ]$|[+-]\d{2}:?\d{2}$');

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

/// 展示用北京时间（Asia/Shanghai），不含 `Z` / 偏移 / `T`。
/// 带时区的 ISO 按绝对时刻转 UTC+8；朴素字符串视为已是北京墙上时钟。
/// [DateTime] 先转 UTC 再 +8。
String formatBeijingTime(Object? input, {bool withSeconds = true}) {
  if (input == null) return '';
  if (input is DateTime) {
    return _formatUtcPlus8(input, withSeconds: withSeconds);
  }
  final raw = input.toString().trim();
  if (raw.isEmpty) return '';
  if (_tzSuffix.hasMatch(raw)) {
    final parsed = _parseZoned(raw);
    if (parsed != null) {
      return _padWallClock(
        parsed.year,
        parsed.month,
        parsed.day,
        parsed.hour,
        parsed.minute,
        parsed.second,
        withSeconds: withSeconds,
        hasTime: true,
      );
    }
  }
  return _normalizeBeijingString(raw, withSeconds: withSeconds);
}

/// 图轴短标签：有时刻则 `MM-dd HH:mm`，否则 `MM-dd`。不含 Z。
String formatBeijingChartLabel(Object? input) {
  final full = formatBeijingTime(input, withSeconds: false);
  if (full.isEmpty) return '';
  if (RegExp(r'^\d{4}-').hasMatch(full)) {
    if (full.length >= 16) return full.substring(5, 16);
    if (full.length >= 10) return full.substring(5, 10);
  }
  return full;
}

String _formatUtcPlus8(DateTime dt, {required bool withSeconds}) {
  final bj = dt.toUtc().add(const Duration(hours: 8));
  return _padWallClock(
    bj.year,
    bj.month,
    bj.day,
    bj.hour,
    bj.minute,
    bj.second,
    withSeconds: withSeconds,
    hasTime: true,
  );
}

String _two(int n) => n.toString().padLeft(2, '0');

String _padWallClock(
  int year,
  int month,
  int day,
  int hour,
  int minute,
  int second, {
  required bool withSeconds,
  required bool hasTime,
}) {
  final date = '$year-${_two(month)}-${_two(day)}';
  if (!hasTime) return date;
  final hm = '${_two(hour)}:${_two(minute)}';
  if (!withSeconds) return '$date $hm';
  return '$date $hm:${_two(second)}';
}

String _normalizeBeijingString(String raw, {required bool withSeconds}) {
  var text = raw.replaceAll('T', ' ').replaceAll(RegExp(r'[zZ]'), '').trim();
  text = text.replaceFirst(RegExp(r'[+-]\d{2}:?\d{2}$'), '').trim();
  text = text.replaceFirst(RegExp(r'\.\d+'), '');
  final m = RegExp(
    r'^(\d{4})[-/](\d{1,2})[-/](\d{1,2})(?:[ ](\d{1,2}):(\d{1,2})(?::(\d{1,2}))?)?$',
  ).firstMatch(text);
  if (m == null) return text;
  final hour = m[4];
  return _padWallClock(
    int.parse(m[1]!),
    int.parse(m[2]!),
    int.parse(m[3]!),
    hour == null ? 0 : int.parse(hour),
    hour == null ? 0 : int.parse(m[5]!),
    int.parse(m[6] ?? '0'),
    withSeconds: withSeconds,
    hasTime: hour != null,
  );
}

DateTime? _parseZoned(String raw) {
  var text = raw.trim();
  if (!text.contains('T') && text.contains(' ')) {
    text = text.replaceFirst(' ', 'T');
  }
  final utc = DateTime.tryParse(text)?.toUtc();
  if (utc == null) return null;
  final bj = utc.add(const Duration(hours: 8));
  return DateTime(
    bj.year,
    bj.month,
    bj.day,
    bj.hour,
    bj.minute,
    bj.second,
    bj.millisecond,
  );
}

/// 兼容 'yyyy-MM-dd HH:mm:ss' / 'yyyy-MM-dd' / 'MM-dd HH:mm'（缺省年份按当前年）。
/// ISO `Z` / 偏移按绝对时刻转到北京墙上时钟（朴素 DateTime，便于与本地 now 做差）。
DateTime? _parseLoose(String text) {
  final raw = text.trim();
  if (_tzSuffix.hasMatch(raw)) {
    return _parseZoned(raw);
  }
  final parts = text.split(RegExp(r'[ :\-T]')).where((p) => p.isNotEmpty).toList();
  if (parts.isNotEmpty && parts.last.contains('.')) {
    parts[parts.length - 1] = parts.last.split('.').first;
  }
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
