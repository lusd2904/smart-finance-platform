import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/theme/app_theme.dart';
import '../../../shared/utils/format.dart';
import '../../../shared/widgets/page_header.dart';
import '../../../shared/widgets/stat_grid.dart';
import '../data/trade_models.dart';
import '../../quant/data/quant_api.dart';
import '../../sentiment/presentation/sentiment_page.dart' show ErrorView;
import '../data/trade_api.dart';
import 'market_watch_panel.dart';

/// 交易台：账户、持仓、委托与自动交易状态。
class TradePage extends ConsumerWidget {
  const TradePage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final wide = MediaQuery.sizeOf(context).width >= AppDimens.wideBreakpoint;

    Widget body = Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const _AccountCard(),
        const SizedBox(height: 12),
        const MarketWatchPanel(),
        const SizedBox(height: 12),
        const _PositionsPanel(),
        const SizedBox(height: 12),
        const _OrdersPanel(),
        const SizedBox(height: 12),
        const _AutoTradeCard(),
        const SizedBox(height: 12),
        const _RiskSection(),
      ],
    );

    if (wide) {
      // 桌面宽屏双列：左行情盘口，右账户/持仓/委托/自动交易/风控。
      body = Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Expanded(flex: 46, child: MarketWatchPanel()),
          const SizedBox(width: 12),
          Expanded(
            flex: 54,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                _AccountCard(),
                const SizedBox(height: 12),
                _PositionsPanel(),
                const SizedBox(height: 12),
                _OrdersPanel(),
                const SizedBox(height: 12),
                _AutoTradeCard(),
                const SizedBox(height: 12),
                _RiskSection(),
              ],
            ),
          ),
        ],
      );
    }

    return Scaffold(
      body: ListView(
        padding: const EdgeInsets.only(bottom: 24),
        children: [
          const PageHeader(title: '交易台', subtitle: '账户 · 持仓 · 委托'),
          Padding(
            padding: const EdgeInsets.symmetric(
              horizontal: AppDimens.pagePadding,
            ),
            child: body,
          ),
        ],
      ),
    );
  }
}

/// 账户资产卡 + 长桥绑定态行。
class _AccountCard extends ConsumerStatefulWidget {
  const _AccountCard();

  @override
  ConsumerState<_AccountCard> createState() => _AccountCardState();
}

class _AccountCardState extends ConsumerState<_AccountCard> {
  bool _testing = false;
  String? _testResult;

