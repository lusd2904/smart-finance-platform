import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:flutter_client/core/market/market_session.dart';
import 'package:flutter_client/features/market/data/market_api.dart';
import 'package:flutter_client/features/market/data/market_models.dart';
import 'package:flutter_client/features/trade/data/trade_api.dart';
import 'package:flutter_client/features/trade/data/trade_models.dart';
import 'package:flutter_client/features/web/trade_terminal_page.dart';
import 'package:flutter_client/shared/utils/format.dart';

final _watchItems = [
  const WatchlistItem(
    symbol: 'AAPL',
    name: 'Apple',
    market: 'US',
    changeRate: 1.2,
    groups: ['科技'],
  ),
  const WatchlistItem(
    symbol: '0700',
    name: '腾讯',
    market: 'HK',
    changeRate: -0.5,
    groups: ['港股'],
  ),
];

class _FakeMarketApi extends MarketApi {
  _FakeMarketApi() : super(Dio());

  final klineCalls = <Map<String, String>>[];

  @override
  Future<List<IndexQuote>> indexQuotes() async => const [
        IndexQuote(
          symbol: 'usIXIC',
          name: '纳斯达克',
          market: 'US',
          last: 17800,
          changePct: 0.5,
        ),
      ];

  @override
  Future<List<WatchlistItem>> watchlistRows({int pageSize = 200}) async =>
      _watchItems;

  @override
  Future<WatchlistOverview> watchlistOverview() async => WatchlistOverview(
        items: _watchItems,
        count: _watchItems.length,
        groups: const [(name: '科技', count: 1), (name: '港股', count: 1)],
      );

  @override
  Future<List<KlineBar>> kline({
    required String symbol,
    required String market,
    String period = 'daily',
    int limit = 80,
  }) async {
    klineCalls.add({
      'symbol': symbol,
      'market': market,
      'period': period,
      'limit': '$limit',
    });
    return [
      KlineBar(
        date: '2026-08-25',
        open: 10,
        high: 11,
        low: 9,
        close: 10.5,
        volume: 100,
      ),
    ];
  }

  @override
  Future<UniversePage> universe({
    String? market,
    String? keyword,
    int pageNum = 1,
    int pageSize = 50,
  }) async {
    final kw = (keyword ?? '').toUpperCase();
    if (kw.contains('MSFT')) {
      return const UniversePage(
        rows: [
          UniverseRow(symbol: 'MSFT', name: 'Microsoft', market: 'US'),
        ],
        total: 1,
      );
    }
    return const UniversePage();
  }
}

class _FakeTradeApi extends TradeApi {
  _FakeTradeApi({this.configured = false, this.autoEnabled = false})
      : super(Dio());

  bool configured;
  bool autoEnabled;
  int saveCount = 0;
  final quoteCalls = <Map<String, String>>[];

  @override
  Future<AccountInfo> account() async => AccountInfo(
        configured: configured,
        currency: 'USD',
        availableCash: 12000,
      );

  @override
  Future<List<PositionItem>> positions() async => const [];

  @override
  Future<List<OrderItem>> orders({String scope = 'today'}) async => const [];

  @override
  Future<Map<String, dynamic>> quoteKline({
    required String symbol,
    required String market,
    String period = 'daily',
    int limit = 200,
  }) async {
    quoteCalls.add({
      'symbol': symbol,
      'market': market,
      'period': period,
      'limit': '$limit',
    });
    return {
      'klines': [
        {
          'date': '2026-08-25T02:00:00Z',
          'open': 10,
          'high': 11,
          'low': 9,
          'close': 10.2,
          'volume': 50,
        },
        {
          'date': '2026-08-25T04:00:00Z',
          'open': 10.1,
          'high': 11,
          'low': 9,
          'close': 10.4,
          'volume': 60,
        },
      ],
    };
  }

  @override
  Future<Map<String, dynamic>> quoteSnapshot({
    required String symbol,
    required String market,
  }) async =>
      const {};

  @override
  Future<DepthData> depth({
    required String symbol,
    required String market,
  }) async =>
      const DepthData();

