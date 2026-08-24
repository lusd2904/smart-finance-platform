import 'package:flutter/material.dart';

import '../../core/theme/app_theme.dart';
import '../../shared/widgets/auth_scaffold.dart';
import '../../shared/charts/radar_chart.dart';
import '../../shared/charts/sentiment_gauge.dart';
import '../../shared/charts/trend_line.dart';
import '../../shared/widgets/page_header.dart';
import '../../shared/widgets/stat_grid.dart';
import '../../shared/widgets/status_dot.dart';

/// 设计系统预览页（仅 debug 构建注册路由 /gallery）。
/// 用途：
/// 1. 视觉回归对照 —— 改令牌后一屏看全组件；
/// 2. 后续里程碑（M2 资讯 / M3 量化 / M4 交易）开发时的活规范。
/// 页内全部为静态示例数据，不发起任何请求。
class DesignGalleryPage extends StatelessWidget {
  const DesignGalleryPage({super.key});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    return Scaffold(
      appBar: AppBar(title: const Text('设计系统预览')),
      body: ListView(
        padding: const EdgeInsets.only(bottom: 32),
        children: [
          const PageHeader(
            title: 'Design Tokens',
            subtitle: '「墨蓝金融终端」· 仅调试构建可见',
          ),
          _wrap([
            _swatchRow('品牌 / 涨跌语义', [
              ('brand', AppColors.brand),
              ('up', AppColors.up),
              ('down', AppColors.down),
              ('flat', AppColors.flat),
              ('warn', AppColors.warn),
            ]),
            const Divider(),
            _swatchRow('表面分层', [
              ('surface', scheme.surface),
              ('contLow', scheme.surfaceContainerLow),
              ('contHigh', scheme.surfaceContainerHigh),
              ('onSurface', scheme.onSurface),
              ('primary', scheme.primary),
            ]),
          ]),
          _gap,
          _wrap(_typeSamples(theme)),
          _gap,
          const PageHeader(title: '数据面板'),
          _wrap([
            StatGrid(
              cells: const [
                StatCellData(label: '恒生指数', value: Text('+1.24%')),
                StatCellData(label: '成交额', value: Text('3821.40亿')),
                StatCellData(label: '涨跌家数', value: Text('示例')),
                StatCellData(label: '热度分', value: Text('87.5')),
              ],
            ),
            const SizedBox(height: 10),
            Row(
              children: [
                StatusDot(color: AppColors.down),
                const SizedBox(width: 6),
                Text('网关已连接', style: theme.textTheme.bodySmall),
                const SizedBox(width: 18),
                StatusDot(color: AppColors.warn),
                const SizedBox(width: 6),
                Text('数据延迟提示', style: theme.textTheme.bodySmall),
              ],
            ),
          ]),
          _gap,
          const PageHeader(title: '列表行 · Top50 样式'),
          _wrap([
            SectionCard(
              title: '热度 Top50',
              subtitle: '按当日热度排序 · 点击行查看 K 线详情',
              padding: const EdgeInsets.fromLTRB(8, 4, 8, 8),
              child: Column(
                children: [
                  _sampleRow(
                    theme,
                    1,
                    'NVDA',
                    '英伟达',
                    '+4.28%',
                    '市值 2.9万亿 · 成交 486亿',
                    starred: true,
                  ),
                  const Divider(height: 1, indent: 46),
                  _sampleRow(
                    theme,
                    2,
                    'TSLA',
                    '特斯拉',
                    '-2.11%',
                    '市值 7420亿 · 成交 312亿',
                  ),
                  const Divider(height: 1, indent: 46),
                  _sampleRow(
                    theme,
                    3,
                    'AAPL',
                    '苹果',
                    '+0.86%',
                    '市值 3.4万亿 · 成交 291亿',
                  ),
                ],
              ),
            ),
          ]),
          _gap,
          const PageHeader(title: '控件'),
          _wrap([
            Row(
              children: [
                FilledButton(onPressed: () {}, child: const Text('主要操作')),
                const SizedBox(width: 10),
                OutlinedButton(onPressed: () {}, child: const Text('次级操作')),
                const SizedBox(width: 10),
                TextButton(onPressed: () {}, child: const Text('文字按钮')),
              ],
            ),
            const SizedBox(height: 12),
            Wrap(
              spacing: 8,
              children: [
                ChoiceChip(
                  label: const Text('美股'),
                  selected: true,
                  onSelected: (_) {},
                ),
                ChoiceChip(
                  label: const Text('港股'),
                  selected: false,
                  onSelected: (_) {},
                ),
                ActionChip(label: const Text('本地预设'), onPressed: () {}),
              ],
            ),
            const SizedBox(height: 12),
            const TextField(decoration: InputDecoration(labelText: '输入框')),
            const SizedBox(height: 12),
            Align(
              alignment: Alignment.centerLeft,
              child: SegmentedButton<int>(
                segments: const [
                  ButtonSegment(value: 0, label: Text('日K')),
                  ButtonSegment(value: 1, label: Text('周K')),
                  ButtonSegment(value: 2, label: Text('月K')),
                ],
                selected: const {0},
                onSelectionChanged: null,
              ),
            ),
            const SizedBox(height: 12),
            const FormErrorText('探测失败：地址不可达或非本平台网关。'),
          ]),
          _gap,
          const PageHeader(title: 'M2 图表组件'),
          _wrap([
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const SentimentGauge(score: 78, size: 180),
                const SizedBox(width: 24),
                Expanded(
                  child: Column(
                    children: [
                      SizedBox(
                        height: 90,
                        width: double.infinity,
                        child: TrendLine(
                          values: [42, 48, 45, 58, 61, 57, 66, 72, 69, 78],
                          color: AppColors.brand,
                        ),
                      ),
                      const SizedBox(height: 10),
                      SizedBox(
                        height: 90,
                        width: double.infinity,
                        child: TrendLine(
                          values: [3.2, -1.4, -2.8, 0.9, 2.2, 1.1, -0.6, 1.8],
                          baselineAtZero: true,
                          color: AppColors.up,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            RadarChart(
              axes: const ['基本面', '技术面', '情绪面', '估值面', '资金面'],
              values: const [0.72, 0.85, 0.6, 0.44, 0.68],
              size: 200,
            ),
          ]),
        ],
      ),
    );
  }

  static const _gap = SizedBox(height: 20);

  static Widget _wrap(List<Widget> children) => Padding(
    padding: const EdgeInsets.symmetric(horizontal: AppDimens.pagePadding),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: children,
    ),
  );

  static Widget _swatchRow(String label, List<(String, Color)> items) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: const TextStyle(fontSize: 12)),
          const SizedBox(height: 6),
          Row(
            children: [
              for (final (name, color) in items)
                Expanded(
                  child: Column(
                    children: [
                      Container(
                        height: 34,
                        decoration: BoxDecoration(
                          color: color,
                          borderRadius: BorderRadius.circular(8),
                        ),
                      ),
                      const SizedBox(height: 3),
                      Text(name, style: const TextStyle(fontSize: 10)),
                    ],
                  ),
                ),
            ],
          ),
        ],
      ),
    );
  }

  static List<Widget> _typeSamples(ThemeData theme) => [
    for (final (label, style) in [
      ('headlineSmall', theme.textTheme.headlineSmall),
      ('titleLarge', theme.textTheme.titleLarge),
      ('titleMedium', theme.textTheme.titleMedium),
      ('bodyMedium', theme.textTheme.bodyMedium),
      ('bodySmall', theme.textTheme.bodySmall),
    ])
      Padding(
        padding: const EdgeInsets.only(bottom: 6),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.baseline,
          textBaseline: TextBaseline.alphabetic,
          children: [
            SizedBox(
              width: 110,
              child: Text(label, style: theme.textTheme.bodySmall),
            ),
            Expanded(child: Text('智慧金融 Aa123', style: style)),
          ],
        ),
      ),
  ];

  static Widget _sampleRow(
    ThemeData theme,
    int rank,
    String symbol,
    String name,
    String pct,
    String meta, {
    bool starred = false,
  }) {
    final scheme = theme.colorScheme;
    final top3 = rank <= 3;
    final up = pct.startsWith('+');
    return InkWell(
      borderRadius: BorderRadius.circular(AppDimens.radiusControl),
      onTap: () {},
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 11),
        child: Row(
          children: [
            Container(
              width: 26,
              height: 26,
              alignment: Alignment.center,
              decoration: BoxDecoration(
                color: top3
                    ? scheme.primary.withValues(alpha: 0.14)
                    : scheme.surfaceContainerHighest,
                shape: BoxShape.circle,
              ),
              child: Text(
                '$rank',
                style: theme.textTheme.labelMedium?.copyWith(
                  fontWeight: FontWeight.w800,
                  fontFeatures: AppNum.fontFeatures,
                  color: top3 ? scheme.primary : scheme.onSurfaceVariant,
                ),
              ),
            ),
            const SizedBox(width: 11),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Flexible(
                        child: Text(
                          symbol,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: theme.textTheme.titleSmall?.copyWith(
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                      ),
                      const SizedBox(width: 6),
                      Flexible(
                        child: Text(
                          name,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: theme.textTheme.bodySmall?.copyWith(
                            color: scheme.onSurfaceVariant,
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 2),
                  Text(
                    meta,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: scheme.onSurfaceVariant,
                    ),
                  ),
                ],
              ),
            ),
            if (starred)
              const Padding(
                padding: EdgeInsets.only(left: 6),
                child: Icon(
                  Icons.star_rounded,
                  size: 17,
                  color: AppColors.warn,
                ),
              ),
            const SizedBox(width: 8),
            Text(
              pct,
              style: theme.textTheme.titleSmall?.copyWith(
                fontWeight: FontWeight.w700,
                color: up ? AppColors.up : AppColors.down,
                fontFeatures: AppNum.fontFeatures,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
