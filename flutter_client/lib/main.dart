import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:flutter_client/app.dart';
import 'package:flutter_client/core/gateway/gateway_store.dart';
import 'package:flutter_client/features/auth/logic/session_controller.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final prefs = await SharedPreferences.getInstance();
  final container = ProviderContainer(
    overrides: [sharedPreferencesProvider.overrideWithValue(prefs)],
  );
  // 首帧前完成会话引导，路由守卫不依赖 unknown 态。
  await container.read(sessionController.notifier).bootstrap();
  runApp(
    UncontrolledProviderScope(container: container, child: const SffApp()),
  );
}
