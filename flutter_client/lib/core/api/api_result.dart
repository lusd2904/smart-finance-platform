import 'package:dio/dio.dart';

/// 后端统一响应包 {code,msg,data} / 分页包 {code,msg,rows,total}。
/// code != 200 视为业务失败并抛 ApiException。
class ApiException implements Exception {
  ApiException(this.message);
  final String message;

  @override
  String toString() => message;
}

class ApiResult {
  ApiResult._({
    required this.code,
    required this.msg,
    this.data,
    this.rows,
    this.total,
  });

  factory ApiResult.from(Response<dynamic> response) {
    final body = response.data;
    if (body is! Map<String, dynamic>) {
      throw ApiException('接口返回格式异常（${response.statusCode}）');
    }
    final result = ApiResult._(
      code: (body['code'] as num?)?.toInt() ?? 200,
      msg: (body['msg'] as String?) ?? '',
      data: body['data'],
      rows: body['rows'] as List<dynamic>?,
      total: (body['total'] as num?)?.toInt(),
    );
    if (result.code != 200) {
      throw ApiException(
        result.msg.isEmpty ? '操作失败（code=${result.code}）' : result.msg,
      );
    }
    return result;
  }

  final int code;
  final String msg;
  final dynamic data;
  final List<dynamic>? rows;
  final int? total;

  Map<String, dynamic>? get dataAsMap =>
      data is Map<String, dynamic> ? data as Map<String, dynamic> : null;
}
