package dashboard

import (
	"context"
	"crypto/sha256"
	"encoding/json"
	"fmt"
	"sort"
	"strings"
	"time"

	"github.com/redis/go-redis/v9"

	"github.com/lusd2904/smart-finance-platform/services/sfp-backend/internal/scheduler"
	"github.com/lusd2904/smart-finance-platform/services/sfp-backend/internal/store"
	"github.com/lusd2904/smart-finance-platform/services/sfp-backend/internal/timeutil"
)

const summaryCacheTTL = 30 * time.Second

var sectionPerms = map[string]string{
	"asset": "quant:factor:list", "quotes": "market:kline:list", "heat": "market:heat:list",
	"watchSignals": "market:watchlist:list", "sentiment": "sentiment:news:list",
	"briefings": "market:finance:list", "health": "analysis:job:list",
}

type Service struct {
	db    *store.DB
	redis *redis.Client
	sched *scheduler.Runtime
}

func New(db *store.DB, rdb *redis.Client, sched *scheduler.Runtime) *Service {
	return &Service{db: db, redis: rdb, sched: sched}
}

func (s *Service) Summary(ctx context.Context, userID int64, permissions []string, refresh bool) (map[string]interface{}, error) {
	cacheKey := summaryCacheKey(userID, permissions)
	if !refresh {
		if cached, err := s.getJSON(ctx, cacheKey); err == nil && cached != nil {
			if cached["generatedAt"] != nil {
				cached["cached"] = true
				return cached, nil
			}
		}
	}
	has := permChecker(permissions)
	sections := s.collect(ctx, userID, has)
	summary := map[string]interface{}{
		"generatedAt": timeutil.NowBeijingRFC(),
		"sessions":    marketSessions(),
		"cached":      false,
	}
	for k, v := range sections {
		summary[k] = v
	}
	_ = s.setJSON(ctx, cacheKey, summary, summaryCacheTTL)
	return summary, nil
}

func summaryCacheKey(userID int64, permissions []string) string {
	perms := make([]string, 0, len(permissions))
	for _, p := range permissions {
		if p != "" {
			perms = append(perms, p)
		}
	}
	sort.Strings(perms)
	digest := sha256.Sum256([]byte(strings.Join(perms, ",")))
	return fmt.Sprintf("dashboard:summary:%d:%x", userID, digest[:8])
}

func permChecker(permissions []string) func(string) bool {
	set := map[string]bool{}
	for _, p := range permissions {
		set[p] = true
	}
	if set["*:*:*"] {
		return func(string) bool { return true }
	}
	return func(perm string) bool { return set[perm] }
}

func (s *Service) collect(ctx context.Context, userID int64, has func(string) bool) map[string]interface{} {
	out := map[string]interface{}{}
	sections := []struct {
		key  string
		perm string
		fn   func(context.Context) map[string]interface{}
	}{
		{"asset", sectionPerms["asset"], func(ctx context.Context) map[string]interface{} { return s.assetBlock(ctx) }},
		{"quotes", sectionPerms["quotes"], func(ctx context.Context) map[string]interface{} { return s.quotesBlock(ctx) }},
		{"heat", sectionPerms["heat"], func(ctx context.Context) map[string]interface{} { return s.heatBlock(ctx) }},
		{"watchSignals", sectionPerms["watchSignals"], func(ctx context.Context) map[string]interface{} {
			if userID <= 0 {
				return denied("watchSignals")
			}
			return s.watchSignalsBlock(ctx, userID)
		}},
		{"sentiment", sectionPerms["sentiment"], func(ctx context.Context) map[string]interface{} { return s.sentimentBlock(ctx) }},
		{"briefings", sectionPerms["briefings"], func(ctx context.Context) map[string]interface{} { return s.briefingsBlock(ctx) }},
		{"health", sectionPerms["health"], func(ctx context.Context) map[string]interface{} { return s.healthBlock(ctx) }},
	}
	for _, sec := range sections {
		if !has(sec.perm) {
			out[sec.key] = denied(sec.key)
			continue
		}
		out[sec.key] = runSection(sec.key, sec.fn(ctx))
	}
	return out
}

func runSection(section string, block map[string]interface{}) map[string]interface{} {
	if block == nil {
		return empty(section, "unavailable")
	}
	return block
}

