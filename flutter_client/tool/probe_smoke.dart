import 'dart:io';

import 'package:flutter_client/core/gateway/gateway_probe.dart';

/// 真实环境探测冒烟：dart run tool/probe_smoke.dart <前端网关> <后端地址>
/// 期望：网关 ok=true；后端 ok=false 且 code=api_only。
Future<void> main(List<String> args) async {
  final gateway = args.isNotEmpty ? args[0] : 'http://127.0.0.1:12580';
  final backend = args.length > 1 ? args[1] : 'http://127.0.0.1:19099';

  final gwResult = await probeGateway(gateway);
  stdout.writeln('[$gateway] ok=${gwResult.ok} code=${gwResult.code} msg=${gwResult.message}');
  if (!gwResult.ok) exit(1);

  final beResult = await probeGateway(backend);
  stdout.writeln('[$backend] ok=${beResult.ok} code=${beResult.code} msg=${beResult.message}');
  if (beResult.ok || beResult.code != 'api_only') exit(2);
  stdout.writeln('probe smoke ok');
}
