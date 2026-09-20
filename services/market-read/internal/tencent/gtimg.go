// Package tencent fetches qt.gtimg.cn snapshots (index + stocks).
// Parser matches Python module_market.service.tencent_quote.parse_gtimg_text.
package tencent

import (
	"bytes"
	"context"
	"fmt"
	"io"
	"net/http"
	"regexp"
	"strconv"
	"strings"
	"time"
	"unicode"

	"golang.org/x/text/encoding/simplifiedchinese"
	"golang.org/x/text/transform"
)

const (
	idxLast   = 3
	idxPrev   = 4
	idxTime   = 30
	idxChgPct = 32
	minParts  = 33
)

var codeRE = regexp.MustCompile(`v_(\w+)="([^"]*)"`)

var defaultUA = http.Header{
	"User-Agent": []string{"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"},
	"Referer":    []string{"https://finance.sina.com.cn"},
}

// Quote is one gtimg field set keyed by code (usAAPL / hk00700 / sh600519).
type Quote struct {
	Name      string
	Last      *float64
	PrevClose *float64
	QuoteTime string
	ChangePct *float64
}

// ParseGtimgText parses qt.gtimg.cn text. Keys omit the v_ prefix.
func ParseGtimgText(text string) map[string]Quote {
	out := map[string]Quote{}
	for _, match := range codeRE.FindAllStringSubmatch(text, -1) {
		if len(match) < 3 {
			continue
		}
		parts := strings.Split(match[2], "~")
		if len(parts) < minParts {
			continue
		}
		out[match[1]] = Quote{
			Name:      parts[1],
			Last:      toFloat(parts[idxLast]),
			PrevClose: toFloat(parts[idxPrev]),
			QuoteTime: parts[idxTime],
			ChangePct: toFloat(parts[idxChgPct]),
		}
	}
	return out
}

func toFloat(value string) *float64 {
	raw := strings.TrimSpace(value)
	if raw == "" || raw == "-" {
		return nil
	}
	n, err := strconv.ParseFloat(raw, 64)
	if err != nil {
		return nil
	}
	return &n
}

// vendorTencentByKey maps "SYMBOL|MARKET" to qt.gtimg.cn codes for pinned indices.
// 上证 is only 000001.SH → sh000001. Bare 000001 / 000001.SZ stay 平安银行 (sz000001).
// ^GSPC is usINX, never usGSPC.
var vendorTencentByKey = map[string]string{
	"^DJI|US":      "usDJI",
	"^GSPC|US":     "usINX",
	"^IXIC|US":     "usIXIC",
	"HSI|HK":       "hkHSI",
	"HSI.HK|HK":    "hkHSI",
	"HSTECH|HK":    "hkHSTECH",
	"HSTECH.HK|HK": "hkHSTECH",
	"HSCEI|HK":     "hkHSCEI",
	"HSCEI.HK|HK":  "hkHSCEI",
	"000001.SH|CN": "sh000001",
	"399001|CN":    "sz399001",
	"399001.SZ|CN": "sz399001",
	"399006|CN":    "sz399006",
	"399006.SZ|CN": "sz399006",
}

func vendorTencent(symbol, market string) (string, bool) {
	key := strings.ToUpper(strings.TrimSpace(symbol)) + "|" + strings.ToUpper(strings.TrimSpace(market))
	code, ok := vendorTencentByKey[key]
	return code, ok
}

// Symbol maps (symbol, market) to a gtimg code. Mirrors kline_sources.tencent_symbol.
func Symbol(symbol, market string) string {
	sym := strings.TrimSpace(symbol)
	mkt := strings.ToUpper(strings.TrimSpace(market))
	if mkt == "" {
		mkt = "US"
	}
	if code, ok := vendorTencent(sym, mkt); ok && code != "" {
		return code
	}
	switch mkt {
	case "HK":
		code := strings.ToUpper(strings.ReplaceAll(sym, ".HK", ""))
		if isDigits(code) {
			return "hk" + padLeft(code, 5, '0')
		}
		return "hk" + code
	case "CN":
		return cnSymbol(sym)
	default:
		return "us" + strings.ReplaceAll(sym, "^", "")
	}
}

func cnSymbol(symbol string) string {
	code := strings.TrimSpace(symbol)
	lower := strings.ToLower(code)
	if strings.HasPrefix(lower, "sh") || strings.HasPrefix(lower, "sz") {
		return lower
	}
	body, suffix := splitCNSuffix(code)
	switch suffix {
	case "SH", "SS":
		return "sh" + body
	case "SZ":
		return "sz" + body
	}
	if strings.HasPrefix(body, "6") || strings.HasPrefix(body, "9") {
		return "sh" + body
	}
	return "sz" + body
}

func splitCNSuffix(symbol string) (body, suffix string) {
	u := strings.ToUpper(strings.TrimSpace(symbol))
	for _, suf := range []string{"SH", "SS", "SZ"} {
		dotSuf := "." + suf
		if strings.HasSuffix(u, dotSuf) {
			return u[:len(u)-len(dotSuf)], suf
		}
	}
	return u, ""
}

func isDigits(s string) bool {
	if s == "" {
		return false
	}
	for _, r := range s {
		if !unicode.IsDigit(r) {
			return false
		}
	}
	return true
}

func padLeft(s string, n int, pad rune) string {
	if len(s) >= n {
		return s
	}
	return strings.Repeat(string(pad), n-len(s)) + s
}

// HTTPFetcher calls qt.gtimg.cn. Safe for concurrent use.
type HTTPFetcher struct {
	Client  *http.Client
	BaseURL string
}

func NewHTTPFetcher() *HTTPFetcher {
	return &HTTPFetcher{
		Client: &http.Client{
			Timeout: 8 * time.Second,
		},
		BaseURL: "https://qt.gtimg.cn/q=",
	}
}

func (f *HTTPFetcher) FetchBatch(ctx context.Context, codes []string) (map[string]Quote, error) {
	cleaned := make([]string, 0, len(codes))
	for _, code := range codes {
		code = strings.TrimSpace(code)
		if code != "" {
			cleaned = append(cleaned, code)
		}
	}
	if len(cleaned) == 0 {
		return map[string]Quote{}, nil
	}
	base := f.BaseURL
	if base == "" {
		base = "https://qt.gtimg.cn/q="
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, base+strings.Join(cleaned, ","), nil)
	if err != nil {
		return nil, err
	}
	req.Header = defaultUA.Clone()
	client := f.Client
	if client == nil {
		client = http.DefaultClient
	}
	resp, err := client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("gtimg status %d", resp.StatusCode)
	}
	raw, err := io.ReadAll(io.LimitReader(resp.Body, 1<<20))
	if err != nil {
		return nil, err
	}
	text := decodeGBK(raw)
	return ParseGtimgText(text), nil
}

func decodeGBK(raw []byte) string {
	reader := transform.NewReader(bytes.NewReader(raw), simplifiedchinese.GBK.NewDecoder())
	decoded, err := io.ReadAll(reader)
	if err != nil {
		return string(raw)
	}
	return string(decoded)
}
