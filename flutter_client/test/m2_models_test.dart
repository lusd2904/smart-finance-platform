import 'package:flutter_test/flutter_test.dart';

import 'package:flutter_client/features/ai/data/ai_models.dart';
import 'package:flutter_client/features/news/data/briefing_models.dart';
import 'package:flutter_client/features/notice/data/notice_api.dart';
import 'package:flutter_client/features/notice/data/notice_models.dart';
import 'package:flutter_client/core/api/api_result.dart';
import 'package:flutter_client/features/market/data/market_models.dart';
import 'package:flutter_client/features/sentiment/data/sentiment_models.dart';
import 'package:flutter_client/features/trade/data/trade_models.dart';
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
      expect(
        SentimentDirection.fromRaw(a.hkDirection),
        SentimentDirection.down,
      );
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

    test('[-10,10] 舆情指数映射到 0–100 仪表盘', () {
      expect(sentimentIndexTo100(-10), 0);
      expect(sentimentIndexTo100(0), 50);
      expect(sentimentIndexTo100(10), 100);
      expect(sentimentIndexTo100(4), 70);
      expect(sentimentIndexTo100(-2), 40);
      expect(sentimentIndexTo100(72.5), 72.5);
      final a = SentimentAnalysis.fromJson(const {
        'usScore': 4,
        'hkScore': -2,
        'aScore': 0,
      });
      expect(a.usScore, 70);
      expect(a.hkScore, 40);
      expect(a.aScore, 50);
      expect(a.overallScore, closeTo(53.33, 0.01));
    });

    test('缺字段容错：null 分值不参与综合分', () {
      final a = SentimentAnalysis.fromJson(const {'usScore': 60});
      expect(a.overallScore, 60);
      expect(a.aReason, isEmpty);
      expect(a.riskEvents, isEmpty);
    });

    test('ApiResult 兼容 Cloudflare 纯文本 502 与业务 401', () {
      final plain = ApiException;
      expect(
        isBusinessUnauthorized({
          'code': 401,
          'data': '',
          'msg': '用户未登录，请先完成登录',
        }),
        isTrue,
      );
      expect(isBusinessUnauthorized({'code': 200}), isFalse);
      expect(asJsonList(''), isEmpty);
      expect(asJsonList('["a"]'), ['a']);
      expect(asJsonMap('{"a":1}')?['a'], 1);
      expect(describeHttpFailure(502, 'error code: 502'), contains('502'));
      expect(plain, isNotNull);
    });

    test('riskEvents 兼容 JSON 字符串', () {
      final a = SentimentAnalysis.fromJson(const {
        'riskEvents': '["美联储讲话", "地缘冲突"]',
      });
      expect(a.riskEvents, ['美联储讲话', '地缘冲突']);
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

    test('AiBatch 兼容 cycleId 为字符串、status 为数字', () {
      final a = AiBatch.fromJson(const {
        'batchId': '12',
        'cycleId': '20260826-scan',
        'symbolsCount': '3',
        'status': 1,
      });
      expect(a.batchId, 12);
      expect(a.cycleId, isNull);
      expect(a.symbolsCount, 3);
      expect(a.finished, isTrue);
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

  group('pickNoticeDelay', () {
    test('未读 5s，全已读/空 30s', () {
      expect(pickNoticeDelay(true), const Duration(seconds: 5));
      expect(pickNoticeDelay(false), const Duration(seconds: 30));
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

  group('formatSigned', () {
    test('正数带加号，负数带减号，null 为占位', () {
      expect(formatSigned(1.2), '+1.20');
      expect(formatSigned(-1), '-1.00');
      expect(formatSigned(null), '--');
    });
  });

  group('TopPickRow', () {
    test('last 兼容 last / price / close', () {
      expect(TopPickRow.fromJson(const {'last': 190.5}).last, 190.5);
      expect(TopPickRow.fromJson(const {'price': 12.3}).last, 12.3);
      expect(TopPickRow.fromJson(const {'close': 8}).last, 8);
      expect(
        TopPickRow.fromJson(const {'last': 1, 'price': 2, 'close': 3}).last,
        1,
      );
      expect(TopPickRow.fromJson(const {}).last, isNull);
    });
  });

  group('PositionQuote / UsdHkdFx', () {
    test('涨跌幅用 last 与 prevClose 自算，盈亏按数量', () {
      const q = PositionQuote(last: 110, prevClose: 100);
      expect(q.changePct, closeTo(10, 0.0001));
      expect(q.dayAmount(2), closeTo(20, 0.0001));
      expect(q.pnl(2, 80), closeTo(60, 0.0001));
    });

    test('港元美元切换时涨跌金额按汇率换算', () {
      const hkd = UsdHkdFx(usdHkd: 8, display: 'HKD');
      const usd = UsdHkdFx(usdHkd: 8, display: 'USD');
      expect(hkd.convert(10, 'USD'), 80);
      expect(usd.convert(80, 'HKD'), 10);
      expect(hkd.convert(100, 'HKD'), 100);
    });

    test('持仓行解析长桥叠加的 last/prevClose', () {
      final p = PositionItem.fromJson(const {
        'symbol': 'AAPL.US',
        'quantity': 10,
        'costPrice': 100,
        'currency': 'USD',
        'last': 110,
        'prevClose': 100,
      });
      expect(p.asQuote?.changePct, closeTo(10, 0.0001));
      expect(p.asQuote?.pnl(p.quantity, p.costPrice), closeTo(100, 0.0001));
    });
  });

  group('热度指数按市场筛选', () {
    const all = [
      IndexQuote(symbol: 'usINX', name: '标普500', market: 'US', changePct: 1),
      IndexQuote(symbol: 'usIXIC', name: '纳斯达克', market: 'US', changePct: 2),
      IndexQuote(symbol: 'usDJI', name: '道琼斯', market: 'US', changePct: 0.5),
      IndexQuote(symbol: 'r_hkHSI', name: '恒生指数', market: 'HK', changePct: -1),
      IndexQuote(
        symbol: 'r_hkHSTECH',
        name: '恒生科技',
        market: 'HK',
        changePct: -2,
      ),
      IndexQuote(
        symbol: 'r_hkHSCEI',
        name: '恒生国企',
        market: 'HK',
        changePct: -0.3,
      ),
      IndexQuote(
        symbol: 'sh000001',
        name: '上证指数',
        market: 'CN',
        changePct: 0.1,
      ),
      IndexQuote(
        symbol: 'sz399006',
        name: '创业板指数',
        market: 'CN',
        changePct: 0.2,
      ),
      IndexQuote(
        symbol: 'sh000688',
        name: '科创板指数',
        market: 'CN',
        changePct: 0.3,
      ),
    ];

    test('三个市场互不串指数，美股统计卡用道琼斯', () {
      expect(heatStripQuotes(all, 'US').map((q) => q.symbol), [
        'usINX',
        'usIXIC',
      ]);
      expect(heatStripQuotes(all, 'HK').map((q) => q.symbol), [
        'r_hkHSI',
        'r_hkHSTECH',
        'r_hkHSCEI',
      ]);
      expect(heatStripQuotes(all, 'CN').map((q) => q.symbol), [
        'sh000001',
        'sz399006',
        'sh000688',
      ]);
      expect(heatStatQuote(all, 'US')?.symbol, 'usDJI');
      expect(indexDisplayName(heatStatQuote(all, 'US')!), '道琼斯');
    });

    test('筛选规则随市场变化', () {
      expect(const HeatDailyData().filterRuleFor('US'), contains('美元'));
      expect(const HeatDailyData().filterRuleFor('HK'), contains('港币'));
      expect(const HeatDailyData().filterRuleFor('CN'), contains('人民币'));
      expect(
        const HeatDailyData(heat: HeatSummary(filterRule: '50亿-500亿港币'))
            .filterRuleFor('HK'),
        '50亿-500亿港币',
      );
    });
  });
}
