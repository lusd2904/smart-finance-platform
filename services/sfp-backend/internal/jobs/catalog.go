package jobs

import "fmt"

type QueueName string

const (
	QueueMarket QueueName = "market"
	QueueQuant  QueueName = "quant"
	QueueLLM    QueueName = "llm"
)

var queueKeys = map[QueueName]string{
	QueueMarket: "sfp:job:queue:market",
	QueueQuant:  "sfp:job:queue:quant",
	QueueLLM:    "sfp:job:queue:llm",
}

var jobGroups = map[string]QueueName{
	"market_sync":         QueueMarket,
	"finance_briefings":   QueueMarket,
	"board_warmup":        QueueMarket,
	"symbol_content":      QueueMarket,
	"market_heat_collect": QueueMarket,
	"eod_kline_sync":      QueueMarket,
	"listings_sync":       QueueMarket,
	"klines_slow":         QueueMarket,
	"mysql_to_influx":     QueueMarket,
	"factor_scan":         QueueQuant,
	"factor_qc":           QueueQuant,
	"indicator_refresh":   QueueQuant,
	"strategy_run":        QueueQuant,
	"position_monitor":    QueueQuant,
	"daily_list_scan":     QueueQuant,
	"daily_list_open":     QueueQuant,
	"auto_trade_scan":     QueueQuant,
	"sentiment_collect":   QueueLLM,
	"sentiment_analyze":   QueueLLM,
	"watchlist_analyze":   QueueLLM,
	"daily_review":        QueueLLM,
	"req_send":            QueueLLM,
	"req_summarize":       QueueLLM,
	"feishu_push":         QueueLLM,
	"stock_pick_run":      QueueLLM,
	"market_review":       QueueLLM,
	"ai_analyze":          QueueLLM,
	"ai_batch":            QueueLLM,
	"user_notice":         QueueLLM,
}

// NativeGoWorkerTypes are handled by Go workers via Redis; /internal/jobs/run enqueues them.
var NativeGoWorkerTypes = map[string]bool{
	"market_sync": true, "eod_kline_sync": true, "klines_slow": true, "mysql_to_influx": true,
	"board_warmup": true, "listings_sync": true, "finance_briefings": true,
	"market_heat_collect": true, "symbol_content": true,
	"indicator_refresh": true, "factor_scan": true, "factor_qc": true, "strategy_run": true,
	"daily_list_scan": true, "position_monitor": true, "daily_list_open": true, "auto_trade_scan": true,
	"feishu_push": true,
	"sentiment_collect": true, "sentiment_analyze": true, "daily_review": true,
	"req_send": true, "req_summarize": true, "user_notice": true,
	"watchlist_analyze": true, "stock_pick_run": true, "market_review": true,
	"ai_analyze": true, "ai_batch": true,
}

// IntelBridgeTypes is reserved for a future Go intel hop. Slim default is empty
// (no Python sentiment-intel container is required).
var IntelBridgeTypes = map[string]bool{}

// QuantBridgeTypes are synchronous jobs forwarded to STRATEGY_EVAL_URL
// (Go-to-Go). Slim default leaves that URL empty unless configured.
var QuantBridgeTypes = map[string]bool{
	"strategy_evaluate": true,
}

func GroupFor(jobType string) QueueName {
	if q, ok := jobGroups[jobType]; ok {
		return q
	}
	return QueueMarket
}

func KnownType(jobType string) bool {
	_, ok := jobGroups[jobType]
	return ok || QuantBridgeTypes[jobType]
}

func QueueKey(q QueueName) string {
	return queueKeys[q]
}

func IsDelegatable(jobType string) bool {
	return NativeGoWorkerTypes[jobType] || IntelBridgeTypes[jobType] || QuantBridgeTypes[jobType]
}

func BridgeLabel(jobType string) string {
	if IntelBridgeTypes[jobType] {
		return "intel-internal-jobs"
	}
	if QuantBridgeTypes[jobType] {
		return "internal-jobs"
	}
	if NativeGoWorkerTypes[jobType] {
		return "redis-go-worker"
	}
	return ""
}

func ValidateType(jobType string) error {
	if !IsDelegatable(jobType) {
		return fmt.Errorf("unknown or non-delegatable job type: %s", jobType)
	}
	return nil
}
