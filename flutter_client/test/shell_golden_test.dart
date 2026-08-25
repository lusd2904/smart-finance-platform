import 'dart:io';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:flutter_client/core/api/api_result.dart';
import 'package:flutter_client/core/api/ruoyi_client.dart';
import 'package:flutter_client/core/gateway/gateway_config.dart';
import 'package:flutter_client/core/gateway/gateway_controller.dart';
import 'package:flutter_client/core/menu/menu_api.dart';
import 'package:flutter_client/core/menu/router_models.dart';
import 'package:flutter_client/core/theme/app_theme.dart';
import 'package:flutter_client/features/auth/data/auth_models.dart';
import 'package:flutter_client/features/auth/logic/session_controller.dart';
import 'package:flutter_client/features/home/home_shell.dart';

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
  GatewayConfig build() => const GatewayConfig(
        url: 'http://127.0.0.1:12580',
        lastGoodUrl: 'http://127.0.0.1:12580',
      );
}

class _FakeMenuApi extends MenuApi {
  _FakeMenuApi() : super(Dio());

  @override
  Future<List<RouterNode>> getRouters() async => [
        RouterNode(
          path: '/market',
          meta: const RouterMeta(title: '行情中心', icon: 'chart'),
          children: const [
            RouterNode(path: 'heat', meta: RouterMeta(title: '市场热度')),
            RouterNode(path: 'board', meta: RouterMeta(title: '行情台')),
          ],
        ),
        RouterNode(
          path: '/trade',
          meta: const RouterMeta(title: '交易中心', icon: 'money'),
          children: const [
            RouterNode(path: 'desk', meta: RouterMeta(title: '交易工作台')),
          ],
        ),
      ];
}

class _FakeRuoyi extends RuoyiClient {
  _FakeRuoyi() : super(Dio());

  @override
  Future<ApiResult> get(String path, {Map<String, dynamic>? query, Duration? timeout}) async =>
      ApiResult.ok(data: const {});

  @override
  Future<ApiResult> post(String path, {dynamic data, Map<String, dynamic>? query, Duration? timeout}) async =>
      ApiResult.ok(data: const {});

  @override
  Future<ApiResult> put(String path, {dynamic data, Map<String, dynamic>? query}) async =>
      ApiResult.ok(data: const {});

  @override
  Future<ApiResult> delete(String path, {dynamic data}) async => ApiResult.ok(data: const {});
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
        menuApiProvider.overrideWith((ref) => _FakeMenuApi()),
        ruoyiClientProvider.overrideWith((ref) => _FakeRuoyi()),
      ],
      child: MaterialApp(theme: AppTheme.light(), home: const HomeShell()),
    ),
  );
  await tester.pump();
  await tester.pump(const Duration(milliseconds: 600));
}

void main() {
  testWidgets('desktop shell golden', (tester) async {
    await _pumpShell(tester, const Size(1440, 900));
    await expectLater(
      find.byType(HomeShell),
      matchesGoldenFile('goldens/shell_desktop.png'),
    );
  }, skip: !Platform.isMacOS);

  testWidgets('mobile shell golden', (tester) async {
    await _pumpShell(tester, const Size(390, 844));
    await expectLater(
      find.byType(HomeShell),
      matchesGoldenFile('goldens/shell_mobile.png'),
    );
  }, skip: !Platform.isMacOS);
}