func empty(section, reason string) map[string]interface{} {
	return map[string]interface{}{"ok": false, "reason": reason, "data": nil}
}

func denied(section string) map[string]interface{} {
	return empty(section, "denied")
}

func marketSessions() []map[string]interface{} {
	meta := map[string]map[string]string{
		"US": {"label": "美股", "timezone": "America/New_York"},
		"HK": {"label": "港股", "timezone": "Asia/Hong_Kong"},
		"CN": {"label": "A股", "timezone": "Asia/Shanghai"},
	}
	var sessions []map[string]interface{}
	for _, market := range []string{"US", "HK", "CN"} {
		m := meta[market]
		loc, err := time.LoadLocation(m["timezone"])
		if err != nil {
			loc = time.UTC
		}
		now := time.Now().In(loc)
		isWeekday := now.Weekday() >= time.Monday && now.Weekday() <= time.Friday
		inSession := isWeekday && now.Hour() >= 9 && now.Hour() < 16
		status := "closed"
		if !isWeekday {
			status = "weekend"
		} else if inSession {
			status = "open"
		}
		sessions = append(sessions, map[string]interface{}{
			"market": market, "label": m["label"], "timezone": m["timezone"],
			"localDate": now.Format("2006-01-02"), "localTime": now.Format("15:04"), "status": status,
		})
	}
	return sessions
}

func (s *Service) assetBlock(ctx context.Context) map[string]interface{} {
	overview, _ := s.getJSON(ctx, "readmodel:scheduled:overview")
	asset, positions := map[string]interface{}(nil), map[string]interface{}(nil)
	if overview != nil {
		if a, ok := overview["asset"].(map[string]interface{}); ok {
			asset = a
		}
		if p, ok := overview["position"].(map[string]interface{}); ok {
			positions = p
		}
	}
	if asset == nil {
		return map[string]interface{}{
			"ok": true, "reason": nil,
			"data": map[string]interface{}{
				"configured": false, "netAssets": nil, "availableCash": nil, "totalCash": nil, "currency": nil,
				"positionCount": posCount(positions), "totalUnrealizedPnl": posPnl(positions),
				"message": "读模型快照尚未生成",
			},
		}
	}
	return map[string]interface{}{
		"ok": true, "reason": nil,
		"data": map[string]interface{}{
			"configured": asset["configured"], "netAssets": asset["netAssets"], "availableCash": asset["availableCash"],
			"totalCash": asset["totalCash"], "currency": asset["currency"],
			"positionCount": posCount(positions), "totalUnrealizedPnl": posPnl(positions),
			"message": asset["message"],
		},
	}
}

func posCount(pos map[string]interface{}) int {
	if pos == nil {
		return 0
	}
	if v, ok := pos["count"].(float64); ok {
		return int(v)
	}
	return 0
}

func posPnl(pos map[string]interface{}) interface{} {
	if pos == nil {
		return nil
	}
	return pos["totalUnrealizedPnl"]
}

func (s *Service) quotesBlock(ctx context.Context) map[string]interface{} {
	board, _ := s.getJSON(ctx, "sfp:cache:board:quotes")
	if board == nil {
		board, _ = s.getJSON(ctx, "readmodel:scheduled:board")
	}
	if board == nil {
		return map[string]interface{}{"ok": false, "reason": "看板缓存尚未生成", "data": map[string]interface{}{
			"indices": []interface{}{}, "quotes": []interface{}{},
		}}
	}
	indices := sliceLimit(board["indices"], 8)
	quotes := sliceLimit(board["quotes"], 8)
	ok := len(indices) > 0 || len(quotes) > 0
	reason := interface{}(nil)
	if !ok {
		reason = board["message"]
		if reason == nil {
			reason = "看板缓存尚未生成"
		}
	}
	return map[string]interface{}{
		"ok": ok, "reason": reason,
		"data": map[string]interface{}{
			"indices": indices, "quotes": quotes, "source": board["source"], "stale": board["stale"],
		},
	}
}

func sliceLimit(v interface{}, n int) []interface{} {
	arr, ok := v.([]interface{})
	if !ok {
		return []interface{}{}
	}
	if len(arr) > n {
		return arr[:n]
	}
	return arr
}

