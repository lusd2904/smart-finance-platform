package queue

import (
	"context"
	"encoding/json"
	"io"
	"log/slog"
	"testing"
	"time"

	"github.com/alicebob/miniredis/v2"
	"github.com/redis/go-redis/v9"
)

func TestIsStaleClaim(t *testing.T) {
	vis := 30 * time.Second
	now := int64(1_000_000)
	if !isStaleClaim("", now, vis) {
		t.Fatal("missing claim should be stale (restart orphan)")
	}
	if !isStaleClaim("bad", now, vis) {
		t.Fatal("unparseable claim should be stale")
	}
	if isStaleClaim("999990", now, vis) {
		t.Fatal("fresh claim should not be stale")
	}
	if !isStaleClaim("999960", now, vis) {
		t.Fatal("expired claim should be stale")
	}
}

func TestRecoverStaleRequeuesOrphans(t *testing.T) {
	c, rdb, cleanup := newTestConsumer(t, 30*time.Second, 3)
	defer cleanup()
	ctx := context.Background()

	raw := mustJobRaw(t, "sentiment_analyze", "job-orphan", 0)
	if err := rdb.LPush(ctx, processingKey(), raw).Err(); err != nil {
		t.Fatal(err)
	}
	if err := c.recoverStale(ctx); err != nil {
		t.Fatal(err)
	}
	if n, _ := rdb.LLen(ctx, processingKey()).Result(); n != 0 {
		t.Fatalf("processing leftover=%d", n)
	}
	if n, _ := rdb.LLen(ctx, QueueKeyLLM).Result(); n != 1 {
		t.Fatalf("queue depth=%d", n)
	}
	queued, _ := rdb.LIndex(ctx, QueueKeyLLM, 0).Result()
	job, err := decode(queued)
	if err != nil {
		t.Fatal(err)
	}
	if job.Retries != 1 {
		t.Fatalf("retries=%d", job.Retries)
	}
}

func TestRecoverStaleSkipsFreshClaims(t *testing.T) {
	c, rdb, cleanup := newTestConsumer(t, 90*time.Second, 3)
	defer cleanup()
	ctx := context.Background()

	raw := mustJobRaw(t, "sentiment_analyze", "job-fresh", 0)
	_ = rdb.LPush(ctx, processingKey(), raw).Err()
	_ = rdb.HSet(ctx, ClaimsKey, "job-fresh", time.Now().Unix()).Err()
	if err := c.recoverStale(ctx); err != nil {
		t.Fatal(err)
	}
	if n, _ := rdb.LLen(ctx, processingKey()).Result(); n != 1 {
		t.Fatalf("fresh job should stay in processing, n=%d", n)
	}
	if n, _ := rdb.LLen(ctx, QueueKeyLLM).Result(); n != 0 {
		t.Fatalf("fresh job should not be requeued, n=%d", n)
	}
}

func TestRecoverStaleRequeuesExpiredClaims(t *testing.T) {
	c, rdb, cleanup := newTestConsumer(t, time.Second, 3)
	defer cleanup()
	ctx := context.Background()

	raw := mustJobRaw(t, "daily_review", "job-expired", 0)
	_ = rdb.LPush(ctx, processingKey(), raw).Err()
	_ = rdb.HSet(ctx, ClaimsKey, "job-expired", time.Now().Add(-2*time.Second).Unix()).Err()
	if err := c.recoverStale(ctx); err != nil {
		t.Fatal(err)
	}
	if n, _ := rdb.LLen(ctx, processingKey()).Result(); n != 0 {
		t.Fatalf("expired job should leave processing, n=%d", n)
	}
	if n, _ := rdb.LLen(ctx, QueueKeyLLM).Result(); n != 1 {
		t.Fatalf("expired job should be requeued, n=%d", n)
	}
	if exists, _ := rdb.HExists(ctx, ClaimsKey, "job-expired").Result(); exists {
		t.Fatal("reclaimed job should drop its claim")
	}
}

func TestRecoverStaleDeadLettersMaxRetries(t *testing.T) {
	c, rdb, cleanup := newTestConsumer(t, time.Second, 1)
	defer cleanup()
	ctx := context.Background()

	raw := mustJobRaw(t, "sentiment_collect", "job-dead", 1)
	_ = rdb.LPush(ctx, processingKey(), raw).Err()
	if err := c.recoverStale(ctx); err != nil {
		t.Fatal(err)
	}
	if n, _ := rdb.LLen(ctx, QueueKeyLLM).Result(); n != 0 {
		t.Fatalf("exhausted job should not requeue, n=%d", n)
	}
	if n, _ := rdb.LLen(ctx, deadKey()).Result(); n != 1 {
		t.Fatalf("exhausted job should dead-letter, n=%d", n)
	}
}

func TestEncodeDecodeRoundtrip(t *testing.T) {
	raw, err := Encode("sentiment_analyze", map[string]interface{}{"analyze": true})
	if err != nil {
		t.Fatal(err)
	}
	job, err := decode(raw)
	if err != nil {
		t.Fatal(err)
	}
	if job.Type != "sentiment_analyze" || job.Queue != group {
		t.Fatalf("job=%+v", job)
	}
}

func newTestConsumer(t *testing.T, visibility time.Duration, maxRetries int) (*Consumer, *redis.Client, func()) {
	t.Helper()
	mr, err := miniredis.Run()
	if err != nil {
		t.Fatal(err)
	}
	rdb := redis.NewClient(&redis.Options{Addr: mr.Addr()})
	logger := slog.New(slog.NewTextHandler(io.Discard, nil))
	c := NewConsumer(rdb, func(context.Context, Job) (interface{}, error) {
		return nil, nil
	}, visibility, maxRetries, time.Millisecond, time.Second, logger)
	return c, rdb, func() {
		_ = rdb.Close()
		mr.Close()
	}
}

func mustJobRaw(t *testing.T, jobType, jobID string, retries int) string {
	t.Helper()
	raw, err := json.Marshal(Job{
		Type:    jobType,
		JobID:   jobID,
		Queue:   group,
		Retries: retries,
		Payload: map[string]interface{}{},
	})
	if err != nil {
		t.Fatal(err)
	}
	return string(raw)
}
