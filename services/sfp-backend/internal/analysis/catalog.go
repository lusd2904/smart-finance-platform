package analysis

import (
	"fmt"
	"strings"
)

type JobSpec struct {
	JobID         int
	Code          string
	Category      string
	Title         string
	Description   string
	InvokeTarget  string
	DefaultCron   string
	ScheduleLabel string
	Heavy         bool
	QueueType     string
	DefaultStatus string
}

var CategoryLabels = map[string]string{
	"market": "行情", "quant": "量化", "sentiment": "舆情", "trade": "交易",
}

var Catalog = []JobSpec{
	{100, "sentiment_collect", "sentiment", "舆情采集与AI分析", "采集财经资讯并调用模型给出美/港/A 影响研判。", "module_task.sentiment_task.collect_and_analyze_job", "0 0/10 * * * ?", "每 10 分钟", true, "sentiment_collect", "0"},
	{101, "market_sync", "market", "行情数据每日同步", "收盘后增量同步目标标的近十年行情到 InfluxDB。", "module_task.market_task.sync_market_job", "0 30 5 * * ?", "每天 05:30", true, "market_sync", "0"},
	{102, "quant_strategy", "quant", "量化策略每日运行", "对自选池按策略档位扫描并生成买卖信号。", "module_task.quant_task.run_strategy_job", "0 0 6 * * ?", "每天 06:00", true, "strategy_run", "1"},
	{103, "finance_briefings", "market", "财经资讯简报刷新", "聚合内部简报与外部新闻，写入财经资讯流。", "module_task.market_task.refresh_finance_briefings_job", "0 15 * * * ?", "每小时第 15 分钟", false, "finance_briefings", "0"},
	{104, "symbol_content", "market", "标的内容缓存刷新", "刷新热门标的公告、资讯与讨论缓存，需长桥凭证。", "module_task.market_task.refresh_symbol_content_job", "0 0/30 * * * ?", "每 30 分钟", false, "symbol_content", "1"},
	{105, "factor_scan", "quant", "全市场因子日扫", "收盘后计算 Alpha101/158 与八大因子族，写入读模型快照。", "module_task.quant_task.run_daily_factor_scan_job", "0 10 6 * * ?", "每天 06:10", true, "factor_scan", "1"},
	{106, "position_monitor", "quant", "持仓止损监控", "检查持仓浮亏，超阈值写入风控事件。", "module_task.quant_task.run_position_monitor_job", "0 0/10 * * * ?", "每 10 分钟", false, "position_monitor", "0"},
	{107, "indicator_refresh", "quant", "行情指标快照刷新", "刷新目标池最新价与涨跌快照，供看板首屏读取。", "module_task.quant_task.run_indicator_refresh_job", "0 0/15 * * * ?", "每 15 分钟", true, "indicator_refresh", "0"},
	{108, "factor_qc", "quant", "因子质检 IC/IR", "对股票池做截面 IC/IR 与五分位收益质检。", "module_task.quant_task.run_factor_qc_job", "0 40 6 * * ?", "每天 06:40", true, "factor_qc", "1"},
	{109, "watchlist_analyze", "market", "自选清单小时分析", "综合技术指标、长桥资讯与舆情，对行情自选给出建议。", "module_task.market_task.analyze_watchlist_job", "0 20 * * * ?", "每小时第 20 分钟", true, "watchlist_analyze", "0"},
	{112, "auto_trade_scan", "trade", "自动交易扫描", "全局调度：扫描美/港热度 Top50（叠加各账户美/港自选）。", "module_task.trade_task.run_auto_trade_scan_job", "0 0/15 * * * ?", "每 15 分钟", true, "auto_trade_scan", "1"},
	{113, "market_heat_cn", "market", "A股收盘热度采集", "A股收盘后拉取指数/成交额/A-D 并生成 Top50 快照。", "module_task.market_task.collect_market_heat_cn_job", "0 5 7 * * ?", "每天 07:05", true, "market_heat_collect", "0"},
	{114, "market_heat_hk", "market", "港股收盘热度采集", "港股收盘后拉取指数/成交额/A-D 并生成 Top50 快照。", "module_task.market_task.collect_market_heat_hk_job", "0 5 8 * * ?", "每天 08:05", true, "market_heat_collect", "0"},
	{115, "market_heat_us", "market", "美股收盘热度采集", "美股收盘后拉取指数/成交额/A-D 并生成 Top50 快照。", "module_task.market_task.collect_market_heat_us_job", "0 5 21 * * ?", "每天 21:05", true, "market_heat_collect", "0"},
	{116, "daily_list_scan", "quant", "收盘后扫描次日策略清单", "A股收盘后扫描策略结果，生成下一交易日清单。", "module_task.quant_task.run_daily_list_scan_job", "0 20 7 * * ?", "每天 07:20", true, "daily_list_scan", "0"},
	{117, "feishu_push", "trade", "飞书策略摘要推送", "按用户时区与交易日历推送次日策略摘要到飞书。", "module_task.trade_task.run_feishu_push_job", "0 0/5 * * * ?", "每 5 分钟", false, "feishu_push", "0"},
	{118, "daily_list_open", "trade", "开盘执行排队模拟单", "A股开盘后把排队的长桥模拟开仓送到券商。", "module_task.quant_task.run_daily_list_open_job", "0 31 1 * * ?", "每天 01:31", true, "daily_list_open", "0"},
	{119, "stock_pick_run", "market", "全市场智能选股", "结合指标、舆情与开盘指数生成选股单。", "module_task.market_task.run_stock_pick_job", "0 50 7,8,21 * * ?", "每天 15:50 / 16:50 / 05:50 北京时间", true, "stock_pick_run", "0"},
	{121, "eod_kline_cn", "market", "A股收盘拉日K与分时", "15:00 收盘后增量日K与分时写入时序库。", "module_task.market_task.eod_kline_sync_cn_job", "0 25 7 * * ?", "每天 15:25 北京时间", true, "eod_kline_sync", "0"},
	{122, "eod_kline_hk", "market", "港股收盘拉日K与分时", "16:00 收盘后增量日K与分时写入时序库。", "module_task.market_task.eod_kline_sync_hk_job", "0 25 8 * * ?", "每天 16:25 北京时间", true, "eod_kline_sync", "0"},
	{123, "eod_kline_us", "market", "美股收盘拉日K与分时", "美股收盘后增量日K与分时写入时序库。", "module_task.market_task.eod_kline_sync_us_job", "0 25 21 * * ?", "每天 05:25 北京时间", true, "eod_kline_sync", "0"},
}

