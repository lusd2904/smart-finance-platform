import 'package:dio/dio.dart';
export 'auth_models.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_client.dart';
import '../../../core/api/api_result.dart';
import 'auth_models.dart';

/// 登录/注册/会话接口。契约依据：
/// - POST /login   OAuth2 表单（username/password/code/uuid）→ {data:{token}}
/// - GET  /captchaImage → {captchaEnabled, registerEnabled, img, uuid}
/// - POST /register JSON {username, password, confirmPassword, code, uuid}
/// - GET  /getInfo  → {user, roles, permissions}
/// - POST /logout
class AuthApi {
  AuthApi(this._dio);

  final Dio _dio;

  Future<CaptchaData> captchaImage() async {
    final response = await _dio.get<dynamic>('/captchaImage');
    ApiResult.from(response); // 业务码校验（code != 200 抛 ApiException）
    final body = response.data;
    if (body is! Map<String, dynamic>) {
      throw ApiException('验证码接口返回格式异常（${response.statusCode}）');
    }
    // 兼容两种形态：信封 {code,msg,data:{...}} 与平铺 {code,msg,img,uuid,...}
    // （RuoYi 原生为平铺，本仓现网栈实测平铺；信封形态来自网关包装）。
    final inner = body['data'];
    final source = <String, dynamic>{
      ...body,
      ...(inner is Map<String, dynamic> ? inner : const <String, dynamic>{}),
    };
    return CaptchaData.fromJson(source);
  }

  Future<String> login({
    required String username,
    required String password,
    String? code,
    String? uuid,
  }) async {
    final response = await _dio.post<dynamic>(
      '/login',
      data: FormData.fromMap(<String, dynamic>{
        'username': username,
        'password': password,
        if (code != null && code.isNotEmpty) 'code': code,
        if (uuid != null && uuid.isNotEmpty) 'uuid': uuid,
      }),
      options: Options(contentType: Headers.formUrlEncodedContentType),
    );
    // 兼容两种返回形态：信封 {code,msg,data:{token}} 与裸 Token {access_token,...}
    final body = response.data;
    if (body is Map<String, dynamic>) {
      final token = body['token'] as String?;
      if (token != null && token.isNotEmpty) return token;
      if (body.containsKey('code')) {
        final result = ApiResult.from(response);
        final inner = result.dataAsMap?['token'] as String?;
        if (inner != null && inner.isNotEmpty) return inner;
      }
    }
    throw ApiException('登录响应中缺少 token');
  }

  Future<CurrentUser> getInfo() async {
    final response = await _dio.get<dynamic>('/getInfo');
    final result = ApiResult.from(response);
    final body = response.data;
    // RuoYi 现网为平铺 {code,msg,user,roles,permissions}，data 可能为空。
    if (body is Map<String, dynamic> &&
        (body['user'] is Map || body['roles'] is List)) {
      return CurrentUser.fromJson(body);
    }
    return CurrentUser.fromJson(result.dataAsMap ?? <String, dynamic>{});
  }

  Future<void> register({
    required String username,
    required String password,
    required String confirmPassword,
    String? code,
    String? uuid,
  }) async {
    await _dio.post<dynamic>('/register', data: <String, dynamic>{
      'username': username,
      'password': password,
      'confirmPassword': confirmPassword,
      if (code != null && code.isNotEmpty) 'code': code,
      if (uuid != null && uuid.isNotEmpty) 'uuid': uuid,
    });
  }

  Future<void> logout() => _dio.post<void>('/logout');
}

final authApiProvider =
    Provider<AuthApi>((ref) => AuthApi(ref.watch(dioProvider)));
