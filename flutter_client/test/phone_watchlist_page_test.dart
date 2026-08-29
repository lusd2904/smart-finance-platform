import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:flutter_client/features/auth/data/auth_models.dart';
import 'package:flutter_client/features/auth/logic/session_controller.dart';
import 'package:flutter_client/features/market/data/market_api.dart';
import 'package:flutter_client/features/market/data/market_models.dart';
import 'package:flutter_client/features/market/data/market_quotes_ws.dart';
import 'package:flutter_client/features/shell/phone_watchlist_page.dart';
import 'package:flutter_client/features/trade/data/trade_api.dart';
import 'package:flutter_client/features/trade/data/trade_models.dart';
import 'package:flutter_client/features/watchlist/logic/watchlist_providers.dart';
import 'package:flutter_client/shared/widgets/quote_row.dart';

class _FakeSession extends SessionController {
  @override
  SessionState build() => const SessionState(
    status: SessionStatus.authenticated,
    user: UserInfo(userId: 1, userName: 'demo', nickName: '示例用户'),
  );
}

class _NoopQuotesHub extends StockQuotesHub {
  _NoopQuotesHub(super.ref);

  @override
  VoidCallback subscribe(
    List<({String symbol, String market})> pairs,
    void Function(List<LiveStockQuote> items) cb,
  ) {
    return () {};
  }
}

class _FakeMarketApi extends MarketApi {
  _FakeMarketApi() : super(Dio());

  final deleted = <List<int>>[];

  @override
  Future<void> deleteWatchlist(List<int> ids) async {
    deleted.add(List<int>.from(ids));
  }
}

const _watchItems = [
  WatchlistItem(
    id: 1,
    symbol: 'AAPL',
    name: '苹果',
    market: 'US',
    last: 100,
    changeRate: 1.2,
    summary: '突破均线',
  ),
  WatchlistItem(
    id: 2,
    symbol: 'TSLA',
    name: '特斯拉',
    market: 'US',
    last: 250,
    changeRate: 5.0,
  ),
  WatchlistItem(
    id: 3,
    symbol: '0700',
    name: '腾讯',
    market: 'HK',
    last: 320,
    changeRate: -0.8,
  ),
];

const _indexes = [
  IndexQuote(
    symbol: 'usINX',
    name: '标普500',
    market: 'US',
    last: 5620,
    changePct: 0.58,
  ),
  IndexQuote(
    symbol: 'usIXIC',
    name: '纳斯达克',
    market: 'US',
    last: 17820,
    changePct: 1.04,
  ),
  IndexQuote(
    symbol: 'r_hkHSI',
    name: '恒生指数',
    market: 'HK',
    last: 17800,
    changePct: -0.3,
  ),
  IndexQuote(
    symbol: 'sh000001',
    name: '上证指数',
    market: 'CN',
    last: 3200,
    changePct: 0.21,
  ),
  IndexQuote(
    symbol: 'sz399006',
    name: '创业板指数',
    market: 'CN',
    last: 2100,
    changePct: 0.4,
  ),
];

Future<void> _pump(
  WidgetTester tester, {
  _FakeMarketApi? api,
  List<WatchlistItem> items = _watchItems,
}) async {
  tester.view.devicePixelRatio = 1.0;
  tester.view.physicalSize = const Size(390, 844);
  addTearDown(tester.view.reset);
  final marketApi = api ?? _FakeMarketApi();
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        sessionController.overrideWith(_FakeSession.new),
        tradeAccountProvider.overrideWith(
          (ref) async => const AccountInfo(netAssets: 48915.7, currency: 'USD'),
        ),
        watchlistOverviewProvider.overrideWith(
          (ref) async => WatchlistOverview(
            items: items,
            count: items.length,
            bullish: 2,
            bearish: 1,
          ),
        ),
        indexQuotesProvider.overrideWith((ref) async => _indexes),
        marketQuotesStreamProvider.overrideWith(
          (ref) => Stream.value(const MarketQuoteStream()),
        ),
        marketApiProvider.overrideWith((ref) => marketApi),
        stockQuotesHubProvider.overrideWith((ref) => _NoopQuotesHub(ref)),
      ],
      child: const MaterialApp(home: Scaffold(body: PhoneWatchlistPage())),
    ),
  );
  await tester.pumpAndSettle();
}

