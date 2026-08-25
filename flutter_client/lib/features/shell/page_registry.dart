import 'package:flutter/material.dart';

import '../../shared/widgets/ruoyi_ui.dart';
import '../web/admin_pages.dart';
import '../web/intel_pages.dart';
import '../web/json_list_page.dart';
import '../web/market_pages.dart';
import '../web/portal_dashboard.dart';
import '../web/quant_pages.dart';
import '../web/trade_pages.dart';
import '../web/trade_terminal_page.dart';

/// 网页端每一个路由都对应一个原生 Flutter 页面，不嵌 HTML / WebView。
Widget buildNativePage(String path, Map<String, String> query, OpenRoute open) {
  switch (path) {
    case '/index':
    case '/dashboard':
      return DashboardPage(open: open);
    case '/portal':
      return PortalPage(open: open);
    case '/user/profile':
      return const ProfilePage();

    case '/market/heat':
      return MarketHeatPage(open: open);
    case '/market/board':
      return MarketBoardPage(open: open);
    case '/market/stocks':
      return MarketStocksPage(open: open);
    case '/market/watchlist':
      return MarketWatchlistPage(open: open);
    case '/market/finance-news':
      return const MarketNewsPage();
    case '/market/ai-workbench':
      return const MarketAiWorkbenchPage();
    case '/market/recommendations':
      return const MarketRecommendationsPage();
    case '/market/review':
      return const MarketReviewPage();
    case '/market/kline':
    case '/market/tradingview':
      return MarketKlinePage(
        symbol: query['symbol'] ?? 'AAPL',
        market: query['market'] ?? 'US',
        open: open,
      );
    case '/market/symbol':
      return MarketSymbolPage(
        symbol: query['symbol'] ?? 'AAPL',
        market: query['market'] ?? 'US',
        open: open,
      );
    case '/market/coverage':
      return const MarketCoveragePage();
    case '/market/stock-pool':
      return MarketStockPoolPage(open: open);
    case '/market/dashboard':
      return MarketHeatPage(open: open);
    case '/market/terminal':
    case '/trade/terminal':
      return const TradeTerminalPage();

    case '/quant/strategy':
      return QuantStrategyPage(open: open);
    case '/quant/factor':
      return const QuantFactorPage();
    case '/quant/scan-runs':
      return QuantScanRunsPage(open: open);
    case '/quant/scan-result':
      return QuantScanResultPage(cycleId: query['cycleId']);
    case '/quant/daily-list':
      return QuantDailyListPage(open: open);
    case '/quant/strategy-config':
      return QuantStrategyConfigPage(open: open);
    case '/quant/longbridge':
      return const QuantLongbridgePage();
    case '/quant/alpha-snapshot':
      return const QuantAlphaPage();
    case '/quant/risk':
      return const QuantRiskPage();
    case '/quant/watchlist':
      return QuantWatchlistPage(open: open);

    case '/trade/desk':
      return const TradeDeskHost();
    case '/trade/trading':
      return TradeTradingPage(
        symbol: query['symbol'] ?? 'AAPL',
        market: query['market'] ?? 'US',
      );
    case '/trade/positions':
      return TradePositionsPage(open: open);
    case '/trade/orders':
      return const TradeOrdersPage();
    case '/trade/broker':
      return TradeBrokerPage(open: open);
    case '/trade/risk':
      return const TradeRiskPage();
    case '/trade/risk-review':
      return const TradeRiskReviewPage();
    case '/trade/backtest':
      return const TradeBacktestPage();
    case '/trade/notifications':
      return const TradeNotificationsPage();
    case '/trade/ai-runs':
      return const TradeAiRunsPage();
    case '/trade/feishu-push':
      return const TradeFeishuPage();

    case '/sentiment/dashboard':
      return const SentimentDashboardPage();
    case '/sentiment/news':
      return const SentimentNewsPage();
    case '/sentiment/analysis':
      return const SentimentAnalysisPage();
    case '/sentiment/config':
      return const SentimentConfigPage();

    case '/ai/chat':
      return const AiChatPage();
    case '/ai/model':
      return const AiModelPage();
    case '/ai/req-chat':
      return const AiReqChatPage();
    case '/ai/req-list':
      return const AiReqListPage();
    case '/ai/req-bot':
      return const AiReqBotPage();

    case '/analysis/jobs':
      return const AnalysisJobsPage();

    case '/system/user':
      return const SystemUserPage();
    case '/system/role':
      return const SystemRolePage();
    case '/system/menu':
      return const SystemMenuPage();
    case '/system/dept':
      return const SystemDeptPage();
    case '/system/post':
      return const SystemPostPage();
    case '/system/dict':
      return const SystemDictPage();
    case '/system/config':
      return const SystemConfigPage();
    case '/system/notice':
      return const SystemNoticePage();

    case '/monitor/online':
      return const MonitorOnlinePage();
    case '/monitor/job':
      return MonitorJobPage(open: open);
    case '/monitor/job-log':
      return MonitorJobLogPage(jobId: query['jobId']);
    case '/monitor/operlog':
      return const MonitorOperlogPage();
    case '/monitor/logininfor':
      return const MonitorLoginPage();
    case '/monitor/server':
      return const MonitorServerPage();
    case '/monitor/cache':
      return const MonitorCachePage();
    case '/monitor/cacheList':
      return const MonitorCacheListPage();
    case '/monitor/druid':
      return const MonitorDruidPage();
    case '/monitor/transportCrypto':
      return const MonitorCryptoPage();

    case '/tool/gen':
      return const ToolGenPage();
    case '/tool/build':
      return const ToolBuildPage();
    case '/tool/swagger':
      return const ToolSwaggerPage();

    default:
      if (path.startsWith('/http')) {
        return JsonDetailPage(title: path, path: path);
      }
      return UnknownRoutePage(path);
  }
}

