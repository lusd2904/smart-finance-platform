package scheduler

import (
	"context"
	"encoding/json"
	"testing"

	"github.com/alicebob/miniredis/v2"
	"github.com/redis/go-redis/v9"
)

func TestJobsLiteSnapshotAlive(t *testing.T) {
	mr, err := miniredis.Run()
	if err != nil {
		t.Fatal(err)
	}
	defer mr.Close()
	rdb := redis.NewClient(&redis.Options{Addr: mr.Addr()})
	rt := New(rdb)
	hb := map[string]interface{}{
		"alive": true, "queueDepth": 3, "running": []string{"job1"}, "ts": "2026-01-01 00:00:00",
	}
	raw, _ := json.Marshal(hb)
	_ = mr.Set("sfp:scheduler:heartbeat", string(raw))
	snap := JobsLiteSnapshot(context.Background(), rt)
	data, ok := snap["data"].(map[string]interface{})
	if !ok {
		t.Fatalf("missing data: %#v", snap)
	}
	if data["schedulerAlive"] != true {
		t.Fatalf("expected alive")
	}
	if data["queueDepth"] != 3 {
		t.Fatalf("queueDepth=%v", data["queueDepth"])
	}
}

func TestJobsLiteSnapshotFallbackDepth(t *testing.T) {
	mr, err := miniredis.Run()
	if err != nil {
		t.Fatal(err)
	}
	defer mr.Close()
	rdb := redis.NewClient(&redis.Options{Addr: mr.Addr()})
	rt := New(rdb)
	mr.Lpush("sfp:job:queue:llm", "x")
	mr.Lpush("sfp:job:queue:llm", "y")
	snap := JobsLiteSnapshot(context.Background(), rt)
	data := snap["data"].(map[string]interface{})
	if data["schedulerAlive"] != false {
		t.Fatalf("expected dead scheduler")
	}
	if data["queueDepth"] != 2 {
		t.Fatalf("queueDepth=%v", data["queueDepth"])
	}
}
