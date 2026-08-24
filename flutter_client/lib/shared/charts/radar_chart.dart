import 'dart:math' as math;

import 'package:flutter/material.dart';

/// 多维雷达图：AI 研判五维（基本面/技术面/情绪面/估值面/资金面）
/// 与 M3 量化 8 族权重共用。
///
/// - [axes] 轴标签，决定维数 n（≥3）。
/// - [values] 各维分值 0~1；越界自动截断。长度不足按 0 补齐。
class RadarChart extends StatelessWidget {
  const RadarChart({
    super.key,
    required this.axes,
    required this.values,
    this.size = 200,
    this.color,
    this.fillAlpha = 0.22,
  });

  final List<String> axes;
  final List<double> values;
  final double size;
  final Color? color;
  final double fillAlpha;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return SizedBox(
      width: size,
      height: size,
      child: CustomPaint(
        painter: _RadarPainter(
          axes: axes,
          values: values,
          lineColor: theme.colorScheme.outlineVariant,
          labelColor: theme.colorScheme.onSurfaceVariant,
          dataColor: color ?? theme.colorScheme.primary,
          fillAlpha: fillAlpha,
          labelStyle: theme.textTheme.labelSmall,
        ),
      ),
    );
  }
}

class _RadarPainter extends CustomPainter {
  const _RadarPainter({
    required this.axes,
    required this.values,
    required this.lineColor,
    required this.labelColor,
    required this.dataColor,
    required this.fillAlpha,
    required this.labelStyle,
  });

  final List<String> axes;
  final List<double> values;
  final Color lineColor;
  final Color labelColor;
  final Color dataColor;
  final double fillAlpha;
  final TextStyle? labelStyle;

  static const _labelGap = 14.0;

  @override
  void paint(Canvas canvas, Size size) {
    final n = axes.length.clamp(3, 12);
    final center = Offset(size.width / 2, size.height / 2);
    // 半径留出标签空间。
    final radius = math.min(size.width, size.height) / 2 - _labelGap * 2;

    Offset point(int i, double r) {
      final angle = -math.pi / 2 + 2 * math.pi * i / n;
      return Offset(
        center.dx + math.cos(angle) * radius * r,
        center.dy + math.sin(angle) * radius * r,
      );
    }

    // 网格环：25% / 50% / 75% / 100%。
    final grid = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1
      ..color = lineColor;
    for (final ring in const [0.25, 0.5, 0.75, 1.0]) {
      final path = Path()..moveTo(point(0, ring).dx, point(0, ring).dy);
      for (var i = 1; i < n; i++) {
        path.lineTo(point(i, ring).dx, point(i, ring).dy);
      }
      path.close();
      canvas.drawPath(path, grid);
    }

    // 轴辐条 + 标签。
    for (var i = 0; i < n; i++) {
      final outer = point(i, 1.0);
      canvas.drawLine(center, outer, grid);
      final tp = TextPainter(
        text: TextSpan(text: axes[i], style: labelStyle?.copyWith(color: labelColor)),
        textDirection: TextDirection.ltr,
      )..layout();
      final dir = (outer - center) / radius;
      final anchor = center + dir * (radius + _labelGap);
      Offset offset = Offset(-tp.width / 2, -tp.height / 2);
      // 水平方向贴边对齐，避免标签被裁切。
      if (dir.dx > 0.4) offset += Offset(tp.width / 2, 0);
      if (dir.dx < -0.4) offset += Offset(-tp.width / 2, 0);
      tp.paint(canvas, anchor + offset);
    }

    // 数据多边形。
    final dataPath = Path();
    for (var i = 0; i < n; i++) {
      final v = i < values.length ? values[i].clamp(0.0, 1.0).toDouble() : 0.0;
      final p = point(i, v);
      if (i == 0) {
        dataPath.moveTo(p.dx, p.dy);
      } else {
        dataPath.lineTo(p.dx, p.dy);
      }
    }
    dataPath.close();

    canvas.drawPath(dataPath, Paint()..color = dataColor.withValues(alpha: fillAlpha));
    canvas.drawPath(
      dataPath,
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2
        ..strokeJoin = StrokeJoin.round
        ..color = dataColor,
    );
    for (var i = 0; i < n; i++) {
      final v = i < values.length ? values[i].clamp(0.0, 1.0).toDouble() : 0.0;
      canvas.drawCircle(point(i, v), 3, Paint()..color = dataColor);
    }
  }

  @override
  bool shouldRepaint(_RadarPainter old) =>
      old.values != values || old.axes != axes || old.dataColor != dataColor;
}