  @override
  Future<List<TradeTick>> trades({
    required String symbol,
    required String market,
    int count = 30,
  }) async =>
      const [];

  @override
  Future<AutoTradeStatus> autoStatus() async => AutoTradeStatus(
        configured: configured,
        autoTradeEnabled: autoEnabled,
        tradingEnabled: autoEnabled,
      );

  @override
  Future<AutoTradeStatus> getAutoTradeStatus() => autoStatus();

  @override
  Future<AutoTradeStatus> saveAutoTradeSettings({
    required bool autoTradeEnabled,
    double? dailyBuyRatio,
  }) async {
    saveCount += 1;
    autoEnabled = autoTradeEnabled;
    return autoStatus();
  }
}

Future<void> _pumpTerminal(
  WidgetTester tester, {
  required _FakeMarketApi market,
  required _FakeTradeApi trade,
  MarketSessionClock? clock,
}) async {
  tester.view.devicePixelRatio = 1.0;
  tester.view.physicalSize = const Size(1400, 900);
  addTearDown(tester.view.reset);
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        marketApiProvider.overrideWith((ref) => market),
        tradeApiProvider.overrideWith((ref) => trade),
      ],
      child: MaterialApp(
        home: Scaffold(body: TradeTerminalPage(sessionClock: clock)),
      ),
    ),
  );
  await tester.pump();
  await tester.pump(const Duration(milliseconds: 50));
  await tester.pump(const Duration(milliseconds: 50));
}

