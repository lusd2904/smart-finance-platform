/// 三市场交易时段：美股始终展示；港股/A 股仅开盘时段展示。
/// 开收盘用各市场本地时区（美东 / 香港 / 北京），与 UI 北京时间展示无关。
class MarketSession {
  const MarketSession({
    required this.market,
    required this.isOpen,
    required this.sessionName,
    required this.tag,
  });

  final String market;
  final bool isOpen;
  final String sessionName;
  final String tag;

  String get label {
    const names = {'US': '美股', 'HK': '港股', 'CN': 'A股'};
    return '${names[market] ?? market}·$sessionName';
  }

  /// 顶栏是否展示该市场指数。
  bool get showChip => market == 'US' || isOpen;

  /// 分钟/分时 K 线是否走交易侧实时接口。
  /// 美股：任意非 closed 时段（盘前/盘中/盘后/夜盘）；港股/A 股：开盘。
  bool get liveForMinuteKline => market == 'US' ? tag != 'closed' : isOpen;
}

class MarketSessionClock {
  MarketSessionClock({DateTime? nowUtc}) : _fixedUtc = nowUtc;

  final DateTime? _fixedUtc;

  DateTime get _nowUtc => _fixedUtc ?? DateTime.now().toUtc();

  MarketSession of(String market) {
    final m = market.toUpperCase();
    if (m == 'US') return _us();
    if (m == 'HK') return _asia(m, offsetHours: 8, windows: const [(570, 720), (780, 960)]);
    if (m == 'CN') return _asia(m, offsetHours: 8, windows: const [(570, 690), (780, 900)]);
    return MarketSession(market: m, isOpen: false, sessionName: '--', tag: 'closed');
  }

  MarketSession _us() {
    final dst = _usDst(_nowUtc);
    final local = _nowUtc.add(Duration(hours: dst ? -4 : -5));
    final minutes = local.hour * 60 + local.minute;
    final weekend = local.weekday >= DateTime.saturday;
    if (weekend) {
      if (local.weekday == DateTime.sunday && minutes >= 20 * 60) {
        return const MarketSession(market: 'US', isOpen: true, sessionName: '夜盘', tag: 'overnight');
      }
      return const MarketSession(market: 'US', isOpen: true, sessionName: '休市', tag: 'closed');
    }
    if (minutes >= 4 * 60 && minutes < 9 * 60 + 30) {
      return const MarketSession(market: 'US', isOpen: true, sessionName: '盘前', tag: 'pre');
    }
    if (minutes >= 9 * 60 + 30 && minutes < 16 * 60) {
      return const MarketSession(market: 'US', isOpen: true, sessionName: '盘中', tag: 'regular');
    }
    if (minutes >= 16 * 60 && minutes < 20 * 60) {
      return const MarketSession(market: 'US', isOpen: true, sessionName: '盘后', tag: 'post');
    }
    return const MarketSession(market: 'US', isOpen: true, sessionName: '夜盘', tag: 'overnight');
  }

  MarketSession _asia(
    String market, {
    required int offsetHours,
    required List<(int, int)> windows,
  }) {
    final local = _nowUtc.add(Duration(hours: offsetHours));
    final weekend = local.weekday >= DateTime.saturday;
    final minutes = local.hour * 60 + local.minute;
    final open = !weekend && windows.any((w) => minutes >= w.$1 && minutes < w.$2);
    return MarketSession(
      market: market,
      isOpen: open,
      sessionName: open ? '盘中' : (weekend ? '休市' : '已收盘'),
      tag: open ? 'regular' : 'closed',
    );
  }

  /// 美国夏令时粗略：3 月第二个周日到 11 月第一个周日。
  static bool _usDst(DateTime utc) {
    final month = utc.month;
    if (month > 3 && month < 11) return true;
    if (month < 3 || month > 11) return false;
    return month == 3 ? utc.day >= 8 : utc.day < 8;
  }
}

/// 终端 K 线路由：日/周/月走行情 Influx；分钟级在开盘走交易侧 quoteKline。
/// 美股分时/1 分钟（盘前/盘中/盘后/夜盘）强制 period=1min、limit≈500，覆盖夜盘曲线；
/// 港股/A 股（及美股休市）收盘则回落到当日日 K。
class TerminalKlineRoute {
  const TerminalKlineRoute({
    required this.useQuote,
    required this.period,
    this.limit = 80,
  });

  final bool useQuote;
  final String period;
  final int limit;
}

bool isMinuteKlinePeriod(String period) {
  const minute = {'intraday', '1min', '5min', 'm5', '15min'};
  return minute.contains(period.toLowerCase());
}

String normalizeKlinePeriod(String period) {
  final p = period.toLowerCase();
  if (p == 'm5') return '5min';
  return p;
}

TerminalKlineRoute resolveTerminalKline({
  required String market,
  required String period,
  MarketSessionClock? clock,
}) {
  final raw = period.toLowerCase();
  if (!isMinuteKlinePeriod(raw)) {
    return TerminalKlineRoute(
      useQuote: false,
      period: normalizeKlinePeriod(raw),
    );
  }
  final session = (clock ?? MarketSessionClock()).of(market);
  if (session.liveForMinuteKline) {
    var p = normalizeKlinePeriod(raw);
    var limit = 80;
    if (session.market == 'US' && (p == 'intraday' || p == '1min')) {
      p = '1min';
      limit = 500;
    }
    return TerminalKlineRoute(useQuote: true, period: p, limit: limit);
  }
  return const TerminalKlineRoute(useQuote: false, period: 'daily');
}
