import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:flutter_client/features/ai/data/ai_api.dart';
import 'package:flutter_client/features/ai/data/ai_models.dart';
import 'package:flutter_client/features/ai/presentation/ai_page.dart';
import 'package:flutter_client/features/news/data/briefing_models.dart';
import 'package:flutter_client/features/news/presentation/news_page.dart';
import 'package:flutter_client/features/notice/data/notice_models.dart';
import 'package:flutter_client/features/notice/presentation/notice_page.dart';
import 'package:flutter_client/features/sentiment/data/sentiment_models.dart';
import 'package:flutter_client/features/sentiment/presentation/sentiment_page.dart';
import 'package:flutter_client/features/news/data/briefing_api.dart';
import 'package:flutter_client/features/notice/data/notice_api.dart';
import 'package:flutter_client/features/sentiment/data/sentiment_api.dart';

/// M2 四页行为测试：假 API 注入，验证页面在数据到达后的真实渲染。
/// （本地无可用登录凭据，网络层契约由 m2_models_test + 后端测试保障。）

class _FakeBriefingApi extends BriefingApi {
 _FakeBriefingApi() : super(Dio());

 @override
 Future<List<BriefingItem>> briefings({
   required String market,
   int limit = 20,
   bool refresh = false,
 }) async {
   return const [
     BriefingItem(
       id: 'a1',
       market: 'US',
       headline: '美联储释放降息信号',
       summary: '市场预期 9 月降息概率上升',
       sourceName: '华尔街见闻',
       generatedAt: '2026-08-24 09:30:00',
     ),
   ];
 }
}

class _FakeSentimentApi extends SentimentApi {
 _FakeSentimentApi() : super(Dio());

 @override
 Future<SentimentAnalysis?> latestAnalysis() async => SentimentAnalysis.fromJson(const {
       'summary': '美股偏多',
       'usDirection': '利多',
       'usScore': 78,
       'hkDirection': '看空',
       'hkScore': 35,
       'aDirection': '中性',
       'aScore': 52,
       'riskEvents': ['美联储议息'],
       'modelName': 'Grok 4.6',
       'createTime': '2026-08-24 10:00:00',
     });

 @override
 Future<List<SentimentTrendPoint>> trend({int limit = 24}) async => const [
      SentimentTrendPoint(createTime: '08-23 10:00', usScore: 60, hkScore: 40, aScore: 50),
      SentimentTrendPoint(createTime: '08-24 10:00', usScore: 78, hkScore: 35, aScore: 52),
      ];
}

class _FakeAiApi extends AiApi {
 _FakeAiApi() : super(Dio());

 @override
 Future<List<AiBatch>> batches() async => const [
       AiBatch(
         batchId: 9,
         symbolsCount: 8,
         successCount: 8,
         status: '1',
         createTime: '2026-08-24 09:00:00',
       ),
     ];

 @override
 Future<List<AiBatchItem>> batchItems({required int batchId}) async => const [
       AiBatchItem(
         itemId: 1,
         symbol: 'NVDA',
         market: 'US',
         decision: '买入',
         confidence: 91,
         status: '1',
       ),
     ];
}

class _FakeNoticeApi extends NoticeApi {
 _FakeNoticeApi() : super(Dio());

 @override
 Future<List<NoticeItem>> list({int limit = 50}) async => const [
       NoticeItem(
         id: 5,
         title: '风控提醒：单标的持仓超限',
         content: 'AAPL 持仓比例 32% 超过阈值 30%',
         level: 'warn',
         category: 'risk',
         createTime: '2026-08-24 08:00:00',
       ),
     ];
}

Future<void> _pump(WidgetTester tester, Widget child, List<Override> overrides) async {
 tester.view.devicePixelRatio = 1.0;
 tester.view.physicalSize = const Size(1200, 800);
 addTearDown(tester.view.reset);
 await tester.pumpWidget(
   ProviderScope(overrides: overrides, child: MaterialApp(home: child)),
 );
}

void main() {
 testWidgets('资讯页渲染简报卡片', (tester) async {
   await _pump(tester, const NewsPage(), [
     briefingApiProvider.overrideWith((ref) => _FakeBriefingApi()),
   ]);
   await tester.pumpAndSettle();
   expect(find.text('美联储释放降息信号'), findsOneWidget);
   expect(find.text('华尔街见闻'), findsOneWidget);
   expect(find.text('美股'), findsOneWidget); // 市场切换段
 });

 testWidgets('舆情页渲染仪表盘与三市场研判卡', (tester) async {
   await _pump(tester, const SentimentPage(), [
     sentimentApiProvider.overrideWith((ref) => _FakeSentimentApi()),
   ]);
   await tester.pumpAndSettle();
   expect(find.text('舆情大盘'), findsOneWidget);
   // 综合分 (78+35+52)/3 ≈ 55；美股研判分 78 与利多徽章同时可见。
   expect(find.text('55'), findsOneWidget);
   expect(find.text('78'), findsOneWidget);
   expect(find.text('利多'), findsOneWidget);
   expect(find.text('风险事件'), findsOneWidget);
 });

 testWidgets('AI 页渲染批量扫描批次并可展开明细', (tester) async {
   await _pump(tester, const AiPage(), [
     aiApiProvider.overrideWith((ref) => _FakeAiApi()),
   ]);
   await tester.pumpAndSettle();
   expect(find.text('AI 研判'), findsOneWidget);
   expect(find.text('批次 #9'), findsOneWidget);

   await tester.tap(find.text('批次 #9'));
   await tester.pumpAndSettle();
   expect(find.textContaining('NVDA'), findsOneWidget);
   expect(find.text('买入'), findsOneWidget);
 });

 testWidgets('通知页渲染通知与全部已读按钮', (tester) async {
   await _pump(tester, const NoticePage(), [
     noticeApiProvider.overrideWith((ref) => _FakeNoticeApi()),
   ]);
   await tester.pumpAndSettle();
   expect(find.text('风控提醒：单标的持仓超限'), findsOneWidget);
   expect(find.text('全部已读'), findsOneWidget);
   expect(find.text('1 条通知 · 1 未读'), findsOneWidget);
 });
}