  Future<void> _runTest() async {
    setState(() => _testing = true);
    try {
      final r = await ref.read(quantApiProvider).longbridgeTest();
      if (mounted) {
        setState(
          () => _testResult =
              'connected=${r['connected'] == true} · ${r['message'] ?? ''}',
        );
      }
    } catch (e) {
      if (mounted) setState(() => _testResult = '测试失败：$e');
    } finally {
      if (mounted) setState(() => _testing = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final account = ref.watch(tradeAccountProvider);
    final theme = Theme.of(context);
    return SectionCard(
      title: '账户资产',
      subtitle: '长桥券商 · 只读',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          FutureBuilder<Map<String, dynamic>>(
            future: ref.read(quantApiProvider).longbridgeConfig(),
            builder: (context, snap) {
              final cfg = snap.data;
              if (cfg == null || cfg.isEmpty) return const SizedBox.shrink();
              final bound = (cfg['appKey'] as String?)?.isNotEmpty == true;
              return Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Row(
                  children: [
                    Icon(
                      bound ? Icons.link : Icons.link_off,
                      size: 15,
                      color: bound
                          ? theme.colorScheme.primary
                          : theme.colorScheme.onSurfaceVariant,
                    ),
                    const SizedBox(width: 5),
                    Text(
                      bound
                          ? '长桥已绑定（${cfg['region'] ?? '--'} · ${cfg['appKey']}）'
                          : '长桥未绑定凭据',
                      style: theme.textTheme.labelSmall?.copyWith(
                        color: theme.colorScheme.onSurfaceVariant,
                      ),
                    ),
                    const Spacer(),
                    InkWell(
                      onTap: _testing ? null : _runTest,
                      borderRadius: BorderRadius.circular(6),
                      child: Padding(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 6,
                          vertical: 2,
                        ),
                        child: Text(
                          _testing ? '测试中…' : '测试连通',
                          style: theme.textTheme.labelSmall?.copyWith(
                            color: theme.colorScheme.primary,
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
              );
            },
          ),
          if (_testResult != null)
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Text(
                _testResult!,
                style: theme.textTheme.labelSmall?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              ),
            ),
          account.when(
            loading: () => const SizedBox(
              height: 70,
              child: Center(child: CircularProgressIndicator()),
            ),
            error: (e, _) => ErrorView(
              error: '$e',
              onRetry: () => ref.invalidate(tradeAccountProvider),
            ),
            data: (a) {
              if (!a.configured) {
                return Padding(
                  padding: const EdgeInsets.symmetric(vertical: 14),
                  child: Text(
                    a.message.isEmpty ? '长桥凭据未配置，账户数据不可用' : a.message,
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: theme.colorScheme.onSurfaceVariant,
                    ),
                  ),
                );
              }
              return StatGrid(
                cells: [
                  StatCellData(
                    label: '总净值(${a.currency})',
                    value: Text(formatAmountCn(a.netAssets)),
                  ),
                  StatCellData(
                    label: '总现金',
                    value: Text(formatAmountCn(a.totalCash)),
                  ),
                  StatCellData(
                    label: '可用资金',
                    value: Text(formatAmountCn(a.availableCash)),
                  ),
                ],
              );
            },
          ),
        ],
      ),
    );
  }
}

/// 持仓列表（成本口径；现价/浮盈待行情叠加，后续增强）。
class _PositionsPanel extends ConsumerWidget {
  const _PositionsPanel();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final positions = ref.watch(tradePositionsProvider);
    final theme = Theme.of(context);
    return SectionCard(
      title: '持仓',
      subtitle: '成本口径 · 现价叠加后续版本',
      padding: const EdgeInsets.fromLTRB(12, 10, 12, 4),
      child: positions.when(
        loading: () => const SizedBox(
          height: 80,
          child: Center(child: CircularProgressIndicator()),
        ),
        error: (e, _) => ErrorView(
          error: '$e',
          onRetry: () => ref.invalidate(tradePositionsProvider),
        ),
        data: (list) {
          if (list.isEmpty) {
            return Padding(
              padding: const EdgeInsets.symmetric(vertical: 20),
              child: Center(
                child: Text(
                  '暂无持仓',
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: theme.colorScheme.onSurfaceVariant,
                  ),
                ),
              ),
            );
          }
          return Column(
            children: [
              for (final p in list)
                Padding(
                  padding: const EdgeInsets.only(bottom: 6),
                  child: Row(
                    children: [
                      Expanded(
                        flex: 5,
                        child: Text(
                          '${p.symbol} · ${p.symbolName}',
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: AppNum.style(theme.textTheme.bodyMedium!)
                              .copyWith(fontWeight: FontWeight.w600),
                        ),
                      ),
                      Expanded(
                        flex: 3,
                        child: Text(
                          '数量 ${formatAmountCn(p.quantity)}',
                          textAlign: TextAlign.end,
                          style: AppNum.style(theme.textTheme.bodySmall!),
                        ),
                      ),
                      Expanded(
                        flex: 4,
                        child: Text(
                          '可用 ${formatAmountCn(p.availableQuantity)} · 成本 ${formatPrice(p.costPrice)}',
                          textAlign: TextAlign.end,
                          style: AppNum.style(
                            theme.textTheme.bodySmall!,
                          ).copyWith(color: theme.colorScheme.onSurfaceVariant),
                        ),
                      ),
                    ],
                  ),
                ),
            ],
          );
        },
      ),
    );
  }
}

/// 委托：当日/历史切换。
class _OrdersPanel extends ConsumerStatefulWidget {
  const _OrdersPanel();

  @override
  ConsumerState<_OrdersPanel> createState() => _OrdersPanelState();
}

class _OrdersPanelState extends ConsumerState<_OrdersPanel> {
  String _scope = 'today';

