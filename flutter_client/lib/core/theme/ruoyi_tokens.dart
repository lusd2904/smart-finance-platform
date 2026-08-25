import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../gateway/gateway_store.dart';

/// 对齐 `设计稿.md`「墨蓝金融终端」令牌：深色一等公民、细描边、无厚投影。
abstract final class WebTokens {
  static const sidebarBg = Color(0xFF12161F);
  static const sidebarSub = Color(0xFF0B0E15);
  static const sidebarHover = Color(0xFF1C2230);
  static const sidebarText = Color(0xFF9AA4B5);
  static const sidebarActive = Color(0xFF409EFF);
  static const primary = Color(0xFF409EFF);
  static const navbarBg = Color(0xFF12161F);
  static const contentBg = Color(0xFF10141C);
  static const contentBgLight = Color(0xFFF5F6FA);
  static const tagBg = Color(0xFF12161F);
  static const sidebarWidth = 216.0;
  static const sidebarCollapsed = 76.0;
  static const navbarHeight = 50.0;
  static const tagsHeight = 34.0;
  static const loginDark = Color(0xFF10141C);
}

class ThemeModeController extends Notifier<ThemeMode> {
  static const _key = 'theme.mode';

  @override
  ThemeMode build() {
    try {
      final raw = ref.watch(sharedPreferencesProvider).getString(_key);
      if (raw == 'light') return ThemeMode.light;
    } catch (_) {}
    return ThemeMode.dark;
  }

  Future<void> setDark(bool dark) async {
    final next = dark ? ThemeMode.dark : ThemeMode.light;
    await ref.read(sharedPreferencesProvider).setString(_key, dark ? 'dark' : 'light');
    state = next;
  }

  Future<void> toggle() => setDark(state != ThemeMode.dark);
}

final themeModeController = NotifierProvider<ThemeModeController, ThemeMode>(
  ThemeModeController.new,
);
