import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../../core/theme/app_theme.dart';
import '../../../shared/utils/format.dart';
import '../../market/data/market_models.dart';

/// K 线自绘：蜡烛或分时面积 + 成交量。横拖平移、双指缩放、长按十字光标。
class InteractiveKlineChart extends StatefulWidget {
  const InteractiveKlineChart({
    super.key,
    required this.bars,
    this.initialVisible = 60,
    this.area = false,
  });

  final List<KlineBar> bars;
  final int initialVisible;

  /// 分时：收盘连线 + 面积，不用蜡烛。
  final bool area;

  @override
  State<InteractiveKlineChart> createState() => _InteractiveKlineChartState();
}

class _InteractiveKlineChartState extends State<InteractiveKlineChart> {
  late int _endIndex;
  late int _visibleCount;
  int? _crossIndex;
  bool _crosshair = false;
  int _scaleBaseVisible = 60;
  Offset? _lastFocal;

  @override
  void initState() {
    super.initState();
    _visibleCount = _clampVisible(widget.initialVisible);
    _endIndex = widget.bars.isEmpty ? 0 : widget.bars.length - 1;
  }

  @override
  void didUpdateWidget(covariant InteractiveKlineChart oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (!identical(oldWidget.bars, widget.bars) ||
        oldWidget.area != widget.area ||
        oldWidget.initialVisible != widget.initialVisible) {
      _visibleCount = _clampVisible(widget.initialVisible);
      _endIndex = widget.bars.isEmpty ? 0 : widget.bars.length - 1;
      _crosshair = false;
      _crossIndex = null;
    }
  }

  int _clampVisible(int want) {
    final n = widget.bars.length;
    if (n <= 0) {
      return 1;
    }
    final maxV = n;
    final minV = n < 15 ? n : 15;
    return want.clamp(minV, maxV);
  }

  void _setCrossAt(Offset local, Size size) {
    if (widget.bars.isEmpty || size.width <= 0) {
      return;
    }
    final layout = _KlineLayout.compute(
      bars: widget.bars,
      endIndex: _endIndex,
      visibleCount: _visibleCount,
      size: size,
    );
    if (layout == null) {
      return;
    }
    final idx = layout.indexForDx(local.dx);
    setState(() {
      _crosshair = true;
      _crossIndex = idx;
    });
  }

  void _onScaleStart(ScaleStartDetails d) {
    _scaleBaseVisible = _visibleCount;
    _lastFocal = d.localFocalPoint;
  }

  void _onScaleUpdate(ScaleUpdateDetails d, Size size) {
    if (_crosshair) {
      _setCrossAt(d.localFocalPoint, size);
      return;
    }
    if (d.pointerCount >= 2) {
      final next = _clampVisible(
        (_scaleBaseVisible / d.scale.clamp(0.25, 4.0)).round(),
      );
      setState(() {
        _visibleCount = next;
        _endIndex = _endIndex.clamp(next - 1, widget.bars.length - 1);
      });
      return;
    }
    final prev = _lastFocal;
    _lastFocal = d.localFocalPoint;
    if (prev == null) {
      return;
    }
    final layout = _KlineLayout.compute(
      bars: widget.bars,
      endIndex: _endIndex,
      visibleCount: _visibleCount,
      size: size,
    );
    if (layout == null) {
      return;
    }
    final dx = d.localFocalPoint.dx - prev.dx;
    final shift = (dx / layout.slot).round();
    if (shift == 0) {
      return;
    }
    setState(() {
      _endIndex = (_endIndex - shift).clamp(
        _visibleCount - 1,
        widget.bars.length - 1,
      );
    });
  }

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final bars = widget.bars;
    if (bars.isEmpty) {
      return const SizedBox.expand();
    }
    final cross = _crosshair ? _crossIndex : null;
    KlineBar? hudBar;
    KlineBar? hudPrev;
    if (cross != null && cross >= 0 && cross < bars.length) {
      hudBar = bars[cross];
      if (cross > 0) {
        hudPrev = bars[cross - 1];
      }
    }
    return LayoutBuilder(
      builder: (context, constraints) {
        final size = Size(constraints.maxWidth, constraints.maxHeight);
        return GestureDetector(
          behavior: HitTestBehavior.opaque,
          onScaleStart: _onScaleStart,
          onScaleUpdate: (d) => _onScaleUpdate(d, size),
          onLongPressStart: (d) {
            HapticFeedback.selectionClick();
            _setCrossAt(d.localPosition, size);
          },
          onLongPressMoveUpdate: (d) => _setCrossAt(d.localPosition, size),
          onTap: () {
            if (_crosshair) {
              setState(() {
                _crosshair = false;
                _crossIndex = null;
              });
            }
          },
          child: Stack(
            children: [
              CustomPaint(
                painter: KlinePainter(
                  bars: bars,
                  endIndex: _endIndex,
                  visibleCount: _visibleCount,
                  maColor: const Color(0xFF409EFF),
                  area: widget.area,
                  crossIndex: cross,
                  surface: scheme.surface,
                  onSurface: scheme.onSurface,
                ),
                child: const SizedBox.expand(),
              ),
              if (hudBar != null)
                Positioned(
                  top: 4,
                  left: 8,
                  right: 8,
                  child: _CrosshairHud(
                    bar: hudBar,
                    prev: hudPrev,
                    area: widget.area,
                    baseline: bars.first.open,
                  ),
                ),
            ],
          ),
        );
      },
    );
  }
}