  @override
  Widget build(BuildContext context) {
    final orders = ref.watch(tradeOrdersProvider(_scope));
    final theme = Theme.of(context);
    return SectionCard(
      title: '委托',
      subtitle: '当日与历史 · 状态只读',
      padding: const EdgeInsets.fromLTRB(12, 10, 12, 8),
      child: Column(
        children: [
          Align(
            alignment: Alignment.centerLeft,
            child: SegmentedButton<String>(
              showSelectedIcon: false,
              style: const ButtonStyle(visualDensity: VisualDensity.compact),
              segments: const [
                ButtonSegment(value: 'today', label: Text('当日')),
                ButtonSegment(value: 'history', label: Text('历史')),
              ],
              selected: {_scope},
              onSelectionChanged: (s) => setState(() => _scope = s.first),
            ),
          ),
          const SizedBox(height: 8),
          orders.when(
            loading: () => const SizedBox(
              height: 80,
              child: Center(child: CircularProgressIndicator()),
            ),
            error: (e, _) => ErrorView(
              error: '$e',
              onRetry: () => ref.invalidate(tradeOrdersProvider(_scope)),
            ),
            data: (list) {
              if (list.isEmpty) {
                return Padding(
                  padding: const EdgeInsets.symmetric(vertical: 18),
                  child: Center(
                    child: Text(
                      '暂无委托记录',
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: theme.colorScheme.onSurfaceVariant,
                      ),
                    ),
                  ),
                );
              }
              return Column(
                children: [for (final o in list.take(20)) OrderTile(order: o)],
              );
            },
          ),
        ],
      ),
    );
  }
}

/// 委托条目：方向色 + 标的 + 状态徽章（在途琥珀）+ 价格/数量。
class OrderTile extends StatelessWidget {
  const OrderTile({super.key, required this.order});

  final OrderItem order;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final sideColor = order.isBuy ? AppColors.up : AppColors.down;
    final statusColor = order.open
        ? AppColors.warn
        : (order.status.contains('filled')
              ? scheme.primary
              : scheme.onSurfaceVariant);
    return Container(
      margin: const EdgeInsets.only(bottom: 6),
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: scheme.surfaceContainerLowest,
        borderRadius: BorderRadius.circular(AppDimens.radiusControl - 2),
        border: Border.all(color: scheme.outlineVariant),
      ),
      child: Row(
        children: [
          Container(width: 3, height: 34, color: sideColor),
          const SizedBox(width: 10),
          Expanded(
            flex: 5,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '${order.symbol} · ${order.stockName}',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: AppNum.style(theme.textTheme.bodyMedium!)
                      .copyWith(fontWeight: FontWeight.w600),
                ),
                Text(
                  order.submittedAt,
                  style: AppNum.style(theme.textTheme.labelSmall!)
                      .copyWith(color: scheme.onSurfaceVariant),
                ),
              ],
            ),
          ),
          Expanded(
            flex: 4,
            child: Text(
              '${order.isBuy ? '买入' : '卖出'} ${formatAmountCn(order.quantity)} @ ${formatPrice(order.price)}',
              textAlign: TextAlign.end,
              style: AppNum.style(theme.textTheme.bodySmall!),
            ),
          ),
          const SizedBox(width: 8),
          Chip(
            visualDensity: VisualDensity.compact,
            padding: EdgeInsets.zero,
            materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
            label: Text(
              order.statusLabel.isEmpty ? order.status : order.statusLabel,
              style: theme.textTheme.labelSmall?.copyWith(color: statusColor),
            ),
            backgroundColor: scheme.surfaceContainerHighest.withValues(
              alpha: 0.5,
            ),
          ),
        ],
      ),
    );
  }
}

