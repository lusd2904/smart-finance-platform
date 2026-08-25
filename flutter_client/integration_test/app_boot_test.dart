import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:flutter_client/app.dart';
import 'package:flutter_client/core/gateway/gateway_store.dart';
import 'package:flutter_client/features/auth/logic/session_controller.dart';
import 'package:flutter_client/features/home/home_shell.dart';

/// 不占用系统键鼠：输入走 Flutter WidgetTester，只驱动本测试窗口。
/// 运行：
///   SMOKE_USER=lustone SMOKE_PASS='...' flutter test integration_test/app_boot_test.dart -d macos
void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  const gateway = String.fromEnvironment(
    'SMOKE_GATEWAY',
    defaultValue: 'http://127.0.0.1:12580',
  );
  final user = const String.fromEnvironment('SMOKE_USER', defaultValue: '');
  final pass = const String.fromEnvironment('SMOKE_PASS', defaultValue: '');

  Future<void> pumpApp(WidgetTester tester) async {
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
    await tester.pump();
    await tester.pump(const Duration(seconds: 1));
  }

  testWidgets('打开即登录页，含网关地址，验证码关闭时隐藏', (tester) async {
    await pumpApp(tester);
    expect(find.byKey(const Key('login-submit')), findsOneWidget);
    expect(find.byKey(const Key('login-gateway')), findsOneWidget);
    expect(find.byKey(const Key('login-username')), findsOneWidget);
    await tester.enterText(find.byKey(const Key('login-gateway')), gateway);

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
    await tester.pump(const Duration(milliseconds: 300));
    expect(captchaHidden, isTrue, reason: '验证码行应在接口返回后隐藏');
  });

  testWidgets('lustone 登录后进入原生壳并打开业务页', (tester) async {
    if (user.isEmpty || pass.isEmpty) {
      // ignore: avoid_print
      print('跳过：未提供 --dart-define=SMOKE_USER/SMOKE_PASS');
      return;
    }
    await pumpApp(tester);
    await tester.enterText(find.byKey(const Key('login-gateway')), gateway);
    await tester.enterText(find.byKey(const Key('login-username')), user);
    await tester.enterText(find.byKey(const Key('login-password')), pass);
    await tester.tap(find.byKey(const Key('login-submit')));
    await tester.pump();
    var entered = false;
    for (var i = 0; i < 40; i++) {
      await tester.pump(const Duration(milliseconds: 250));
      if (find.byType(HomeShell).evaluate().isNotEmpty) {
        entered = true;
        break;
      }
    }
    expect(entered, isTrue, reason: '登录后应进入原生壳');
    expect(find.text('子系统门户'), findsWidgets);

    Future<void> expand(String parent) async {
      final t = find.text(parent);
      if (t.evaluate().isEmpty) return;
      await tester.tap(t.first);
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 400));
    }

    Future<void> openMenu(String title) async {
      final target = find.text(title);
      expect(target, findsWidgets, reason: '侧栏应有 $title');
      await tester.ensureVisible(target.first);
      await tester.tap(target.first);
      await tester.pump();
      await tester.pump(const Duration(seconds: 2));
    }

    await expand('行情中心');
    await openMenu('市场热度');
    expect(find.text('市场热度'), findsWidgets);

    await expand('交易中心');
    await openMenu('交易工作台');
    expect(find.textContaining('交易'), findsWidgets);

    await expand('量化交易');
    await openMenu('策略配置');
    expect(find.textContaining('策略'), findsWidgets);
  });
}
