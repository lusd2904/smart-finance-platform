package tradeexec

import (
	"encoding/base64"
	"encoding/json"
	"fmt"
	"strings"
	"time"
)

// Official Longbridge Go SDK (v0.27.0) has two auth paths that must not be mixed:
//   - HMAC: config.WithConfigKey → x-api-signature HMAC-SHA256
//   - OAuth/Bearer: Authorization: Bearer <token>, HMAC skipped
// Stored console tokens are RS256 JWTs, often prefixed m_ (sometimes hk_m_).
// Paper accounts (JWT ac=lb_papertrading) need header x-papertrading: true
// (Rust/Python/Node enable_papertrading; Go SDK has ExtraHeaders only).

const (
	AuthModeHMAC  = "hmac"
	AuthModeOAuth = "oauth"

	paperHeaderKey   = "x-papertrading"
	paperHeaderValue = "true"
)

// jwtNow is replaceable in tests.
var jwtNow = time.Now

// ClientPlan is the SDK construction decision. Tests lock HMAC vs OAuth,
// hk_ stripping, paper header, and fail-closed expiry without a live broker.
type ClientPlan struct {
	AuthMode            string
	AppKey              string
	AccessToken         string
	UseHMAC             bool
	AuthorizationBearer bool
	Paper               bool
	PaperHeader         string
}

// NormalizeAppKey strips whitespace, a leading "Bearer " prefix, and a leading
// hk_ region prefix (hk_m_… → m_…). Official console keys are m_…; some rows
// were saved with an extra hk_ routing prefix.
func NormalizeAppKey(appKey string) string {
	s := strings.TrimSpace(appKey)
	s = strings.TrimPrefix(s, "Bearer ")
	s = strings.TrimPrefix(s, "bearer ")
	if len(s) >= 3 && strings.EqualFold(s[:3], "hk_") {
		return s[3:]
	}
	return s
}

// NormalizeAccessToken applies the same hk_ / Bearer strip as app_key.
func NormalizeAccessToken(token string) string {
	return NormalizeAppKey(token)
}

// FormatSecretForLog is the only allowed way to mention a token or secret in
// debug/info logs: mask everything but the last 4 characters.
func FormatSecretForLog(value string) string {
	value = strings.TrimSpace(value)
	if value == "" {
		return ""
	}
	if len(value) <= 4 {
		return "****"
	}
	return "****" + value[len(value)-4:]
}

// CredsLogSummary is a log-safe credential line. Never interpolate AppSecret
// or AccessToken directly.
func CredsLogSummary(c Creds) string {
	return fmt.Sprintf("user=%d app_key=%s access_token=%s region=%s paper=%v auth=%s",
		c.UserID,
		FormatSecretForLog(c.AppKey),
		FormatSecretForLog(c.AccessToken),
		c.Region,
		IsPaperAccount(c),
		SelectAuthMode(c.AccessToken),
	)
}

// SelectAuthMode returns oauth for RS256 / m_ JWT access tokens, else hmac.
func SelectAuthMode(accessToken string) string {
	if UseOAuthBearer(accessToken) {
		return AuthModeOAuth
	}
	return AuthModeHMAC
}

// UseOAuthBearer reports whether the access token must be sent as Bearer
// (no HMAC). RS256 JWTs and m_… tokens that look like JWTs qualify.
func UseOAuthBearer(accessToken string) bool {
	raw := NormalizeAccessToken(accessToken)
	if raw == "" {
		return false
	}
	if alg, ok := jwtAlg(raw); ok {
		return strings.EqualFold(alg, "RS256")
	}
	unwrapped := unwrapLongbridgeJWT(raw)
	if unwrapped != raw {
		if alg, ok := jwtAlg(unwrapped); ok {
			return strings.EqualFold(alg, "RS256")
		}
	}
	body := strings.TrimPrefix(raw, "m_")
	return strings.HasPrefix(raw, "m_") && looksLikeJWT(body)
}

// IsPaperAccount is true when the user/region/JWT says paper trading
// (ac=lb_papertrading or an equivalent region/flag).
func IsPaperAccount(c Creds) bool {
	if c.Paper {
		return true
	}
	if isPaperRegion(c.Region) {
		return true
	}
	return jwtAccountIsPaper(c.AccessToken)
}

func isPaperRegion(region string) bool {
	switch strings.ToLower(strings.TrimSpace(region)) {
	case "lb_papertrading", "paper", "papertrading", "paper_trading", "sim", "trading-test", "trading_test":
		return true
	default:
		return false
	}
}

func jwtAccountIsPaper(token string) bool {
	_, payload, ok := jwtHeaderPayload(token)
	if !ok {
		return false
	}
	for _, key := range []string{"ac", "account", "account_type"} {
		if isPaperClaim(payload[key]) {
			return true
		}
	}
	return false
}

func isPaperClaim(v any) bool {
	s := strings.ToLower(strings.TrimSpace(fmt.Sprint(v)))
	if s == "" || s == "<nil>" {
		return false
	}
	return strings.Contains(s, "paper") || s == "sim" || s == "trading-test"
}

// RejectExpiredAccessToken fails closed when the token is a JWT whose exp
// is in the past. Non-JWT legacy secrets are left to the HMAC path.
func RejectExpiredAccessToken(accessToken string) error {
	return rejectExpiredAt(accessToken, jwtNow())
}

func rejectExpiredAt(accessToken string, now time.Time) error {
	raw := NormalizeAccessToken(accessToken)
	if raw == "" {
		return nil
	}
	exp, ok := jwtExpiry(raw)
	if !ok {
		return nil
	}
	if !exp.After(now) {
		return &BrokerRejectError{
			Code:    BrokerTokenExpiredCode,
			Message: BrokerTokenExpiredMsg,
		}
	}
	return nil
}