String defaultTitleFor(String path) {
  const titles = {
    '/index': '工作台首页',
    '/portal': '子系统门户',
    '/user/profile': '个人中心',
    '/market/heat': '市场热度',
    '/market/board': '行情台',
    '/market/stocks': '全部股票',
    '/market/watchlist': '自选清单',
    '/market/finance-news': '财经资讯',
    '/market/ai-workbench': 'AI研判',
    '/market/recommendations': '智能选股',
    '/market/review': '市场分析',
    '/market/kline': '行情K线',
    '/market/symbol': '标的详情',
    '/market/coverage': '行情覆盖',
    '/market/stock-pool': '标的股票池',
    '/market/tradingview': '高级图表',
    '/market/dashboard': '行情概览',
    '/quant/strategy': '策略信号',
    '/quant/factor': '因子分析',
    '/quant/scan-runs': '扫描台账',
    '/quant/scan-result': '扫描结果',
    '/quant/daily-list': '次日策略清单',
    '/quant/strategy-config': '策略配置',
    '/quant/longbridge': '长桥配置',
    '/quant/alpha-snapshot': 'Alpha快照',
    '/quant/risk': '风险概览',
    '/quant/watchlist': '自选池',
    '/market/terminal': '行情交易',
    '/trade/terminal': '行情交易',
    '/trade/desk': '交易工作台',
    '/trade/trading': '交易台',
    '/trade/positions': '持仓',
    '/trade/orders': '订单',
    '/trade/broker': '券商账户',
    '/trade/risk': '风控管理',
    '/trade/risk-review': '风险复核',
    '/trade/backtest': '策略回测',
    '/trade/notifications': '通知中心',
    '/trade/ai-runs': 'AI交易台账',
    '/trade/feishu-push': '飞书推送',
    '/sentiment/dashboard': '舆情大盘',
    '/sentiment/news': '资讯列表',
    '/sentiment/analysis': '分析历史',
    '/sentiment/config': '舆情配置',
    '/ai/chat': 'AI 对话',
    '/ai/model': 'AI模型',
    '/ai/req-chat': '需求沟通',
    '/ai/req-list': 'AI需求清单',
    '/ai/req-bot': 'AI机器人',
    '/analysis/jobs': '自动分析任务',
    '/system/user': '用户管理',
    '/system/role': '角色管理',
    '/system/menu': '菜单管理',
    '/system/dept': '部门管理',
    '/system/post': '岗位管理',
    '/system/dict': '字典管理',
    '/system/config': '参数设置',
    '/system/notice': '通知公告',
    '/monitor/online': '在线用户',
    '/monitor/job': '定时任务',
    '/monitor/job-log': '调度日志',
    '/monitor/operlog': '操作日志',
    '/monitor/logininfor': '登录日志',
    '/monitor/server': '服务监控',
    '/monitor/cache': '缓存监控',
    '/monitor/cacheList': '缓存列表',
    '/monitor/druid': '数据监控',
    '/monitor/transportCrypto': '传输加密',
    '/tool/gen': '代码生成',
    '/tool/build': '表单构建',
    '/tool/swagger': '系统接口',
  };
  return titles[path] ?? path;
}
