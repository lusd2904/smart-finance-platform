package influx

import (
	"context"
	"errors"
	"net"
	"net/http"
	"sync/atomic"
	"testing"
	"time"

	"github.com/lusd2904/smart-finance-platform/workers/market-worker/internal/config"
)

type roundTripFunc func(*http.Request) (*http.Response, error)

func (f roundTripFunc) RoundTrip(req *http.Request) (*http.Response, error) {
	return f(req)
}

func sampleWriteBar() Bar {
	return Bar{
		Symbol:    "AAPL",
		TradeDate: time.Date(2026, 9, 15, 0, 0, 0, 0, time.UTC),
		Open:      1, High: 2, Low: 0.5, Close: 1.5, Volume: 10,
	}
}

func enabledCfg() config.Config {
	return config.Config{
		InfluxURL:       "http://sentiment-influxdb:8086",
		InfluxToken:     "tok",
		InfluxOrg:       "longbridge",
		InfluxBucketUS:  "market_us",
		InfluxDualWrite: "1",
	}
}

func TestNewWriterDisabledByDefault(t *testing.T) {
	w, err := NewWriter(config.Config{InfluxURL: "http://sentiment-influxdb:8086", InfluxToken: "tok"})
	if err != nil {
		t.Fatal(err)
	}
	if w != nil {
		t.Fatal("dual-write must stay off unless INFLUX_DUAL_WRITE is set")
	}
}

func TestNewWriterEmptyTokenIsNotFatal(t *testing.T) {
	w, err := NewWriter(config.Config{InfluxDualWrite: "1", InfluxURL: "http://sentiment-influxdb:8086"})
	if err != nil || w != nil {
		t.Fatalf("missing token must skip writer, got w=%v err=%v", w, err)
	}
}

func TestWriteSkipsWhenDisabled(t *testing.T) {
	var calls atomic.Int32
	w := &Writer{
		cfg: enabledCfg(),
		client: &http.Client{Transport: roundTripFunc(func(*http.Request) (*http.Response, error) {
			calls.Add(1)
			return nil, errors.New("should not be called")
		})},
	}
	w.disabled.Store(true)
	n, err := w.WriteMinute(context.Background(), "US", []Bar{sampleWriteBar()})
	if err != nil || n != 0 || calls.Load() != 0 {
		t.Fatalf("n=%d err=%v calls=%d", n, err, calls.Load())
	}
}

func TestWriteDisablesAfterDNSError(t *testing.T) {
	var calls atomic.Int32
	w := &Writer{
		cfg: enabledCfg(),
		client: &http.Client{Transport: roundTripFunc(func(*http.Request) (*http.Response, error) {
			calls.Add(1)
			return nil, &net.DNSError{Err: "no such host", Name: "sentiment-influxdb", IsNotFound: true}
		})},
	}
	n, err := w.WriteDaily(context.Background(), "US", []Bar{sampleWriteBar()})
	if err != nil || n != 0 {
		t.Fatalf("unavailable must not surface: n=%d err=%v", n, err)
	}
	if !w.disabled.Load() {
		t.Fatal("writer must circuit-break after DNS failure")
	}
	n, err = w.WriteMinute(context.Background(), "US", []Bar{sampleWriteBar()})
	if err != nil || n != 0 || calls.Load() != 1 {
		t.Fatalf("second write must be skipped: n=%d err=%v calls=%d", n, err, calls.Load())
	}
}

func TestIsInfluxUnavailable(t *testing.T) {
	if !isInfluxUnavailable(&net.DNSError{Err: "no such host", Name: "sentiment-influxdb"}) {
		t.Fatal("DNS")
	}
	if !isInfluxUnavailable(errors.New("lookup sentiment-influxdb on 127.0.0.11:53: no such host")) {
		t.Fatal("string")
	}
	if isInfluxUnavailable(errors.New("influx write 503: overloaded")) {
		t.Fatal("HTTP status is not a transport outage")
	}
}
