import 'dart:async';
import 'dart:math';

import 'package:dio/dio.dart';

/// 网关地址格式错误（与 desktop/src/gateway.js 的 normalizeGateway 抛错语义一致）。
class GatewayFormatException implements Exception {
  const GatewayFormatException(this.message);
  final String message;

  @override
  String toString() => message;
}

/// 单次探测抓到的页面快照。error 非 null 表示该路径网络层失败。
class ProbePage {
  const ProbePage({
    required this.pathname,
    this.status,
    this.contentType = '',
    this.body = '',
    this.error,
  });

  final String pathname;
  final int? status;
  final String contentType;
  final String body;
  final String? error;

  /// 连接/读取超时的哨兵标记，用于区分超时与其它网络错误。
  static const timeoutMark = '__timeout__';
}

class ProbeResult {
  const ProbeResult({
    required this.ok,
    required this.message,
    this.origin,
    this.code,
    this.fallbackUrl,
  });

  final bool ok;
  final String message;
  final String? origin;

  /// unreachable / https_unreachable / api_only
  final String? code;
  final String? fallbackUrl;
}

final _apiBodyPattern =
    RegExp(r'swagger-ui|redoc|openapi|FastAPI', caseSensitive: false);
final _frontendBrandPattern =
    RegExp(r'智慧金融|NEXUS|id="app"', caseSensitive: false);
final _jsonDetailPattern = RegExp(r'"detail"|"code"');

bool _isApi(ProbePage page) =>
    _apiBodyPattern.hasMatch(page.body) ||
    (page.contentType.contains('application/json') &&
        _jsonDetailPattern.hasMatch(page.body));

bool _isFrontend(ProbePage page) {
  if (_apiBodyPattern.hasMatch(page.body)) return false;
  if (_frontendBrandPattern.hasMatch(page.body)) return true;
  return page.contentType.contains('text/html') && page.status == 200 && !_isApi(page);
}

/// 无协议地址默认按 https 处理（不静默降级 http）；显式 http:// 保留；返回 origin。
String normalizeGateway(String raw) {
  final text = raw.trim();
  if (text.isEmpty) return '';
  final withScheme = RegExp(r'^[a-zA-Z][a-zA-Z0-9+.\-]*://').hasMatch(text)
      ? text
      : 'https://$text';
  Uri parsed;
  try {
    parsed = Uri.parse(withScheme);
  } on FormatException {
    throw const GatewayFormatException('网关地址格式无效');
  }
  if (parsed.scheme != 'http' && parsed.scheme != 'https') {
    throw const GatewayFormatException('仅支持 http 或 https 网关');
  }
  if (parsed.host.isEmpty) {
    throw const GatewayFormatException('网关地址格式无效');
  }
  // 对齐 JS URL.origin：小写 host、省略默认端口。
  final host = parsed.host.toLowerCase();
  final isDefaultPort = parsed.port == (parsed.scheme == 'https' ? 443 : 80);
  final portPart = parsed.hasPort && !isDefaultPort ? ':${parsed.port}' : '';
  return '${parsed.scheme}://$host$portPart';
}

/// 纯判定逻辑（probeGateway 各分支的逐条移植），与网络层分离以便单测。
ProbeResult classifyProbe(List<ProbePage> pages, String origin) {
  if (pages.isNotEmpty && pages.every((p) => p.error != null)) {
    final aborted = pages.any((p) => p.error == ProbePage.timeoutMark);
    final detail =
        pages.firstWhere((p) => p.error != null).error ?? '未知网络错误';
    var message = aborted ? '连接超时，请检查地址、端口和防火墙' : '无法连接：$detail';
    String? code;
    String? fallbackUrl;
    if (origin.startsWith('https://')) {
      code = 'https_unreachable';
      fallbackUrl = 'http://${origin.substring('https://'.length)}';
      message +=
          '。不会自动降级为明文 HTTP；如你确认该环境没有 TLS，请手动把地址改为以 http:// 开头后再试。';
    } else {
      code = 'unreachable';
    }
    return ProbeResult(
        ok: false, origin: origin, code: code, message: message, fallbackUrl: fallbackUrl);
  }

  final htmlPages = pages.where(_isFrontend).toList();
  final apiPages = pages.where(_isApi).toList();

  for (final page in htmlPages) {
    final s = page.status;
    if (s != null && s < 500) {
      return ProbeResult(ok: true, origin: origin, message: '已连通前端网关，可以进入登录');
    }
  }

  if (apiPages.isNotEmpty && htmlPages.isEmpty) {
    return const ProbeResult(
      ok: false,
      code: 'api_only',
      message: '这是后端 API 地址。请填写前端网关（本机默认 http://127.0.0.1:12580），不要填 19099/9099。',
    );
  }

  for (final page in pages) {
    final s = page.status;
    if (s != null && s >= 500) {
      return ProbeResult(ok: false, origin: origin, message: '网关返回 $s，请确认服务已启动');
    }
  }

  return ProbeResult(
      ok: false, origin: origin, message: '该地址没有平台前端，请改填 Nginx/前端网关');
}

/// 并发抓取 /、/login、/docs 三个路径（desktop probeGateway 同款探测面）。
Future<List<ProbePage>> fetchProbePages(Dio dio, String origin,
    {Duration timeout = const Duration(seconds: 6)}) async {
  return Future.wait(['/', '/login', '/docs'].map((pathname) async {
    try {
      final res = await dio.get<String>(
        '$origin$pathname',
        options: Options(
          responseType: ResponseType.plain,
          validateStatus: (_) => true,
          headers: {'Accept': 'text/html,application/json;q=0.9,*/*;q=0.8'},
        ),
      );
      final raw = res.data ?? '';
      return ProbePage(
        pathname: pathname,
        status: res.statusCode ?? 0,
        contentType: res.headers.value(Headers.contentTypeHeader) ?? '',
        body: raw.substring(0, min(raw.length, 32000)),
      );
    } on DioException catch (e) {
      final timedOut = e.type == DioExceptionType.connectionTimeout ||
          e.type == DioExceptionType.receiveTimeout;
      return ProbePage(
        pathname: pathname,
        error: timedOut ? ProbePage.timeoutMark : (e.message ?? e.toString()),
      );
    } catch (e) {
      return ProbePage(pathname: pathname, error: e.toString());
    }
  }));
}

/// 探测网关是否为平台前端入口。语义与 desktop/src/gateway.js#probeGateway 一致：
/// HTTPS 绝不自动降级 HTTP，仅在结果里附 fallbackUrl 供用户手动选择。
Future<ProbeResult> probeGateway(String rawUrl,
    {Duration timeout = const Duration(seconds: 6)}) async {
  String origin;
  try {
    origin = normalizeGateway(rawUrl);
  } on GatewayFormatException catch (e) {
    return ProbeResult(ok: false, message: e.message);
  }
  if (origin.isEmpty) {
    return const ProbeResult(ok: false, message: '请填写网关地址');
  }
  final dio = Dio()
    ..options.connectTimeout = timeout
    ..options.receiveTimeout = timeout
    ..options.sendTimeout = timeout;
  try {
    final pages = await fetchProbePages(dio, origin, timeout: timeout);
    return classifyProbe(pages, origin);
  } finally {
    dio.close();
  }
}
