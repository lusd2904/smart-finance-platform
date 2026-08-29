import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:flutter_client/features/kline/logic/kline_painter.dart';
import 'package:flutter_client/features/market/data/market_models.dart';

List<KlineBar> _bars({int n = 40, bool timed = false}) {
  return [
    for (var i = 0; i < n; i++)
      KlineBar(
        date: timed
            ? '2026-08-29 ${9 + i ~/ 60}:${(i % 60).toString().padLeft(2, '0')}:00'
            : '2026-08-${(i % 27 + 1).toString().padLeft(2, '0')}',
        open: 10 + i * 0.01,
        high: 10.2 + i * 0.01,
        low: 9.8 + i * 0.01,
        close: 10.1 + i * 0.01,
        volume: 1000 + i * 10,
      ),
  ];
}

Future<void> _pump(
  WidgetTester tester, {
  required List<KlineBar> bars,
  bool area = false,
}) async {
  await tester.pumpWidget(
    MaterialApp(
      home: Scaffold(
        body: SizedBox(
          width: 400,
          height: 300,
          child: InteractiveKlineChart(
            bars: bars,
            area: area,
            initialVisible: bars.length,
          ),
        ),
      ),
    ),
  );
  await tester.pump();
}

void main() {
  testWidgets('candle chart long-press shows OHLC hud', (tester) async {
    await _pump(tester, bars: _bars());
    expect(find.byType(InteractiveKlineChart), findsOneWidget);
    await tester.longPress(find.byType(InteractiveKlineChart));
    await tester.pump();
    expect(find.textContaining('收'), findsOneWidget);
    expect(find.textContaining('量'), findsOneWidget);
  });

  testWidgets('intraday area long-press shows time hud', (tester) async {
    await _pump(tester, bars: _bars(timed: true), area: true);
    await tester.longPress(find.byType(InteractiveKlineChart));
    await tester.pump();
    expect(find.textContaining('收'), findsNothing);
    expect(find.textContaining('量'), findsOneWidget);
  });

  testWidgets('tap dismisses crosshair hud', (tester) async {
    await _pump(tester, bars: _bars());
    await tester.longPress(find.byType(InteractiveKlineChart));
    await tester.pump();
    expect(find.textContaining('收'), findsOneWidget);
    await tester.tap(find.byType(InteractiveKlineChart));
    await tester.pump();
    expect(find.textContaining('收'), findsNothing);
  });
}
