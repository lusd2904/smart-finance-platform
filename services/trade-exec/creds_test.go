package tradeexec

import (
	"encoding/base64"
	"encoding/json"
	"errors"
	"strings"
	"testing"
	"time"
)

func b64url(obj any) string {
	raw, err := json.Marshal(obj)
	if err != nil {
		panic(err)
	}
	return base64.RawURLEncoding.EncodeToString(raw)
}

func makeJWT(alg string, exp int64, extra map[string]any) string {
	header := map[string]any{"alg": alg, "typ": "JWT"}
	payload := map[string]any{"exp": exp}
	for k, v := range extra {
		payload[k] = v
	}
	return "m_" + b64url(header) + "." + b64url(payload) + ".sig"
}

func TestSelectAuthModeHMACvsOAuth(t *testing.T) {
	oauthTok := makeJWT("RS256", time.Now().Add(24*time.Hour).Unix(), nil)
	if SelectAuthMode(oauthTok) != AuthModeOAuth {
		t.Fatalf("RS256 m_ token must be OAuth, got %s", SelectAuthMode(oauthTok))
	}
	if !UseOAuthBearer(oauthTok) {
		t.Fatal("RS256 must use Bearer")
	}
	plan, err := PlanClient(Creds{AppKey: "m_app", AppSecret: "legacy-secret", AccessToken: oauthTok})
	if err != nil {
		t.Fatal(err)
	}
	if plan.UseHMAC || !plan.AuthorizationBearer || plan.AuthMode != AuthModeOAuth {
		t.Fatalf("OAuth plan=%+v", plan)
	}

	legacy := "legacy-access-token-not-jwt"
	if SelectAuthMode(legacy) != AuthModeHMAC {
		t.Fatalf("legacy secret must stay HMAC, got %s", SelectAuthMode(legacy))
	}
	hs := makeJWT("HS256", time.Now().Add(24*time.Hour).Unix(), nil)
	if SelectAuthMode(hs) != AuthModeHMAC {
		t.Fatalf("HS256 legacy JWT must stay HMAC, got %s", SelectAuthMode(hs))
	}
	plan, err = PlanClient(Creds{AppKey: "app-key", AppSecret: "app-secret", AccessToken: legacy})
	if err != nil {
		t.Fatal(err)
	}
	if !plan.UseHMAC || plan.AuthorizationBearer || plan.AuthMode != AuthModeHMAC {
		t.Fatalf("HMAC plan=%+v", plan)
	}
}

func TestNormalizeAppKeyStripsHKPrefix(t *testing.T) {
	cases := []struct{ in, want string }{
		{"hk_m_abc123", "m_abc123"},
		{"HK_m_abc123", "m_abc123"},
		{"m_abc123", "m_abc123"},
		{"  hk_m_xyz  ", "m_xyz"},
		{"Bearer hk_m_tok", "m_tok"},
	}
	for _, tc := range cases {
		if got := NormalizeAppKey(tc.in); got != tc.want {
			t.Fatalf("NormalizeAppKey(%q)=%q want %q", tc.in, got, tc.want)
		}
	}
	tok := makeJWT("RS256", time.Now().Add(time.Hour).Unix(), nil)
	plan, err := PlanClient(Creds{AppKey: "hk_m_consolekey", AccessToken: "hk_" + tok})
	if err != nil {
		t.Fatal(err)
	}
	if plan.AppKey != "m_consolekey" {
		t.Fatalf("app_key=%q", plan.AppKey)
	}
	if !strings.HasPrefix(plan.AccessToken, "m_") {
		t.Fatalf("token should lose hk_, got %s", FormatSecretForLog(plan.AccessToken))
	}
}

func TestPaperFlagForLBPapertrading(t *testing.T) {
	tok := makeJWT("RS256", time.Now().Add(time.Hour).Unix(), map[string]any{"ac": "lb_papertrading"})
	plan, err := PlanClient(Creds{AppKey: "m_key", AccessToken: tok})
	if err != nil {
		t.Fatal(err)
	}
	if !plan.Paper || plan.PaperHeader != "x-papertrading=true" {
		t.Fatalf("JWT ac paper plan=%+v", plan)
	}
	live := makeJWT("RS256", time.Now().Add(time.Hour).Unix(), map[string]any{"ac": "lb_live"})
	plan, err = PlanClient(Creds{AppKey: "m_key", AccessToken: live})
	if err != nil {
		t.Fatal(err)
	}
	if plan.Paper || plan.PaperHeader != "" {
		t.Fatalf("live account must not set paper header: %+v", plan)
	}
	plan, err = PlanClient(Creds{AppKey: "m_key", AppSecret: "s", AccessToken: "legacy", Region: "lb_papertrading"})
	if err != nil {
		t.Fatal(err)
	}
	if !plan.Paper {
		t.Fatal("region lb_papertrading must be paper")
	}
	cfg, err := buildConfig(Creds{AppKey: "m_key", AccessToken: tok})
	if err != nil {
		t.Fatal(err)
	}
	if cfg.ExtraHeaders[paperHeaderKey] != paperHeaderValue {
		t.Fatalf("SDK paper header missing: %+v", cfg.ExtraHeaders)
	}
}

