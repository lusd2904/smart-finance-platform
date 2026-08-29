import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:flutter_client/shared/utils/format.dart';
import 'package:flutter_client/shared/widgets/quote_row.dart';

void main() {
  testWidgets('ChgPill shows signed percent', (tester) async {
    await tester.pumpWidget(
      const MaterialApp(home: Scaffold(body: ChgPill(1.23))),
    );
    expect(find.text('+1.23%'), findsOneWidget);
  });

  testWidgets('QuoteListRow shows name, symbol and ChgPill', (tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: QuoteListRow(
            name: '苹果',
            symbol: 'AAPL',
            last: 190,
            changePct: 1.5,
          ),
        ),
      ),
    );
    expect(find.text('苹果'), findsOneWidget);
    expect(find.text('AAPL'), findsOneWidget);
    expect(find.text('+1.50%'), findsOneWidget);
  });

  test('formatSigned', () {
    expect(formatSigned(1.2), '+1.20');
    expect(formatSigned(-1), '-1.00');
    expect(formatSigned(null), '--');
  });

  test('compareQuotes nulls last and desc by default', () {
    expect(
      compareQuotes(
        field: QuoteSort.changePct,
        ascending: false,
        nameA: 'A',
        nameB: 'B',
        changePctA: 1.2,
        changePctB: 5.0,
      ),
      greaterThan(0),
    );
    expect(
      compareQuotes(
        field: QuoteSort.changePct,
        ascending: false,
        nameA: 'A',
        nameB: 'B',
        changePctA: null,
        changePctB: 1,
      ),
      greaterThan(0),
    );
    expect(
      compareQuotes(
        field: QuoteSort.name,
        ascending: true,
        nameA: 'apple',
        nameB: 'Tesla',
      ),
      lessThan(0),
    );
  });

  testWidgets('QuoteListRow shows subtitle', (tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: QuoteListRow(
            name: '苹果',
            symbol: 'AAPL',
            last: 190,
            changePct: 1.5,
            subtitle: '82 · 偏多 · 突破均线',
          ),
        ),
      ),
    );
    expect(find.text('82 · 偏多 · 突破均线'), findsOneWidget);
  });

  testWidgets('QuoteListHeader onSort fires', (tester) async {
    QuoteSort? got;
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: QuoteListHeader(
            sort: QuoteSort.changePct,
            onSort: (s) => got = s,
          ),
        ),
      ),
    );
    await tester.tap(find.text('最新'));
    expect(got, QuoteSort.last);
  });
}
