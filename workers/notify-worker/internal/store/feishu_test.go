package store

import (
	"testing"
	"time"

	"github.com/lusd2904/smart-finance-platform/workers/notify-worker/internal/timeutil"
)

func TestDueNowUsesShanghaiWhenTimezoneInvalid(t *testing.T) {
	// 18:32 CST = 10:32 UTC
	now := time.Date(2026, 9, 3, 10, 32, 0, 0, time.UTC)
	if !dueNow("18:30", "Invalid/Timezone", now) {
		t.Fatal("dueNow should fall back to Shanghai for invalid timezone")
	}
}

func TestDueNowRespectsPushWindow(t *testing.T) {
	now := time.Date(2026, 9, 3, 10, 31, 0, 0, time.UTC) // 18:31 CST
	if !dueNow("18:30", timeutil.ShanghaiTZ, now) {
		t.Fatal("expected push window to match 18:30-18:34 CST")
	}
	early := time.Date(2026, 9, 3, 10, 20, 0, 0, time.UTC) // 18:20 CST
	if dueNow("18:30", timeutil.ShanghaiTZ, early) {
		t.Fatal("18:20 CST should be before push window")
	}
}