void main() {
  test('pickWatchlistIndexes 优先三市场代码且不重复市场', () {
    expect(pickWatchlistIndexes(_indexes).map((q) => q.symbol.toLowerCase()), [
      'sh000001',
      'r_hkhsi',
      'usixic',
    ]);

    const missingSse = [
      IndexQuote(symbol: 'usIXIC', market: 'US'),
      IndexQuote(symbol: 'usINX', market: 'US'),
      IndexQuote(symbol: 'r_hkHSI', market: 'HK'),
      IndexQuote(symbol: 'sz399006', market: 'CN'),
    ];
    expect(pickWatchlistIndexes(missingSse).map((q) => q.symbol), [
      'r_hkHSI',
      'usIXIC',
      'sz399006',
    ]);

    const mixedCase = [IndexQuote(symbol: 'USIXIC', market: 'US')];
    expect(pickWatchlistIndexes(mixedCase).single.symbol, 'USIXIC');
    expect(pickWatchlistIndexes(const <IndexQuote>[]), isEmpty);
  });

  testWidgets('顶栏无胶囊，指数条三市场，可按涨跌幅排序', (tester) async {
    await _pump(tester);
    expect(find.text('净资产'), findsOneWidget);
    expect(find.textContaining('48,915.70'), findsOneWidget);
    expect(find.text('搜索代码或名称'), findsOneWidget);
    expect(find.text('上证指数'), findsOneWidget);
    expect(find.text('恒生指数'), findsOneWidget);
    expect(find.text('纳斯达克'), findsOneWidget);
    expect(find.text('标普500'), findsNothing);
    expect(find.text('创业板指数'), findsNothing);
    expect(find.text('突破均线'), findsOneWidget);

    expect(
      tester
          .widgetList<QuoteListRow>(find.byType(QuoteListRow))
          .map((r) => r.symbol),
      ['AAPL', 'TSLA', '0700'],
    );

    await tester.tap(find.text('涨跌幅'));
    await tester.pump();
    expect(
      tester
          .widgetList<QuoteListRow>(find.byType(QuoteListRow))
          .map((r) => r.symbol),
      ['TSLA', 'AAPL', '0700'],
    );

    await tester.tap(find.text('涨跌幅'));
    await tester.pump();
    expect(
      tester
          .widgetList<QuoteListRow>(find.byType(QuoteListRow))
          .map((r) => r.symbol),
      ['0700', 'AAPL', 'TSLA'],
    );

    await tester.tap(find.text('名称'));
    await tester.pump();
    expect(
      tester
          .widgetList<QuoteListRow>(find.byType(QuoteListRow))
          .map((r) => r.symbol),
      ['TSLA', '0700', 'AAPL'],
    );
  });

  testWidgets('左滑删除调用接口', (tester) async {
    final api = _FakeMarketApi();
    await _pump(tester, api: api);
    expect(find.byType(Dismissible), findsNWidgets(3));
    await tester.drag(find.byType(Dismissible).first, const Offset(-500, 0));
    await tester.pump();
    await tester.pump(const Duration(seconds: 1));
    expect(api.deleted, [
      [1],
    ]);
  });

  testWidgets('长按弹出删除确认', (tester) async {
    final api = _FakeMarketApi();
    await _pump(tester, api: api);
    await tester.longPress(find.text('苹果'));
    await tester.pumpAndSettle();
    expect(find.text('删除自选'), findsOneWidget);
    await tester.tap(find.widgetWithText(FilledButton, '删除'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));
    expect(api.deleted, [
      [1],
    ]);
  });
}
