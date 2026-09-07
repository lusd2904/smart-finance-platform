package queue

import (
	"encoding/json"
	"testing"
)

func TestEncodeDecodeRoundtrip(t *testing.T) {
	raw, err := Encode("eod_kline_sync", map[string]interface{}{"market": "US"})
	if err != nil {
		t.Fatalf("encode: %v", err)
	}
	job, err := Decode(raw)
	if err != nil {
		t.Fatalf("decode: %v", err)
	}
	if job.Type != "eod_kline_sync" {
		t.Fatalf("type mismatch: %s", job.Type)
	}
	if job.Payload["market"] != "US" {
		t.Fatalf("payload mismatch: %v", job.Payload)
	}
	if job.Queue != "market" {
		t.Fatalf("queue=%s", job.Queue)
	}
}

func TestDecodeRejectsUnknownType(t *testing.T) {
	raw, _ := json.Marshal(map[string]interface{}{"type": "factor_scan", "payload": map[string]interface{}{}})
	if _, err := Decode(string(raw)); err == nil {
		t.Fatal("expected error for quant job on market worker")
	}
}

func TestMarketJobTypes(t *testing.T) {
	for _, jobType := range []string{
		"market_sync", "eod_kline_sync", "klines_slow", "mysql_to_influx", "market_heat_collect",
	} {
		if !marketJobTypes[jobType] {
			t.Fatalf("missing job type %s", jobType)
		}
	}
}