void main() {
  test('自选分组过滤与组名收集', () {
    final watch = WatchlistOverview(
      items: _watchItems,
      count: 2,
      groups: const [(name: '科技', count: 1), (name: '港股', count: 1)],
    );
    expect(terminalWatchGroups(watch), ['全部', '科技', '港股']);
    expect(filterWatchlistByGroup(watch.items, '全部'), hasLength(2));
    expect(
      filterWatchlistByGroup(watch.items, '港股').single.symbol,
      '0700',
    );
    expect(watchlistContainsSymbol(watch.items, 'AAPL', 'US'), isTrue);
    expect(watchlistContainsSymbol(watch.items, 'MSFT', 'US'), isFalse);
  });

  testWidgets('分组切换选中该组第一只标的', (tester) async {
    final market = _FakeMarketApi();
    final trade = _FakeTradeApi();
    await _pumpTerminal(tester, market: market, trade: trade);

    expect(find.text('AAPL.US'), findsOneWidget);
    expect(find.text('Apple'), findsOneWidget);
    expect(find.text('腾讯'), findsOneWidget);

    await tester.tap(find.byKey(const Key('terminal-group')));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));
    await tester.tap(find.text('港股').last);
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));

    expect(find.text('0700.HK'), findsOneWidget);
    expect(find.text('腾讯'), findsOneWidget);
    expect(find.text('Apple'), findsNothing);
  });

  testWidgets('搜索宇宙标的可加载非自选代码', (tester) async {
    final market = _FakeMarketApi();
    final trade = _FakeTradeApi();
    await _pumpTerminal(tester, market: market, trade: trade);

    await tester.enterText(find.byKey(const Key('terminal-search')), 'MSFT');
    await tester.pump(const Duration(milliseconds: 350));
    await tester.pump();

    expect(find.text('Microsoft'), findsOneWidget);
    await tester.tap(find.text('Microsoft'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));

    expect(find.text('MSFT.US'), findsOneWidget);
    expect(
      market.klineCalls.any((c) => c['symbol'] == 'MSFT'),
      isTrue,
    );
  });

  testWidgets('量化开关未配置时长桥时禁用', (tester) async {
    final market = _FakeMarketApi();
    final trade = _FakeTradeApi(configured: false, autoEnabled: false);
    await _pumpTerminal(tester, market: market, trade: trade);

    final sw = tester.widget<Switch>(find.byKey(const Key('terminal-quant-switch')));
    expect(sw.onChanged, isNull);
    expect(sw.value, isFalse);
    expect(find.text('SIM'), findsOneWidget);
  });

  testWidgets('量化开关已配置时可切换并调用 settings', (tester) async {
    final market = _FakeMarketApi();
    final trade = _FakeTradeApi(configured: true, autoEnabled: false);
    await _pumpTerminal(tester, market: market, trade: trade);

    expect(find.text('LIVE'), findsOneWidget);
    final sw = tester.widget<Switch>(find.byKey(const Key('terminal-quant-switch')));
    expect(sw.onChanged, isNotNull);
    await tester.tap(find.byKey(const Key('terminal-quant-switch')));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));
    expect(trade.saveCount, 1);
    expect(trade.autoEnabled, isTrue);
  });

  testWidgets('美股盘中分时走 quote 1min 且 limit 500，画收盘折线', (tester) async {
    final market = _FakeMarketApi();
    final trade = _FakeTradeApi();
    final clock = MarketSessionClock(nowUtc: DateTime.utc(2026, 8, 25, 15));
    await _pumpTerminal(tester, market: market, trade: trade, clock: clock);

    await tester.tap(find.text('分时'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));

    expect(
      trade.quoteCalls.any(
        (c) =>
            c['symbol'] == 'AAPL' &&
            c['period'] == '1min' &&
            c['limit'] == '500',
      ),
      isTrue,
    );
    expect(find.byKey(const Key('terminal-intraday-line')), findsOneWidget);
  });

  testWidgets('港股收盘分时回落行情日 K', (tester) async {
    final market = _FakeMarketApi();
    final trade = _FakeTradeApi();
    final clock = MarketSessionClock(nowUtc: DateTime.utc(2026, 8, 25, 10));
    await _pumpTerminal(tester, market: market, trade: trade, clock: clock);

    await tester.tap(find.byKey(const Key('terminal-group')));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));
    await tester.tap(find.text('港股').last);
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));

    await tester.tap(find.text('分时'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));

    expect(
      market.klineCalls.any(
        (c) => c['symbol'] == '0700' && c['period'] == 'daily',
      ),
      isTrue,
    );
    expect(trade.quoteCalls.where((c) => c['symbol'] == '0700'), isEmpty);
    expect(find.byKey(const Key('terminal-intraday-line')), findsNothing);
  });

  test('K 线展示时间 ISO Z 转为北京墙上时钟且不含 Z', () {
    final bar = klineBarForDisplay(
      const KlineBar(date: '2026-08-25T04:00:00Z', close: 10),
    );
    expect(bar.date, '2026-08-25 12:00');
    expect(bar.date.contains('Z'), isFalse);
    expect(bar.date.contains('T'), isFalse);
    expect(formatBeijingChartLabel(bar.date), '08-25 12:00');
    expect(terminalDrawsCloseLine('intraday', [bar]), isTrue);
    expect(
      terminalDrawsCloseLine('intraday', [
        const KlineBar(date: '2026-08-25', close: 10),
      ]),
      isFalse,
    );
  });

  test('formatBeijingTime：Z / UTC DateTime 转 +8，朴素字符串不位移', () {
    expect(formatBeijingTime('2026-08-24T04:55:00Z'), '2026-08-24 12:55:00');
    expect(
      formatBeijingTime('2026-08-24T04:55:00+00:00', withSeconds: false),
      '2026-08-24 12:55',
    );
    expect(
      formatBeijingTime(DateTime.utc(2026, 8, 25, 8, 15)),
      '2026-08-25 16:15:00',
    );
    expect(formatBeijingTime('2026-08-24 20:00:00'), '2026-08-24 20:00:00');
    expect(formatBeijingTime('2026-08-24T20:00:00'), '2026-08-24 20:00:00');
    expect(formatBeijingTime('2026-08-25'), '2026-08-25');
    expect(formatBeijingTime(DateTime.utc(2026, 8, 25, 8, 15)).contains('Z'), isFalse);
    expect(formatBeijingTime(DateTime.utc(2026, 8, 25, 8, 15)).contains('T'), isFalse);
    expect(
      formatRelativeTime(
        '2026-08-24T04:00:00Z',
        now: DateTime(2026, 8, 24, 12, 5, 0),
      ),
      '5分钟前',
    );
  });
}
