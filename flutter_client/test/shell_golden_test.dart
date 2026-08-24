// 临时视觉验证：真实渲染 HomeShell 桌面/手机两种壳并产出 golden PNG。
// 仅用于本地设计走查，验证完成后删除本文件与 goldens/ 产物。
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:flutter_client/core/gateway/gateway_controller.dart';
import 'package:flutter_client/core/gateway/gateway_config.dart';
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
  GatewayConfig build() =>
      const GatewayConfig(url: 'http://127.0.0.1:12580', lastGoodUrl: 'http://127.0.0.1:12580');
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
      ],
      child: MaterialApp(theme: AppTheme.light(), home: const HomeShell()),
    ),
  );
  // 首帧 + 让 IndexedStack 内的行情/自选请求快速失败并落到错误态。
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
