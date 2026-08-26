import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:flutter_client/shared/widgets/ruoyi_ui.dart';

void main() {
  testWidgets('QueryBar 输入不因重建丢失', (tester) async {
    var keyword = '';
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: StatefulBuilder(
            builder: (context, setState) {
              return QueryBar(
                fields: const [QueryField('kw', '代码')],
                values: {'kw': keyword},
                onChanged: (k, v) => setState(() => keyword = v),
                onSearch: () {},
              );
            },
          ),
        ),
      ),
    );
    await tester.enterText(find.byType(TextField), 'AAPL');
    await tester.pump();
    expect(find.widgetWithText(TextField, 'AAPL'), findsOneWidget);
    expect(keyword, 'AAPL');
  });
}
