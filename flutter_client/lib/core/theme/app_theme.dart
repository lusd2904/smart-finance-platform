import 'package:flutter/material.dart';

/// ─────────────────────────────────────────────────────────────
/// SFF 客户端设计令牌 —— 「墨蓝金融终端」
///
/// 原则：
/// 1. 深色为一等公民（金融终端习惯），亮色为浅灰纸面；
/// 2. 涨红跌绿（A股习惯）全端唯一取用处在此；
/// 3. 层次靠「背景分层 + 细描边」表达，不用重阴影；
/// 4. 数字一律 tabular figures 对齐（见 AppNum）。
/// 后续里程碑页面只允许取用这里的令牌，禁止散落裸色值。
/// ─────────────────────────────────────────────────────────────

/// 品牌 / 语义色。亮度无关的基础值；随明暗的成套色走 [ColorScheme]。
abstract final class AppColors {
  /// 品牌主色锚点：对齐 Web 端 Element Plus 蓝，降低迁移认知成本。
  static const brand = Color(0xFF409EFF);

  /// 涨（A股红）
  static const up = Color(0xFFE5484D);

  /// 跌（A股绿）
  static const down = Color(0xFF30A46C);

  /// 平盘 / 无数据
  static const flat = Color(0xFF8A9099);

  /// 警示琥珀（数据延迟、风控提示）
  static const warn = Color(0xFFF5A524);
}

/// 几何与密度令牌。
abstract final class AppDimens {
  /// 页面水平留白
  static const pagePadding = 20.0;

  /// 卡片圆角
  static const radiusCard = 14.0;

  /// 输入框 / 按钮圆角
  static const radiusControl = 10.0;

  /// 内容区最大宽度（超宽屏居中）
  static const maxContentWidth = 1280.0;

  /// 桌面侧栏宽：折叠 / 展开
  static const sideRailWidth = 76.0;
  static const sideNavWidth = 216.0;

  /// 自适应断点：≥900 走桌面壳（侧栏 + 页签）；更窄走手机壳（抽屉菜单）。
  static const wideBreakpoint = 900.0;

  static bool isWide(BuildContext context) =>
      MediaQuery.sizeOf(context).width >= wideBreakpoint;
}

/// 数字排版工具：报价、金额等数值文本统一套用，保证纵向对齐。
abstract final class AppNum {
  static const fontFeatures = [FontFeature.tabularFigures()];

  /// 在任意 TextStyle 上叠加数字对齐特征。
  static TextStyle style(TextStyle base) =>
      base.copyWith(fontFeatures: fontFeatures);
}

/// 大数字报价样式（详情页头部价格等）。
extension AppNumTextTheme on TextTheme {
  /// 头部大价格：w700 + tabular。
  TextStyle get quoteDisplay => displaySmall!.copyWith(
    fontWeight: FontWeight.w700,
    fontFeatures: AppNum.fontFeatures,
  );
}

abstract final class AppTheme {
  static ThemeData light() => _build(Brightness.light);
  static ThemeData dark() => _build(Brightness.dark);

