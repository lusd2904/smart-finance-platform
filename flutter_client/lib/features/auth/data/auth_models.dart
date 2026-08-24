/// 鉴权域数据模型，字段对齐后端 login_vo.py（camelCase 别名输出）。
class CaptchaData {
  const CaptchaData({
    required this.captchaEnabled,
    required this.registerEnabled,
    required this.img,
    required this.uuid,
  });

  factory CaptchaData.fromJson(Map<String, dynamic> json) => CaptchaData(
        captchaEnabled: (json['captchaEnabled'] as bool?) ?? true,
        registerEnabled: (json['registerEnabled'] as bool?) ?? false,
        img: (json['img'] as String?) ?? '',
        uuid: (json['uuid'] as String?) ?? '',
      );

  /// base64 图片体（不含 data: 前缀）。
  final String img;
  final bool captchaEnabled;
  final bool registerEnabled;
  final String uuid;
}

class UserInfo {
  const UserInfo({this.userId, this.userName, this.nickName});

  factory UserInfo.fromJson(Map<String, dynamic> json) => UserInfo(
        userId: (json['userId'] as num?)?.toInt(),
        userName: json['userName'] as String?,
        nickName: json['nickName'] as String?,
      );

  final int? userId;
  final String? userName;
  final String? nickName;

  String get displayName =>
      (nickName != null && nickName!.isNotEmpty) ? nickName! : (userName ?? '');
}

class CurrentUser {
  const CurrentUser({this.user, this.roles = const []});

  factory CurrentUser.fromJson(Map<String, dynamic> json) => CurrentUser(
        user: json['user'] is Map<String, dynamic>
            ? UserInfo.fromJson(json['user'] as Map<String, dynamic>)
            : null,
        roles: (json['roles'] as List<dynamic>?)?.cast<String>() ?? const [],
      );

  final UserInfo? user;
  final List<String> roles;
}
