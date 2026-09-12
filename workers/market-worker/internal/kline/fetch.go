package kline

import (
	"encoding/json"
	"fmt"
	"io"
	"log/slog"
	"math"
	"net/http"
	"net/url"
	"regexp"
	"strconv"
	"strings"
	"time"
)

const (
	sinaUSDailyURL = "https://stock.finance.sina.com.cn/usstock/api/jsonp_v2.php/var%20t=/US_MinKService.getDailyK"
	sinaHKDailyURL = "https://stock.finance.sina.com.cn/hkstock/api/jsonp_v2.php/var%20t=/HK_MinKService.getDailyK"
	sinaCNDailyURL = "https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData"
	tencentFQURL   = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
	tencentHKFQURL = "https://web.ifzq.gtimg.cn/appstock/app/hkfqkline/get"
)

var minuteURLs = map[string]string{
	"CN": "https://web.ifzq.gtimg.cn/appstock/app/minute/query",
	"HK": "https://web.ifzq.gtimg.cn/appstock/app/hkMinute/query",
	"US": "https://web.ifzq.gtimg.cn/appstock/app/UsMinute/query",
}

type vendorIndex struct {
	Tencent string
	Sina    string
}

// vendorIndexByKey maps "SYMBOL|MARKET" to Tencent qt / Sina daily codes.
// 上证指数 is only 000001.SH → sh000001. Bare 000001 and 000001.SZ are 平安银行 (sz000001).
var vendorIndexByKey = map[string]vendorIndex{
	"^DJI|US":      {Tencent: "usDJI", Sina: ".DJI"},
	"^GSPC|US":     {Tencent: "usINX", Sina: ".INX"},
	"^IXIC|US":     {Tencent: "usIXIC", Sina: ".IXIC"},
	"HSI|HK":       {Tencent: "hkHSI", Sina: "HSI"},
	"HSI.HK|HK":    {Tencent: "hkHSI", Sina: "HSI"},
	"HSTECH|HK":    {Tencent: "hkHSTECH", Sina: "HSTECH"},
	"HSTECH.HK|HK": {Tencent: "hkHSTECH", Sina: "HSTECH"},
	"HSCEI|HK":     {Tencent: "hkHSCEI", Sina: "HSCEI"},
	"HSCEI.HK|HK":  {Tencent: "hkHSCEI", Sina: "HSCEI"},
	"000001.SH|CN": {Tencent: "sh000001", Sina: "sh000001"},
	"399001|CN":    {Tencent: "sz399001", Sina: "sz399001"},
	"399001.SZ|CN": {Tencent: "sz399001", Sina: "sz399001"},
	"399006|CN":    {Tencent: "sz399006", Sina: "sz399006"},
	"399006.SZ|CN": {Tencent: "sz399006", Sina: "sz399006"},
}

func vendorKey(symbol, market string) string {
	return strings.ToUpper(strings.TrimSpace(symbol)) + "|" + strings.ToUpper(strings.TrimSpace(market))
}

// VendorIndex returns Tencent qt and Sina daily codes for a pinned index.
// ok is false for ordinary stocks, including bare 000001 and 000001.SZ (平安银行).
func VendorIndex(symbol, market string) (tencentCode, sinaCode string, ok bool) {
	row, found := vendorIndexByKey[vendorKey(symbol, market)]
	if !found {
		return "", "", false
	}
	return row.Tencent, row.Sina, true
}

type Row struct {
	Symbol    string
	Market    string
	TradeDate string
	Open      float64
	High      float64
	Low       float64
	Close     float64
	Volume    float64
	Source    string
}

type Client struct {
	httpClient *http.Client
	interval   float64
}

func NewClient(sourceInterval float64) *Client {
	return &Client{
		httpClient: &http.Client{Timeout: 60 * time.Second},
		interval:   sourceInterval,
	}
}