  static ThemeData _build(Brightness brightness) {
    final dark = brightness == Brightness.dark;
    final base = ColorScheme.fromSeed(
      seedColor: AppColors.brand,
      brightness: brightness,
    );

    // 背景分层：bg < surface < container。层次靠分层与细描边，不靠阴影。
    final scheme = base.copyWith(
      // 主色在暗色下提亮一档，保证对比度。
      primary: dark ? const Color(0xFF67AEFF) : AppColors.brand,
      // 涨跌语义注入 scheme，组件内可直接取 error/tertiary 之外的自定义角色。
      error: dark ? const Color(0xFFFF7076) : AppColors.up,
      surface: dark ? const Color(0xFF10141C) : const Color(0xFFF5F6FA),
      surfaceContainerLowest: dark ? const Color(0xFF0B0E15) : Colors.white,
      surfaceContainerLow: dark ? const Color(0xFF12161F) : Colors.white,
      surfaceContainer: dark ? const Color(0xFF161B25) : Colors.white,
      surfaceContainerHigh: dark
          ? const Color(0xFF1C2230)
          : const Color(0xFFFFFFFF),
      surfaceContainerHighest: dark
          ? const Color(0xFF232A3A)
          : const Color(0xFFF0F2F7),
      onSurface: dark ? const Color(0xFFE8ECF3) : const Color(0xFF18202E),
      onSurfaceVariant: dark
          ? const Color(0xFF9AA4B5)
          : const Color(0xFF5C6675),
      outline: dark ? const Color(0xFF39414F) : const Color(0xFFC9CFDA),
      outlineVariant: dark ? const Color(0x14FFFFFF) : const Color(0xFFE7EAF0),
    );

    final cardShape = RoundedRectangleBorder(
      borderRadius: BorderRadius.circular(AppDimens.radiusCard),
      side: BorderSide(color: scheme.outlineVariant),
    );

    return ThemeData(
      useMaterial3: true,
      colorScheme: scheme,
      scaffoldBackgroundColor: scheme.surface,
      splashFactory: InkSparkle.splashFactory,
      appBarTheme: AppBarTheme(
        backgroundColor: scheme.surface,
        foregroundColor: scheme.onSurface,
        elevation: 0,
        scrolledUnderElevation: 0,
        centerTitle: false,
        titleTextStyle: TextStyle(
          fontSize: 17,
          fontWeight: FontWeight.w700,
          color: scheme.onSurface,
        ),
      ),
      cardTheme: CardThemeData(
        color: scheme.surfaceContainerLow,
        elevation: 0,
        margin: EdgeInsets.zero,
        clipBehavior: Clip.antiAlias,
        shape: cardShape,
      ),
      dividerTheme: DividerThemeData(
        color: scheme.outlineVariant,
        thickness: 1,
        space: 1,
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: dark
            ? scheme.surfaceContainer
            : scheme.surfaceContainerLowest,
        isDense: true,
        contentPadding: const EdgeInsets.symmetric(
          horizontal: 14,
          vertical: 13,
        ),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(AppDimens.radiusControl),
          borderSide: BorderSide(color: scheme.outline),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(AppDimens.radiusControl),
          borderSide: BorderSide(color: scheme.outlineVariant),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(AppDimens.radiusControl),
          borderSide: BorderSide(color: scheme.primary, width: 1.6),
        ),
        errorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(AppDimens.radiusControl),
          borderSide: BorderSide(color: scheme.error),
        ),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          minimumSize: const Size(64, 44),
          padding: const EdgeInsets.symmetric(horizontal: 20),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(AppDimens.radiusControl),
          ),
          textStyle: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          minimumSize: const Size(64, 44),
          padding: const EdgeInsets.symmetric(horizontal: 18),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(AppDimens.radiusControl),
          ),
          side: BorderSide(color: scheme.outline),
          textStyle: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600),
        ),
      ),
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(
          textStyle: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600),
        ),
      ),
      navigationBarTheme: NavigationBarThemeData(
        height: 68,
        backgroundColor: scheme.surfaceContainerLow,
        indicatorColor: scheme.primary.withValues(alpha: 0.14),
        surfaceTintColor: Colors.transparent,
        labelTextStyle: WidgetStatePropertyAll(
          TextStyle(
            fontSize: 11.5,
            fontWeight: FontWeight.w600,
            color: scheme.onSurfaceVariant,
          ),
        ),
      ),
      navigationRailTheme: NavigationRailThemeData(
        backgroundColor: scheme.surfaceContainerLow,
        indicatorColor: scheme.primary.withValues(alpha: 0.14),
      ),
      chipTheme: ChipThemeData(
        side: BorderSide(color: scheme.outlineVariant),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
        labelStyle: TextStyle(fontSize: 12.5, color: scheme.onSurfaceVariant),
      ),
      segmentedButtonTheme: SegmentedButtonThemeData(
        style: ButtonStyle(
          shape: WidgetStatePropertyAll(
            RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(AppDimens.radiusControl),
            ),
          ),
          textStyle: const WidgetStatePropertyAll(
            TextStyle(fontWeight: FontWeight.w600),
          ),
        ),
      ),
      snackBarTheme: SnackBarThemeData(
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(AppDimens.radiusControl),
        ),
      ),
      dialogTheme: DialogThemeData(
        backgroundColor: scheme.surfaceContainerLow,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      ),
      progressIndicatorTheme: ProgressIndicatorThemeData(
        color: scheme.primary,
        linearTrackColor: scheme.surfaceContainerHighest,
      ),
      tooltipTheme: TooltipThemeData(
        decoration: BoxDecoration(
          color: dark ? const Color(0xFF2A3142) : const Color(0xFF23293A),
          borderRadius: BorderRadius.circular(8),
        ),
        textStyle: const TextStyle(fontSize: 12, color: Colors.white),
      ),
    );
  }
}