/// 自动交易状态卡：护栏用量 + 近期运行/决策。
class _AutoTradeCard extends ConsumerWidget {
  const _AutoTradeCard();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final status = ref.watch(tradeAutoStatusProvider);
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    return SectionCard(
      title: '自动交易',
      subtitle: '扫描与护栏',
      child: status.when(
        loading: () => const SizedBox(
          height: 90,
          child: Center(child: CircularProgressIndicator()),
        ),
        error: (e, _) => ErrorView(
          error: '$e',
          onRetry: () => ref.invalidate(tradeAutoStatusProvider),
        ),
        data: (s) {
          if (!s.configured) {
            return Padding(
              padding: const EdgeInsets.symmetric(vertical: 16),
              child: Text(
                s.message.isEmpty ? '长桥凭据未配置' : s.message,
                style: theme.textTheme.bodySmall?.copyWith(
                  color: scheme.onSurfaceVariant,
                ),
              ),
            );
          }
          return Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Icon(
                    s.tradingEnabled
                        ? Icons.gpp_bad_outlined
                        : Icons.verified_user_outlined,
                    size: 17,
                    color: s.tradingEnabled ? scheme.error : AppColors.warn,
                  ),
                  const SizedBox(width: 6),
                  Text(
                    s.tradingEnabled ? '本账户自动交易已开启' : '本账户自动交易已关闭',
                    style: theme.textTheme.titleSmall?.copyWith(
                      color: s.tradingEnabled ? scheme.error : AppColors.warn,
                    ),
                  ),
                  const Spacer(),
                  Text(
                    '档位 ${s.strategyProfile} · 单日≤${s.maxDailyOrders}单 · 置信≥${s.minConfidence?.toStringAsFixed(0)}%',
                    style: AppNum.style(theme.textTheme.labelSmall!)
                        .copyWith(color: scheme.onSurfaceVariant),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              ClipRRect(
                borderRadius: BorderRadius.circular(4),
                child: LinearProgressIndicator(
                  value: s.maxDailyOrders == 0
                      ? 0
                      : (s.todayOrdersCount / s.maxDailyOrders).clamp(0.0, 1.0),
                  minHeight: 5,
                  color: scheme.primary,
                  backgroundColor: scheme.surfaceContainerHighest,
                ),
              ),
              const SizedBox(height: 4),
              Text(
                '今日 ${s.todayOrdersCount}/${s.maxDailyOrders} 单 · 名义额 ${formatAmountCn(s.todayNotionalAmount)}/${formatAmountCn(s.maxDailyNotionalAmount)}',
                style: AppNum.style(theme.textTheme.labelSmall!)
                    .copyWith(color: scheme.onSurfaceVariant),
              ),
              if (s.recentRuns.isNotEmpty) ...[
                const SizedBox(height: 10),
                Text('近期运行', style: theme.textTheme.labelLarge),
                for (final r in s.recentRuns.take(3))
                  Padding(
                    padding: const EdgeInsets.only(top: 4),
                    child: Row(
                      children: [
                        Expanded(
                          child: Text(
                            '${r.startedAt} · ${r.strategyProfile} · 机会${r.opportunityCount}/标的${r.targetCount}',
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: AppNum.style(theme.textTheme.bodySmall!),
                          ),
                        ),
                        Text(
                          r.status,
                          style: theme.textTheme.labelSmall?.copyWith(
                            color: scheme.onSurfaceVariant,
                          ),
                        ),
                      ],
                    ),
                  ),
              ],
              if (s.recentDecisions.isNotEmpty) ...[
                const SizedBox(height: 8),
                Text('近期决策', style: theme.textTheme.labelLarge),
                for (final d in s.recentDecisions.take(3))
                  Padding(
                    padding: const EdgeInsets.only(top: 4),
                    child: Row(
                      children: [
                        Expanded(
                          child: Text(
                            '${d.symbol} ${d.side} ×${d.quantity ?? '--'} @ ${formatPrice(d.price)}',
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: AppNum.style(theme.textTheme.bodySmall!),
                          ),
                        ),
                        Text(
                          d.status,
                          style: theme.textTheme.labelSmall?.copyWith(
                            color: scheme.onSurfaceVariant,
                          ),
                        ),
                      ],
                    ),
                  ),
              ],
            ],
          );
        },
      ),
    );
  }
}

/// 风控区：规则列表 + 事件历史。
class _RiskSection extends ConsumerWidget {
  const _RiskSection();

