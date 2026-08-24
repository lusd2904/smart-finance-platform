import 'package:flutter/material.dart';

import '../../../core/theme/app_theme.dart';
import '../../market/data/market_models.dart';

/// K线自绘：蜡烛主图（70%）+ 成交量副图（30%）。
/// 纯绘制无 IO；横向拖动平移查看更早数据，初始展示最后 [initialVisible] 根。
class InteractiveKlineChart extends StatefulWidget {
  const InteractiveKlineChart({super.key, required this.bars, this.initialVisible = 60});

  final List<KlineBar> bars;
  final int initialVisible;

  @override
  State<InteractiveKlineChart> createState() => _InteractiveKlineChartState();
}

class _InteractiveKlineChartState extends State<InteractiveKlineChart> {
  /// 可视窗口右端在 bars 中的索引（含），拖动左移查看更早。
  late int _endIndex;

  @override
  void initState() {
    super.initState();
    _endIndex = widget.bars.length - 1;
  }

  @override
  void didUpdateWidget(covariant InteractiveKlineChart oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (!identical(oldWidget.bars, widget.bars)) {
      _endIndex = widget.bars.length - 1;
    }
  }

  void _onDrag(DragUpdateDetails d) {
    final candleWidth = _candleWidth;
    final shift = (d.delta.dx / candleWidth).round();
    if (shift == 0) return;
    setState(() {
      _endIndex = (_endIndex - shift).clamp(widget.initialVisible - 1, widget.bars.length - 1);
    });
  }

  double get _candleWidth => 8;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onHorizontalDragUpdate: _onDrag,
      child: CustomPaint(
        painter: KlinePainter(
          bars: widget.bars,
          endIndex: _endIndex,
          visibleCount: widget.initialVisible,
          maColor: const Color(0xFF409EFF),
        ),
        child: const SizedBox.expand(),
      ),
    );
  }
}

/// 蜡烛 + 成交量绘制器。涨红空心、跌绿实心（A股习惯），MA5 折线叠加主图。
class KlinePainter extends CustomPainter {
  KlinePainter({
    required this.bars,
    required this.endIndex,
    required this.visibleCount,
    required this.maColor,
  });

  final List<KlineBar> bars;
  final int endIndex;
  final int visibleCount;
  final Color maColor;

  static const _gridLines = 3;
  static const _volumeRatio = 0.3; // 副图高度占比
  static const _gapRatio = 0.02; // 主副图间隔

