import 'dart:math' as math;
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter/scheduler.dart';

/// 对齐 Web `CyberBackground`：0/1/Hex 节点、连线、穿梭光。登录页与 NEXUS 门户共用。
class CyberBackground extends StatefulWidget {
  const CyberBackground({super.key, required this.dark});
  final bool dark;

  @override
  State<CyberBackground> createState() => _CyberBackgroundState();
}

class _CyberBackgroundState extends State<CyberBackground> with SingleTickerProviderStateMixin {
  late final Ticker _ticker;
  final _rnd = math.Random(7);
  Size _size = Size.zero;
  final _particles = <_Particle>[];
  final _shots = <_Shot>[];
  Duration _last = Duration.zero;

  @override
  void initState() {
    super.initState();
    _ticker = createTicker(_tick)..start();
  }

  @override
  void dispose() {
    _ticker.dispose();
    super.dispose();
  }

  void _ensure(Size size) {
    if (size == _size && _particles.isNotEmpty) return;
    _size = size;
    final count = math.min(56, math.max(18, (size.width * size.height / 16000).round()));
    while (_particles.length < count) {
      _particles.add(_Particle.spawn(_rnd, size));
    }
    if (_particles.length > count) {
      _particles.removeRange(count, _particles.length);
    }
    if (_shots.isEmpty) {
      for (var i = 0; i < 6; i++) {
        _shots.add(_Shot.spawn(_rnd, size));
      }
    }
  }

  void _tick(Duration elapsed) {
    if (!mounted || _size == Size.zero) return;
    final dt = _last == Duration.zero ? 0.016 : (elapsed - _last).inMicroseconds / 1e6;
    _last = elapsed;
    final clamped = dt.clamp(0.0, 0.04);
    for (final p in _particles) {
      p.update(_size, clamped);
    }
    for (final s in _shots) {
      s.update(_rnd, _size, clamped);
    }
    setState(() {});
  }

  @override
  Widget build(BuildContext context) {
    return IgnorePointer(
      child: LayoutBuilder(
        builder: (context, c) {
          _ensure(Size(c.maxWidth, c.maxHeight));
          return CustomPaint(
            painter: _CyberPainter(
              dark: widget.dark,
              particles: _particles,
              shots: _shots,
            ),
            size: Size.infinite,
          );
        },
      ),
    );
  }
}

class _Particle {
  _Particle(this.x, this.y, this.vx, this.vy, this.text, this.size);
  factory _Particle.spawn(math.Random rnd, Size area) {
    final hex = rnd.nextBool();
    final text = hex
        ? String.fromCharCode(rnd.nextBool() ? 48 : 49)
        : String.fromCharCode(65 + rnd.nextInt(6));
    return _Particle(
      rnd.nextDouble() * area.width,
      rnd.nextDouble() * area.height,
      (rnd.nextDouble() - 0.5) * 22,
      (rnd.nextDouble() - 0.5) * 22,
      text,
      10 + rnd.nextDouble() * 8,
    );
  }

  double x;
  double y;
  double vx;
  double vy;
  final String text;
  final double size;

  void update(Size area, double dt) {
    x += vx * dt;
    y += vy * dt;
    if (x < 0 || x > area.width) vx *= -1;
    if (y < 0 || y > area.height) vy *= -1;
    x = x.clamp(0, area.width);
    y = y.clamp(0, area.height);
  }
}

class _Shot {
  _Shot({
    required this.start,
    required this.end,
    required this.length,
    required this.speed,
    this.progress = 0,
  });

  factory _Shot.spawn(math.Random rnd, Size area) {
    final length = 200 + rnd.nextDouble() * 400;
    final dir = rnd.nextInt(4);
    late Offset start;
    late Offset end;
    switch (dir) {
      case 0:
        start = Offset(-length, rnd.nextDouble() * area.height);
        end = Offset(area.width + length, start.dy + (rnd.nextDouble() - 0.5) * 200);
      case 1:
        start = Offset(area.width + length, rnd.nextDouble() * area.height);
        end = Offset(-length, start.dy + (rnd.nextDouble() - 0.5) * 200);
      case 2:
        start = Offset(-length, -length);
        end = Offset(area.width + length, area.height + length);
      default:
        start = Offset(area.width + length, area.height + length);
        end = Offset(-length, -length);
    }
    return _Shot(
      start: start,
      end: end,
      length: length,
      speed: 0.08 + rnd.nextDouble() * 0.18,
      progress: rnd.nextDouble(),
    );
  }

  Offset start;
  Offset end;
  double length;
  double speed;
  double progress;

  void update(math.Random rnd, Size area, double dt) {
    progress += speed * dt;
    if (progress > 1.2) {
      final next = _Shot.spawn(rnd, area);
      start = next.start;
      end = next.end;
      length = next.length;
      speed = next.speed;
      progress = 0;
    }
  }
}

class _CyberPainter extends CustomPainter {
  _CyberPainter({required this.dark, required this.particles, required this.shots});
  final bool dark;
  final List<_Particle> particles;
  final List<_Shot> shots;

  @override
  void paint(Canvas canvas, Size size) {
    final glow = dark ? const Color(0xFF38BDF8) : const Color(0xFF0284C7);
    canvas.drawCircle(
      Offset(size.width * 0.12, size.height * 0.18),
      size.width * 0.28,
      Paint()..color = const Color(0x6B3B82F6).withValues(alpha: dark ? 0.38 : 0.22),
    );
    canvas.drawCircle(
      Offset(size.width * 0.88, size.height * 0.82),
      size.width * 0.3,
      Paint()..color = const Color(0x669333EA).withValues(alpha: dark ? 0.34 : 0.18),
    );

    for (final s in shots) {
      final head = Offset.lerp(s.start, s.end, s.progress.clamp(0.0, 1.0))!;
      final angle = math.atan2(s.end.dy - s.start.dy, s.end.dx - s.start.dx);
      final tail = Offset(head.dx - math.cos(angle) * s.length, head.dy - math.sin(angle) * s.length);
      final shader = ui.Gradient.linear(
        tail,
        head,
        [glow.withValues(alpha: 0), glow.withValues(alpha: dark ? 0.65 : 0.45)],
      );
      canvas.drawLine(
        tail,
        head,
        Paint()
          ..shader = shader
          ..strokeWidth = 2,
      );
      canvas.drawCircle(head, 3, Paint()..color = dark ? const Color(0xFFBAE6FD) : glow);
    }

    const maxDist = 160.0;
    for (var i = 0; i < particles.length; i++) {
      final a = particles[i];
      for (var j = i + 1; j < particles.length; j++) {
        final b = particles[j];
        final d = (Offset(a.x, a.y) - Offset(b.x, b.y)).distance;
        if (d >= maxDist) continue;
        canvas.drawLine(
          Offset(a.x, a.y),
          Offset(b.x, b.y),
          Paint()
            ..color = glow.withValues(alpha: (1 - d / maxDist) * 0.35)
            ..strokeWidth = 1,
        );
      }
    }

    final tp = TextPainter(textDirection: TextDirection.ltr);
    for (final p in particles) {
      tp.text = TextSpan(
        text: p.text,
        style: TextStyle(
          fontSize: p.size,
          fontWeight: FontWeight.w700,
          fontFamily: 'Menlo',
          color: glow.withValues(alpha: dark ? 0.85 : 0.7),
        ),
      );
      tp.layout();
      tp.paint(canvas, Offset(p.x, p.y));
    }
  }

  @override
  bool shouldRepaint(covariant _CyberPainter oldDelegate) => true;
}