func (c *Client) FetchReal(symbol, market string, years int) ([]Row, []string) {
	mkt := strings.ToUpper(market)
	order := []string{"sina", "tencent"}
	if mkt == "HK" {
		order = []string{"tencent", "sina"}
	}
	var used []string
	var merged map[string]Row
	for _, src := range order {
		rows, err := c.fetchSource(src, symbol, mkt, years)
		if err != nil || len(rows) == 0 {
			continue
		}
		used = append(used, src)
		if merged == nil {
			merged = map[string]Row{}
		}
		for _, r := range rows {
			merged[r.TradeDate] = r
		}
		if len(merged) >= 40 {
			break
		}
		time.Sleep(time.Duration(c.interval * float64(time.Second)))
	}
	if merged == nil {
		return nil, used
	}
	out := make([]Row, 0, len(merged))
	for d := range merged {
		out = append(out, merged[d])
	}
	sortRows(out)
	return out, used
}

func sortRows(rows []Row) {
	for i := 0; i < len(rows); i++ {
		for j := i + 1; j < len(rows); j++ {
			if rows[j].TradeDate < rows[i].TradeDate {
				rows[i], rows[j] = rows[j], rows[i]
			}
		}
	}
}

func (c *Client) fetchSource(source, symbol, market string, years int) ([]Row, error) {
	switch source {
	case "sina":
		return c.fetchSina(symbol, market, years)
	case "tencent":
		return c.fetchTencent(symbol, market, years)
	default:
		return nil, fmt.Errorf("unknown source")
	}
}

func (c *Client) fetchSina(symbol, market string, years int) ([]Row, error) {
	sinaSym := sinaSymbol(symbol, market)
	var endpoint string
	switch market {
	case "CN":
		endpoint = sinaCNDailyURL
	case "HK":
		endpoint = sinaHKDailyURL
	default:
		endpoint = sinaUSDailyURL
	}
	q := url.Values{}
	q.Set("symbol", sinaSym)
	if market == "CN" {
		q.Set("scale", "240")
		q.Set("ma", "no")
		q.Set("datalen", "1023")
	} else {
		q.Set("___qn", "3n")
	}
	body, err := c.get(endpoint+"?"+q.Encode(), sinaHeaders())
	if err != nil {
		return nil, err
	}
	arr := extractJSONArray(body)
	start := startDate(years).Format("2006-01-02")
	return parseSinaBars(arr, symbol, market, start), nil
}

func parseSinaBars(arr []interface{}, symbol, market, start string) []Row {
	rows := make([]Row, 0, len(arr))
	for _, item := range arr {
		m, ok := item.(map[string]interface{})
		if !ok {
			continue
		}
		d, ok := tradeDatePrefix(m["d"])
		if !ok || d < start {
			continue
		}
		row, ok := validateOHLCV(symbol, market, d, m["o"], m["h"], m["l"], m["c"], m["v"], "sina")
		if ok {
			rows = append(rows, row)
		}
	}
	return rows
}

func tencentDailyURL(endpoint, code string) string {
	q := url.Values{}
	q.Set("param", code+",day,,,320,qfq")
	return endpoint + "?" + q.Encode()
}

func (c *Client) fetchTencent(symbol, market string, years int) ([]Row, error) {
	code := tencentSymbol(symbol, market)
	endpoint := tencentFQURL
	if market == "HK" {
		endpoint = tencentHKFQURL
	}
	body, err := c.get(tencentDailyURL(endpoint, code), defaultHeaders())
	if err != nil {
		return nil, err
	}
	payload := map[string]interface{}{}
	if err := json.Unmarshal(body, &payload); err != nil {
		return nil, err
	}
	start := startDate(years).Format("2006-01-02")
	rows := parseTencentDaily(payload, symbol, market, start)
	return rows, nil
}