// NormalizeAndValidateForStore strips hk_ and rejects expired JWTs before
// any write to quant_longbridge_config. Empty token (keep-existing / mask)
// is not validated.
func NormalizeAndValidateForStore(appKey, accessToken string) (string, string, error) {
	key := NormalizeAppKey(appKey)
	tok := NormalizeAccessToken(accessToken)
	if tok != "" {
		if err := RejectExpiredAccessToken(tok); err != nil {
			return "", "", err
		}
	}
	return key, tok, nil
}

// DecodeLongbridgeCreds decrypts and normalizes a DB row for SDK use.
func DecodeLongbridgeCreds(userID int, appKey, secret, token, region, credKey, jwtSecret, appEnv string) Creds {
	return Creds{
		UserID:      userID,
		AppKey:      NormalizeAppKey(appKey),
		AppSecret:   strings.TrimSpace(DecryptOrRaw(secret, credKey, jwtSecret, appEnv)),
		AccessToken: NormalizeAccessToken(DecryptOrRaw(token, credKey, jwtSecret, appEnv)),
		Region:      strings.TrimSpace(region),
		Source:      "db",
	}
}

// PlanClient decides auth mode, paper header, and normalized keys.
// Expired JWTs fail before a plan that could be sent to the broker is built.
func PlanClient(creds Creds) (ClientPlan, error) {
	key := NormalizeAppKey(creds.AppKey)
	tok := NormalizeAccessToken(creds.AccessToken)
	if err := RejectExpiredAccessToken(tok); err != nil {
		return ClientPlan{}, err
	}
	prepared := creds
	prepared.AppKey = key
	prepared.AccessToken = tok
	paper := IsPaperAccount(prepared)
	plan := ClientPlan{
		AppKey:      key,
		AccessToken: tok,
		Paper:       paper,
	}
	if paper {
		plan.PaperHeader = paperHeaderKey + "=" + paperHeaderValue
	}
	if UseOAuthBearer(tok) {
		plan.AuthMode = AuthModeOAuth
		plan.UseHMAC = false
		plan.AuthorizationBearer = true
		return plan, nil
	}
	plan.AuthMode = AuthModeHMAC
	plan.UseHMAC = true
	return plan, nil
}

func jwtExpiry(token string) (time.Time, bool) {
	_, payload, ok := jwtHeaderPayload(token)
	if !ok {
		return time.Time{}, false
	}
	switch v := payload["exp"].(type) {
	case float64:
		if v <= 0 {
			return time.Time{}, false
		}
		return time.Unix(int64(v), 0).UTC(), true
	case json.Number:
		n, err := v.Int64()
		if err != nil || n <= 0 {
			return time.Time{}, false
		}
		return time.Unix(n, 0).UTC(), true
	case int64:
		if v <= 0 {
			return time.Time{}, false
		}
		return time.Unix(v, 0).UTC(), true
	default:
		return time.Time{}, false
	}
}

func jwtAlg(token string) (string, bool) {
	header, _, ok := jwtHeaderPayload(token)
	if !ok {
		return "", false
	}
	alg, _ := header["alg"].(string)
	if alg == "" {
		return "", false
	}
	return alg, true
}

func jwtHeaderPayload(token string) (header, payload map[string]any, ok bool) {
	raw := unwrapLongbridgeJWT(NormalizeAccessToken(token))
	if !looksLikeJWT(raw) {
		return nil, nil, false
	}
	parts := strings.Split(raw, ".")
	if len(parts) < 2 {
		return nil, nil, false
	}
	header, ok = decodeJWTSegment(parts[0])
	if !ok {
		return nil, nil, false
	}
	payload, ok = decodeJWTSegment(parts[1])
	if !ok {
		return nil, nil, false
	}
	return header, payload, true
}

func unwrapLongbridgeJWT(token string) string {
	s := NormalizeAccessToken(token)
	if strings.HasPrefix(s, "m_") {
		rest := s[2:]
		if looksLikeJWT(rest) {
			return rest
		}
	}
	return s
}

func looksLikeJWT(s string) bool {
	s = strings.TrimSpace(s)
	if s == "" {
		return false
	}
	parts := strings.Split(s, ".")
	return len(parts) >= 2 && parts[0] != "" && parts[1] != ""
}

func decodeJWTSegment(seg string) (map[string]any, bool) {
	b, err := base64.RawURLEncoding.DecodeString(seg)
	if err != nil {
		pad := len(seg) % 4
		if pad > 0 {
			seg += strings.Repeat("=", 4-pad)
		}
		b, err = base64.URLEncoding.DecodeString(seg)
		if err != nil {
			return nil, false
		}
	}
	var out map[string]any
	dec := json.NewDecoder(strings.NewReader(string(b)))
	dec.UseNumber()
	if err := dec.Decode(&out); err != nil || out == nil {
		return nil, false
	}
	// Prefer float64-style numbers for exp via a second pass if needed.
	var generic map[string]any
	if err := json.Unmarshal(b, &generic); err == nil && generic != nil {
		if _, ok := generic["alg"]; ok || generic["exp"] != nil || generic["ac"] != nil {
			return generic, true
		}
	}
	// Convert json.Number fields.
	converted := make(map[string]any, len(out))
	for k, v := range out {
		if n, ok := v.(json.Number); ok {
			if i, err := n.Int64(); err == nil {
				converted[k] = float64(i)
				continue
			}
			if f, err := n.Float64(); err == nil {
				converted[k] = f
				continue
			}
		}
		converted[k] = v
	}
	return converted, true
}
