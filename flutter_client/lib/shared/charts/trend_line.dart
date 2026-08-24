import 'dart:math' as math;


import 'package:flutter/material.dart';

import '../../core/theme/app_theme.dart';

/// 轻量走势折线：舆情历史、热度趋势等单序列场景。
/// 自绘而非引入图表库（规划文档决策：CustomPainter 自绘）。
class TrendLine extends StatelessWidget {
  const TrendLine({
    super.key,
    required this.values,
    this.height = 96,
    this.color,
    this.baselineAtZero = false,
    this.lineWidth = 2,
  });

  /// 序列值；空或单点时绘制占位基线。
  final List<double> values;

  final double height;
  final Color? color;
  final bool baselineAtZero;
  final double lineWidth;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return SizedBox(
      height: height,
      child: CustomPaint(
        size: Size.infinite,
        painter: _TrendPainter(
          values: values,
          color: color ?? AppColors.brand,
          gridColor: theme.colorScheme.outlineVariant,
          placeholderColor: theme.colorScheme.surfaceContainerHighest,
          baselineAtZero: baselineAtZero,
          lineWidth: lineWidth,
        ),
      ),
    );
  }
}

class _TrendPainter extends CustomPainter {
  const _TrendPainter({
    required this.values,
    required this.color,
    required this.gridColor,
    required this.placeholderColor,
    required this.baselineAtZero,
    required this.lineWidth,
  });

  final List<double> values;
  final Color color;
  final Color gridColor;
  final Color placeholderColor;
  final bool baselineAtZero;
  final double lineWidth;

  @override
  void paint(Canvas canvas, Size size) {
    if (values.length < 2) {
      // 占位：一条居中虚线（SDK 未导出 ui.PathEffect，手绘短段）。
      _drawDashedLine(
        canvas,
        Offset(0, size.height / 2),
        Offset(size.width, size.height / 2),
        Paint()
          ..strokeWidth = 1
          ..color = placeholderColor,
      );
      return;
    }
    var lo = values.reduce(math.min);
    var hi = values.reduce(math.max);
    if (baselineAtZero) {
      lo = math.min(lo, 0);
      hi = math.max(hi, 0);
    }
    if (hi - lo < 1e-9) {
      hi += 1;
      lo -= 1;
    }
    final pad = (hi - lo) * 0.12;
    lo -= pad;
    hi += pad;

    Offset at(int i, int n) {
      final x = n <= 1 ? 0.0 : size.width * i / (n - 1);
      final y = size.height * (1 - (values[i] - lo) / (hi - lo));
      return Offset(x, y.clamp(0.0, size.height));
    }

    final first = at(0, values.length);
    final path = Path()..moveTo(first.dx, first.dy);
    for (var i = 1; i < values.length; i++) {
      path.lineTo(at(i, values.length).dx, at(i, values.length).dy);
    }

    // 面积填充。
    final fillPath = Path.from(path)
      ..lineTo(size.width, size.height)
      ..lineTo(0, size.height)
      ..close();
    canvas.drawPath(
      fillPath,
      Paint()
        ..shader = LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [
            color.withValues(alpha: 0.18),
            color.withValues(alpha: 0.01),
          ],
        ).createShader(Offset.zero & size),
    );

    // 零轴（可选，涨跌序列用）。
    if (baselineAtZero && lo < 0 && hi > 0) {
      final zeroY = size.height * (1 - (0 - lo) / (hi - lo));
      canvas.drawLine(
        Offset(0, zeroY),
        Offset(size.width, zeroY),
        Paint()
          ..strokeWidth = 1
          ..color = gridColor,
      );
    }

    canvas.drawPath(
      path,
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = lineWidth
        ..strokeJoin = StrokeJoin.round
        ..strokeCap = StrokeCap.round
        ..color = color,
    );

    // 尾点高亮。
    final last = at(values.length - 1, values.length);
    canvas.drawCircle(last, lineWidth + 1, Paint()..color = color);
  }

  @override
  bool shouldRepaint(_TrendPainter old) =>
      old.values != values || old.color != color;
}

void _drawDashedLine(Canvas canvas, Offset a, Offset b, Paint paint) {
  const dashLen = 4.0;
  const gapLen = 4.0;
  final dx = b.dx - a.dx;
  final dy = b.dy - a.dy;
  final len = math.sqrt(dx * dx + dy * dy);
  if (len == 0) return;
  final ux = dx / len;
  final uy = dy / len;
  var dist = 0.0;
  while (dist < len) {
    final end = math.min(dist + dashLen, len);
    canvas.drawLine(
      Offset(a.dx + ux * dist, a.dy + uy * dist),
      Offset(a.dx + ux * end, a.dy + uy * end),
      paint,
    );
    dist = end + gapLen;
  }
}
