package flow

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func sampleSectorJSON() []byte {
	payload := map[string]interface{}{
		"data": map[string]interface{}{
			"diff": []map[string]interface{}{
				{
					"f12":  "BK0477",
					"f14":  "酿酒行业",
					"f2":   100.5,
					"f3":   1.2,
					"f62":  1.5e8,
					"f184": 2.3,
					"f204": "贵州茅台",
					"f205": "600519",
				},
			},
		},
	}
	raw, _ := json.Marshal(payload)
	return raw
}

func TestFetchSectorsFallsBackToDelayHostOnPush2Failure(t *testing.T) {
	var hit []string
	push2 := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		hit = append(hit, "push2")
		w.WriteHeader(http.StatusBadGateway)
	}))
	defer push2.Close()

	delay := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		hit = append(hit, "delay")
		if !strings.Contains(r.URL.RawQuery, "fields=f12,f14,f2,f3,f62,f184,f204,f205") {
			t.Fatalf("unexpected fields query: %s", r.URL.RawQuery)
		}
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write(sampleSectorJSON())
	}))
	defer delay.Close()

	prevPush, prevDelay := eastmoneyPush2Base, eastmoneyDelayBase
	eastmoneyPush2Base, eastmoneyDelayBase = push2.URL, delay.URL
	t.Cleanup(func() {
		eastmoneyPush2Base, eastmoneyDelayBase = prevPush, prevDelay
	})

	svc := &Service{Client: http.DefaultClient}
	sectors := svc.fetchSectors("industry", 10)
	if len(sectors) != 1 {
		t.Fatalf("got %d sectors, want 1 after delay fallback: %v", len(sectors), sectors)
	}
	if sectors[0]["code"] != "BK0477" || sectors[0]["name"] != "酿酒行业" {
		t.Fatalf("mapped: %v", sectors[0])
	}
	if len(hit) < 2 || hit[0] != "push2" || hit[1] != "delay" {
		t.Fatalf("host order = %v, want [push2 delay]", hit)
	}
}

func TestFetchSectorsFallsBackToDelayHostOnEmptyDiff(t *testing.T) {
	var hit []string
	push2 := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		hit = append(hit, "push2")
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"data":{"diff":[]}}`))
	}))
	defer push2.Close()

	delay := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		hit = append(hit, "delay")
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write(sampleSectorJSON())
	}))
	defer delay.Close()

	prevPush, prevDelay := eastmoneyPush2Base, eastmoneyDelayBase
	eastmoneyPush2Base, eastmoneyDelayBase = push2.URL, delay.URL
	t.Cleanup(func() {
		eastmoneyPush2Base, eastmoneyDelayBase = prevPush, prevDelay
	})

	svc := &Service{Client: http.DefaultClient}
	sectors := svc.fetchSectors("industry", 5)
	if len(sectors) != 1 {
		t.Fatalf("got %d sectors, want 1 after empty-diff fallback", len(sectors))
	}
	if len(hit) != 2 || hit[0] != "push2" || hit[1] != "delay" {
		t.Fatalf("host order = %v, want [push2 delay]", hit)
	}
}

func TestFetchSectorsKeepsPush2WhenPopulated(t *testing.T) {
	var delayHits int
	push2 := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write(sampleSectorJSON())
	}))
	defer push2.Close()

	delay := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		delayHits++
		w.WriteHeader(http.StatusOK)
	}))
	defer delay.Close()

	prevPush, prevDelay := eastmoneyPush2Base, eastmoneyDelayBase
	eastmoneyPush2Base, eastmoneyDelayBase = push2.URL, delay.URL
	t.Cleanup(func() {
		eastmoneyPush2Base, eastmoneyDelayBase = prevPush, prevDelay
	})

	svc := &Service{Client: http.DefaultClient}
	sectors := svc.fetchSectors("industry", 5)
	if len(sectors) != 1 {
		t.Fatalf("got %d sectors, want 1 from push2", len(sectors))
	}
	if delayHits != 0 {
		t.Fatalf("delay host hit %d times, want 0 when push2 succeeds", delayHits)
	}
}
