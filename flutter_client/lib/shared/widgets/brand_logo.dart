import 'package:flutter/material.dart';

/// 品牌标：渐变圆角方块 + 蜡烛图刻。侧栏、登录页、关于页统一取用。
class BrandMark extends StatelessWidget {
  const BrandMark({super.key, this.size = 36});

  final double size;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [Color(0xFF409EFF), Color(0xFF2E6FE8)],
        ),
        borderRadius: BorderRadius.circular(size * 0.28),
      ),
      child: Icon(
        Icons.candlestick_chart_rounded,
        color: Colors.white,
        size: size * 0.62,
      ),
    );
  }
}

/// 品牌字标：标 + 名称 + 可选副题。横向紧凑排列。
class BrandWordmark extends StatelessWidget {
  const BrandWordmark({
    super.key,
    this.markSize = 36,
    this.showSubtitle = true,
  });

  final double markSize;
  final bool showSubtitle;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        BrandMark(size: markSize),
        const SizedBox(width: 10),
        Flexible(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                '智慧金融',
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: theme.textTheme.titleLarge?.copyWith(
                  fontWeight: FontWeight.w800,
                  letterSpacing: 0.5,
                ),
              ),
              if (showSubtitle)
                Text(
                  'SMART FINANCE TERMINAL',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: theme.textTheme.labelSmall?.copyWith(
                    color: theme.colorScheme.onSurfaceVariant,
                    letterSpacing: 1.6,
                    fontSize: 9,
                  ),
                ),
            ],
          ),
        ),
      ],
    );
  }
}
