import 'package:flutter/material.dart';

/// 金融涨跌色（A股习惯：涨红跌绿），全端统一取用。
abstract final class AppColors {
  static const up = Color(0xFFE5484D);
  static const down = Color(0xFF30A46C);
  static const flat = Color(0xFF8D8D99);
}

/// 平台主色沿用 Web 端 Element Plus 蓝，降低迁移认知成本。
abstract final class AppTheme {
  static const seed = Color(0xFF409EFF);

  static ThemeData light() => _build(Brightness.light);
  static ThemeData dark() => _build(Brightness.dark);

  static ThemeData _build(Brightness brightness) {
    final scheme = ColorScheme.fromSeed(seedColor: seed, brightness: brightness);
    return ThemeData(
      useMaterial3: true,
      colorScheme: scheme,
      scaffoldBackgroundColor:
          brightness == Brightness.light ? const Color(0xFFF5F7FA) : null,
      inputDecorationTheme: const InputDecorationTheme(
        border: OutlineInputBorder(),
        isDense: true,
      ),
    );
  }
}
