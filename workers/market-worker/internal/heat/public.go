package heat

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strconv"
	"strings"
	"time"
)

const (
	publicUA             = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
	amountSmallThreshold = 1e8
	sinaCapUnitThreshold = 1e11
)

var httpClient = &http.Client{Timeout: 20 * time.Second}

type textGetter func(rawURL string) (string, error)

var getText textGetter = defaultGetText

func defaultGetText(rawURL string) (string, error) {
	req, err := http.NewRequest(http.MethodGet, rawURL, nil)
	if err != nil {
		return "", err
	}
	req.Header.Set("User-Agent", publicUA)
	req.Header.Set("Referer", "https://finance.sina.com.cn")
	resp, err := httpClient.Do(req)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return "", fmt.Errorf("GET %s status %d", rawURL, resp.StatusCode)
	}
	body, err := io.ReadAll(io.LimitReader(resp.Body, 8<<20))
	if err != nil {
		return "", err
	}
	return decodeBestEffort(body), nil
}

func decodeBestEffort(raw []byte) string {
	// Rank APIs are UTF-8/JSON. Tencent qt.gtimg.cn is GBK, but numeric ~ fields are ASCII.
	return string(raw)
}

func FetchPublicUniverse(market string) ([]Candidate, Extras) {
	switch market {
	case "CN":
		return fetchCN()
	case "HK":
		return fetchHK()
	default:
		return fetchUS()
	}
}

func fetchCN() ([]Candidate, Extras) {
	tencent := safeQuote(func() (map[string]any, error) { return ParseTencentQuote(mustGet("https://qt.gtimg.cn/q=sh000001")) })
	emIndex := safeQuote(func() (map[string]any, error) { return FetchEastmoneyIndex("1.000001") })
	sinaRows := safeList(func() ([]Candidate, error) { return FetchSinaCNRank(3) })
	emRows := safeList(func() ([]Candidate, error) {
		return FetchEastmoneyRank("m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23", 1, 80)
	})
	extras := Extras{Source: []string{"tencent-index", "sina-rank", "eastmoney-rank"}}
	extras.IndexChange = firstFloat(emIndex["change_pct"], tencent["change_pct"])
	extras.Advance = asIntPtr(emIndex["advance"])
	extras.Decline = asIntPtr(emIndex["decline"])
	extras.Flat = asIntPtr(emIndex["flat"])
	extras.IndexTurnover = firstFloat(emIndex["turnover"], tencent["turnover"])
	return MergeCandidates(emRows, sinaRows), extras
}

func fetchHK() ([]Candidate, Extras) {
	tencent := safeQuote(func() (map[string]any, error) { return ParseTencentQuote(mustGet("https://qt.gtimg.cn/q=r_hkHSI")) })
	emIndex := safeQuote(func() (map[string]any, error) { return FetchEastmoneyIndex("116.HSI") })
	sinaRows := safeList(func() ([]Candidate, error) { return FetchSinaHKRank(3) })
	emRows := safeList(func() ([]Candidate, error) {
		return FetchEastmoneyRank("m:128+t:3,m:128+t:4,m:128+t:1,m:128+t:2", 1, 80)
	})
	extras := Extras{Source: []string{"tencent-index", "sina-rank", "eastmoney-rank"}}
	extras.IndexChange = firstFloat(tencent["change_pct"], emIndex["change_pct"])
	extras.Advance = asIntPtr(emIndex["advance"])
	extras.Decline = asIntPtr(emIndex["decline"])
	extras.Flat = asIntPtr(emIndex["flat"])
	extras.IndexTurnover = firstFloat(tencent["turnover"], emIndex["turnover"])
	return MergeCandidates(emRows, sinaRows), extras
}

func fetchUS() ([]Candidate, Extras) {
	sinaVol := safeList(func() ([]Candidate, error) { return FetchSinaUSRank(6, "volume") })
	sinaAmt := safeList(func() ([]Candidate, error) { return FetchSinaUSRank(3, "amount") })
	emRows := safeList(func() ([]Candidate, error) {
		return FetchEastmoneyRank("m:105,m:106,m:107", 1, 80)
	})
	emIndex := safeQuote(func() (map[string]any, error) { return FetchEastmoneyIndex("100.SPX") })
	extras := Extras{Source: []string{"sina-us", "eastmoney-rank", "eastmoney-index"}}
	extras.IndexChange = firstFloat(emIndex["change_pct"])
	extras.Advance = asIntPtr(emIndex["advance"])
	extras.Decline = asIntPtr(emIndex["decline"])
	extras.Flat = asIntPtr(emIndex["flat"])
	return MergeCandidates(emRows, sinaVol, sinaAmt), extras
}