func (s *Service) heatBlock(ctx context.Context) map[string]interface{} {
	markets := map[string]interface{}{}
	for _, market := range []string{"US", "HK", "CN"} {
		row, err := s.db.GetLatestHeat(ctx, market)
		if err != nil || row == nil {
			markets[market] = nil
			continue
		}
		markets[market] = row
	}
	ok := false
	for _, v := range markets {
		if v != nil {
			ok = true
			break
		}
	}
	reason := interface{}(nil)
	if !ok {
		reason = "暂无热度快照，收盘任务完成后写入"
	}
	return map[string]interface{}{"ok": ok, "reason": reason, "data": markets}
}

func (s *Service) watchSignalsBlock(ctx context.Context, userID int64) map[string]interface{} {
	count, bullish, bearish, neutral, items, err := s.db.WatchlistOverview(ctx, userID)
	if err != nil {
		return empty("watchSignals", "unavailable")
	}
	signals := make([]map[string]interface{}, 0, len(items))
	for _, it := range items {
		sig := map[string]interface{}{
			"symbol": it.Symbol, "market": it.Market, "name": it.Name, "stance": it.Stance,
			"confidence": it.Confidence, "recommendation": it.Recommendation, "summary": it.Summary,
			"analysisTime": it.AnalysisTime,
		}
		if it.Last != nil {
			sig["last"] = *it.Last
		}
		if it.ChangeRate != nil {
			sig["changeRate"] = *it.ChangeRate
		}
		signals = append(signals, sig)
	}
	ok := len(signals) > 0
	reason := interface{}(nil)
	if !ok {
		reason = "暂无启用中的自选标的"
	}
	return map[string]interface{}{
		"ok": ok, "reason": reason,
		"data": map[string]interface{}{
			"count": count, "bullish": bullish, "bearish": bearish, "neutral": neutral,
			"aiAvailable": true, "signals": signals,
		},
	}
}

func (s *Service) sentimentBlock(ctx context.Context) map[string]interface{} {
	stats, err := s.db.SentimentStats(ctx)
	if err != nil {
		return empty("sentiment", "unavailable")
	}
	latest, _ := s.db.LatestSentimentAnalysis(ctx)
	return map[string]interface{}{
		"ok": true, "reason": nil,
		"data": map[string]interface{}{
			"total": stats["total"], "today": stats["today"], "unanalyzed": stats["unanalyzed"],
			"latestAnalysis": latest,
		},
	}
}

func (s *Service) briefingsBlock(ctx context.Context) map[string]interface{} {
	data, err := s.db.ListFinanceBriefings(ctx, 8)
	if err != nil {
		return empty("briefings", "unavailable")
	}
	ok := len(data) > 0
	reason := interface{}(nil)
	if !ok {
		reason = "简报尚未生成，采集任务完成后展示"
	}
	return map[string]interface{}{"ok": ok, "reason": reason, "data": data}
}

func (s *Service) healthBlock(ctx context.Context) map[string]interface{} {
	since := time.Now().Add(-24 * time.Hour)
	total, failed, _ := s.db.CountJobLogsSince(ctx, since)
	jobName, status, createTime, _ := s.db.LatestJobLog(ctx)
	lastJob := interface{}(nil)
	if jobName != "" {
		lastJob = map[string]interface{}{"jobName": jobName, "status": status, "createTime": createTime}
	}
	heartbeat, _ := s.sched.ReadHeartbeat(ctx)
	alive := scheduler.IsAlive(heartbeat)
	return map[string]interface{}{
		"ok": true, "reason": nil,
		"data": map[string]interface{}{
			"jobs24h": map[string]interface{}{"total": total, "failed": failed},
			"lastJob": lastJob,
			"schedulerAlive": alive,
			"coverage": nil,
		},
	}
}

func (s *Service) getJSON(ctx context.Context, key string) (map[string]interface{}, error) {
	if s.redis == nil {
		return nil, nil
	}
	raw, err := s.redis.Get(ctx, key).Result()
	if err != nil || raw == "" {
		return nil, err
	}
	var out map[string]interface{}
	if err := json.Unmarshal([]byte(raw), &out); err != nil {
		return nil, err
	}
	return out, nil
}

func (s *Service) setJSON(ctx context.Context, key string, value map[string]interface{}, ttl time.Duration) error {
	if s.redis == nil {
		return nil
	}
	raw, err := json.Marshal(value)
	if err != nil {
		return err
	}
	return s.redis.Set(ctx, key, raw, ttl).Err()
}