  static const _ruleTypeLabels = {
    'position': '单票仓位上限',
    'loss': '单日亏损熔断',
    'concentration': '集中度上限',
  };

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final rules = ref.watch(riskRulesProvider);
    final events = ref.watch(riskEventsProvider);
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    return SectionCard(
      title: '风控中心',
      subtitle: '规则与事件 · 只读',
      padding: const EdgeInsets.fromLTRB(12, 10, 12, 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          rules.when(
            loading: () => const SizedBox(height: 40),
            error: (e, _) => Text('$e', style: TextStyle(color: scheme.error)),
            data: (list) => Wrap(
              spacing: 6,
              runSpacing: 6,
              children: [
                for (final r in list)
                  Tooltip(
                    message: r.remark,
                    triggerMode: TooltipTriggerMode.tap,
                    child: Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 9,
                        vertical: 5,
                      ),
                      decoration: BoxDecoration(
                        color: r.enabled
                            ? scheme.primary.withValues(alpha: 0.1)
                            : scheme.surfaceContainerHighest.withValues(
                                alpha: 0.5,
                              ),
                        borderRadius: BorderRadius.circular(7),
                        border: Border.all(color: scheme.outlineVariant),
                      ),
                      child: Text(
                        '${_ruleTypeLabels[r.ruleType] ?? r.ruleType}'
                        '${r.threshold != null ? ' ${r.threshold!.toStringAsFixed(r.threshold! <= 10 ? 1 : 0)}%' : ''}'
                        '${r.symbol.isNotEmpty ? ' · ${r.symbol}' : ''}'
                        '${r.enabled ? '' : ' · 停用'}',
                        style: AppNum.style(theme.textTheme.labelSmall!)
                            .copyWith(
                              color: r.enabled
                                  ? scheme.primary
                                  : scheme.onSurfaceVariant,
                            ),
                      ),
                    ),
                  ),
              ],
            ),
          ),
          const SizedBox(height: 10),
          events.when(
            loading: () => const SizedBox(
              height: 60,
              child: Center(child: CircularProgressIndicator()),
            ),
            error: (e, _) => ErrorView(
              error: '$e',
              onRetry: () => ref.invalidate(riskEventsProvider),
            ),
            data: (list) {
              if (list.isEmpty) {
                return Padding(
                  padding: const EdgeInsets.symmetric(vertical: 14),
                  child: Center(
                    child: Text(
                      '暂无风控事件',
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: scheme.onSurfaceVariant,
                      ),
                    ),
                  ),
                );
              }
              return Column(
                children: [
                  for (final ev in list.take(10))
                    Container(
                      margin: const EdgeInsets.only(bottom: 6),
                      padding: const EdgeInsets.all(10),
                      decoration: BoxDecoration(
                        color: scheme.surfaceContainerLowest,
                        borderRadius: BorderRadius.circular(
                          AppDimens.radiusControl - 2,
                        ),
                        border: Border.all(color: scheme.outlineVariant),
                      ),
                      child: Row(
                        children: [
                          Icon(
                            ev.handled
                                ? Icons.check_circle_outline
                                : Icons.warning_amber_outlined,
                            size: 16,
                            color: ev.handled ? scheme.primary : AppColors.warn,
                          ),
                          const SizedBox(width: 8),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  ev.title,
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                  style: theme.textTheme.bodyMedium?.copyWith(
                                    fontWeight: FontWeight.w600,
                                  ),
                                ),
                                if (ev.content.isNotEmpty)
                                  Text(
                                    ev.content,
                                    maxLines: 1,
                                    overflow: TextOverflow.ellipsis,
                                    style: theme.textTheme.labelSmall?.copyWith(
                                      color: scheme.onSurfaceVariant,
                                    ),
                                  ),
                              ],
                            ),
                          ),
                          Text(
                            ev.createTime,
                            style: AppNum.style(theme.textTheme.labelSmall!)
                                .copyWith(color: scheme.onSurfaceVariant),
                          ),
                        ],
                      ),
                    ),
                ],
              );
            },
          ),
        ],
      ),
    );
  }
}
