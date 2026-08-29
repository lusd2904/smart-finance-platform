import 'package:flutter_test/flutter_test.dart';

import 'package:flutter_client/features/quant/data/quant_models.dart';

void main() {
  group('FactorQcReport / FactorQcItem', () {
    test('完整载荷解析：IC/IR 汇总 + 五分位收益', () {
      final r = FactorQcReport.fromJson(const {
        'ok': true,
        'market': 'US',
        'asOf': '2026-08-21',
        'symbolCount': 120,
        'message': '',
        'items': [
          {
            'factorKey': 'mom_20',
            'factorLabel': '动量20日',
            'family': 'momentum',
            'horizon': 5,
            'icMean': 0.042,
            'icStd': 0.15,
            'ir': 0.28,
            'icPositiveRatio': 0.61,
            'sampleDates': 250,
            'quantiles': {
              'q1': -1.2,
              'q2': 0.3,
              'q3': 0.5,
              'q4': 0.9,
              'q5': 2.1,
            },
            'spread': 3.3,
            'ok': true,
          },
        ],
      });
      expect(r.ok, isTrue);
      expect(r.items, hasLength(1));
      final item = r.items.first;
      expect(item.ir, 0.28);
      expect(item.quantiles['q5'], 2.1);
      expect(item.spread, 3.3);
      expect(item.sampleDates, 250);
    });

    test('缺字段容错：quantiles 缺失为空表、ok 缺省 false', () {
      final item = FactorQcItem.fromJson(const {'factorKey': 'x'});
      expect(item.quantiles, isEmpty);
      expect(item.ok, isFalse);
    });
  });

  group('DailyListPayload / SignalItem', () {
    test('list 为 null 时保留 message（服务端无清单场景）', () {
      final p = DailyListPayload.fromJson(const {
        'list': null,
        'message': '尚未生成',
      });
      expect(p.list, isNull);
      expect(p.message, '尚未生成');
    });

    test('信号条目方向判定与数值解析', () {
      final p = DailyListPayload.fromJson(const {
        'list': {
          'listId': 7,
          'scanDate': '2026-08-24',
          'tradeDate': '2026-08-25',
          'profile': 'balanced',
          'status': 'listed',
          'itemCount': 1,
          'items': [
            {
              'itemId': 1,
              'symbol': 'NVDA',
              'market': 'US',
              'name': '英伟达',
              'signal': 'BUY',
              'score': 86.5,
              'confidence': 88,
              'reason': '动量与舆情共振',
              'status': 'listed',
            },
          ],
        },
      });
      final item = p.list!.items.single;
      expect(item.isBuy, isTrue);
      expect(item.isSell, isFalse);
      expect(item.confidence, 88.0);
      expect(item.name, '英伟达');
    });
  });

  group('StrategyProfile', () {
    test('config 嵌套权重解析与雷达值按最大权重归一', () {
      final p = StrategyProfile.fromJson(const {
        'profileCode': 'balanced',
        'profileName': '均衡',
        'config': {
          'buyThreshold': 75,
          'sellThreshold': 30,
          'weights': {
            'trend': 1.5,
            'momentum': 1.2,
            'breakout': 1.0,
            'volumeFlow': 0.8,
            'reversion': 0.6,
            'volatility': 0.4,
            'liquidity': 0.3,
            'priceAction': 1.0,
          },
        },
        'updateTime': '2026-08-24 10:00:00',
        'active': true,
        'accountOwned': true,
      });
      expect(p.weights, hasLength(8));
      expect(p.active, isTrue);
      expect(p.accountOwned, isTrue);
      expect(p.buyThreshold, 75);
      final values = p.radarValues;
      expect(values.length, 8);
      expect(values.reduce((a, b) => a > b ? a : b), 1.0); // 最大权重 → 1
      expect(p.radarAxes.first, '趋势'); // 键序保持，trend 映射中文
    });

    test('空权重不产生除零', () {
      final p = StrategyProfile.fromJson(const {
        'config': {'weights': {}},
      });
      expect(p.radarValues.every((v) => v == 0.0), isTrue);
    });
  });

  group('ScanRun', () {
    test('台账行计数字段解析', () {
      final r = ScanRun.fromJson(const {
        'runId': 3,
        'cycleId': 300,
        'status': 'completed',
        'strategyProfile': 'aggressive',
        'targetCount': 50,
        'opportunityCount': 6,
        'signalCount': 4,
        'submittedCount': 2,
        'startedAt': '2026-08-24 09:00:00',
      });
      expect(r.status, 'completed');
      expect(r.opportunityCount, 6);
      expect(r.cycleId, 300);
    });
  });
}
