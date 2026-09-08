package jobqueue

import (
	"encoding/json"
	"testing"
)

func TestEncodeDecodeRoundTrip(t *testing.T) {
	payload := map[string]interface{}{
		"market":    "US",
		"tradeDate": "2026-01-02",
		"years":     float64(10),
	}
	raw, err := Encode("market_sync", payload, "abc123def4567890abcdef7890abcd")
	if err != nil {
		t.Fatalf("encode: %v", err)
	}
	job, err := Decode(raw)
	if err != nil {
		t.Fatalf("decode: %v", err)
	}
	if job.Type != "market_sync" {
		t.Fatalf("type=%q", job.Type)
	}
	if job.JobID != "abc123def4567890abcdef7890abcd" {
		t.Fatalf("jobId=%q", job.JobID)
	}
	if job.Queue != "market" {
		t.Fatalf("queue=%q", job.Queue)
	}
	if job.Payload["market"] != "US" {
		t.Fatalf("payload market=%v", job.Payload["market"])
	}
}

func TestEncodeUnknownJob(t *testing.T) {
	_, err := Encode("not_a_real_job", nil, "")
	if err == nil {
		t.Fatal("expected error")
	}
}

func TestDecodeInvalidJSON(t *testing.T) {
	if _, err := Decode("{not json"); err == nil {
		t.Fatal("expected error")
	}
}

func TestDecodeUnknownType(t *testing.T) {
	raw, _ := json.Marshal(map[string]interface{}{
		"type":   "bogus",
		"jobId":  "x",
		"queue":  "market",
		"payload": map[string]interface{}{},
	})
	if _, err := Decode(string(raw)); err == nil {
		t.Fatal("expected error")
	}
}

func TestTicketView(t *testing.T) {
	job := &Job{Type: "ai_analyze", JobID: "deadbeef", Queue: "llm", EnqueuedAt: "2026-01-01 12:00:00"}
	ticket := TicketView(job, "queued")
	if ticket["status"] != "queued" || ticket["queue"] != "llm" {
		t.Fatalf("ticket=%v", ticket)
	}
}

func TestGroupForAndQueueKey(t *testing.T) {
	if GroupFor("factor_scan") != "quant" {
		t.Fatal("factor_scan group")
	}
	if QueueKeyFor("watchlist_analyze") != QueueLLM {
		t.Fatal("watchlist queue")
	}
}

func TestKnownJobsMatchesPython(t *testing.T) {
	expected := []string{
		"market_sync", "finance_briefings", "board_warmup", "symbol_content",
		"market_heat_collect", "factor_scan", "factor_qc", "indicator_refresh",
		"strategy_run", "position_monitor", "sentiment_collect", "sentiment_analyze",
		"watchlist_analyze", "daily_review", "req_send", "req_summarize",
		"daily_list_scan", "daily_list_open", "auto_trade_scan", "feishu_push",
		"stock_pick_run", "eod_kline_sync", "market_review", "ai_analyze", "ai_batch",
		"listings_sync", "klines_slow", "mysql_to_influx", "user_notice",
	}
	for _, name := range expected {
		if _, ok := KnownJobs[name]; !ok {
			t.Fatalf("missing job %s", name)
		}
	}
	if len(KnownJobs) != len(expected) {
		t.Fatalf("KnownJobs count=%d expected=%d", len(KnownJobs), len(expected))
	}
}
