import 'package:flutter_test/flutter_test.dart';

import 'package:flutter_client/features/ai/data/ai_models.dart';
import 'package:flutter_client/features/news/data/briefing_models.dart';
import 'package:flutter_client/features/notice/data/notice_models.dart';
import 'package:flutter_client/features/sentiment/data/sentiment_models.dart';
import 'package:flutter_client/shared/utils/format.dart';

void main() {
  group('SentimentAnalysis', () {
    test('完整载荷解析（camelCase 字段照抄后端 VO）', () {
      final a = SentimentAnalysis.fromJson(const {
        'analysisId': 7,
        'newsCount': 32,
        'summary': '美股偏多，A股震荡',
        'usDirection': '利多',
        'usScore': 72.5,
        'usReason': '科技股财报超预期',
        'hkDirection': '看空',
        'hkScore': 38.0,
        'aDirection': '中性',
        'aScore': 50.5,
        'riskEvents': ['美联储议息', '地缘冲突'],
        'modelName': 'Grok 4.6',
        'createTime': '2026-08-24 10:00:00',
      });
      expect(a.analysisId, 7);
      expect(a.newsCount, 32);
      expect(SentimentDirection.fromRaw(a.usDirection), SentimentDirection.up);
      expect(SentimentDirection.fromRaw(a.hkDirection), SentimentDirection.down);
      expect(SentimentDirection.fromRaw(a.aDirection), SentimentDirection.flat);
      expect(a.overallScore, closeTo(53.67, 0.01));
      expect(a.overallDirection, SentimentDirection.flat); // 1:1:1 平票 → 中性
      expect(a.riskEvents, hasLength(2));
    });

    test('方向归一镜像后端 _normalize_direction', () {
      expect(SentimentDirection.fromRaw('bullish'), SentimentDirection.up);
      expect(SentimentDirection.fromRaw('UP'), SentimentDirection.up);
      expect(SentimentDirection.fromRaw('positive'), SentimentDirection.up);
      expect(SentimentDirection.fromRaw('bearish'), SentimentDirection.down);
      expect(SentimentDirection.fromRaw('下跌'), SentimentDirection.down);
      expect(SentimentDirection.fromRaw('negative'), SentimentDirection.down);
      expect(SentimentDirection.fromRaw('sideways'), SentimentDirection.flat);
      expect(SentimentDirection.fromRaw(''), SentimentDirection.unknown);
      expect(SentimentDirection.fromRaw(null), SentimentDirection.unknown);
    });

    test('缺字段容错：null 分值不参与综合分', () {
      final a = SentimentAnalysis.fromJson(const {'usScore': 60});
      expect(a.overallScore, 60);
      expect(a.aReason, isEmpty);
      expect(a.riskEvents, isEmpty);
    });

    test('多数票决定综合方向（2 票起）', () {
      final a = SentimentAnalysis.fromJson(const {
        'usDirection': '涨',
        'hkDirection': 'up',
        'aDirection': '跌',
      });
      expect(a.overallDirection, SentimentDirection.up);
    });
  });

  group('AiLatestAnalysis', () {
    test('summary 兼容 summaryText 回退与 advice 别名', () {
      final a = AiLatestAnalysis.fromJson(const {
        'symbol': 'AAPL',
        'market': 'US',
        'price': 182.5,
        'recommendation': '买入',
        'confidence': 88.0,
        'advice': '分批建仓',
      });
      expect(a.summaryText, isEmpty);
      expect(a.operationAdvice, '分批建仓');
      expect(a.isBullish, isTrue);
      expect(a.isBearish, isFalse);

      final b = AiLatestAnalysis.fromJson(const {
        'summaryText': '综合评分良好',
        'recommendation': '减持',
      });
      expect(b.summaryText, '综合评分良好');
      expect(b.isBearish, isTrue);
    });
  });

  group('批量扫描模型', () {
    test('AiBatch 状态语义：1 完成 / 0 执行中', () {
      final done = AiBatch.fromJson(const {'batchId': 3, 'status': '1'});
      final running = AiBatch.fromJson(const {'batchId': 4, 'status': '0'});
      expect(done.finished, isTrue);
      expect(running.finished, isFalse);
    });

    test('AiBatchItem 成功状态与决策解析', () {
      final item = AiBatchItem.fromJson(const {
        'itemId': 11,
        'symbol': 'NVDA',
        'market': 'US',
        'decision': '买入',
        'confidence': 91,
        'status': '1',
      });
      expect(item.succeeded, isTrue);
      expect(item.confidence, 91.0);
    });
  });

  group('BriefingFeed', () {
    test('非标准包结构 {success,data:[...],meta} 解析', () {
      final feed = BriefingFeed.fromJson(const {
        'success': true,
        'data': [
          {
            'id': 'abc',
            'market': 'US',
            'headline': '美联储释放降息信号',
            'summary': '市场预期 9 月降息概率上升',
            'sourceName': '华尔街见闻',
            'generatedAt': '2026-08-24 09:30:00',
          },
        ],
        'message': '',
        'meta': {'snapshotAt': '2026-08-24 09:31:00'},
      });
      expect(feed.items, hasLength(1));
      expect(feed.items.first.headline, '美联储释放降息信号');
      expect(feed.items.first.sourceName, '华尔街见闻');
      expect(feed.snapshotAt, '2026-08-24 09:31:00');
    });

    test('服务端异常降级：data 缺失时为空列表不抛', () {
      final feed = BriefingFeed.fromJson(const {});
      expect(feed.items, isEmpty);
    });
  });

  group('NoticeItem', () {
    test('read 字段布尔解析与级别透传', () {
      final n = NoticeItem.fromJson(const {
        'id': 5,
        'title': '风控提醒',
        'level': 'warn',
        'category': 'risk',
        'read': false,
        'createTime': '2026-08-24 08:00:00',
      });
      expect(n.read, isFalse);
      expect(n.level, 'warn');
      expect(n.category, 'risk');
    });
  });

  group('formatRelativeTime', () {
    final now = DateTime(2026, 8, 24, 12, 0, 0);

    test('分钟/小时/天级文案', () {
      expect(formatRelativeTime('2026-08-24 11:59:30', now: now), '刚刚');
      expect(formatRelativeTime('2026-08-24 11:30:00', now: now), '30分钟前');
      expect(formatRelativeTime('2026-08-24 09:00:00', now: now), '3小时前');
      expect(formatRelativeTime('2026-08-20 12:00:00', now: now), '4天前');
    });

    test('趋势点短格式 MM-dd HH:mm 补当前年', () {
      final t = formatRelativeTime('08-24 11:00', now: now);
      expect(t, anyOf('刚刚', '60分钟前', '1小时前'));
    });

    test('非法输入原样返回', () {
      expect(formatRelativeTime('', now: now), '');
      expect(formatRelativeTime('not-a-time', now: now), 'not-a-time');
    });
  });
}
