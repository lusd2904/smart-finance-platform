import 'package:flutter_test/flutter_test.dart';

import 'package:flutter_client/features/market/data/market_models.dart';
import 'package:flutter_client/features/market/presentation/market_tab.dart';

void main() {
  TopPickRow row({
    required int rankNo,
    required String symbol,
    double? changePct,
    double? turnover,
  }) {
    return TopPickRow(
      rankNo: rankNo,
      symbol: symbol,
      name: symbol,
      changePct: changePct,
      turnover: turnover,
    );
  }

  final rows = [
    row(rankNo: 1, symbol: 'AAA', changePct: 1.2, turnover: 10),
    row(rankNo: 2, symbol: 'BBB', changePct: 5.0, turnover: 3),
    row(rankNo: 3, symbol: 'CCC', changePct: -2.5, turnover: 30),
    row(rankNo: 4, symbol: 'DDD', changePct: null, turnover: null),
  ];

  test('heat keeps rank order', () {
    expect(
      sortHeatBoard(rows, 'heat').map((e) => e.symbol).toList(),
      ['AAA', 'BBB', 'CCC', 'DDD'],
    );
  });

  test('up sorts higher changePct first', () {
    expect(
      sortHeatBoard(rows, 'up').map((e) => e.symbol).toList(),
      ['BBB', 'AAA', 'CCC', 'DDD'],
    );
  });

  test('down sorts lower first', () {
    expect(
      sortHeatBoard(rows, 'down').map((e) => e.symbol).toList(),
      ['CCC', 'AAA', 'BBB', 'DDD'],
    );
  });
}