func TestExpiredJWTNotSentToBroker(t *testing.T) {
	expired := makeJWT("RS256", time.Date(2026, 5, 31, 0, 0, 0, 0, time.UTC).Unix(), nil)
	plan, err := PlanClient(Creds{AppKey: "m_key", AppSecret: "hmac-secret", AccessToken: expired})
	if err == nil {
		t.Fatalf("expired JWT must fail closed, plan=%+v", plan)
	}
	var br *BrokerRejectError
	if !errors.As(err, &br) || br.Code != BrokerTokenExpiredCode {
		t.Fatalf("want 401003, got %v", err)
	}
	if !strings.Contains(err.Error(), "token expired, re-save from console") {
		t.Fatalf("msg=%s", err)
	}
	if plan.UseHMAC {
		t.Fatal("must not HMAC-sign an expired JWT")
	}
	cfg, err := buildConfig(Creds{AppKey: "m_key", AppSecret: "hmac-secret", AccessToken: expired})
	if err == nil || cfg != nil {
		t.Fatal("buildConfig must not construct an SDK client with an expired JWT")
	}
	if !IsBrokerTokenExpired(err) || IsBrokerTokenRejected(err) {
		t.Fatal("expired must be 401003, not 401004")
	}
}

func TestRejectOnSaveExpiredJWT(t *testing.T) {
	expired := makeJWT("RS256", 1717200000, nil) // 2024-06-01
	_, _, err := NormalizeAndValidateForStore("hk_m_key", expired)
	if err == nil {
		t.Fatal("save must reject expired token")
	}
	if !IsBrokerTokenExpired(err) {
		t.Fatalf("want expired, got %v", err)
	}
	if !strings.Contains(err.Error(), "token expired, re-save from console") {
		t.Fatalf("msg=%s", err)
	}

	fresh := makeJWT("RS256", time.Now().Add(48*time.Hour).Unix(), nil)
	key, tok, err := NormalizeAndValidateForStore("hk_m_key", "hk_"+fresh)
	if err != nil {
		t.Fatal(err)
	}
	if key != "m_key" {
		t.Fatalf("key=%s", key)
	}
	if !strings.HasPrefix(tok, "m_") {
		t.Fatalf("stored token must be stripped: %s", FormatSecretForLog(tok))
	}

	// Empty token = keep existing; do not invent or persist a fake value.
	key, tok, err = NormalizeAndValidateForStore("hk_m_key", "")
	if err != nil || key != "m_key" || tok != "" {
		t.Fatalf("empty token keep-existing: key=%s tok=%q err=%v", key, tok, err)
	}
}

func TestFormatSecretForLogLast4Only(t *testing.T) {
	tok := makeJWT("RS256", time.Now().Add(time.Hour).Unix(), map[string]any{"ac": "lb_papertrading"})
	got := FormatSecretForLog(tok)
	if got == tok || strings.Contains(got, tok) {
		t.Fatal("log must not contain the full access token")
	}
	if !strings.HasPrefix(got, "****") {
		t.Fatalf("want **** prefix, got %q", got)
	}
	if !strings.HasSuffix(got, tok[len(tok)-4:]) {
		t.Fatalf("want last 4 of token, got %q", got)
	}
	if strings.Contains(got, "hmac-secret-value") {
		t.Fatal("unexpected")
	}
	secret := "hmac-secret-value"
	logged := FormatSecretForLog(secret)
	if strings.Contains(logged, secret) || logged != "****alue" {
		t.Fatalf("app_secret log=%q", logged)
	}
	summary := CredsLogSummary(Creds{UserID: 7, AppKey: "hk_m_consolekey", AppSecret: secret, AccessToken: tok})
	if strings.Contains(summary, tok) || strings.Contains(summary, secret) || strings.Contains(summary, "hk_m_consolekey") {
		t.Fatalf("summary leaked secret: %s", summary)
	}
	if !strings.Contains(summary, FormatSecretForLog(tok)) {
		t.Fatalf("summary=%s", summary)
	}
}

func TestBuildConfigOAuthSetsBearerNotHMAC(t *testing.T) {
	tok := makeJWT("RS256", time.Now().Add(time.Hour).Unix(), nil)
	cfg, err := buildConfig(Creds{AppKey: "hk_m_key", AppSecret: "must-not-be-used", AccessToken: tok})
	if err != nil {
		t.Fatal(err)
	}
	if cfg.AppSecret != "" {
		t.Fatal("OAuth config must not carry app_secret for HMAC")
	}
	if cfg.ExtraHeaders["Authorization"] != "Bearer "+NormalizeAccessToken(tok) {
		t.Fatalf("Authorization=%q", cfg.ExtraHeaders["Authorization"])
	}
}

func TestConfiguredOAuthDoesNotRequireSecret(t *testing.T) {
	tok := makeJWT("RS256", time.Now().Add(time.Hour).Unix(), nil)
	c := Creds{AppKey: "m_key", AccessToken: tok}
	if !c.Configured() {
		t.Fatal("OAuth token + app_key should be configured")
	}
	legacy := Creds{AppKey: "k", AccessToken: "legacy-token"}
	if legacy.Configured() {
		t.Fatal("HMAC without secret is not configured")
	}
}

func TestClassify401003DistinctFrom401004(t *testing.T) {
	expired := ClassifyBrokerError(errors.New("longbridge: http 401 code=401003 message=token expired"))
	var br *BrokerRejectError
	if !errors.As(expired, &br) || br.Code != 401003 {
		t.Fatalf("401003=%v", expired)
	}
	if IsBrokerTokenRejected(expired) {
		t.Fatal("401003 must not be classified as 401004 invalid")
	}
	invalid := ClassifyBrokerError(errors.New("401004 access token invalid"))
	if !errors.As(invalid, &br) || br.Code != 401004 {
		t.Fatalf("401004=%v", invalid)
	}
}
