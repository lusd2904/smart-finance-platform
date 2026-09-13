package store

import (
	"context"
	"encoding/base64"
	"encoding/json"
	"strings"
	"testing"
	"time"

	tradeexec "github.com/lusd2904/smart-finance-platform/services/trade-exec"
)

func jwtForStore(alg string, exp int64) string {
	header, _ := json.Marshal(map[string]any{"alg": alg, "typ": "JWT"})
	payload, _ := json.Marshal(map[string]any{"exp": exp})
	return "m_" + base64.RawURLEncoding.EncodeToString(header) + "." + base64.RawURLEncoding.EncodeToString(payload) + ".sig"
}

func TestSaveLongbridgeConfigRejectsExpiredJWT(t *testing.T) {
	d := &DB{} // nil sql — must fail before any INSERT
	expired := jwtForStore("RS256", time.Date(2026, 5, 31, 0, 0, 0, 0, time.UTC).Unix())
	err := d.SaveLongbridgeConfig(context.Background(), 42, LongbridgeConfig{
		AppKey:      "hk_m_lustone",
		AccessToken: expired,
	}, "", "", "test")
	if err == nil {
		t.Fatal("expired token must not be persisted")
	}
	if !tradeexec.IsBrokerTokenExpired(err) {
		t.Fatalf("want 401003, got %v", err)
	}
	if !strings.Contains(err.Error(), "token expired, re-save from console") {
		t.Fatalf("msg=%s", err)
	}
}

func TestFormatSecretForLogUsedOnConfigRead(t *testing.T) {
	secret := "super-secret-app-secret"
	tok := jwtForStore("RS256", time.Now().Add(time.Hour).Unix())
	if masked := maskSecret(secret); strings.Contains(masked, secret) || !strings.HasSuffix(masked, secret[len(secret)-4:]) {
		t.Fatalf("mask=%q", masked)
	}
	if masked := maskSecret(tok); strings.Contains(masked, tok) || !strings.HasPrefix(masked, "****") {
		t.Fatalf("token mask leaked: %q", masked)
	}
}
