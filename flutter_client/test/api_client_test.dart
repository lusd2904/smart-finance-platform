import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:flutter_client/core/api/api_client.dart';
import 'package:flutter_client/core/gateway/gateway_controller.dart';
import 'package:flutter_client/core/gateway/gateway_store.dart';

void main() {
  // 回归：首启引导期会话层急切构建 dioProvider，此时网关尚未配置。
  // 修复前 BaseOptions(baseUrl: '/docker-api') 抛
  // 「Invalid argument (baseUrl): Must be a valid URL」。
  test('未配置网关时 Dio 构造不抛，占位合法 baseUrl', () async {
    SharedPreferences.setMockInitialValues({});
    final prefs = await SharedPreferences.getInstance();
    final container = ProviderContainer(
      overrides: [sharedPreferencesProvider.overrideWithValue(prefs)],
    );
    addTearDown(container.dispose);

    expect(container.read(gatewayController).url, isEmpty);
    final dio = container.read(dioProvider); // 修复前此处抛异常
    expect(Uri.tryParse(dio.options.baseUrl)?.hasScheme ?? false, isTrue);
  });

  test('已配置网关时 baseUrl 拼接 docker-api 前缀', () async {
    SharedPreferences.setMockInitialValues({
      'gateway.config.v1':
          '{"url":"https://demo.example.com","confirmOnLaunch":false}',
    });
    final prefs = await SharedPreferences.getInstance();
    final container = ProviderContainer(
      overrides: [sharedPreferencesProvider.overrideWithValue(prefs)],
    );
    addTearDown(container.dispose);

    final dio = container.read(dioProvider);
    expect(dio.options.baseUrl, 'https://demo.example.com/docker-api');
  });
}
