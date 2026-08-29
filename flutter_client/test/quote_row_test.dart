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
}
