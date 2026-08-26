import 'package:flutter_test/flutter_test.dart';

import 'package:flutter_client/features/trade/data/trade_models.dart';

void main() {
  group('AccountInfo / PositionItem', () {
    test('账户平铺键解析', () {
      final a = AccountInfo.fromJson(const {
        'configured': true,
        'currency': 'USD',
        'totalCash': 50000.5,
        'availableCash': 30000.25,
        'netAssets': 82000.75,
      });
      expect(a.configured, isTrue);
      expect(a.netAssets, 82000.75);
      expect(a.currency, 'USD');
    });

    test('多币种余额优先取 USD', () {
      final a = AccountInfo.fromJson(const {
        'configured': true,
        'balances': [
          {'currency': 'HKD', 'availableCash': 10, 'totalCash': 10, 'netAssets': 10},
          {'currency': 'USD', 'availableCash': 25000.5, 'totalCash': 26000, 'netAssets': 40000},
        ],
      });
      expect(a.currency, 'USD');
      expect(a.availableCash, 25000.5);
      expect(a.netAssets, 40000);
    });

    test('持仓行成本口径字段', () {
      final p = PositionItem.fromJson(const {
        'symbol': 'AAPL',
        'symbolName': '苹果',
        'quantity': 100,
        'availableQuantity': 60,
        'costPrice': 182.5,
        'currency': 'USD',
      });
      expect(p.quantity, 100.0);
      expect(p.availableQuantity, 60.0);
      expect(p.costPrice, 182.5);
    });
  });

  group('OrderItem', () {
    test('_map_order 键解析与在途判定', () {
      final open = OrderItem.fromJson(const {
        'orderId': 'o-1',
        'symbol': 'NVDA',
        'stockName': '英伟达',
        'side': 'buy',
        'status': 'partial_filled',
        'statusLabel': '部分成交',
        'quantity': 100,
        'price': 180.0,
        'executedQuantity': 40,
        'executedPrice': 179.8,
        'open': true,
      });
      expect(open.open, isTrue);
      expect(open.isBuy, isTrue);
      expect(open.executedQuantity, 40.0);

      final done = OrderItem.fromJson(const {
        'orderId': 'o-2',
        'side': 'SELL',
        'status': 'cancelled',
        'open': false,
      });
      expect(done.open, isFalse);
      expect(done.isBuy, isFalse);
    });

    test('orderId 数字型转字符串容错', () {
      final o = OrderItem.fromJson(const {'orderId': 12345});
      expect(o.orderId, '12345');
    });
  });

  group('DepthData / TradeTick', () {
    test('十档载荷与不可用原因透传', () {
      final d = DepthData.fromJson(const {
        'configured': true,
        'available': true,
        'asks': [
          {'position': 1, 'price': 182.6, 'volume': 300},
          {'position': 2, 'price': 182.7, 'volume': 500},
        ],
        'bids': [
          {'position': 1, 'price': 182.5, 'volume': 200},
        ],
      });
      expect(d.available, isTrue);
      expect(d.asks, hasLength(2));
      expect(d.bids.single.price, 182.5);

      final cn = DepthData.fromJson(
          const {'configured': true, 'available': false, 'reason': 'cn_no_depth'});
      expect(cn.reason, 'cn_no_depth');
    });

    test('逐笔方向字段解析', () {
      final t = TradeTick.fromJson(const {
        'time': '2026-08-24 10:00:00',
        'price': 182.55,
        'volume': 100,
        'side': 'buy',
      });
      expect(t.side, 'buy');
      expect(t.volume, 100);
    });
  });

  group('AutoTradeStatus', () {
    test('config snake_case 与 guardrails camelCase 混合键解析', () {
      final s = AutoTradeStatus.fromJson(const {
        'configured': true,
        'tradingEnabled': false,
        'submitAllowed': false,
        'submitBlockReason': '实盘交易未启用',
        'config': {
          'enabled': true,
          'auto_execute': false,
          'strategy_profile': 'balanced',
          'max_symbols': 3,
          'max_daily_orders': 10,
          'min_confidence': 65,
          'require_paper': true,
        },
        'guardrails': {
          'todayOrdersCount': 2,
          'maxDailyOrders': 10,
          'todayNotionalAmount': 1200.5,
          'maxDailyNotionalAmount': 6000.0,
          'requirePaper': true,
          'tradingEnabled': false,
        },
        'recentRuns': [
          {
            'runId': 1,
            'cycleId': 100,
            'source': 'scheduler',
            'strategyProfile': 'balanced',
            'targetCount': 20,
            'opportunityCount': 3,
            'submittedOrdersCount': 0,
            'status': 'completed',
            'startedAt': '2026-08-24 09:00:00',
          },
        ],
        'recentDecisions': [
          {
            'decisionId': 9,
            'symbol': 'AAPL',
            'market': 'US',
            'side': 'BUY',
            'quantity': 10,
            'confidence': 88,
            'status': 'skipped',
          },
        ],
      });
      expect(s.tradingEnabled, isFalse);
      expect(s.requirePaper, isTrue);
      expect(s.submitAllowed, isFalse);
      expect(s.strategyProfile, 'balanced');
      expect(s.todayOrdersCount, 2);
      expect(s.recentRuns.single.cycleId, 100);
      expect(s.recentDecisions.single.confidence, 88.0);
    });

    test('require_paper 缺省为关闭', () {
      final s = AutoTradeStatus.fromJson(const {'config': {}});
      expect(s.requirePaper, isFalse);
    });

    test('autoTradeEnabled 与 tradingEnabled 互通', () {
      final a = AutoTradeStatus.fromJson(const {
        'configured': true,
        'autoTradeEnabled': true,
      });
      expect(a.autoTradeEnabled, isTrue);
      expect(a.tradingEnabled, isTrue);
      final b = AutoTradeStatus.fromJson(const {'tradingEnabled': true});
      expect(b.autoTradeEnabled, isTrue);
    });
  });

  group('RiskRule / RiskEvent', () {
    test('enabled 兼容字符串与布尔', () {
      expect(RiskRule.fromJson(const {'enabled': '1'}).enabled, isTrue);
      expect(RiskRule.fromJson(const {'enabled': '0'}).enabled, isFalse);
      expect(RiskRule.fromJson(const {'enabled': true}).enabled, isTrue);
    });

    test('事件处理状态解析', () {
      final e = RiskEvent.fromJson(const {
        'eventId': 4,
        'eventLevel': 'warn',
        'title': '单票仓位超限',
        'handled': false,
      });
      expect(e.handled, isFalse);
      expect(e.eventLevel, 'warn');
    });
  });
}
