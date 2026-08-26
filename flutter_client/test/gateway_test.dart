import 'package:flutter_client/core/gateway/gateway_config.dart';
import 'package:flutter_client/core/gateway/gateway_probe.dart';
import 'package:flutter_test/flutter_test.dart';

ProbePage _page({
  String pathname = '/',
  int? status,
  String contentType = '',
  String body = '',
  String? error,
}) =>
    ProbePage(
      pathname: pathname,
      status: status,
      contentType: contentType,
      body: body,
      error: error,
    );

void main() {
  test('Debug 默认本机网关，不改写模拟器环回', () {
    expect(kProdGateway, 'https://sfp.luapi.top');
    expect(kLocalGateway, 'http://127.0.0.1:12580');
    expect(kDefaultGateway, isNot(kProdGateway));
    expect(
      kDefaultGateway,
      anyOf(kLocalGateway, kAndroidEmulatorGateway),
    );
    expect(resolveStoredGateway(''), kDefaultGateway);
    expect(
      resolveStoredGateway('http://10.0.2.2:12580'),
      'http://10.0.2.2:12580',
    );
    expect(resolveStoredGateway('https://sfp.luapi.top'), 'https://sfp.luapi.top');
    expect(suggestedLocalGateway(), startsWith('http://'));
    expect(
      suggestedLocalGateway(),
      anyOf(kLocalGateway, kAndroidEmulatorGateway),
    );
  });

  group('normalizeGateway（对齐 desktop/src/gateway.test.js 用例）', () {
    test('无协议地址默认按 https 处理，不静默降级 http', () {
      expect(normalizeGateway('127.0.0.1:12580'), 'https://127.0.0.1:12580');
    });

    test('显式 http:// 保留且去掉路径与尾斜杠', () {
      expect(normalizeGateway('http://127.0.0.1:12580/'), 'http://127.0.0.1:12580');
    });

    test('去掉路径只留 origin', () {
      expect(normalizeGateway('https://fin.example.com/login'), 'https://fin.example.com');
    });

    test('仅支持 http 或 https', () {
      expect(
        () => normalizeGateway('file:///tmp'),
        throwsA(isA<GatewayFormatException>()
            .having((e) => e.message, 'message', contains('仅支持'))),
      );
    });

    test('空白串归一为空（未配置态）', () {
      expect(normalizeGateway('   '), '');
    });
  });

  group('classifyProbe（移植 desktop probeGateway 判定分支）', () {
    test('前端页面命中即放行', () {
      final result = classifyProbe([
        _page(status: 200, contentType: 'text/html', body: '<div id="app"></div>'),
        _page(pathname: '/login', status: 200, contentType: 'text/html', body: '<div id="app"></div>'),
        _page(pathname: '/docs', error: '404'),
      ], 'http://127.0.0.1:12580');
      expect(result.ok, isTrue);
      expect(result.message, contains('前端网关'));
    });

    test('后端 API 地址给出明确纠正提示', () {
      const swaggerBody =
          '{"openapi":"3.0","info":{"title":"FastAPI"},"detail":"Not Found"}';
      final result = classifyProbe([
        _page(status: 404, contentType: 'application/json', body: swaggerBody),
        _page(pathname: '/login', status: 404, contentType: 'application/json', body: swaggerBody),
        _page(pathname: '/docs', status: 200, contentType: 'text/html', body: 'swagger-ui'),
      ], 'http://127.0.0.1:19099');
      expect(result.ok, isFalse);
      expect(result.code, 'api_only');
      expect(result.message, contains('后端 API'));
      expect(result.message, contains('19099'));
    });

    test('HTTPS 不可达不自动降级，附带回退建议', () {
      final result = classifyProbe([
        _page(error: 'Connection refused'),
        _page(pathname: '/login', error: 'Connection refused'),
        _page(pathname: '/docs', error: 'Connection refused'),
      ], 'https://fin.example.com');
      expect(result.ok, isFalse);
      expect(result.code, 'https_unreachable');
      expect(result.fallbackUrl, 'http://fin.example.com');
      expect(result.message, contains('不会自动降级'));
    });

    test('HTTP 不可达标记 unreachable', () {
      final result = classifyProbe([
        _page(error: 'Connection refused'),
        _page(pathname: '/login', error: 'Connection refused'),
        _page(pathname: '/docs', error: 'Connection refused'),
      ], 'http://127.0.0.1:12580');
      expect(result.ok, isFalse);
      expect(result.code, 'unreachable');
      expect(result.fallbackUrl, isNull);
    });

    test('超时给出防火墙提示', () {
      final result = classifyProbe([
        _page(error: ProbePage.timeoutMark),
        _page(pathname: '/login', error: ProbePage.timeoutMark),
        _page(pathname: '/docs', error: ProbePage.timeoutMark),
      ], 'https://fin.example.com');
      expect(result.message, contains('连接超时'));
    });

    test('5xx 提示确认服务已启动', () {
      final result = classifyProbe([
        _page(status: 502, contentType: 'text/html', body: '<html>Bad Gateway</html>'),
        _page(pathname: '/login', status: 502, contentType: 'text/html'),
        _page(pathname: '/docs', status: 502, contentType: 'text/html'),
      ], 'http://127.0.0.1:12580');
      expect(result.ok, isFalse);
      expect(result.message, contains('502'));
    });

    test('连通但无平台前端时要求改填网关', () {
      final result = classifyProbe([
        _page(status: 200, contentType: 'application/json', body: '{"hello":"world"}'),
      ], 'http://10.0.0.8:8081');
      expect(result.ok, isFalse);
      expect(result.message, contains('没有平台前端'));
    });
  });
}
