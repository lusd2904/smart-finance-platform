/// 版本检查数据模型。契约依据：
/// module_admin/controller/app_version_controller.py（GET /app/version）。
library;

/// 版本检查响应 data
class UpdateCheck {
  const UpdateCheck({
    this.platform = '',
    this.currentVersion = '',
    this.latestVersion = '',
    this.downloadUrl = '',
    this.notes = '',
    this.updateAvailable = false,
    this.forceUpdate = false,
  });

  factory UpdateCheck.fromJson(Map<String, dynamic> json) => UpdateCheck(
    platform: (json['platform'] as String?) ?? '',
    currentVersion: (json['currentVersion'] as String?) ?? '',
    latestVersion: (json['latestVersion'] as String?) ?? '',
    downloadUrl: (json['downloadUrl'] as String?) ?? '',
    notes: (json['notes'] as String?) ?? '',
    updateAvailable: json['updateAvailable'] == true,
    forceUpdate: json['forceUpdate'] == true,
  );

  final String platform;
  final String currentVersion;
  final String latestVersion;
  final String downloadUrl;
  final String notes;
  final bool updateAvailable;

  /// 服务端依据 sys_config 的 min 基线计算：低于则强制升级。
  final bool forceUpdate;
}
