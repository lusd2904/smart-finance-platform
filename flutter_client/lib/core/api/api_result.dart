import 'dart:convert';

import 'package:dio/dio.dart';

/// 后端统一响应包 {code,msg,data} / 分页包 {code,msg,rows,total}。
/// code != 200 视为业务失败并抛 ApiException。
class ApiException implements Exception {
  ApiException(this.message, {this.code});
  final String message;
  final int? code;

  @override
  String toString() => message;
}

Map<String, dynamic>? asJsonMap(dynamic raw) {
  if (raw is Map<String, dynamic>) return raw;
  if (raw is Map) return Map<String, dynamic>.from(raw);
  if (raw is String) {
    final text = raw.trim();
    if (text.startsWith('{')) {
      try {
        return asJsonMap(jsonDecode(text));
      } catch (_) {}
    }
  }
  return null;
}

List<dynamic> asJsonList(dynamic raw) {
  if (raw is List) return raw;
  if (raw is String) {
    final text = raw.trim();
    if (text.startsWith('[')) {
      try {
        final parsed = jsonDecode(text);
        if (parsed is List) return parsed;
      } catch (_) {}
    }
  }
  return const [];
}

String asString(dynamic raw, [String fallback = '']) {
  if (raw == null) return fallback;
  final text = raw.toString().trim();
  if (text.isEmpty || text == 'null') return fallback;
  return text;
}

int? asInt(dynamic raw) {
  if (raw == null) return null;
  if (raw is int) return raw;
  if (raw is num) return raw.toInt();
  return int.tryParse(raw.toString().trim());
}

double? asDouble(dynamic raw) {
  if (raw == null) return null;
  if (raw is double) return raw;
  if (raw is num) return raw.toDouble();
  return double.tryParse(raw.toString().trim());
}

bool isBusinessUnauthorized(dynamic body) {
  final map = asJsonMap(body);
  if (map == null) return false;
  final code = map['code'];
  return code == 401 || code == '401';
}

String describeHttpFailure(int? status, String? body) {
  if (status == 502 || status == 503 || status == 504) {
    return '网关暂时不可用（$status），请稍后重试';
  }
  final text = (body ?? '').trim();
  if (text.isNotEmpty && text.length < 120 && !text.startsWith('<')) {
    return text;
  }
  if (status != null) return '请求失败（HTTP $status）';
  return '网络异常';
}

class ApiResult {
  ApiResult._({
    required this.code,
    required this.msg,
    this.data,
    this.rows,
    this.total,
  });

  factory ApiResult.ok({
    dynamic data,
    List<dynamic>? rows,
    int? total,
    String msg = '',
  }) =>
      ApiResult._(code: 200, msg: msg, data: data, rows: rows, total: total);

  factory ApiResult.from(Response<dynamic> response) {
    var body = response.data;
    if (body is String) {
      final text = body.trim();
      if (text.startsWith('{') || text.startsWith('[')) {
        try {
          body = jsonDecode(text);
        } catch (_) {
          throw ApiException(describeHttpFailure(response.statusCode, text));
        }
      } else {
        throw ApiException(describeHttpFailure(response.statusCode, text));
      }
    }
    if (body is List) {
      return ApiResult._(code: 200, msg: '', data: body, rows: body, total: body.length);
    }
    final map = asJsonMap(body);
    if (map == null) {
      throw ApiException(describeHttpFailure(response.statusCode, body?.toString()));
    }
    final code = (map['code'] is num) ? (map['code'] as num).toInt() : 200;
    final msg = map['msg']?.toString() ?? '';
    final result = ApiResult._(
      code: code,
      msg: msg,
      data: map['data'],
      rows: map['rows'] is List ? map['rows'] as List<dynamic> : null,
      total: (map['total'] as num?)?.toInt(),
    );
    if (result.code != 200) {
      throw ApiException(
        result.msg.isEmpty ? '操作失败（code=${result.code}）' : result.msg,
        code: result.code,
      );
    }
    return result;
  }

  final int code;
  final String msg;
  final dynamic data;
  final List<dynamic>? rows;
  final int? total;

  Map<String, dynamic>? get dataAsMap => asJsonMap(data);
}
