package queue

import (
	"encoding/json"
	"testing"
	"time"

	"github.com/lusd2904/smart-finance-platform/services/sfp-scheduler/internal/jobs"
)

func TestEncodePayloadShapeMatchesPython(t *testing.T) {
	loc, err := time.LoadLocation("Asia/Shanghai")
	if err != nil {
		t.Fatal(err)
	}
	cases := []struct {
		id      int
		target  string
		kwargs  string
		jobType string
		queue   string
	}{
		{101, "market_sync", "", "market_sync", "market"},
		{103, "finance_briefings", "", "finance_briefings", "market"},
		{104, "symbol_content", "", "symbol_content", "market"},
		{107, "indicator_refresh", "", "indicator_refresh", "quant"},
		{113, "market_heat_collect", `{"market":"CN"}`, "market_heat_collect", "market"},
		{114, "market_heat_collect", `{"market":"HK"}`, "market_heat_collect", "market"},
		{115, "market_heat_collect", `{"market":"US"}`, "market_heat_collect", "market"},
		{117, "feishu_push", "", "feishu_push", "llm"},
		{121, "eod_kline_sync", `{"market":"CN"}`, "eod_kline_sync", "market"},
		{122, "eod_kline_sync", `{"market":"HK"}`, "eod_kline_sync", "market"},
		{123, "eod_kline_sync", `{"market":"US"}`, "eod_kline_sync", "market"},
	}
	for _, tc := range cases {
		spec, err := jobs.Resolve(tc.target, "", tc.kwargs)
		if err != nil {
			t.Fatalf("job %d resolve: %v", tc.id, err)
		}
		raw, job, err := Encode(spec.JobType, spec.Payload, loc, "abc123def456")
		if err != nil {
			t.Fatalf("job %d encode: %v", tc.id, err)
		}
		var decoded map[string]any
		if err := json.Unmarshal([]byte(raw), &decoded); err != nil {
			t.Fatalf("job %d json: %v", tc.id, err)
		}
		for _, key := range []string{"type", "payload", "jobId", "queue", "enqueuedAt"} {
			if _, ok := decoded[key]; !ok {
				t.Fatalf("job %d missing key %s in %s", tc.id, key, raw)
			}
		}
		if decoded["type"] != tc.jobType {
			t.Fatalf("job %d type=%v", tc.id, decoded["type"])
		}
		if decoded["queue"] != tc.queue {
			t.Fatalf("job %d queue=%v", tc.id, decoded["queue"])
		}
		if decoded["jobId"] != "abc123def456" {
			t.Fatalf("job %d jobId=%v", tc.id, decoded["jobId"])
		}
		if _, err := time.ParseInLocation(TimeLayout, job.EnqueuedAt, loc); err != nil {
			t.Fatalf("job %d enqueuedAt %q: %v", tc.id, job.EnqueuedAt, err)
		}
		roundtrip, err := Decode(raw)
		if err != nil {
			t.Fatalf("job %d decode: %v", tc.id, err)
		}
		if roundtrip.Type != tc.jobType || roundtrip.Queue != tc.queue {
			t.Fatalf("job %d roundtrip %#v", tc.id, roundtrip)
		}
	}
}

func TestEncodeHeatPayloadKeepsNullTradeDate(t *testing.T) {
	spec, err := jobs.Resolve("market_heat_collect", "", `{"market":"US"}`)
	if err != nil {
		t.Fatal(err)
	}
	raw, _, err := Encode(spec.JobType, spec.Payload, time.UTC, "heat1")
	if err != nil {
		t.Fatal(err)
	}
	var decoded map[string]any
	if err := json.Unmarshal([]byte(raw), &decoded); err != nil {
		t.Fatal(err)
	}
	payload, _ := decoded["payload"].(map[string]any)
	if payload["market"] != "US" {
		t.Fatalf("market=%v", payload["market"])
	}
	if payload["tradeDate"] != nil {
		t.Fatalf("tradeDate=%v want null", payload["tradeDate"])
	}
}

func TestEncodeRejectsUnknownType(t *testing.T) {
	if _, _, err := Encode("not_a_job", map[string]any{}, time.UTC, ""); err == nil {
		t.Fatal("expected error")
	}
}

func TestQueueKeys(t *testing.T) {
	if jobs.QueueKey(jobs.QueueMarket) != "sfp:job:queue:market" {
		t.Fatal(jobs.QueueKey(jobs.QueueMarket))
	}
	if jobs.QueueKey(jobs.QueueQuant) != "sfp:job:queue:quant" {
		t.Fatal(jobs.QueueKey(jobs.QueueQuant))
	}
	if jobs.QueueKey(jobs.QueueLLM) != "sfp:job:queue:llm" {
		t.Fatal(jobs.QueueKey(jobs.QueueLLM))
	}
}
