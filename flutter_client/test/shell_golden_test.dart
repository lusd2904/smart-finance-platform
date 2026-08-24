// 壳层视觉回归：真实渲染 HomeShell 桌面/手机两种壳并产出 golden PNG。
// 行情/自选数据源以假 API 注入（不发真请求，保证快照确定性与零网络依赖）；
// 布局性改动后执行 `flutter test --update-goldens test/shell_golden_test.dart` 更新基线。
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:flutter_client/core/gateway/gateway_controller.dart';
import 'package:flutter_client/core/gateway/gateway_config.dart';
import 'package:flutter_client/core/theme/app_theme.dart';
import 'package:flutter_client/features/auth/data/auth_models.dart';
import 'package:flutter_client/features/auth/logic/session_controller.dart';
import 'package:flutter_client/features/home/home_shell.dart';
import 'package:dio/dio.dart';
import 'package:flutter_client/features/market/data/market_api.dart';
import 'package:flutter_client/features/market/data/market_models.dart';


/// 假会话：绕开真实登录态。
class _FakeSession extends SessionController {
  @override
  SessionState build() => const SessionState(
        status: SessionStatus.authenticated,
        user: UserInfo(userId: 1, userName: 'demo', nickName: '示例用户'),
        roles: ['admin'],
      );
}

class _FakeGateway extends GatewayController {
  @override
  GatewayConfig build() =>
      const GatewayConfig(url: 'http://127.0.0.1:12580', lastGoodUrl: 'http://127.0.0.1:12580');
}

/// 假行情 API：golden 不发真请求（Dio 超时 Timer 会泄漏导致测试挂），
/// 返回固定内容让快照可复现。
class _FakeMarketApi extends MarketApi {
  _FakeMarketApi() : super(Dio());

  @override
  Future<HeatDailyData> heatDaily({required String market, String? tradeDate}) async {
    return const HeatDailyData(
      heat: HeatSummary(
        asOfTime: '2026-08-24 10:00:00',
        indexName: '纳斯达克综合指数',
        indexChangePct: 1.28,
        totalTurnover: 286000000000,
        advanceCount: 3210,
        declineCount: 1540,
        flatCount: 120,
        heatScore: 72.5,
        heatSummary: '示例热度摘要',
      ),
    );
  }

  @override
  Future<List<IndexQuote>> indexQuotes() async => const [
        IndexQuote(
            symbol: '.IXIC', name: '纳斯达克', market: 'US', last: 20819.4, changePct: 1.28),
        IndexQuote(
            symbol: 'HSI', name: '恒生指数', market: 'HK', last: 25330.1, changePct: -0.62),
        IndexQuote(symbol: '000001.SH', name: '上证指数', market: 'CN', last: 3712.5, changePct: 0.35),
      ];

  @override
  Future<WatchlistOverview> watchlistOverview() async => const WatchlistOverview();
}

Future<void> _pumpShell(WidgetTester tester, Size size) async {
  tester.view.devicePixelRatio = 1.0;
  tester.view.physicalSize = size;
  addTearDown(tester.view.reset);
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        sessionController.overrideWith(_FakeSession.new),
        gatewayController.overrideWith(_FakeGateway.new),
        marketApiProvider.overrideWith((ref) => _FakeMarketApi()),
      ],
      child: MaterialApp(theme: AppTheme.light(), home: const HomeShell()),
    ),
  );
  // 首帧 + 让假数据 Future 完成、页面落到稳定内容态。
  await tester.pump();
  await tester.pump(const Duration(milliseconds: 600));
}

void main() {
  testWidgets('desktop shell golden', (tester) async {
    await _pumpShell(tester, const Size(1440, 900));
    await expectLater(
        find.byType(HomeShell), matchesGoldenFile('goldens/shell_desktop.png'));
  });

  testWidgets('mobile shell golden', (tester) async {
    await _pumpShell(tester, const Size(390, 844));
    await expectLater(
        find.byType(HomeShell), matchesGoldenFile('goldens/shell_mobile.png'));
  });
}
