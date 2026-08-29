import 'package:flutter_test/flutter_test.dart';

import 'package:flutter_client/features/trade/logic/ticket_qty.dart';

void main() {
  test('CN buy 100% rounds down to board lot', () {
    expect(
      ticketQtyForPercent(
        percent: 100,
        side: 'buy',
        market: 'CN',
        price: 10,
        cash: 10000,
      ),
      1000,
    );
  });

  test('CN buy 25% rounds down to 100-share lot', () {
    // 10000/10 = 1000 股，25% = 250 → 200。
    expect(
      ticketQtyForPercent(
        percent: 25,
        side: 'buy',
        market: 'CN',
        price: 10,
        cash: 10000,
      ),
      200,
    );
  });

  test('US buy 25% uses 1-share lot', () {
    // 10000/190 ≈ 52 股，25% = 13。
    expect(
      ticketQtyForPercent(
        percent: 25,
        side: 'buy',
        market: 'US',
        price: 190,
        cash: 10000,
      ),
      13,
    );
  });

  test('sell 50% US', () {
    expect(
      ticketQtyForPercent(
        percent: 50,
        side: 'sell',
        market: 'US',
        sellable: 300,
      ),
      150,
    );
  });

  test('sell CN 50% rounds down to lot', () {
    expect(
      ticketQtyForPercent(
        percent: 50,
        side: 'sell',
        market: 'CN',
        sellable: 250,
      ),
      100,
    );
  });

  test('missing price or cash yields 0', () {
    expect(
      ticketQtyForPercent(
        percent: 100,
        side: 'buy',
        market: 'US',
        price: null,
        cash: 10000,
      ),
      0,
    );
    expect(
      ticketQtyForPercent(
        percent: 100,
        side: 'buy',
        market: 'US',
        price: 10,
        cash: 0,
      ),
      0,
    );
  });

  test('lotSize and cash currency', () {
    expect(lotSizeForMarket('CN'), 100);
    expect(lotSizeForMarket('US'), 1);
    expect(cashCurrencyForMarket('HK'), 'HKD');
  });
}
