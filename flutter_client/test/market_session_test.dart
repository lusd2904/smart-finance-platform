import 'package:flutter_test/flutter_test.dart';

import 'package:flutter_client/core/market/market_session.dart';
import 'package:flutter_client/features/market/data/market_models.dart';

void main() {
  test('美股始终展示，周末也显示', () {
    final clock = MarketSessionClock(nowUtc: DateTime.utc(2026, 8, 23, 12));
    expect(clock.of('US').showChip, isTrue);
    expect(clock.of('HK').showChip, isFalse);
    expect(clock.of('CN').showChip, isFalse);
    expect(clock.of('US').sessionName, '休市');
  });

  test('美股周日夜盘 20:00 ET 起为 overnight', () {
    // 2026-08-24 01:00 UTC = 周日 21:00 EDT。
    final clock = MarketSessionClock(nowUtc: DateTime.utc(2026, 8, 24, 1));
    expect(clock.of('US').tag, 'overnight');
    expect(clock.of('US').liveForMinuteKline, isTrue);
    expect(clock.of('US').sessionName, '夜盘');
  });

  test('北京时间上午 10:00 港股 A 股开盘', () {
    final clock = MarketSessionClock(nowUtc: DateTime.utc(2026, 8, 25, 2, 0));
    expect(clock.of('CN').isOpen, isTrue);
    expect(clock.of('HK').isOpen, isTrue);
    expect(clock.of('CN').showChip, isTrue);
    expect(clock.of('HK').showChip, isTrue);
    expect(clock.of('US').showChip, isTrue);
  });

  test('午休隐藏港股 A 股', () {
    final clock = MarketSessionClock(nowUtc: DateTime.utc(2026, 8, 25, 4, 30));
    expect(clock.of('CN').isOpen, isFalse);
    expect(clock.of('HK').isOpen, isFalse);
    expect(clock.of('US').showChip, isTrue);
  });

  test('A 股 15:20 已收盘、港股仍开', () {
    final clock = MarketSessionClock(nowUtc: DateTime.utc(2026, 8, 25, 7, 20));
    expect(clock.of('CN').isOpen, isFalse);
    expect(clock.of('HK').isOpen, isTrue);
    expect(clock.of('HK').showChip, isTrue);
  });

  test('分钟 K 线：美股非 closed 走 quote 1min，休市回落日 K', () {
    final live = MarketSessionClock(nowUtc: DateTime.utc(2026, 8, 25, 15));
    expect(live.of('US').liveForMinuteKline, isTrue);
    final intra = resolveTerminalKline(market: 'US', period: 'intraday', clock: live);
    expect(intra.useQuote, isTrue);
    expect(intra.period, '1min');
    expect(intra.limit, 500);
    final oneMin = resolveTerminalKline(market: 'US', period: '1min', clock: live);
    expect(oneMin.useQuote, isTrue);
    expect(oneMin.period, '1min');
    expect(oneMin.limit, 500);
    final m5 = resolveTerminalKline(market: 'US', period: 'm5', clock: live);
    expect(m5.useQuote, isTrue);
    expect(m5.period, '5min');

    final weekend = MarketSessionClock(nowUtc: DateTime.utc(2026, 8, 23, 12));
    expect(weekend.of('US').liveForMinuteKline, isFalse);
    final closed = resolveTerminalKline(market: 'US', period: 'intraday', clock: weekend);
    expect(closed.useQuote, isFalse);
    expect(closed.period, 'daily');
  });

  test('美股开收盘用美东时间而非北京时间', () {
    // 01:45 UTC = 北京 09:45 开盘，美东夏令 21:45（前一日）夜盘。
    final clock = MarketSessionClock(nowUtc: DateTime.utc(2026, 8, 25, 1, 45));
    expect(clock.of('CN').isOpen, isTrue);
    expect(clock.of('US').tag, 'overnight');
    expect(clock.of('US').liveForMinuteKline, isTrue);
    final route = resolveTerminalKline(market: 'US', period: 'intraday', clock: clock);
    expect(route.useQuote, isTrue);
    expect(route.period, '1min');
    expect(route.limit, 500);
  });

  test('美股盘前/盘后/夜盘分时均走 1min quote', () {
    final samples = <(DateTime, String)>[
      (DateTime.utc(2026, 8, 25, 12, 0), 'pre'), // 08:00 EDT
      (DateTime.utc(2026, 8, 25, 20, 30), 'post'), // 16:30 EDT
      (DateTime.utc(2026, 8, 25, 3, 0), 'overnight'), // 23:00 EDT 24日
    ];
    for (final s in samples) {
      final clock = MarketSessionClock(nowUtc: s.$1);
      expect(clock.of('US').tag, s.$2, reason: s.$2);
      final route = resolveTerminalKline(market: 'US', period: 'intraday', clock: clock);
      expect(route.useQuote, isTrue, reason: s.$2);
      expect(route.period, '1min', reason: s.$2);
      expect(route.limit, 500, reason: s.$2);
    }
  });

  test('分钟 K 线：港股/A 股开盘走 quote，收盘回落日 K', () {
    final open = MarketSessionClock(nowUtc: DateTime.utc(2026, 8, 25, 2));
    expect(open.of('HK').liveForMinuteKline, isTrue);
    expect(open.of('CN').liveForMinuteKline, isTrue);
    expect(
      resolveTerminalKline(market: 'HK', period: '5min', clock: open).useQuote,
      isTrue,
    );

    final closed = MarketSessionClock(nowUtc: DateTime.utc(2026, 8, 25, 10));
    expect(closed.of('HK').isOpen, isFalse);
    expect(closed.of('CN').isOpen, isFalse);
    final hk = resolveTerminalKline(market: 'HK', period: 'intraday', clock: closed);
    final cn = resolveTerminalKline(market: 'CN', period: 'm5', clock: closed);
    expect(hk.useQuote, isFalse);
    expect(hk.period, 'daily');
    expect(cn.useQuote, isFalse);
    expect(cn.period, 'daily');
  });

  test('日/周/月 K 始终走行情 Influx', () {
    final live = MarketSessionClock(nowUtc: DateTime.utc(2026, 8, 25, 15));
    for (final p in ['daily', 'weekly', 'monthly']) {
      final route = resolveTerminalKline(market: 'US', period: p, clock: live);
      expect(route.useQuote, isFalse, reason: p);
      expect(route.period, p);
    }
  });

  test('KlineBar.listFrom 兼容 klines/items/bars', () {
    const bar = {
      'date': '2026-08-25',
      'open': 10,
      'high': 11,
      'low': 9,
      'close': 10.5,
      'volume': 100,
    };
    expect(KlineBar.listFrom({'klines': [bar]}), hasLength(1));
    expect(KlineBar.listFrom({'items': [bar]}), hasLength(1));
    expect(KlineBar.listFrom({'bars': [bar]}), hasLength(1));
    expect(KlineBar.listFrom([bar]).first.close, 10.5);
  });
}
