package flow

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"

	"github.com/lusd2904/smart-finance-platform/services/market-read/pkg/cache"
	"github.com/lusd2904/smart-finance-platform/services/market-read/pkg/timeutil"
)

const sectorCachePrefix = "market:flow:board:"

var emHeaders = map[string]string{
	"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
	"Referer":    "https://data.eastmoney.com/",
	"Accept":     "application/json, text/plain, */*",
}

var sectorFS = map[string]string{
	"industry": "m:90+t:2",
	"concept":  "m:90+t:3",
}

type Service struct {
	Cache  *cache.Cache
	Client *http.Client
}

func New(cacheClient *cache.Cache) *Service {
	return &Service{
		Cache:  cacheClient,
		Client: &http.Client{Timeout: 12 * time.Second},
	}
}

func (s *Service) GetBoard(ctx context.Context, sectorKind string, limit int) map[string]interface{} {
	kind := sectorKind
	if kind != "industry" && kind != "concept" {
		kind = "industry"
	}
	if limit < 5 {
		limit = 5
	}
	if limit > 30 {
		limit = 30
	}
	cacheKey := fmt.Sprintf("%s%s:%d", sectorCachePrefix, kind, limit)
	if cached, err := s.Cache.GetJSON(ctx, cacheKey); err == nil && cached != nil && cached["sectors"] != nil {
		return cached
	}
	sectors := s.fetchSectors(kind, limit)
	payload := map[string]interface{}{
		"asOf":          timeutil.NowBeijing().Format("2006-01-02 15:04:05"),
		"tradeDate":     time.Now().Format("2006-01-02"),
		"sectorKind":    kind,
		"sectors":       sectors,
		"industry":      sectors,
		"concept":       []interface{}{},
		"limitUp":       []interface{}{},
		"limitUpCount":  0,
		"lhb":           []interface{}{},
		"calendar":      map[string]interface{}{"date": time.Now().Format("2006-01-02"), "macro": []interface{}{}, "earnings": []interface{}{}},
		"sources":       map[string]interface{}{"sectors": "eastmoney", "limitUp": "eastmoney", "lhb": "eastmoney", "calendar": "nasdaq"},
		"stale":         len(sectors) == 0,
	}
	if kind == "concept" {
		payload["sectors"] = sectors
	}
	_ = s.Cache.SetJSON(ctx, cacheKey, payload, 90)
	return payload
}

func (s *Service) fetchSectors(kind string, limit int) []map[string]interface{} {
	fs, ok := sectorFS[kind]
	if !ok {
		fs = sectorFS["industry"]
	}
	url := fmt.Sprintf(
		"https://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=%d&po=1&np=1&fltt=2&invt=2&fid=f62&fs=%s&fields=f12,f14,f2,f3,f62,f184,f204,f205",
		limit, fs)
	req, err := http.NewRequest(http.MethodGet, url, nil)
	if err != nil {
		return nil
	}
	for k, v := range emHeaders {
		req.Header.Set(k, v)
	}
	resp, err := s.Client.Do(req)
	if err != nil {
		return nil
	}
	defer resp.Body.Close()
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil
	}
	var payload map[string]interface{}
	if json.Unmarshal(body, &payload) != nil {
		return nil
	}
	return parseSectorPayload(payload, limit)
}

func parseSectorPayload(payload map[string]interface{}, limit int) []map[string]interface{} {
	data, _ := payload["data"].(map[string]interface{})
	rows, _ := data["diff"].([]interface{})
	items := []map[string]interface{}{}
	for _, row := range rows {
		m, ok := row.(map[string]interface{})
		if !ok {
			continue
		}
		name := strings.TrimSpace(fmt.Sprint(m["f14"]))
		if name == "" {
			continue
		}
		items = append(items, map[string]interface{}{
			"code":           fmt.Sprint(m["f12"]),
			"name":           name,
			"last":           m["f2"],
			"changePct":      m["f3"],
			"netInflow":      m["f62"],
			"netInflowPct":   m["f184"],
			"leaderName":     strings.ReplaceAll(fmt.Sprint(m["f204"]), " ", ""),
			"leaderCode":     fmt.Sprint(m["f205"]),
		})
		if len(items) >= limit {
			break
		}
	}
	return items
}