func ParseTencentQuote(text string) (map[string]any, error) {
	start := strings.Index(text, `="`)
	if start < 0 {
		return map[string]any{}, nil
	}
	rest := text[start+2:]
	end := strings.Index(rest, `"`)
	if end < 0 {
		return map[string]any{}, nil
	}
	parts := strings.Split(rest[:end], "~")
	const minParts = 6
	if len(parts) < minParts {
		return map[string]any{}, nil
	}
	last := parseFloat(indexAt(parts, 3))
	prev := parseFloat(indexAt(parts, 4))
	var change *float64
	if len(parts) > 32 {
		change = parseFloat(parts[32])
	}
	if change == nil && last != nil && prev != nil && *prev != 0 {
		v := round4((*last / *prev - 1) * 100)
		change = &v
	}
	var turnover *float64
	if len(parts) > 37 {
		turnover = parseFloat(parts[37])
		if turnover != nil && *turnover < amountSmallThreshold && last != nil {
			turnover = parseFloat(indexAt(parts, 36))
		}
	}
	out := map[string]any{"name": indexAt(parts, 1), "last": last, "prev": prev, "change_pct": change, "turnover": turnover}
	return out, nil
}

func FetchEastmoneyIndex(secid string) (map[string]any, error) {
	qs := url.Values{"fltt": {"2"}, "secids": {secid}, "fields": {"f3,f6,f14,f104,f105,f106"}}
	payload, err := getJSON("https://push2.eastmoney.com/api/qt/ulist.np/get?" + qs.Encode())
	if err != nil {
		return nil, err
	}
	rows := jsonList(jsonMap(payload["data"])["diff"])
	if len(rows) == 0 {
		return map[string]any{}, nil
	}
	row := jsonMap(rows[0])
	return map[string]any{
		"name":       fmt.Sprint(row["f14"]),
		"change_pct": anyFloat(row["f3"]),
		"turnover":   anyFloat(row["f6"]),
		"advance":    anyInt(row["f104"]),
		"decline":    anyInt(row["f105"]),
		"flat":       anyInt(row["f106"]),
	}, nil
}

func FetchEastmoneyRank(fs string, pages, pageSize int) ([]Candidate, error) {
	out := []Candidate{}
	for page := 1; page <= pages; page++ {
		qs := url.Values{
			"pn": {strconv.Itoa(page)}, "pz": {strconv.Itoa(pageSize)}, "po": {"1"}, "np": {"1"},
			"fltt": {"2"}, "invt": {"2"}, "fs": {fs}, "fid": {"f6"},
			"fields": {"f12,f14,f2,f3,f4,f6,f7,f8,f9,f10,f15,f16,f18,f20,f62"},
		}
		payload, err := getJSON("https://push2.eastmoney.com/api/qt/clist/get?" + qs.Encode())
		if err != nil {
			return out, err
		}
		rows := jsonList(jsonMap(payload["data"])["diff"])
		if len(rows) == 0 {
			break
		}
		for _, raw := range rows {
			out = append(out, candidateFromEastmoney(jsonMap(raw)))
		}
	}
	return out, nil
}

func FetchSinaCNRank(pages int) ([]Candidate, error) {
	out := []Candidate{}
	for page := 1; page <= pages; page++ {
		qs := url.Values{"page": {strconv.Itoa(page)}, "num": {"80"}, "sort": {"amount"}, "asc": {"0"}, "node": {"hs_a"}}
		text, err := getText("https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData?" + qs.Encode())
		if err != nil {
			return out, err
		}
		var rows []map[string]any
		if err := json.Unmarshal([]byte(text), &rows); err != nil || len(rows) == 0 {
			break
		}
		for _, row := range rows {
			cap := anyFloat(row["mktcap"])
			if cap != nil && *cap < sinaCapUnitThreshold {
				v := *cap * 10000
				cap = &v
			}
			c := Candidate{
				Symbol:       fmt.Sprint(orDefault(row["code"], row["symbol"])),
				Name:         fmt.Sprint(orDefault(row["name"], "")),
				MarketCap:    cap,
				Turnover:     anyFloat(row["amount"]),
				ChangePct:    anyFloat(row["changepercent"]),
				Last:         anyFloat(row["trade"]),
				ChangeAmount: pickFloat(row, "pricechange", "change"),
				TurnoverRate: pickFloat(row, "turnoverratio", "turnoverRatio"),
				PE:           pickFloat(row, "per", "pe"),
			}
			fillDerived(&c, anyFloat(row["high"]), anyFloat(row["low"]), pickFloat(row, "settlement", "preclose", "prevclose"))
			out = append(out, c)
		}
	}
	return out, nil
}

