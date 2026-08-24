import 'package:flutter/material.dart';

import '../../core/theme/app_theme.dart';
import '../utils/format.dart';

/// 涨跌幅文本：正红负绿平灰（A股习惯），带符号两位小数 + %。
class PctText extends StatelessWidget {
  const PctText(this.value, {super.key, this.style, this.bold = false});

  final double? value;
  final TextStyle? style;
  final bool bold;

  @override
  Widget build(BuildContext context) {
    final v = value;
    final color = switch (v) {
      null => AppColors.flat,
      > 0 => AppColors.up,
      < 0 => AppColors.down,
      _ => AppColors.flat,
    };
    return Text(
      formatPct(v),
      style: (style ?? const TextStyle()).copyWith(
        color: color,
        fontWeight: bold ? FontWeight.w600 : null,
        fontFeatures: const [FontFeature.tabularFigures()],
      ),
    );
  }
}

/// 价格文本：tabular 数字对齐。
class PriceText extends StatelessWidget {
  const PriceText(this.value, {super.key, this.style});

  final double? value;
  final TextStyle? style;

  @override
  Widget build(BuildContext context) {
    return Text(
      formatPrice(value),
      style: (style ?? const TextStyle()).copyWith(
        fontFeatures: const [FontFeature.tabularFigures()],
      ),
    );
  }
}