class _CrosshairHud extends StatelessWidget {
  const _CrosshairHud({
    required this.bar,
    required this.area,
    required this.baseline,
    this.prev,
  });

  final KlineBar bar;
  final KlineBar? prev;
  final bool area;
  final double baseline;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final base = area ? baseline : (prev?.close ?? bar.open);
    final chg = base == 0 ? null : (bar.close - base);
    final chgPct = base == 0 ? null : (bar.close - base) / base * 100;
    final color = switch (chg) {
      null => AppColors.flat,
      > 0 => AppColors.up,
      < 0 => AppColors.down,
      _ => AppColors.flat,
    };
    final time = _shortLabel(bar.date, intraday: area);
    final text = area
        ? '$time  ${formatPrice(bar.close)}  ${formatSigned(chg)}  ${formatPct(chgPct)}  量 ${formatAmountCn(bar.volume)}'
        : '$time  开${formatPrice(bar.open)} 高${formatPrice(bar.high)} 低${formatPrice(bar.low)} 收${formatPrice(bar.close)}  ${formatPct(chgPct)}  量 ${formatAmountCn(bar.volume)}';
    return Material(
      color: scheme.surface.withValues(alpha: 0.88),
      child: Text(
        text,
        maxLines: 1,
        overflow: TextOverflow.ellipsis,
        style: TextStyle(
          fontSize: 11,
          height: 1.2,
          color: color,
          fontFeatures: AppNum.fontFeatures,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }
}

String _shortLabel(String raw, {required bool intraday}) {
  if (intraday) {
    final m = RegExp(r'(\d{1,2}:\d{2})').firstMatch(raw);
    return m?.group(1) ?? raw;
  }
  final datePart = raw.split(RegExp(r'[ T]')).first;
  final parts = datePart.split(RegExp(r'[-/]'));
  if (parts.length >= 3) {
    return '${parts[parts.length - 2]}-${parts.last}';
  }
  return raw;
}

class _KlineLayout {
  _KlineLayout({
    required this.start,
    required this.visible,
    required this.slot,
    required this.mainH,
    required this.volTop,
    required this.volH,
    required this.lo,
    required this.hi,
    required this.maxVol,
    required this.bodyW,
  });

  final int start;
  final List<KlineBar> visible;
  final double slot;
  final double mainH;
  final double volTop;
  final double volH;
  final double lo;
  final double hi;
  final double maxVol;
  final double bodyW;

  static const volumeRatio = 0.3;
  static const gapRatio = 0.02;

  static _KlineLayout? compute({
    required List<KlineBar> bars,
    required int endIndex,
    required int visibleCount,
    required Size size,
  }) {
    if (bars.isEmpty || size.width <= 0 || size.height <= 0) {
      return null;
    }
    final count = visibleCount.clamp(1, bars.length);
    final start = (endIndex - count + 1).clamp(0, bars.length - 1);
    final end = start + count <= bars.length ? start + count : bars.length;
    final visible = bars.sublist(start, end);
    if (visible.isEmpty) {
      return null;
    }
    final chartHeight = size.height * (1 - gapRatio);
    final mainH = chartHeight * (1 - volumeRatio);
    final volTop = chartHeight * (1 - volumeRatio) + size.height * gapRatio;
    final volH = size.height - volTop;
    var lo = visible.first.low;
    var hi = visible.first.high;
    var maxVol = visible.first.volume;
    for (final b in visible) {
      if (b.low < lo) {
        lo = b.low;
      }
      if (b.high > hi) {
        hi = b.high;
      }
      if (b.volume > maxVol) {
        maxVol = b.volume;
      }
    }
    if (hi <= lo) {
      hi = lo + 1;
    }
    final pad = (hi - lo) * 0.05;
    lo -= pad;
    hi += pad;
    if (maxVol <= 0) {
      maxVol = 1;
    }
    final slot = size.width / visible.length;
    return _KlineLayout(
      start: start,
      visible: visible,
      slot: slot,
      mainH: mainH,
      volTop: volTop,
      volH: volH,
      lo: lo,
      hi: hi,
      maxVol: maxVol,
      bodyW: (slot * 0.7).clamp(1.5, 14.0),
    );
  }

  double priceY(double p) => mainH - (p - lo) / (hi - lo) * mainH;

  double volY(double v) => volTop + volH - v / maxVol * volH;

  double x(int i) => i * slot + slot / 2;

  int indexForDx(double dx) {
    final i = (dx / slot).floor().clamp(0, visible.length - 1);
    return start + i;
  }
}

/// 蜡烛 + 成交量绘制器。涨红空心、跌绿实心（A股习惯），MA5 折线叠加主图。
class KlinePainter extends CustomPainter {
  KlinePainter({
    required this.bars,
    required this.endIndex,
    required this.visibleCount,
    required this.maColor,
    this.area = false,
    this.crossIndex,
    this.surface = const Color(0xFFFFFFFF),
    this.onSurface = const Color(0xFF1C1C1E),
  });

  final List<KlineBar> bars;
  final int endIndex;
  final int visibleCount;
  final Color maColor;
  final bool area;
  final int? crossIndex;
  final Color surface;
  final Color onSurface;

  static const _gridLines = 3;

  @override
  void paint(Canvas canvas, Size size) {
    final layout = _KlineLayout.compute(
      bars: bars,
      endIndex: endIndex,
      visibleCount: visibleCount,
      size: size,
    );
    if (layout == null) {
      return;
    }
    final visible = layout.visible;
    final start = layout.start;

    final gridPaint = Paint()
      ..color = const Color(0x22808080)
      ..strokeWidth = 0.5;
    final tp = TextPainter(textDirection: TextDirection.ltr);
    for (var g = 0; g <= _gridLines; g++) {
      final t = g / _gridLines;
      final y = layout.mainH * t;
      canvas.drawLine(Offset(0, y), Offset(size.width, y), gridPaint);
      final price = layout.hi - (layout.hi - layout.lo) * t;
      tp.text = TextSpan(
        text: price.toStringAsFixed(2),
        style: const TextStyle(fontSize: 9, color: Color(0xFF8D8D99)),
      );
      tp.layout();
      tp.paint(canvas, Offset(size.width - tp.width - 2, y - tp.height - 1));
    }

    if (area) {
      _paintArea(canvas, layout);
    } else {
      _paintCandles(canvas, layout);
      _paintMa5(canvas, layout, start);
    }

    if (crossIndex != null) {
      final local = crossIndex! - start;
      if (local >= 0 && local < visible.length) {
        final b = visible[local];
        final cx = layout.x(local);
        final cy = layout.priceY(b.close);
        final hair = Paint()
          ..color = onSurface.withValues(alpha: 0.45)
          ..strokeWidth = 0.8;
        canvas.drawLine(Offset(cx, 0), Offset(cx, size.height), hair);
        canvas.drawLine(Offset(0, cy), Offset(size.width, cy), hair);
      }
    }

    tp.text = TextSpan(
      text: _shortLabel(visible.first.date, intraday: area),
      style: const TextStyle(fontSize: 9, color: Color(0xFF8D8D99)),
    );
    tp.layout();
    tp.paint(canvas, Offset(2, size.height - tp.height));

    tp.text = TextSpan(
      text: _shortLabel(visible.last.date, intraday: area),
      style: const TextStyle(fontSize: 9, color: Color(0xFF8D8D99)),
    );
    tp.layout();
    tp.paint(
      canvas,
      Offset(size.width - tp.width - 2, size.height - tp.height),
    );
  }

  void _paintCandles(Canvas canvas, _KlineLayout layout) {
    final visible = layout.visible;
    for (var i = 0; i < visible.length; i++) {
      final b = visible[i];
      final cx = layout.x(i);
      final color = b.isUp ? AppColors.up : AppColors.down;
      final wick = Paint()
        ..color = color
        ..strokeWidth = 1;
      canvas.drawLine(
        Offset(cx, layout.priceY(b.high)),
        Offset(cx, layout.priceY(b.low)),
        wick,
      );
      final top = layout.priceY(b.close > b.open ? b.close : b.open);
      final bottom = layout.priceY(b.close > b.open ? b.open : b.close);
      final rect = Rect.fromLTWH(
        cx - layout.bodyW / 2,
        top,
        layout.bodyW,
        (bottom - top).clamp(1.0, double.infinity),
      );
      if (b.isUp) {
        canvas.drawRect(rect, Paint()..color = surface);
        canvas.drawRect(
          rect,
          Paint()
            ..color = color
            ..style = PaintingStyle.stroke
            ..strokeWidth = 1,
        );
      } else {
        canvas.drawRect(rect, Paint()..color = color);
      }
      canvas.drawRect(
        Rect.fromLTWH(
          cx - layout.bodyW / 2,
          layout.volY(b.volume),
          layout.bodyW,
          layout.volTop + layout.volH - layout.volY(b.volume),
        ),
        Paint()..color = color.withValues(alpha: 0.6),
      );
    }
  }

  void _paintArea(Canvas canvas, _KlineLayout layout) {
    final visible = layout.visible;
    if (visible.isEmpty) {
      return;
    }
    final baseline = bars.first.open;
    final lastClose = visible.last.close;
    final color = lastClose >= baseline ? AppColors.up : AppColors.down;
    final line = Path();
    final fill = Path();
    for (var i = 0; i < visible.length; i++) {
      final px = layout.x(i);
      final py = layout.priceY(visible[i].close);
      if (i == 0) {
        line.moveTo(px, py);
        fill.moveTo(px, layout.mainH);
        fill.lineTo(px, py);
      } else {
        line.lineTo(px, py);
        fill.lineTo(px, py);
      }
    }
    fill.lineTo(layout.x(visible.length - 1), layout.mainH);
    fill.close();
    canvas.drawPath(
      fill,
      Paint()
        ..color = color.withValues(alpha: 0.16)
        ..style = PaintingStyle.fill,
    );
    canvas.drawPath(
      line,
      Paint()
        ..color = color
        ..strokeWidth = 1.4
        ..style = PaintingStyle.stroke
        ..strokeJoin = StrokeJoin.round,
    );
    if (baseline >= layout.lo && baseline <= layout.hi) {
      final by = layout.priceY(baseline);
      canvas.drawLine(
        Offset(0, by),
        Offset(layout.slot * visible.length, by),
        Paint()
          ..color = AppColors.flat.withValues(alpha: 0.5)
          ..strokeWidth = 0.8,
      );
    }
    for (var i = 0; i < visible.length; i++) {
      final b = visible[i];
      final prevClose = i == 0
          ? (layout.start > 0 ? bars[layout.start - 1].close : b.open)
          : visible[i - 1].close;
      final up = b.close >= prevClose;
      final volColor = up ? AppColors.up : AppColors.down;
      final cx = layout.x(i);
      canvas.drawRect(
        Rect.fromLTWH(
          cx - layout.bodyW / 2,
          layout.volY(b.volume),
          layout.bodyW,
          layout.volTop + layout.volH - layout.volY(b.volume),
        ),
        Paint()..color = volColor.withValues(alpha: 0.55),
      );
    }
  }

  void _paintMa5(Canvas canvas, _KlineLayout layout, int start) {
    final visible = layout.visible;
    final maPath = Path();
    var started = false;
    for (var i = 0; i < visible.length; i++) {
      final globalIdx = start + i;
      if (globalIdx < 4) {
        continue;
      }
      var sum = 0.0;
      for (var k = globalIdx - 4; k <= globalIdx; k++) {
        sum += bars[k].close;
      }
      final px = layout.x(i);
      final py = layout.priceY(sum / 5);
      if (started) {
        maPath.lineTo(px, py);
      } else {
        maPath.moveTo(px, py);
        started = true;
      }
    }
    canvas.drawPath(
      maPath,
      Paint()
        ..color = maColor
        ..strokeWidth = 1
        ..style = PaintingStyle.stroke,
    );
  }

  @override
  bool shouldRepaint(KlinePainter oldDelegate) =>
      identical(oldDelegate.bars, bars) == false ||
      oldDelegate.endIndex != endIndex ||
      oldDelegate.visibleCount != visibleCount ||
      oldDelegate.area != area ||
      oldDelegate.crossIndex != crossIndex;
}
