import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/theme/app_theme.dart';
import '../../shared/utils/format.dart';
import '../news/data/briefing_api.dart';
import '../news/data/briefing_models.dart';
import '../quant/data/quant_api.dart';
import '../quant/data/quant_models.dart';
import '../trade/data/trade_api.dart';
import 'phone_trade_page.dart';

/// 反重力设计稿图 02：量化雷达 + AI 台账 + 舆情快讯。
class PhoneQuantPage extends ConsumerWidget {
  const PhoneQuantPage({super.key, this.onOpenSymbol});
  final void Function(String symbol, String market, String name)? onOpenSymbol;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final daily = ref.watch(quantDailyListProvider);
    final runs = ref.watch(quantScanRunsProvider);
    final risk = ref.watch(riskEventsProvider);
    final lb = ref.watch(_longbridgeProvider);
    final news = ref.watch(_usNewsProvider);
    final scheme = Theme.of(context).colorScheme;
    final items = daily.asData?.value.list?.items ?? const <SignalItem>[];

    return RefreshIndicator(
      onRefresh: () async {
        ref.invalidate(quantDailyListProvider);
        ref.invalidate(quantScanRunsProvider);
        ref.invalidate(riskEventsProvider);
        ref.invalidate(_longbridgeProvider);
        ref.invalidate(_usNewsProvider);
      },
      child: ListView(
        padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
        children: [
          Text('量化研究', style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w800)),
          const SizedBox(height: 10),
          _StatusCard(longbridge: lb.asData?.value ?? const {}),
          const SizedBox(height: 16),
          Text('次日策略清单', style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w800)),
          const SizedBox(height: 8),
          if (items.isEmpty)
            Text(daily.asData?.value.message.isNotEmpty == true ? daily.asData!.value.message : '暂无今日清单', style: TextStyle(color: scheme.onSurfaceVariant))
          else
            for (final s in items.take(8))
              _SignalCard(
                item: s,
                onOpen: onOpenSymbol,
                onExec: () => showFastTicket(
                  context,
                  symbol: s.symbol,
                  market: s.market.isEmpty ? 'US' : s.market,
                  name: s.name,
                ),
              ),
          const SizedBox(height: 16),
          Text('扫描台账', style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w800)),
          const SizedBox(height: 8),
          for (final r in (runs.asData?.value ?? const <ScanRun>[]).take(6))
            ListTile(
              contentPadding: EdgeInsets.zero,
              leading: Icon(
                r.status.toLowerCase().contains('ok') || r.status.toLowerCase().contains('done') || r.status.toLowerCase().contains('success')
                    ? Icons.check_circle
                    : Icons.timelapse,
                color: AppColors.brand,
              ),
              title: Text(r.strategyProfile.isEmpty ? '扫描 ${r.cycleId ?? r.runId ?? ''}' : r.strategyProfile),
              subtitle: Text('${r.status} · 命中 ${r.opportunityCount} · ${r.finishedAt.isEmpty ? r.startedAt : r.finishedAt}'),
            ),
          const SizedBox(height: 16),
          Text('财经简报', style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w800)),
          const SizedBox(height: 8),
          for (final n in (news.asData?.value ?? const <BriefingItem>[]).take(6))
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Text.rich(
                TextSpan(children: [
                  TextSpan(text: n.headline.isEmpty ? n.summary : n.headline, style: const TextStyle(fontWeight: FontWeight.w600)),
                  if (n.generatedAt.isNotEmpty)
                    TextSpan(
                      text: '  ${formatRelativeTime(n.generatedAt)}',
                      style: TextStyle(color: scheme.onSurfaceVariant, fontSize: 12),
                    ),
                ]),
              ),
            ),
          const SizedBox(height: 12),
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: AppColors.down.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Text(
              (risk.asData?.value ?? const []).isEmpty ? '风控：暂无事件' : '风控：${risk.asData!.value.length} 条事件',
              style: const TextStyle(fontWeight: FontWeight.w700),
            ),
          ),
        ],
      ),
    );
  }
}

final _longbridgeProvider = FutureProvider.autoDispose<Map<String, dynamic>>(
  (ref) => ref.read(quantApiProvider).longbridgeConfig(),
);

final _usNewsProvider = FutureProvider.autoDispose<List<BriefingItem>>(
  (ref) => ref.read(briefingApiProvider).briefings(market: 'US', limit: 8),
);

class _StatusCard extends StatelessWidget {
  const _StatusCard({required this.longbridge});
  final Map<String, dynamic> longbridge;

  @override
  Widget build(BuildContext context) {
    final ok = longbridge['configured'] == true || (longbridge['appKey']?.toString().isNotEmpty ?? false);
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surfaceContainerLow,
        borderRadius: BorderRadius.circular(14),
      ),
      child: Column(
        children: [
          _dot(ok ? '长桥通道已配置' : '长桥通道未绑定', ok),
        ],
      ),
    );
  }

  Widget _dot(String text, bool on) {
    return Row(
      children: [
        Icon(Icons.circle, size: 10, color: on ? AppColors.down : AppColors.warn),
        const SizedBox(width: 8),
        Expanded(child: Text(text, style: const TextStyle(fontSize: 13))),
      ],
    );
  }
}

class _SignalCard extends StatelessWidget {
  const _SignalCard({required this.item, this.onOpen, this.onExec});
  final SignalItem item;
  final void Function(String symbol, String market, String name)? onOpen;
  final VoidCallback? onExec;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Material(
        color: scheme.surfaceContainerLow,
        borderRadius: BorderRadius.circular(14),
        child: InkWell(
          borderRadius: BorderRadius.circular(14),
          onTap: onOpen == null ? null : () => onOpen!(item.symbol, item.market, item.name),
          child: Padding(
            padding: const EdgeInsets.fromLTRB(12, 10, 8, 10),
            child: Row(
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        item.name.isEmpty ? item.symbol : '${item.name}  ${item.symbol}',
                        style: const TextStyle(fontWeight: FontWeight.w800),
                      ),
                      Text(
                        [
                          if (item.signal.isNotEmpty) item.signal else if (item.side.isNotEmpty) item.side,
                          if (item.score != null) '评分 ${item.score!.toStringAsFixed(1)}',
                          if (item.reason.isNotEmpty) item.reason,
                        ].join(' · '),
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(fontSize: 12, color: scheme.onSurfaceVariant),
                      ),
                    ],
                  ),
                ),
                TextButton(
                  onPressed: onExec,
                  child: const Text('下单'),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
