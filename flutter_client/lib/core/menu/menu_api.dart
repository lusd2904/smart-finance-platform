import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../api/api_client.dart';
import '../api/api_result.dart';
import 'router_models.dart';

class MenuApi {
  MenuApi(this._dio);

  final Dio _dio;

  Future<List<RouterNode>> getRouters() async {
    final result = ApiResult.from(await _dio.get<void>('/getRouters'));
    final data = result.data;
    if (data is! List) return const [];
    return data.whereType<Map<String, dynamic>>().map(RouterNode.fromJson).toList();
  }
}

final menuApiProvider = Provider<MenuApi>(
  (ref) => MenuApi(ref.watch(dioProvider)),
);

final routersProvider = FutureProvider<List<RouterNode>>((ref) {
  return ref.watch(menuApiProvider).getRouters();
});
