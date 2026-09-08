package longbridge

import (
	"context"
	"crypto/hmac"
	"crypto/sha1"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"strconv"
	"strings"
	"time"
)

const signedHeaders = "authorization;x-api-key;x-timestamp"

type Creds struct {
	AppKey      string
	AppSecret   string
	AccessToken string
	Region      string
	HTTPURL     string
}

func (c Creds) Configured() bool {
	return c.AppKey != "" && c.AppSecret != "" && c.AccessToken != ""
}

func (c Creds) BaseURL() string {
	if strings.TrimSpace(c.HTTPURL) != "" {
		return strings.TrimRight(c.HTTPURL, "/")
	}
	if strings.EqualFold(c.Region, "cn") || c.Region == "" {
		return "https://openapi.longbridge.cn"
	}
	return "https://openapi.longbridge.com"
}

func LoadCredsFromEnv() Creds {
	return Creds{
		AppKey:      firstEnv("LONGPORT_APP_KEY", "LONGBRIDGE_APP_KEY"),
		AppSecret:   firstEnv("LONGPORT_APP_SECRET", "LONGBRIDGE_APP_SECRET"),
		AccessToken: firstEnv("LONGPORT_ACCESS_TOKEN", "LONGBRIDGE_ACCESS_TOKEN"),
		Region:      firstEnv("LONGPORT_REGION", "LONGBRIDGE_REGION"),
		HTTPURL:     firstEnv("LONGPORT_HTTP_URL", "LONGBRIDGE_HTTP_URL"),
	}
}

func firstEnv(keys ...string) string {
	for _, key := range keys {
		if v := strings.TrimSpace(os.Getenv(key)); v != "" {
			return v
		}
	}
	return ""
}

type Position struct {
	Symbol            string
	SymbolName        string
	Quantity          float64
	AvailableQuantity float64
	CostPrice         float64
	LastPrice         float64
	Currency          string
	Market            string
}

type Client struct {
	HTTP  *http.Client
	Creds Creds
	Now   func() time.Time
}

func NewClient(creds Creds) *Client {
	return &Client{HTTP: &http.Client{Timeout: 20 * time.Second}, Creds: creds, Now: time.Now}
}

func (c *Client) GetPositions(ctx context.Context) ([]Position, error) {
	if !c.Creds.Configured() {
		return nil, nil
	}
	raw, err := c.getJSON(ctx, "/v1/asset/stock", "")
	if err != nil {
		return nil, err
	}
	data := asMap(raw["data"])
	channels := asList(data["channels"])
	out := []Position{}
	for _, ch := range channels {
		for _, row := range asList(asMap(ch)["positions"]) {
			m := asMap(row)
			out = append(out, Position{
				Symbol:            firstString(m, "symbol"),
				SymbolName:        firstString(m, "symbol_name", "symbolName"),
				Quantity:          asFloat(m["quantity"]),
				AvailableQuantity: asFloat(m["available_quantity"], m["availableQuantity"]),
				CostPrice:         asFloat(m["cost_price"], m["costPrice"]),
				LastPrice:         asFloat(m["last_done"], m["lastDone"], m["last_price"], m["current_price"]),
				Currency:          firstString(m, "currency"),
				Market:            firstString(m, "market"),
			})
		}
	}
	return out, nil
}

func (c *Client) getJSON(ctx context.Context, path, query string) (map[string]any, error) {
	full := c.Creds.BaseURL() + path
	if query != "" {
		full += "?" + query
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, full, nil)
	if err != nil {
		return nil, err
	}
	ts := strconv.FormatInt(c.Now().UnixMilli(), 10)
	req.Header.Set("x-api-key", c.Creds.AppKey)
	req.Header.Set("authorization", c.Creds.AccessToken)
	req.Header.Set("x-timestamp", ts)
	req.Header.Set("x-api-signature", SignRequest(http.MethodGet, path, query, "", c.Creds.AppKey, c.Creds.AccessToken, ts, c.Creds.AppSecret))
	req.Header.Set("Accept", "application/json")
	resp, err := c.HTTP.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	body, err := io.ReadAll(io.LimitReader(resp.Body, 4<<20))
	if err != nil {
		return nil, err
	}
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return nil, fmt.Errorf("longbridge HTTP %d: %s", resp.StatusCode, truncate(string(body), 200))
	}
	var payload map[string]any
	if err := json.Unmarshal(body, &payload); err != nil {
		return nil, err
	}
	code := 0
	switch v := payload["code"].(type) {
	case float64:
		code = int(v)
	}
	if code != 0 {
		return nil, fmt.Errorf("longbridge code=%v message=%v", payload["code"], payload["message"])
	}
	return payload, nil
}

func SignRequest(method, uri, query, body, appKey, accessToken, timestamp, appSecret string) string {
	method = strings.ToUpper(method)
	headerBlock := strings.Join([]string{
		"authorization:" + accessToken,
		"x-api-key:" + appKey,
		"x-timestamp:" + timestamp,
	}, "\n")
	canonical := method + "|" + uri + "|" + query + "|" + headerBlock + "\n|" + signedHeaders + "|"
	if body != "" {
		canonical += sha1Hex(body)
	}
	signStr := "HMAC-SHA256|" + sha1Hex(canonical)
	sig := hmacSHA256Hex(appSecret, signStr)
	return fmt.Sprintf("HMAC-SHA256 SignedHeaders=%s, Signature=%s", signedHeaders, sig)
}

func sha1Hex(s string) string {
	sum := sha1.Sum([]byte(s))
	return hex.EncodeToString(sum[:])
}

func hmacSHA256Hex(secret, data string) string {
	mac := hmac.New(sha256.New, []byte(secret))
	_, _ = mac.Write([]byte(data))
	return hex.EncodeToString(mac.Sum(nil))
}

func ParseSymbolMarket(raw, fallback string) (string, string) {
	text := strings.ToUpper(strings.TrimSpace(raw))
	fb := strings.ToUpper(strings.TrimSpace(fallback))
	if fb == "" {
		fb = "US"
	}
	if i := strings.LastIndex(text, "."); i > 0 {
		code, suffix := text[:i], text[i+1:]
		market := suffix
		if suffix == "SH" || suffix == "SZ" {
			market = "CN"
		}
		return code, market
	}
	return text, fb
}

func asMap(v any) map[string]any {
	if m, ok := v.(map[string]any); ok {
		return m
	}
	return map[string]any{}
}

func asList(v any) []any {
	if list, ok := v.([]any); ok {
		return list
	}
	return nil
}

func firstString(m map[string]any, keys ...string) string {
	for _, key := range keys {
		if v, ok := m[key]; ok && v != nil {
			s := strings.TrimSpace(fmt.Sprint(v))
			if s != "" && s != "<nil>" {
				return s
			}
		}
	}
	return ""
}

func asFloat(vals ...any) float64 {
	for _, v := range vals {
		if v == nil {
			continue
		}
		switch x := v.(type) {
		case float64:
			return x
		case json.Number:
			f, _ := x.Float64()
			return f
		case string:
			f, _ := strconv.ParseFloat(strings.TrimSpace(x), 64)
			return f
		}
	}
	return 0
}

func truncate(s string, n int) string {
	if len(s) <= n {
		return s
	}
	return s[:n]
}
