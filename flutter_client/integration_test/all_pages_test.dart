import 'dart:io';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:flutter_client/core/api/api_client.dart';
import 'package:flutter_client/core/gateway/gateway_config.dart';
import 'package:flutter_client/core/gateway/gateway_controller.dart';
import 'package:flutter_client/core/gateway/gateway_store.dart';
import 'package:flutter_client/core/theme/app_theme.dart';
import 'package:flutter_client/features/auth/data/auth_models.dart';
import 'package:flutter_client/features/auth/logic/session_controller.dart';
import 'package:flutter_client/features/home/home_shell.dart';
import 'package:flutter_client/features/shell/admin_shell.dart';
import 'package:flutter_client/features/shell/page_registry.dart';
import 'package:flutter_client/features/web/admin_pages.dart';

/// 全量原生页：IntegrationTest 允许真实 HTTP，输入走 WidgetTester，不抢系统键鼠。
void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  const defineUser = String.fromEnvironment('SMOKE_USER');
  const definePass = String.fromEnvironment('SMOKE_PASS');
  const defineGw = String.fromEnvironment('SMOKE_GATEWAY');
  const defineToken = String.fromEnvironment('SMOKE_TOKEN');
  const defineTokenFile = String.fromEnvironment('SMOKE_TOKEN_FILE');
  final gateway = defineGw.isNotEmpty
      ? defineGw
      : (Platform.environment['SMOKE_GATEWAY'] ?? 'http://127.0.0.1:12580');
  final user = defineUser.isNotEmpty
      ? defineUser
      : (Platform.environment['SMOKE_USER'] ?? '');
  final pass = definePass.isNotEmpty
      ? definePass
      : (Platform.environment['SMOKE_PASS'] ?? '');
  final tokenFile = defineTokenFile.isNotEmpty
      ? defineTokenFile
      : (Platform.environment['SMOKE_TOKEN_FILE'] ?? '');
  var tokenEnv = defineToken.isNotEmpty
      ? defineToken
      : (Platform.environment['SMOKE_TOKEN'] ?? '');
  if (tokenEnv.isEmpty && tokenFile.isNotEmpty) {
    final f = File(tokenFile);
    if (f.existsSync()) tokenEnv = f.readAsStringSync().trim();
  }

  if (tokenEnv.isEmpty && (user.isEmpty || pass.isEmpty)) {
    // ignore: avoid_print
    print('---- 跳过：未提供 SMOKE_USER / SMOKE_PASS 或 SMOKE_TOKEN[_FILE] ----');
    return;
  }

  late String token;
  late UserInfo userInfo;
  late List<String> roles;

  setUpAll(() async {
    final dio = Dio(
      BaseOptions(
        baseUrl: '$gateway/docker-api',
        connectTimeout: const Duration(seconds: 8),
        receiveTimeout: const Duration(seconds: 20),
      ),
    );
    if (tokenEnv.isNotEmpty) {
      token = tokenEnv;
    } else {
      final login = await dio.post<dynamic>(
        '/login',
        data: FormData.fromMap({'username': user, 'password': pass}),
        options: Options(contentType: Headers.formUrlEncodedContentType),
      );
      final body = login.data as Map<String, dynamic>;
      token = body['token'] as String? ??
          ((body['data'] as Map?)?['token'] as String?) ??
          '';
    }
    expect(token, isNotEmpty);
    dio.options.headers['Authorization'] = 'Bearer $token';
    final info = (await dio.get<dynamic>('/getInfo')).data as Map<String, dynamic>;
    final current = CurrentUser.fromJson(info);
    userInfo = current.user ?? UserInfo(userName: user, nickName: user);
    roles = current.roles;
  });

  testWidgets('打开全部原生页面', (tester) async {
    SharedPreferences.setMockInitialValues({});
    final prefs = await SharedPreferences.getInstance();
    final container = ProviderContainer(
      overrides: [
        sharedPreferencesProvider.overrideWithValue(prefs),
        gatewayController.overrideWith(() => _FixedGateway(gateway)),
        sessionController.overrideWith(() => _FixedSession(userInfo, roles)),
        dioProvider.overrideWith((ref) {
          final dio = Dio(
            BaseOptions(
              baseUrl: '$gateway/docker-api',
              connectTimeout: const Duration(seconds: 8),
              receiveTimeout: const Duration(seconds: 25),
            ),
          );
          dio.interceptors.add(
            InterceptorsWrapper(
              onRequest: (options, handler) {
                options.headers['Authorization'] = 'Bearer $token';
                handler.next(options);
              },
            ),
          );
          return dio;
        }),
      ],
    );
    addTearDown(container.dispose);

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: MaterialApp(theme: AppTheme.dark(), home: const HomeShell()),
      ),
    );
    await tester.pump();

    const pages = <String>[
      '/portal',
      '/index',
      '/user/profile',
      '/market/heat',
      '/market/board',
      '/market/stocks',
      '/market/watchlist',
      '/market/finance-news',
      '/market/ai-workbench',
      '/market/recommendations',
      '/market/review',
      '/market/kline',
      '/market/symbol',
      '/market/coverage',
      '/market/stock-pool',
      '/market/tradingview',
      '/market/dashboard',
      '/market/terminal',
      '/trade/terminal',
      '/quant/strategy',
      '/quant/factor',
      '/quant/scan-runs',
      '/quant/scan-result',
      '/quant/daily-list',
      '/quant/strategy-config',
      '/quant/longbridge',
      '/quant/alpha-snapshot',
      '/quant/risk',
      '/quant/watchlist',
      '/trade/desk',
      '/trade/trading',
      '/trade/positions',
      '/trade/orders',
      '/trade/broker',
      '/trade/risk',
      '/trade/risk-review',
      '/trade/backtest',
      '/trade/notifications',
      '/trade/ai-runs',
      '/trade/feishu-push',
      '/sentiment/dashboard',
      '/sentiment/news',
      '/sentiment/analysis',
      '/sentiment/config',
      '/ai/chat',
      '/ai/model',
      '/ai/req-chat',
      '/ai/req-list',
      '/ai/req-bot',
      '/analysis/jobs',
      '/system/user',
      '/system/role',
      '/system/menu',
      '/system/dept',
      '/system/post',
      '/system/dict',
      '/system/config',
      '/system/notice',
      '/monitor/online',
      '/monitor/job',
      '/monitor/job-log',
      '/monitor/operlog',
      '/monitor/logininfor',
      '/monitor/server',
      '/monitor/cache',
      '/monitor/cacheList',
      '/monitor/druid',
      '/monitor/transportCrypto',
      '/tool/gen',
      '/tool/build',
      '/tool/swagger',
    ];

    final ok = <String>[];
    final fail = <String, String>{};

    for (final path in pages) {
      container.read(shellNavRequestProvider.notifier).state =
          ShellNavRequest(path, title: defaultTitleFor(path));
      await tester.pump();
      await tester.runAsync(() async {
        await Future<void>.delayed(const Duration(milliseconds: 650));
      });
      await tester.pump();

      final crashes = <String>[];
      Object? ex;
      while ((ex = tester.takeException()) != null) {
        crashes.add(ex.toString());
      }
      final realCrashes = crashes
          .where((c) => !c.contains('ListTile background color'))
          .toList();
      if (find.byType(UnknownRoutePage).evaluate().isNotEmpty) {
        fail[path] = '页面未注册';
        // ignore: avoid_print
        print('FAIL\t$path\t页面未注册');
        continue;
      }
      if (realCrashes.isNotEmpty) {
        final msg = realCrashes.first.replaceAll('\n', ' ');
        fail[path] = msg.length > 180 ? msg.substring(0, 180) : msg;
        // ignore: avoid_print
        print('FAIL\t$path\t${fail[path]}');
        continue;
      }
      ok.add(path);
      // ignore: avoid_print
      print('OK\t$path\t${defaultTitleFor(path)}');
    }

    // ignore: avoid_print
    print('---- 原生页 ${ok.length} 通过 / ${fail.length} 失败 / 共 ${pages.length} ----');
    fail.forEach((p, m) {
      // ignore: avoid_print
      print('  FAIL $p :: $m');
    });
    expect(fail.isEmpty, isTrue, reason: '失败：${fail.keys.join(', ')}');
  }, timeout: const Timeout(Duration(minutes: 8)));
}

class _FixedGateway extends GatewayController {
  _FixedGateway(this.url);
  final String url;

  @override
  GatewayConfig build() => GatewayConfig(url: url, lastGoodUrl: url);
}

class _FixedSession extends SessionController {
  _FixedSession(this._user, this._roles);
  final UserInfo _user;
  final List<String> _roles;

  @override
  SessionState build() => SessionState(
        status: SessionStatus.authenticated,
        user: _user,
        roles: _roles,
      );
}