func (c *Client) FetchMinute(symbol, market string) ([]Row, error) {
	mkt := strings.ToUpper(market)
	base := minuteURLs[mkt]
	if base == "" {
		base = minuteURLs["US"]
	}
	code := tencentSymbol(symbol, mkt)
	endpoint := fmt.Sprintf("%s?code=%s", base, url.QueryEscape(code))
	body, err := c.get(endpoint, defaultHeaders())
	if err != nil {
		return nil, err
	}
	payload := map[string]interface{}{}
	if err := json.Unmarshal(body, &payload); err != nil {
		return nil, err
	}
	return parseTencentMinute(payload, symbol, mkt), nil
}

func parseTencentDaily(payload map[string]interface{}, symbol, market, start string) []Row {
	data, _ := payload["data"].(map[string]interface{})
	if data == nil {
		return nil
	}
	var series []interface{}
	for _, v := range data {
		block, _ := v.(map[string]interface{})
		if block == nil {
			continue
		}
		if day, ok := block["day"].([]interface{}); ok {
			series = day
			break
		}
		if qfq, ok := block["qfqday"].([]interface{}); ok {
			series = qfq
			break
		}
	}
	rows := make([]Row, 0, len(series))
	for _, item := range series {
		parts, ok := item.([]interface{})
		if !ok || len(parts) < 6 {
			continue
		}
		d, ok := tradeDatePrefix(parts[0])
		if !ok || d < start {
			continue
		}
		row, ok := validateOHLCV(symbol, market, d, parts[1], parts[3], parts[4], parts[2], parts[5], "tencent")
		if ok {
			rows = append(rows, row)
		}
	}
	return rows
}

func parseTencentMinute(payload map[string]interface{}, symbol, market string) []Row {
	data, _ := payload["data"].(map[string]interface{})
	if data == nil {
		return nil
	}
	var block map[string]interface{}
	for _, v := range data {
		candidate, _ := v.(map[string]interface{})
		if candidate == nil {
			continue
		}
		inner, _ := candidate["data"].(map[string]interface{})
		if inner != nil {
			if series, ok := inner["data"].([]interface{}); ok && len(series) > 0 {
				block = inner
				break
			}
		}
	}
	if block == nil {
		return nil
	}
	day := strings.TrimSpace(fmt.Sprint(block["date"]))
	if len(day) != 8 {
		return nil
	}
	dayISO := fmt.Sprintf("%s-%s-%s", day[:4], day[4:6], day[6:8])
	series, _ := block["data"].([]interface{})
	prevVol := 0.0
	rows := make([]Row, 0, len(series))
	for _, item := range series {
		text := strings.TrimSpace(fmt.Sprint(item))
		parts := strings.Fields(text)
		if len(parts) < 2 {
			continue
		}
		hhmm := parts[0]
		if len(hhmm) < 4 {
			hhmm = fmt.Sprintf("%04s", hhmm)
		}
		price := toFloat(parts[1])
		if price <= 0 {
			continue
		}
		cum := 0.0
		if len(parts) > 2 {
			cum = toFloat(parts[2])
		}
		delta := cum - prevVol
		if delta < 0 {
			delta = cum
		}
		prevVol = cum
		stamp := fmt.Sprintf("%s %s:%s:00", dayISO, hhmm[:2], hhmm[2:4])
		rows = append(rows, Row{
			Symbol: symbol, Market: market, TradeDate: stamp,
			Open: price, High: price, Low: price, Close: price, Volume: delta, Source: "tencent",
		})
	}
	return rows
}

// tradeDatePrefix returns the YYYY-MM-DD prefix of a vendor date field.
// Short, empty, or unexpected values are skipped instead of slicing [:10].
func tradeDatePrefix(raw interface{}) (string, bool) {
	if raw == nil {
		return "", false
	}
	s := strings.TrimSpace(fmt.Sprint(raw))
	if s == "" {
		return "", false
	}
	if len(s) < 10 {
		slog.Warn("kline: skip bar with short date", "date", s, "len", len(s))
		return "", false
	}
	d := s[:10]
	if _, err := time.Parse("2006-01-02", d); err != nil {
		slog.Warn("kline: skip bar with invalid date", "date", s)
		return "", false
	}
	return d, true
}