  @override
  void paint(Canvas canvas, Size size) {
    if (bars.isEmpty || size.width <= 0 || size.height <= 0) return;

    final count = visibleCount.clamp(1, bars.length);
    final start = (endIndex - count + 1).clamp(0, bars.length - 1);
    final end = start + count <= bars.length ? start + count : bars.length;
    final visible = bars.sublist(start, end);
    if (visible.isEmpty) return;

    final chartHeight = size.height * (1 - _gapRatio);
    final mainH = chartHeight * (1 - _volumeRatio);
    final volTop = chartHeight * (1 - _volumeRatio) + size.height * _gapRatio;
    final volH = size.height - volTop;

    final slot = size.width / visible.length;
    final bodyW = (slot * 0.7).clamp(1.5, 14.0);

    // y 轴范围：可见区间高低价，上下各留 5%
    var lo = visible.first.low, hi = visible.first.high;
    var maxVol = visible.first.volume;
    for (final b in visible) {
      if (b.low < lo) lo = b.low;
      if (b.high > hi) hi = b.high;
      if (b.volume > maxVol) maxVol = b.volume;
    }
    if (hi <= lo) hi = lo + 1;
    final pad = (hi - lo) * 0.05;
    lo -= pad;
    hi += pad;
    if (maxVol <= 0) maxVol = 1;

    double priceY(double p) => mainH - (p - lo) / (hi - lo) * mainH;
    double volY(double v) => volTop + volH - v / maxVol * volH;
    double x(int i) => i * slot + slot / 2;

    // 网格与右缘价格刻度
    final gridPaint = Paint()
      ..color = const Color(0x22808080)
      ..strokeWidth = 0.5;
    final tp = TextPainter(textDirection: TextDirection.ltr);
    for (var g = 0; g <= _gridLines; g++) {
      final t = g / _gridLines;
      final y = mainH * t;
      canvas.drawLine(Offset(0, y), Offset(size.width, y), gridPaint);
      final price = hi - (hi - lo) * t;
      tp.text = TextSpan(
        text: price.toStringAsFixed(2),
        style: TextStyle(fontSize: 9, color: const Color(0xFF8D8D99)),
      );
      tp.layout();
      tp.paint(canvas, Offset(size.width - tp.width - 2, y - tp.height - 1));
    }

    // 蜡烛
    final upFill = Paint()..color = AppColors.flat; // 占位，逐根重建
    for (var i = 0; i < visible.length; i++) {
      final b = visible[i];
      final cx = x(i);
      final color = b.isUp ? AppColors.up : AppColors.down;
      final wick = Paint()
        ..color = color
        ..strokeWidth = 1;
      canvas.drawLine(Offset(cx, priceY(b.high)), Offset(cx, priceY(b.low)), wick);
      final top = priceY(b.close > b.open ? b.close : b.open);
      final bottom = priceY(b.close > b.open ? b.open : b.close);
      final rect = Rect.fromLTWH(cx - bodyW / 2, top, bodyW, (bottom - top).clamp(1.0, double.infinity));
      if (b.isUp) {
        // 涨：空心（白底描边）
        canvas.drawRect(rect, upFill..color = const Color(0xFFFFFFFF));
        canvas.drawRect(rect, Paint()..color = color..style = PaintingStyle.stroke..strokeWidth = 1);
      } else {
        canvas.drawRect(rect, Paint()..color = color);
      }
      // 成交量柱
      canvas.drawRect(
        Rect.fromLTWH(cx - bodyW / 2, volY(b.volume), bodyW, volTop + volH - volY(b.volume)),
        Paint()..color = color.withValues(alpha: 0.6),
      );
    }

    // MA5 折线（窗口整体前移需全量均值，简化为可见段内从第 5 根起）
    final maPath = Path();
    var started = false;
    for (var i = 0; i < visible.length; i++) {
      final globalIdx = start + i;
      if (globalIdx < 4) continue;
      var sum = 0.0;
      for (var k = globalIdx - 4; k <= globalIdx; k++) {
        sum += bars[k].close;
      }
      final px = x(i);
      final py = priceY(sum / 5);
      started ? maPath.lineTo(px, py) : maPath.moveTo(px, py);
      started = true;
    }
    canvas.drawPath(
      maPath,
      Paint()
        ..color = maColor
        ..strokeWidth = 1
        ..style = PaintingStyle.stroke,
    );

    // 首尾日期标签（MM-dd）
    String shortDate(String raw) {
      final parts = raw.split(RegExp(r'[-/ ]'));
      return parts.length >= 3 ? '${parts[parts.length - 2]}-${parts.last}' : raw;
    }

    tp.text = TextSpan(
      text: shortDate(visible.first.date),
      style: const TextStyle(fontSize: 9, color: Color(0xFF8D8D99)),
    );
    tp.layout();
    tp.paint(canvas, Offset(2, size.height - tp.height));

    tp.text = TextSpan(
      text: shortDate(visible.last.date),
      style: const TextStyle(fontSize: 9, color: Color(0xFF8D8D99)),
    );
    tp.layout();
    tp.paint(canvas, Offset(size.width - tp.width - 2, size.height - tp.height));
  }

  @override
  bool shouldRepaint(KlinePainter oldDelegate) =>
      identical(oldDelegate.bars, bars) == false ||
      oldDelegate.endIndex != endIndex ||
      oldDelegate.visibleCount != visibleCount;
}