func FetchSinaHKRank(pages int) ([]Candidate, error) {
	out := []Candidate{}
	for page := 1; page <= pages; page++ {
		qs := url.Values{"page": {strconv.Itoa(page)}, "num": {"80"}, "sort": {"amount"}, "asc": {"0"}, "node": {"qbgg_hk"}}
		text, err := getText("https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHKStockData?" + qs.Encode())
		if err != nil {
			return out, err
		}
		var rows []map[string]any
		if err := json.Unmarshal([]byte(text), &rows); err != nil || len(rows) == 0 {
			break
		}
		for _, row := range rows {
			cap := anyFloat(row["market_value"])
			if cap != nil && *cap <= 0 {
				cap = nil
			}
			c := Candidate{
				Symbol:       fmt.Sprint(orDefault(row["symbol"], "")),
				Name:         fmt.Sprint(orDefault(row["name"], row["engname"])),
				MarketCap:    cap,
				Turnover:     anyFloat(row["amount"]),
				ChangePct:    anyFloat(row["changepercent"]),
				Last:         anyFloat(row["lasttrade"]),
				ChangeAmount: pickFloat(row, "change", "pricechange"),
				PE:           pickFloat(row, "pe", "per"),
			}
			fillDerived(&c, anyFloat(row["high"]), anyFloat(row["low"]), pickFloat(row, "prevclose", "preclose", "settlement"))
			out = append(out, c)
		}
	}
	return out, nil
}

func FetchSinaUSRank(pages int, sortField string) ([]Candidate, error) {
	out := []Candidate{}
	for page := 1; page <= pages; page++ {
		qs := url.Values{"page": {strconv.Itoa(page)}, "num": {"80"}, "sort": {sortField}, "asc": {"0"}, "market": {""}, "id": {""}}
		text, err := getText("https://stock.finance.sina.com.cn/usstock/api/jsonp.php/var%20xx=/US_CategoryService.getList?" + qs.Encode())
		if err != nil {
			return out, err
		}
		raw, err := extractJSONP(text)
		if err != nil {
			break
		}
		var payload map[string]any
		if err := json.Unmarshal(raw, &payload); err != nil {
			var rows []map[string]any
			if err := json.Unmarshal(raw, &rows); err != nil {
				break
			}
			for _, row := range rows {
				out = append(out, sinaUSRow(row))
			}
			continue
		}
		rows := jsonList(payload["data"])
		if len(rows) == 0 {
			break
		}
		for _, rawRow := range rows {
			out = append(out, sinaUSRow(jsonMap(rawRow)))
		}
	}
	return out, nil
}

func sinaUSRow(row map[string]any) Candidate {
	price := anyFloat(row["price"])
	volume := anyFloat(row["volume"])
	amount := anyFloat(row["amount"])
	if amount == nil && price != nil && volume != nil {
		v := *price * *volume
		amount = &v
	}
	c := Candidate{
		Symbol:       strings.ToUpper(fmt.Sprint(orDefault(row["symbol"], ""))),
		Name:         fmt.Sprint(orDefault(row["cname"], row["name"])),
		MarketCap:    anyFloat(row["mktcap"]),
		Turnover:     amount,
		ChangePct:    anyFloat(row["chg"]),
		Last:         price,
		ChangeAmount: pickFloat(row, "diff", "pricechange", "change"),
		TurnoverRate: pickFloat(row, "turnoverratio", "turnoverRate"),
		VolumeRatio:  pickFloat(row, "volumeRatio", "volratio"),
		Amplitude:    pickFloat(row, "amplitude"),
		PE:           pickFloat(row, "pe", "per", "perc"),
	}
	fillDerived(&c, anyFloat(row["high"]), anyFloat(row["low"]), pickFloat(row, "preclose", "prevclose", "settlement"))
	return c
}

