import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../market/data/market_api.dart';
import '../../market/data/market_models.dart';

/// 自选概览：自选 tab 与加自选/删自选后的统一刷新入口。
/// autoDispose：离开页面释放，重进自动拉新。
final watchlistOverviewProvider =
    FutureProvider.autoDispose<WatchlistOverview>((ref) async {
  return ref.read(marketApiProvider).watchlistOverview();
});
