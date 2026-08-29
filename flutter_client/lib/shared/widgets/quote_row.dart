import 'package:flutter/material.dart';

import '../../core/theme/app_theme.dart';
import '../utils/format.dart';
import 'quote_text.dart';

Color _chgColor(double? v) => switch (v) {
  null => AppColors.flat,
  > 0 => AppColors.up,
  < 0 => AppColors.down,
  _ => AppColors.flat,
};

/// 涨跌幅实心胶囊：红涨绿跌灰平，白字 tabular。
class ChgPill extends StatelessWidget {
  const ChgPill(this.pct, {super.key, this.width = 72});

  final double? pct;
  final double width;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: width,
      height: 28,
      child: DecoratedBox(
        decoration: BoxDecoration(
          color: _chgColor(pct),
          borderRadius: BorderRadius.circular(4),
        ),
        child: Center(
          child: FittedBox(
            fit: BoxFit.scaleDown,
            child: Text(
              formatPct(pct),
              style: const TextStyle(
                color: Colors.white,
                fontWeight: FontWeight.w700,
                fontFeatures: AppNum.fontFeatures,
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// 报价表头排序字段。null 表示保持接口顺序。
enum QuoteSort { name, last, changePct }

/// 报价比较：空值永远排最后；[ascending] 为 false 时名称/数值都倒序。
int compareQuotes({
  required QuoteSort field,
  required bool ascending,
  required String nameA,
  required String nameB,
  double? lastA,
  double? lastB,
  double? changePctA,
  double? changePctB,
}) {
  if (field == QuoteSort.name) {
    final r = nameA.toLowerCase().compareTo(nameB.toLowerCase());
    if (r == 0) {
      return 0;
    }
    return ascending ? r : -r;
  }
  final a = field == QuoteSort.last ? lastA : changePctA;
  final b = field == QuoteSort.last ? lastB : changePctB;
  if (a == null && b == null) {
    return 0;
  }
  if (a == null) {
    return 1;
  }
  if (b == null) {
    return -1;
  }
  final r = a.compareTo(b);
  return ascending ? r : -r;
}

/// 报价列表行：左名称代码，右最新价 + 涨跌胶囊。无卡片底。
class QuoteListRow extends StatelessWidget {
  const QuoteListRow({
    super.key,
    required this.name,
    required this.symbol,
    this.marketLabel = '',
    this.last,
    this.changePct,
    this.rank,
    this.leadingExtra,
    this.subtitle = '',
    this.trailing,
    this.onTap,
    this.onLongPress,
  });

  final String name;
  final String symbol;
  final String marketLabel;
  final double? last;
  final double? changePct;
  final int? rank;
  final Widget? leadingExtra;
  final String subtitle;
  final Widget? trailing;
  final VoidCallback? onTap;
  final VoidCallback? onLongPress;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final code = marketLabel.isEmpty ? symbol : '$symbol $marketLabel';
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        onLongPress: onLongPress,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
          child: Row(
            children: [
              if (rank != null) ...[
                SizedBox(
                  width: 22,
                  child: Text(
                    '$rank',
                    style: TextStyle(
                      color: scheme.onSurfaceVariant,
                      fontFeatures: AppNum.fontFeatures,
                    ),
                  ),
                ),
                const SizedBox(width: 4),
              ],
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Row(
                      children: [
                        if (leadingExtra != null) ...[
                          leadingExtra!,
                          const SizedBox(width: 4),
                        ],
                        Expanded(
                          child: Text(
                            name,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(
                              fontWeight: FontWeight.w800,
                              fontSize: 15,
                              height: 1.15,
                            ),
                          ),
                        ),
                      ],
                    ),
                    Text(
                      code,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                        fontSize: 11,
                        color: scheme.onSurfaceVariant,
                        height: 1.2,
                      ),
                    ),
                    if (subtitle.isNotEmpty)
                      Text(
                        subtitle,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(
                          fontSize: 11,
                          color: scheme.onSurfaceVariant,
                          height: 1.2,
                        ),
                      ),
                  ],
                ),
              ),
              PriceText(
                last,
                style: const TextStyle(
                  fontWeight: FontWeight.w800,
                  fontSize: 16,
                ),
              ),
              const SizedBox(width: 8),
              ChgPill(changePct),
              if (trailing != null) ...[const SizedBox(width: 4), trailing!],
            ],
          ),
        ),
      ),
    );
  }
}

