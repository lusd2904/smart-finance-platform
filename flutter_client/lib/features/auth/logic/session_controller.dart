import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:flutter_client/core/api/api_client.dart';
import 'package:flutter_client/core/api/api_result.dart';
import 'package:flutter_client/core/storage/token_store.dart';
import 'package:flutter_client/features/auth/data/auth_api.dart';

enum SessionStatus { unknown, anonymous, authenticated }

class SessionState {
  const SessionState({
    this.status = SessionStatus.unknown,
    this.user,
    this.roles = const [],
  });

  final SessionStatus status;
  final UserInfo? user;
  final List<String> roles;

  bool get isAnonymous => status == SessionStatus.anonymous;
  bool get isAuthenticated => status == SessionStatus.authenticated;

  SessionState copyWith({
    SessionStatus? status,
    UserInfo? user,
    List<String>? roles,
  }) =>
      SessionState(
        status: status ?? this.status,
        user: user ?? this.user,
        roles: roles ?? this.roles,
      );
}

/// 会话状态机：启动引导恢复登录态 → 登录/登出/401 踢出。
/// 网络类失败保留本地 token（重连后重启可恢复），仅业务拒绝（401/过期）才清除。
class SessionController extends Notifier<SessionState> {
  bool _wiredUnauthorized = false;

  @override
  SessionState build() => const SessionState();

  /// 401 统一踢出挂在共享 Dio 上，只注册一次（核心层不反向依赖会话层）。
  void _ensureUnauthorizedWiring() {
    if (_wiredUnauthorized) return;
    ref.read(dioProvider).interceptors.add(
          InterceptorsWrapper(
            onError: (e, handler) {
              if (e.response?.statusCode == 401) {
                onUnauthorized();
              }
              handler.next(e);
            },
          ),
        );
    _wiredUnauthorized = true;
  }

  Future<void> bootstrap() async {
    _ensureUnauthorizedWiring();
    final token = await ref.read(tokenStoreProvider).read();
    if (token == null || token.isEmpty) {
      state = const SessionState(status: SessionStatus.anonymous);
      return;
    }
    try {
      final current = await ref.read(authApiProvider).getInfo();
      state = SessionState(
        status: SessionStatus.authenticated,
        user: current.user,
        roles: current.roles,
      );
    } on ApiException {
      // token 失效/被拒：清除并回登录页。
      await _signOutLocal();
    } catch (_) {
      // 网络不通：保留 token，仅回到登录界面等待重新连通。
      state = const SessionState(status: SessionStatus.anonymous);
    }
  }

  /// 返回 null 表示成功；否则为用户可读错误文案。
  Future<String?> login({
    required String username,
    required String password,
    required CaptchaData captcha,
    required String code,
  }) async {
    try {
      final token = await ref.read(authApiProvider).login(
            username: username,
            password: password,
            code: code,
            uuid: captcha.uuid,
          );
      if (token.isEmpty) return '登录响应中缺少 token';
      await ref.read(tokenStoreProvider).write(token);
      final current = await ref.read(authApiProvider).getInfo();
      state = SessionState(
        status: SessionStatus.authenticated,
        user: current.user,
        roles: current.roles,
      );
      return null;
    } catch (e) {
      return describeApiError(e);
    }
  }

  Future<void> logout() async {
    try {
      await ref.read(authApiProvider).logout();
    } catch (_) {
      // 服务端登出失败不阻断本地登出。
    }
    await _signOutLocal();
  }

  /// Dio 拦截器在收到 401 时调用。
  Future<void> onUnauthorized() async {
    if (state.isAuthenticated) await _signOutLocal();
  }

  Future<void> _signOutLocal() async {
    await ref.read(tokenStoreProvider).clear();
    state = const SessionState(status: SessionStatus.anonymous);
  }
}

final sessionController =
    NotifierProvider<SessionController, SessionState>(SessionController.new);