func candidateFromEastmoney(row map[string]any) Candidate {
	c := Candidate{
		Symbol:        fmt.Sprint(row["f12"]),
		Name:          fmt.Sprint(orDefault(row["f14"], row["f12"])),
		MarketCap:     anyFloat(row["f20"]),
		Turnover:      anyFloat(row["f6"]),
		ChangePct:     anyFloat(row["f3"]),
		Last:          anyFloat(row["f2"]),
		ChangeAmount:  anyFloat(row["f4"]),
		TurnoverRate:  anyFloat(row["f8"]),
		VolumeRatio:   anyFloat(row["f10"]),
		Amplitude:     anyFloat(row["f7"]),
		PE:            anyFloat(row["f9"]),
		MainNetInflow: anyFloat(row["f62"]),
	}
	fillDerived(&c, anyFloat(row["f15"]), anyFloat(row["f16"]), anyFloat(row["f18"]))
	return c
}

func pickFloat(row map[string]any, keys ...string) *float64 {
	for _, key := range keys {
		if f := anyFloat(row[key]); f != nil {
			return f
		}
	}
	return nil
}

func fillDerived(c *Candidate, high, low, prev *float64) {
	if c == nil {
		return
	}
	if c.ChangeAmount == nil && c.Last != nil && c.ChangePct != nil {
		denom := 100 + *c.ChangePct
		if denom != 0 {
			v := *c.Last * *c.ChangePct / denom
			c.ChangeAmount = &v
		}
	}
	if c.Amplitude == nil && high != nil && low != nil && prev != nil && *prev != 0 {
		v := (*high - *low) / *prev * 100
		c.Amplitude = &v
	}
}

func extractJSONP(raw string) ([]byte, error) {
	start := strings.Index(raw, "(")
	end := strings.LastIndex(raw, ")")
	if start < 0 || end <= start {
		return nil, fmt.Errorf("jsonp payload missing")
	}
	return []byte(raw[start+1 : end]), nil
}

func getJSON(rawURL string) (map[string]any, error) {
	text, err := getText(rawURL)
	if err != nil {
		return nil, err
	}
	var payload map[string]any
	if err := json.Unmarshal([]byte(text), &payload); err != nil {
		return nil, err
	}
	return payload, nil
}

func mustGet(rawURL string) string {
	text, err := getText(rawURL)
	if err != nil {
		return ""
	}
	return text
}

func safeQuote(fn func() (map[string]any, error)) map[string]any {
	out, err := fn()
	if err != nil || out == nil {
		return map[string]any{}
	}
	return out
}

func safeList(fn func() ([]Candidate, error)) []Candidate {
	out, err := fn()
	if err != nil || out == nil {
		return []Candidate{}
	}
	return out
}

func parseFloat(raw string) *float64 {
	text := strings.TrimSpace(strings.ReplaceAll(strings.ReplaceAll(raw, ",", ""), "%", ""))
	if text == "" || text == "-" {
		return nil
	}
	v, err := strconv.ParseFloat(text, 64)
	if err != nil {
		return nil
	}
	return &v
}

func anyFloat(v any) *float64 {
	if v == nil {
		return nil
	}
	switch x := v.(type) {
	case float64:
		return &x
	case json.Number:
		f, err := x.Float64()
		if err != nil {
			return nil
		}
		return &f
	case int:
		f := float64(x)
		return &f
	case string:
		return parseFloat(x)
	default:
		return parseFloat(fmt.Sprint(x))
	}
}

func anyInt(v any) int {
	f := anyFloat(v)
	if f == nil {
		return 0
	}
	return int(*f)
}

func asIntPtr(v any) *int {
	if v == nil {
		return nil
	}
	n := anyInt(v)
	return &n
}

func firstFloat(vals ...any) *float64 {
	for _, v := range vals {
		if f := asFloatPtr(v); f != nil {
			return f
		}
	}
	return nil
}

func asFloatPtr(v any) *float64 {
	if v == nil {
		return nil
	}
	if f, ok := v.(*float64); ok {
		return f
	}
	return anyFloat(v)
}

func jsonMap(v any) map[string]any {
	if m, ok := v.(map[string]any); ok {
		return m
	}
	return map[string]any{}
}

func jsonList(v any) []any {
	if list, ok := v.([]any); ok {
		return list
	}
	return nil
}

func indexAt(parts []string, i int) string {
	if i < 0 || i >= len(parts) {
		return ""
	}
	return parts[i]
}

func orDefault(v, fallback any) any {
	if v == nil {
		return fallback
	}
	s := fmt.Sprint(v)
	if s == "" || s == "<nil>" {
		return fallback
	}
	return v
}