/// 指数迷你条：三列 name / last / %，无色块底。
class IndexMiniStrip extends StatelessWidget {
  const IndexMiniStrip({super.key, required this.items});

  final List<({String name, double? last, double? changePct})> items;

  @override
  Widget build(BuildContext context) {
    if (items.isEmpty) return const SizedBox.shrink();
    final scheme = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.fromLTRB(8, 6, 8, 6),
      child: IntrinsicHeight(
        child: Row(
          children: [
            for (var i = 0; i < items.length; i++) ...[
              if (i > 0) Container(width: 1, color: scheme.outlineVariant),
              Expanded(child: _cell(scheme, items[i])),
            ],
          ],
        ),
      ),
    );
  }

  Widget _cell(
    ColorScheme scheme,
    ({String name, double? last, double? changePct}) item,
  ) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 8),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            item.name,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: TextStyle(fontSize: 11, color: scheme.onSurfaceVariant),
          ),
          PriceText(
            item.last,
            style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w700),
          ),
          PctText(
            item.changePct,
            bold: true,
            style: const TextStyle(fontSize: 12),
          ),
        ],
      ),
    );
  }
}

/// 列表表头：名称 · 最新 / 涨跌幅。传入 [onSort] 时可点按切换排序。
class QuoteListHeader extends StatelessWidget {
  const QuoteListHeader({
    super.key,
    this.sort,
    this.ascending = false,
    this.onSort,
    this.trailingWidth = 0,
  });

  final QuoteSort? sort;
  final bool ascending;
  final ValueChanged<QuoteSort>? onSort;

  /// 右侧额外控件占位（例如加自选按钮），与 [QuoteListRow.trailing] 对齐。
  final double trailingWidth;

  @override
  Widget build(BuildContext context) {
    final muted = Theme.of(context).colorScheme.onSurfaceVariant;
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: Row(
        children: [
          _label(context, '名称', QuoteSort.name, muted, align: TextAlign.left),
          const Spacer(),
          _label(context, '最新', QuoteSort.last, muted, align: TextAlign.right),
          const SizedBox(width: 8),
          SizedBox(
            width: 72,
            child: _label(
              context,
              '涨跌幅',
              QuoteSort.changePct,
              muted,
              align: TextAlign.center,
            ),
          ),
          if (trailingWidth > 0) SizedBox(width: trailingWidth),
        ],
      ),
    );
  }

  Widget _label(
    BuildContext context,
    String text,
    QuoteSort field,
    Color muted, {
    required TextAlign align,
  }) {
    final on = sort == field;
    final style = TextStyle(
      fontSize: 11,
      color: on ? Theme.of(context).colorScheme.onSurface : muted,
      fontWeight: on ? FontWeight.w700 : FontWeight.w400,
    );
    final row = Row(
      mainAxisSize: MainAxisSize.min,
      mainAxisAlignment: align == TextAlign.left
          ? MainAxisAlignment.start
          : align == TextAlign.center
          ? MainAxisAlignment.center
          : MainAxisAlignment.end,
      children: [
        Text(text, style: style),
        if (on)
          Icon(
            ascending ? Icons.arrow_drop_up : Icons.arrow_drop_down,
            size: 16,
            color: style.color,
          ),
      ],
    );
    if (onSort == null) return row;
    return InkWell(
      onTap: () => onSort!(field),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 4),
        child: row,
      ),
    );
  }
}
