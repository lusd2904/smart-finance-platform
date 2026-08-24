import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../../core/theme/app_theme.dart';

/// 情绪分档（0~100）。语义对齐设计稿 §3.4：
/// 极度悲观 / 悲观 / 中性 / 乐观 / 极度贪婪。
enum SentimentZone {
  extremeFear('极度悲观'),
  fear('悲观'),
  neutral('中性'),
  greed('乐观'),
  extremeGreed('极度贪婪');

  const SentimentZone(this.label);
  final String label;

  static SentimentZone of(double score) {
    if (score < 20) return extremeFear;
    if (score < 40) return fear;
    if (score < 60) return neutral;
    if (score < 80) return greed;
    return extremeGreed;
  }
}

/// 半环温度计仪表盘：舆情大盘与 iOS 小组件风格的极简情绪表盘。
///
/// - [score] 0~100，越接近 100 越贪婪（A 股习惯：乐观段用涨红）。
/// - 弧形分段着色：悲观段跌绿 → 中性平灰 → 乐观段涨红；当前值以指针刻度指示。
class SentimentGauge extends StatelessWidget {
  const SentimentGauge({
    super.key,
    required this.score,
    this.size = 180,
    this.strokeWidth = 14,
    this.showLabel = true,
  });

  final double score;
  final double size;
  final double strokeWidth;
  final bool showLabel;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final clamped = score.clamp(0, 100).toDouble();
    final zone = SentimentZone.of(clamped);
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        SizedBox(
          width: size,
          height: size / 2,
          child: CustomPaint(
            size: Size(size, size / 2),
            painter: _GaugePainter(
              score: clamped,
              strokeWidth: strokeWidth,
              trackColor: theme.colorScheme.surfaceContainerHighest,
            ),
          ),
        ),
          if (showLabel) ...[
            const SizedBox(height: 4),
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              crossAxisAlignment: CrossAxisAlignment.baseline,
              textBaseline: TextBaseline.alphabetic,
              children: [
                Text(
                  clamped.toStringAsFixed(0),
                  style: theme.textTheme.headlineMedium?.copyWith(
                    fontWeight: FontWeight.w700,
                    fontFeatures: const [FontFeature.tabularFigures()],
                    color: _zoneColor(zone),
                  ),
                ),
                const SizedBox(width: 4),
                Text(
                  '分 · ${zone.label}',
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: theme.colorScheme.onSurfaceVariant,
                  ),
                ),
              ],
            ),
          ],
        ],
    );
  }
}

Color _zoneColor(SentimentZone zone) {
  switch (zone) {
    case SentimentZone.extremeFear:
    case SentimentZone.fear:
      return AppColors.down;
    case SentimentZone.neutral:
      return AppColors.flat;
    case SentimentZone.extremeGreed:
    case SentimentZone.greed:
      return AppColors.up;
  }
}

class _GaugePainter extends CustomPainter {
  const _GaugePainter({
    required this.score,
    required this.strokeWidth,
    required this.trackColor,
  });

  final double score;
  final double strokeWidth;
  final Color trackColor;

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height);
    final radius = math.min(size.width / 2, size.height) - strokeWidth;
    final rect = Rect.fromCircle(center: center, radius: radius);

    // 底轨：半圆。
    final track = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = strokeWidth
      ..strokeCap = StrokeCap.round
      ..color = trackColor;
    canvas.drawArc(rect, math.pi, math.pi, false, track);

    // 分段色弧：0~50 绿→灰（悲观），50~100 灰→红（贪婪）。
    void seg(double from, double to, Color c) {
      final p = Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = strokeWidth
        ..strokeCap = StrokeCap.butt
        ..color = c;
      // 角度：0 分在 π（左端），100 分在 2π（右端）。
      canvas.drawArc(rect, math.pi * (1 + from), math.pi * (to - from), false, p);
    }

    seg(0.00, 0.20, AppColors.down.withValues(alpha: 0.9));
    seg(0.20, 0.40, AppColors.down.withValues(alpha: 0.45));
    seg(0.40, 0.60, AppColors.flat);
    seg(0.60, 0.80, AppColors.up.withValues(alpha: 0.45));
    seg(0.80, 1.00, AppColors.up.withValues(alpha: 0.9));

    // 指针刻度线。
    final angle = math.pi * (1 + score / 100);
    final inner = Offset(
      center.dx + math.cos(angle) * (radius - strokeWidth),
      center.dy + math.sin(angle) * (radius - strokeWidth),
    );
    final outer = Offset(
      center.dx + math.cos(angle) * (radius + strokeWidth * 0.7),
      center.dy + math.sin(angle) * (radius + strokeWidth * 0.7),
    );
    final needle = Paint()
      ..strokeWidth = 3
      ..strokeCap = StrokeCap.round
      ..color = AppColors.brand;
    canvas.drawLine(inner, outer, needle);
  }

  @override
  bool shouldRepaint(_GaugePainter old) =>
      old.score != score || old.trackColor != trackColor;
}
