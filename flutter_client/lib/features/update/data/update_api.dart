import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:package_info_plus/package_info_plus.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../core/api/api_client.dart';
import '../../../core/api/api_result.dart';
import 'update_models.dart';

/// 客户端版本检查（M5 发布工程）。
/// 契约依据：module_admin/controller/app_version_controller.py。
/// 仅 release/profile 构建触发（调用方负责 kDebugMode 门禁）；
/// 强更弹窗不可关闭，弱更仅提示一次。
class UpdateApi {
  UpdateApi(this._dio);

  final Dio _dio;

  Future<UpdateCheck> check({
    required String platform,
    required String version,
  }) async {
    final result = ApiResult.from(
      await _dio.get<void>(
        '/app/version',
        queryParameters: {'platform': platform, 'version': version},
      ),
    );
    return UpdateCheck.fromJson(result.dataAsMap ?? <String, dynamic>{});
  }
}

final updateApiProvider = Provider<UpdateApi>(
  (ref) => UpdateApi(ref.watch(dioProvider)),
);

/// 目标平台标识（对齐后端 Literal 枚举）。
String? currentPlatformId() {
  switch (defaultTargetPlatform) {
    case TargetPlatform.android:
      return 'android';
    case TargetPlatform.iOS:
      return 'ios';
    case TargetPlatform.macOS:
      return 'macos';
    case TargetPlatform.windows:
      return 'windows';
    default:
      return null; // linux 等未发布平台不检查。
  }
}

/// 拉起外部下载页/安装包；失败返回 false 由调用方提示。
Future<bool> launchDownload(String url) =>
    launchUrl(Uri.parse(url), mode: LaunchMode.externalApplication);

/// 检查一次更新；任何失败静默返回 null（更新检查绝不阻塞主流程）。
Future<UpdateCheck?> checkOnce(WidgetRef ref) async {
  try {
    final platform = currentPlatformId();
    if (platform == null) return null;
    final info = await PackageInfo.fromPlatform();
    return await ref
        .read(updateApiProvider)
        .check(platform: platform, version: info.version);
  } catch (_) {
    return null;
  }
}
