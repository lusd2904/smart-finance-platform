/// 通知中心数据模型。契约依据：
/// module_trade/service/platform_ext_service.py:387-408（notices / read）。
library;

/// 应用内通知：GET /trade/notices → data[i]
class NoticeItem {
  const NoticeItem({
    this.id,
    this.title = '',
    this.content = '',
    this.level = '',
    this.category = '',
    this.read = false,
    this.createTime = '',
  });

  factory NoticeItem.fromJson(Map<String, dynamic> json) => NoticeItem(
        id: (json['id'] as num?)?.toInt(),
        title: (json['title'] as String?) ?? '',
        content: (json['content'] as String?) ?? '',
        level: (json['level'] as String?) ?? '',
        category: (json['category'] as String?) ?? '',
        read: json['read'] == true,
        createTime: (json['createTime'] as String?) ?? '',
      );

  final int? id;
  final String title;
  final String content;

  /// 服务端为自由字符串（如 success/error/warn/info），客户端按前缀映射色与图标。
  final String level;
  final String category;
  final bool read;
  final String createTime;
}
