import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_client/core/gateway/gateway_controller.dart';
import 'package:flutter_client/core/storage/token_store.dart';
import 'package:flutter_client/core/api/api_result.dart';

/// 业务 Dio 实例：baseUrl 指向 {网关}/docker-api，自动附带 JWT。
final dioProvider = Provider<Dio>((ref) {
  final gateway = ref.watch(gatewayController);
  final dio = Dio(BaseOptions(
    // 首启引导期会话层会急切构建本 Provider，此时网关尚未配置：
    // 占位合法 URL 保证 BaseOptions 构造不抛；路由守卫保证该阶段无业务请求发出。
    baseUrl: gateway.url.isEmpty
        ? 'http://127.0.0.1'
        : '${gateway.url}/docker-api',
    connectTimeout: const Duration(seconds: 6),
    receiveTimeout: const Duration(seconds: 30),
    sendTimeout: const Duration(seconds: 10),
  ));
  dio.interceptors.add(InterceptorsWrapper(
    onRequest: (options, handler) async {
      // 安全存储不可用（钥匙串授权缺失等）时按无 token 放行：
      // 后端返回 401 由统一踢出逻辑处理，不让存储故障挂死所有业务请求。
      try {
        final token = await ref.read(tokenStoreProvider).read();
        if (token != null && token.isNotEmpty) {
          options.headers['Authorization'] = 'Bearer $token';
        }
      } catch (_) {}
      handler.next(options);
    },
  ));
  return dio;
});

/// 把任意 DioException / ApiException 转成用户可读文案。
String describeApiError(Object error) {
  if (error is ApiException) return error.message;
  if (error is DioException) {
    switch (error.type) {
      case DioExceptionType.connectionTimeout:
      case DioExceptionType.receiveTimeout:
      case DioExceptionType.sendTimeout:
        return '连接超时，请检查网关地址、端口和防火墙';
      case DioExceptionType.connectionError:
        return '无法连接网关，请确认服务已启动';
      default:
        final code = error.response?.statusCode;
        if (code != null) return '请求失败（HTTP $code）';
        return '网络异常：${error.message ?? error.toString()}';
    }
  }
  return error.toString();
}
