import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:flutter_client/app.dart';
import 'package:flutter_client/core/gateway/gateway_store.dart';
import 'package:flutter_client/features/auth/logic/session_controller.dart';

/// M0 验收关键路径（对真实本地栈跑）：
/// 首启强制网关页 → 填地址探测通过 → 路由放行进登录页；
/// 现栈验证码关闭时验证码输入框自动隐藏。
/// 运行：flutter test integration_test -d macos
/// （需本机 sentiment 栈在 12580；可用 SMOKE_GATEWAY 覆盖，见下方 define）
void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  // dart-define 传参：--dart-define=SMOKE_GATEWAY=http://host:port
  const gateway = String.fromEnvironment(
    'SMOKE_GATEWAY',
    defaultValue: 'http://127.0.0.1:12580',
  );

  testWidgets('首启配网关→探测→进入登录页', (tester) async {
    SharedPreferences.setMockInitialValues({});
    final prefs = await SharedPreferences.getInstance();
    final container = ProviderContainer(
      overrides: [sharedPreferencesProvider.overrideWithValue(prefs)],
    );
    addTearDown(container.dispose);
    await container.read(sessionController.notifier).bootstrap();

    await tester.pumpWidget(
      UncontrolledProviderScope(container: container, child: const SffApp()),
    );
    await tester.pumpAndSettle();

    // 首启未配网关：路由守卫强制落在网关设置页
    expect(find.text('网关设置'), findsOneWidget);

    // 填入网关地址并探测（打真实本地栈）
    await tester.enterText(find.byType(TextField).first, gateway);
    await tester.tap(find.text('探测并进入'));
    await tester.pumpAndSettle();

    // 探测落盘后守卫放行到登录页
    expect(find.text('登 录'), findsOneWidget);
    expect(find.text('用户名'), findsOneWidget);
    // 现网部署 captchaEnabled=false：验证码输入行应隐藏。
    // 行在 _captcha 未返回前会先渲染；若接口报错则行保留并显示错误文案。
    var captchaHidden = false;
    await tester.runAsync(() async {
      for (var i = 0; i < 30; i++) {
        if (find.text('验证码').evaluate().isEmpty) {
          captchaHidden = true;
          return;
        }
        await Future<void>.delayed(const Duration(milliseconds: 100));
      }
    });
    await tester.pumpAndSettle();
    expect(captchaHidden, isTrue, reason: '验证码行应在接口返回后隐藏');
  });
}
