// Package jobs maps sys_job.invoke_target to the Redis queue payload that
// Python module_task.* enqueue functions already produce. The scheduler
// does not run job bodies.
package jobs

import (
	"encoding/json"
	"fmt"
	"strconv"
	"strings"
)

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

func QueueKey(q QueueName) string {
	return queueKeys[q]
}

type Spec struct {
	JobType  string
	Queue    QueueName
	Payload  map[string]any
	Known    bool
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

// EnabledProductionIDs are the sys_job ids currently enabled on cursor-1.
var EnabledProductionIDs = []int{101, 103, 104, 107, 113, 114, 115, 117, 121, 122, 123}

func GroupFor(jobType string) QueueName {
	if q, ok := jobGroups[jobType]; ok {
		return q
	}
	return QueueMarket
}

func KnownType(jobType string) bool {
	_, ok := jobGroups[jobType]
	return ok
}

// Resolve maps sys_job.invoke_target plus optional args/kwargs onto the
// Redis job type and payload workers consume. Canonical DB values are the
// bare Go keys (resolveGoKey). module_task.* aliases stay for one release
// after the SQL migration so mixed or rolled-back rows still enqueue.
func Resolve(invokeTarget, jobArgs, jobKwargs string) (Spec, error) {
	target := strings.TrimSpace(invokeTarget)
	args := splitArgs(jobArgs)
	kwargs := parseKwargs(jobKwargs)
	spec, ok := resolveTarget(target, args, kwargs)
	if !ok {
		return Spec{}, fmt.Errorf("unmapped invoke_target %q", target)
	}
	spec.Known = true
	if spec.Payload == nil {
		spec.Payload = map[string]any{}
	}
	spec.Queue = GroupFor(spec.JobType)
	return spec, nil
}

func resolveTarget(target string, args []string, kwargs map[string]any) (Spec, bool) {
	switch target {
	case "module_task.sentiment_task.collect_and_analyze_job":
		return Spec{JobType: "sentiment_collect", Payload: map[string]any{"analyze": true}}, true
	case "module_task.sentiment_task.collect_only_job":
		return Spec{JobType: "sentiment_collect", Payload: map[string]any{"analyze": false}}, true
	case "module_task.market_task.sync_market_job":
		return Spec{JobType: "market_sync", Payload: map[string]any{"years": 10}}, true
	case "module_task.market_task.sync_klines_slow_job":
		years := intFrom(kwargs, "years", firstArgInt(args, 10))
		return Spec{JobType: "klines_slow", Payload: map[string]any{"years": years}}, true
	case "module_task.market_task.sync_listings_job":
		return Spec{JobType: "listings_sync", Payload: map[string]any{}}, true
	case "module_task.market_task.refresh_finance_briefings_job":
		return Spec{JobType: "finance_briefings", Payload: map[string]any{}}, true
	case "module_task.market_task.refresh_symbol_content_job":
		return Spec{JobType: "symbol_content", Payload: map[string]any{}}, true
	case "module_task.market_task.analyze_watchlist_job":
		return Spec{JobType: "watchlist_analyze", Payload: map[string]any{}}, true
	case "module_task.market_task.analyze_market_review_job":
		markets := marketsFrom(args, kwargs)
		return Spec{JobType: "market_review", Payload: map[string]any{"markets": markets}}, true
	case "module_task.market_task.collect_market_heat_cn_job":
		return heatSpec("CN"), true
	case "module_task.market_task.collect_market_heat_hk_job":
		return heatSpec("HK"), true
	case "module_task.market_task.collect_market_heat_us_job":
		return heatSpec("US"), true
	case "module_task.market_task.eod_kline_sync_cn_job":
		return Spec{JobType: "eod_kline_sync", Payload: map[string]any{"market": "CN"}}, true
	case "module_task.market_task.eod_kline_sync_hk_job":
		return Spec{JobType: "eod_kline_sync", Payload: map[string]any{"market": "HK"}}, true
	case "module_task.market_task.eod_kline_sync_us_job":
		return Spec{JobType: "eod_kline_sync", Payload: map[string]any{"market": "US"}}, true
	case "module_task.market_task.run_stock_pick_job":
		return Spec{JobType: "stock_pick_run", Payload: map[string]any{"trigger": "schedule"}}, true
	case "module_task.quant_task.run_strategy_job":
		return Spec{JobType: "strategy_run", Payload: optionalProfileUser(args, kwargs)}, true
	case "module_task.quant_task.run_daily_factor_scan_job":
		profile := stringFrom(kwargs, "profile", firstArg(args, "balanced"))
		if profile == "" {
			profile = "balanced"
		}
		return Spec{JobType: "factor_scan", Payload: map[string]any{"profile": profile}}, true
	case "module_task.quant_task.run_position_monitor_job":
		return Spec{JobType: "position_monitor", Payload: map[string]any{}}, true
	case "module_task.quant_task.run_indicator_refresh_job":
		return Spec{JobType: "indicator_refresh", Payload: map[string]any{}}, true
	case "module_task.quant_task.run_factor_qc_job":
		market := stringFrom(kwargs, "market", firstArg(args, "US"))
		if market == "" {
			market = "US"
		}
		return Spec{JobType: "factor_qc", Payload: map[string]any{"market": market}}, true
	case "module_task.quant_task.run_daily_list_scan_job":
		payload := map[string]any{}
		if p := stringFrom(kwargs, "profile", firstArg(args, "")); p != "" {
			payload["profile"] = p
		}
		return Spec{JobType: "daily_list_scan", Payload: payload}, true
	case "module_task.quant_task.run_daily_list_open_job":
		return Spec{JobType: "daily_list_open", Payload: map[string]any{}}, true
	case "module_task.trade_task.run_auto_trade_scan_job":
		return Spec{JobType: "auto_trade_scan", Payload: optionalProfileUser(args, kwargs)}, true
	case "module_task.trade_task.run_feishu_push_job":
		return Spec{JobType: "feishu_push", Payload: map[string]any{}}, true
	default:
		return resolveGoKey(target, args, kwargs)
	}
}

// resolveGoKey is the canonical path: sys_job.invoke_target is the Redis job type.
// Python module_task.* strings above remain as a one-release safety net.
func resolveGoKey(target string, args []string, kwargs map[string]any) (Spec, bool) {
	if !KnownType(target) {
		return Spec{}, false
	}
	switch target {
	case "sentiment_collect":
		analyze := true
		if raw, ok := kwargs["analyze"]; ok {
			analyze = boolFrom(raw, true)
		}
		return Spec{JobType: target, Payload: map[string]any{"analyze": analyze}}, true
	case "market_sync":
		return Spec{JobType: target, Payload: map[string]any{"years": 10}}, true
	case "klines_slow":
		years := intFrom(kwargs, "years", firstArgInt(args, 10))
		return Spec{JobType: target, Payload: map[string]any{"years": years}}, true
	case "market_review":
		return Spec{JobType: target, Payload: map[string]any{"markets": marketsFrom(args, kwargs)}}, true
	case "market_heat_collect":
		market := strings.ToUpper(stringFrom(kwargs, "market", firstArg(args, "CN")))
		return heatSpec(market), true
	case "eod_kline_sync":
		market := strings.ToUpper(stringFrom(kwargs, "market", firstArg(args, "")))
		if market == "" {
			return Spec{}, false
		}
		return Spec{JobType: target, Payload: map[string]any{"market": market}}, true
	case "stock_pick_run":
		return Spec{JobType: target, Payload: map[string]any{"trigger": "schedule"}}, true
	case "strategy_run", "auto_trade_scan":
		return Spec{JobType: target, Payload: optionalProfileUser(args, kwargs)}, true
	case "factor_scan":
		profile := stringFrom(kwargs, "profile", firstArg(args, "balanced"))
		if profile == "" {
			profile = "balanced"
		}
		return Spec{JobType: target, Payload: map[string]any{"profile": profile}}, true
	case "factor_qc":
		market := stringFrom(kwargs, "market", firstArg(args, "US"))
		if market == "" {
			market = "US"
		}
		return Spec{JobType: target, Payload: map[string]any{"market": market}}, true
	case "daily_list_scan":
		payload := map[string]any{}
		if profile := stringFrom(kwargs, "profile", firstArg(args, "")); profile != "" {
			payload["profile"] = profile
		}
		return Spec{JobType: target, Payload: payload}, true
	default:
		return Spec{JobType: target, Payload: map[string]any{}}, true
	}
}

func heatSpec(market string) Spec {
	return Spec{
		JobType: "market_heat_collect",
		Payload: map[string]any{"market": market, "tradeDate": nil},
	}
}

func optionalProfileUser(args []string, kwargs map[string]any) map[string]any {
	payload := map[string]any{}
	profile := stringFrom(kwargs, "profile", firstArg(args, ""))
	if profile != "" {
		payload["profile"] = profile
	}
	if uid := intFrom(kwargs, "userId", 0); uid > 0 {
		payload["userId"] = uid
	}
	return payload
}

func marketsFrom(args []string, kwargs map[string]any) any {
	if raw, ok := kwargs["markets"]; ok && raw != nil {
		return normalizeMarkets(raw)
	}
	if raw, ok := kwargs["market"]; ok && raw != nil {
		return normalizeMarkets(raw)
	}
	if len(args) > 0 {
		return normalizeMarkets(args)
	}
	return nil
}

func normalizeMarkets(raw any) any {
	switch v := raw.(type) {
	case []any:
		out := make([]string, 0, len(v))
		for _, item := range v {
			s := strings.ToUpper(strings.TrimSpace(fmt.Sprint(item)))
			if s != "" {
				out = append(out, s)
			}
		}
		if len(out) == 0 {
			return nil
		}
		return out
	case []string:
		out := make([]string, 0, len(v))
		for _, item := range v {
			s := strings.ToUpper(strings.TrimSpace(item))
			if s != "" {
				out = append(out, s)
			}
		}
		if len(out) == 0 {
			return nil
		}
		return out
	default:
		text := strings.TrimSpace(fmt.Sprint(v))
		if text == "" || text == "<nil>" {
			return nil
		}
		parts := strings.Split(text, ",")
		out := make([]string, 0, len(parts))
		for _, p := range parts {
			s := strings.ToUpper(strings.TrimSpace(p))
			if s != "" {
				out = append(out, s)
			}
		}
		if len(out) == 0 {
			return nil
		}
		return out
	}
}

func splitArgs(raw string) []string {
	raw = strings.TrimSpace(raw)
	if raw == "" {
		return nil
	}
	parts := strings.Split(raw, ",")
	out := make([]string, 0, len(parts))
	for _, p := range parts {
		p = strings.TrimSpace(p)
		if p != "" {
			out = append(out, p)
		}
	}
	return out
}

func parseKwargs(raw string) map[string]any {
	raw = strings.TrimSpace(raw)
	if raw == "" || raw == "{}" {
		return map[string]any{}
	}
	var out map[string]any
	if err := json.Unmarshal([]byte(raw), &out); err != nil {
		return map[string]any{}
	}
	if out == nil {
		return map[string]any{}
	}
	return out
}

func firstArg(args []string, fallback string) string {
	if len(args) > 0 && strings.TrimSpace(args[0]) != "" {
		return strings.TrimSpace(args[0])
	}
	return fallback
}

func firstArgInt(args []string, fallback int) int {
	if len(args) == 0 {
		return fallback
	}
	n, err := strconv.Atoi(strings.TrimSpace(args[0]))
	if err != nil {
		return fallback
	}
	return n
}

func stringFrom(kwargs map[string]any, key, fallback string) string {
	if kwargs == nil {
		return fallback
	}
	raw, ok := kwargs[key]
	if !ok || raw == nil {
		return fallback
	}
	s := strings.TrimSpace(fmt.Sprint(raw))
	if s == "" || s == "<nil>" {
		return fallback
	}
	return s
}

func boolFrom(raw any, fallback bool) bool {
	switch v := raw.(type) {
	case bool:
		return v
	case string:
		switch strings.ToLower(strings.TrimSpace(v)) {
		case "1", "true", "yes", "on":
			return true
		case "0", "false", "no", "off":
			return false
		default:
			return fallback
		}
	default:
		return fallback
	}
}

func intFrom(kwargs map[string]any, key string, fallback int) int {
	if kwargs == nil {
		return fallback
	}
	raw, ok := kwargs[key]
	if !ok || raw == nil {
		return fallback
	}
	switch n := raw.(type) {
	case int:
		return n
	case int64:
		return int(n)
	case float64:
		return int(n)
	default:
		v, err := strconv.Atoi(strings.TrimSpace(fmt.Sprint(raw)))
		if err != nil {
			return fallback
		}
		return v
	}
}