var ByID = map[int]JobSpec{}

func init() {
	for _, spec := range Catalog {
		ByID[spec.JobID] = spec
	}
}

func CategoryLabel(category string) string {
	if label, ok := CategoryLabels[category]; ok {
		return label
	}
	return category
}

func HumanizeCron(expr string) string {
	parts := stringsSplit(expr)
	if len(parts) < 6 {
		if expr == "" {
			return "--"
		}
		return expr
	}
	minute, hour, day := parts[1], parts[2], parts[3]
	dayAny := day == "*" || day == "?"
	if idx := stringsIndex(minute, "/"); idx >= 0 && hour == "*" && dayAny {
		step := minute[idx+1:]
		return "每 " + step + " 分钟"
	}
	if hour != "*" && minute != "" && dayAny {
		if h, m := atoi(hour), atoi(minute); h >= 0 && m >= 0 {
			return fmt.Sprintf("每天 %02d:%02d", h, m)
		}
	}
	if hour == "*" && minute != "" && dayAny {
		if m := atoi(minute); m >= 0 {
			return fmt.Sprintf("每小时第 %d 分钟", m)
		}
	}
	if expr == "" {
		return "--"
	}
	return expr
}

func stringsSplit(s string) []string {
	return strings.FieldsFunc(strings.TrimSpace(s), func(r rune) bool { return r == ' ' || r == '\t' })
}

func stringsIndex(s, sub string) int {
	return strings.Index(s, sub)
}

func atoi(s string) int {
	n := 0
	for _, ch := range s {
		if ch < '0' || ch > '9' {
			return -1
		}
		n = n*10 + int(ch-'0')
	}
	return n
}