func validateOHLCV(symbol, market, tradeDate string, o, h, l, c, v interface{}, source string) (Row, bool) {
	open := toFloat(o)
	high := toFloat(h)
	low := toFloat(l)
	close := toFloat(c)
	vol := toFloat(v)
	if close <= 0 || open <= 0 || high <= 0 || low <= 0 || high < low {
		return Row{}, false
	}
	if len(tradeDate) != 10 {
		return Row{}, false
	}
	return Row{
		Symbol: symbol, Market: strings.ToUpper(market), TradeDate: tradeDate,
		Open: open, High: high, Low: low, Close: close, Volume: vol, Source: source,
	}, true
}

func toFloat(v interface{}) float64 {
	switch x := v.(type) {
	case float64:
		if math.IsNaN(x) || math.IsInf(x, 0) {
			return 0
		}
		return x
	case string:
		f, err := strconv.ParseFloat(strings.TrimSpace(x), 64)
		if err != nil || math.IsNaN(f) || math.IsInf(f, 0) {
			return 0
		}
		return f
	default:
		f, err := strconv.ParseFloat(strings.TrimSpace(fmt.Sprint(v)), 64)
		if err != nil || math.IsNaN(f) || math.IsInf(f, 0) {
			return 0
		}
		return f
	}
}

func sinaSymbol(symbol, market string) string {
	if _, sina, ok := VendorIndex(symbol, market); ok && sina != "" {
		return sina
	}
	if strings.ToUpper(market) == "CN" {
		code := strings.ToLower(strings.ReplaceAll(strings.ReplaceAll(symbol, ".SH", ""), ".SZ", ""))
		if strings.HasPrefix(code, "6") || strings.HasPrefix(code, "9") {
			return "sh" + code
		}
		return "sz" + code
	}
	return strings.ReplaceAll(symbol, "^", "")
}

func tencentSymbol(symbol, market string) string {
	mkt := strings.ToUpper(market)
	if tencent, _, ok := VendorIndex(symbol, mkt); ok && tencent != "" {
		return tencent
	}
	if mkt == "HK" {
		code := strings.ToUpper(strings.ReplaceAll(symbol, ".HK", ""))
		if regexp.MustCompile(`^\d+$`).MatchString(code) {
			return "hk" + fmt.Sprintf("%05s", code)
		}
		return "hk" + code
	}
	if mkt == "CN" {
		return sinaSymbol(symbol, mkt)
	}
	return "us" + strings.ReplaceAll(symbol, "^", "")
}

func startDate(years int) time.Time {
	years = max(1, min(years, 20))
	now := time.Now()
	target := now.AddDate(-years, 0, 0)
	return target
}

func max(a, b int) int {
	if a > b {
		return a
	}
	return b
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}

func (c *Client) get(url string, headers map[string]string) ([]byte, error) {
	req, err := http.NewRequest(http.MethodGet, url, nil)
	if err != nil {
		return nil, err
	}
	for k, v := range headers {
		req.Header.Set(k, v)
	}
	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, err
	}
	if resp.StatusCode >= 400 {
		return nil, fmt.Errorf("http %d", resp.StatusCode)
	}
	return body, nil
}

func defaultHeaders() map[string]string {
	return map[string]string{
		"User-Agent": "Mozilla/5.0 (compatible; SFP-MarketWorker/1.0)",
		"Accept":     "*/*",
	}
}

func sinaHeaders() map[string]string {
	h := defaultHeaders()
	h["Referer"] = "https://finance.sina.com.cn"
	return h
}

func extractJSONArray(text []byte) []interface{} {
	s := string(text)
	start := strings.Index(s, "[")
	end := strings.LastIndex(s, "]")
	if start < 0 || end <= start {
		return nil
	}
	var arr []interface{}
	if err := json.Unmarshal([]byte(s[start:end+1]), &arr); err != nil {
		return nil
	}
	return arr
}
