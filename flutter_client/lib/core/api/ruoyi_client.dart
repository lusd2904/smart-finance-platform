import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'api_client.dart';
import 'api_result.dart';

/// 通用 RuoYi 客户端：网页端每个页面的 `{网关}/docker-api` + 路由都走这里。
class RuoyiClient {
  RuoyiClient(this._dio);

  final Dio _dio;

  Future<ApiResult> get(
    String path, {
    Map<String, dynamic>? query,
    Duration? timeout,
  }) async {
    final response = await _dio.get<dynamic>(
      path,
      queryParameters: _clean(query),
      options: timeout == null ? null : Options(receiveTimeout: timeout),
    );
    return ApiResult.from(response);
  }

  Future<ApiResult> post(
    String path, {
    dynamic data,
    Map<String, dynamic>? query,
    Duration? timeout,
  }) async {
    final response = await _dio.post<dynamic>(
      path,
      data: data,
      queryParameters: _clean(query),
      options: timeout == null ? null : Options(receiveTimeout: timeout),
    );
    return ApiResult.from(response);
  }

  Future<ApiResult> put(
    String path, {
    dynamic data,
    Map<String, dynamic>? query,
  }) async {
    final response = await _dio.put<dynamic>(
      path,
      data: data,
      queryParameters: _clean(query),
    );
    return ApiResult.from(response);
  }

  Future<ApiResult> delete(String path, {dynamic data}) async {
    final response = await _dio.delete<dynamic>(path, data: data);
    return ApiResult.from(response);
  }

  Map<String, dynamic>? _clean(Map<String, dynamic>? query) {
    if (query == null) return null;
    final out = <String, dynamic>{};
    query.forEach((key, value) {
      if (value == null) return;
      if (value is String && value.isEmpty) return;
      out[key] = value;
    });
    return out;
  }
}

/// 从 RuoYi 响应里抽出表格行：优先 rows，再 data.items / data.list / data 数组。
List<Map<String, dynamic>> extractRows(ApiResult result, {List<String>? preferKeys}) {
  if (result.rows != null) {
    return result.rows!.whereType<Map<String, dynamic>>().toList();
  }
  final data = result.data;
  if (data is List) {
    return data.whereType<Map<String, dynamic>>().toList();
  }
  if (data is Map) {
    final keys = [
      ...?preferKeys,
      'items',
      'list',
      'records',
      'rows',
      'positions',
      'orders',
      'quotes',
      'jobs',
      'messages',
      'sessions',
      'points',
      'top50',
    ];
    for (final key in keys) {
      final value = data[key];
      if (value is List) {
        return value.whereType<Map<String, dynamic>>().toList();
      }
    }
  }
  return const [];
}

int extractTotal(ApiResult result, List<Map<String, dynamic>> rows) {
  if (result.total != null) return result.total!;
  final data = result.data;
  if (data is Map && data['total'] is num) {
    return (data['total'] as num).toInt();
  }
  return rows.length;
}

Map<String, dynamic> asMap(dynamic value) {
  if (value is Map<String, dynamic>) return value;
  if (value is Map) return Map<String, dynamic>.from(value);
  return <String, dynamic>{};
}

String cellText(dynamic value) {
  if (value == null) return '';
  if (value is bool) return value ? '是' : '否';
  if (value is num) {
    if (value is int || value == value.roundToDouble()) return value.toString();
    return value.toStringAsFixed(value.abs() >= 100 ? 2 : 4);
  }
  if (value is List) return value.map(cellText).join(', ');
  if (value is Map) {
    const prefer = [
      'name',
      'title',
      'label',
      'symbol',
      'userName',
      'nickName',
      'msg',
      'message',
    ];
    for (final key in prefer) {
      if (value[key] != null) return cellText(value[key]);
    }
    return '';
  }
  return value.toString();
}

final ruoyiClientProvider = Provider<RuoyiClient>(
  (ref) => RuoyiClient(ref.watch(dioProvider)),
);
