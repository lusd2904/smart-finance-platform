import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_client.dart';
import '../../../core/api/api_result.dart';
import 'notice_models.dart';

/// 通知中心接口。契约依据：module_trade/controller/trade_controller.py:534-547。
class NoticeApi {
  NoticeApi(this._dio);

  final Dio _dio;

  /// 应用内通知列表（最新在前）。
  Future<List<NoticeItem>> list({int limit = 50}) async {
    final result = ApiResult.from(
      await _dio.get<void>('/trade/notices', queryParameters: {'limit': limit}),
    );
    return ((result.data as List<dynamic>?) ?? const [])
        .whereType<Map<String, dynamic>>()
        .map(NoticeItem.fromJson)
        .toList();
  }

  /// 标记已读；id 为空 = 全部已读。
  Future<void> markRead({int? id}) async {
    await _dio.post<void>('/trade/notices/read', data: {'id': ?id});
  }
}

final noticeApiProvider = Provider<NoticeApi>(
  (ref) => NoticeApi(ref.watch(dioProvider)),
);

/// 通知列表 + 未读数。
typedef NoticeBoard = ({List<NoticeItem> items, int unread});

/// 通知轮询：页面存活期间每 30s 重拉（规划文档 M2「应用内轮询」语义）。
/// 用可取消 Timer 实现（async* 的延时无法在容器销毁时取消，
/// 会在 widget 测试中留下 pending timer）；单次失败保留旧数据继续轮询。
final noticeBoardProvider = StreamProvider.autoDispose<NoticeBoard>((ref) {
  final controller = StreamController<NoticeBoard>();
  Timer? timer;
  var disposed = false;

  Future<void> tick() async {
    try {
      final items = await ref.read(noticeApiProvider).list();
      if (!disposed) {
        controller.add((
          items: items,
          unread: items.where((n) => !n.read).length,
        ));
      }
    } catch (_) {}
    if (!disposed) timer = Timer(const Duration(seconds: 30), tick);
  }

  unawaited(tick());
  ref.onDispose(() {
    disposed = true;
    timer?.cancel();
    controller.close();
  });
  return controller.stream;
});
