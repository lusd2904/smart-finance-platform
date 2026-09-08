package jobs

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"strings"

	"github.com/lusd2904/smart-finance-platform/workers/notify-worker/internal/crypto"
	"github.com/lusd2904/smart-finance-platform/workers/notify-worker/internal/factor"
	"github.com/lusd2904/smart-finance-platform/workers/notify-worker/internal/influx"
	"github.com/lusd2904/smart-finance-platform/workers/notify-worker/internal/market"
)

var marketsAll = []string{"CN", "HK", "US"}

var marketLabels = map[string]string{"US": "美股", "HK": "港股", "CN": "A股"}

var marketBenchmarks = map[string][]struct {
	Symbol string
	Name   string
}{
	"US": {{"^DJI", "道指"}, {"^GSPC", "标普500"}, {"^IXIC", "纳指"}},
	"HK": {{"0700.HK", "腾讯"}, {"9988.HK", "阿里"}, {"3690.HK", "美团"}, {"0005.HK", "汇丰"}},
	"CN": {{"600519", "茅台"}, {"300750", "宁德时代"}, {"601318", "平安"}, {"000858", "五粮液"}},
}

var marketNewsKeywords = map[string][]string{
	"US": {"美股", "美联储", "纳斯达克", "标普", "道琼斯", "US", "Fed"},
	"HK": {"港股", "恒生", "港交所", "HK", "香港"},
	"CN": {"A股", "上证", "深证", "创业板", "科创板", "央行", "中国"},
}

func (s *Service) influxReader() *influx.Reader {
	if s.influx == nil {
		s.influx = influx.NewReader(s.cfg)
	}
	return s.influx
}

func (s *Service) listMarketModels(ctx context.Context) ([]aiModelRow, error) {
	rows, err := s.listAllModels(ctx)
	if err != nil {
		return nil, err
	}
	return orderMarketModels(rows), nil
}

func (s *Service) listAllModels(ctx context.Context) ([]aiModelRow, error) {
	rows, err := s.db.QueryContext(ctx, `
SELECT model_id, base_url, api_key, model_code, temperature, scope
FROM ai_models WHERE status = '0' ORDER BY model_sort, model_id`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := []aiModelRow{}
	for rows.Next() {
		var r aiModelRow
		var baseURL, apiKey, modelCode, scope sql.NullString
		var temp sql.NullFloat64
		if err := rows.Scan(&r.ModelID, &baseURL, &apiKey, &modelCode, &temp, &scope); err != nil {
			return nil, err
		}
		r.BaseURL = strings.TrimSpace(baseURL.String)
		r.APIKey = crypto.DecryptCredential(strings.TrimSpace(apiKey.String), s.cfg.CredentialKey, s.cfg.JWTSecret)
		r.ModelCode = strings.TrimSpace(modelCode.String)
		if temp.Valid {
			r.Temperature = temp.Float64
		}
		r.Scope = scope.String
		if r.BaseURL != "" && r.APIKey != "" && r.ModelCode != "" {
			out = append(out, r)
		}
	}
	return out, rows.Err()
}

func orderMarketModels(models []aiModelRow) []aiModelRow {
	preferred := []string{"grok-4.6", "x-ai/grok-4.6"}
	scopeRank := map[string]int{"market": 30, "global": 20, "chat": 10}
	scored := make([]struct {
		row   aiModelRow
		score int
	}, len(models))
	for i, m := range models {
		score := scopeRank[m.Scope]
		for j, code := range preferred {
			if m.ModelCode == code {
				score += 50 - j
			}
		}
		scored[i] = struct {
			row   aiModelRow
			score int
		}{row: m, score: score}
	}
	for i := 0; i < len(scored); i++ {
		for j := i + 1; j < len(scored); j++ {
			if scored[j].score > scored[i].score {
				scored[i], scored[j] = scored[j], scored[i]
			}
		}
	}
	out := make([]aiModelRow, len(scored))
	for i, item := range scored {
		out[i] = item.row
	}
	return out
}

type moodPayload struct {
	OpenMarkets []string
	Sentiment   map[string]interface{}
	Heat        map[string]map[string]interface{}
	Indices     []map[string]interface{}
	Hint        string
	Sessions    map[string]map[string]interface{}
}

func (s *Service) loadMood(ctx context.Context) (moodPayload, error) {
	now := nowBeijing()
	sessions := market.ListSessionStatus(now)
	openMarkets := []string{}
	for mkt, info := range sessions {
		if boolFrom(info["open"], false) {
			openMarkets = append(openMarkets, mkt)
		}
	}
	sentiment, err := s.loadLatestSentiment(ctx)
	if err != nil {
		return moodPayload{}, err
	}
	heats, err := s.loadLatestHeats(ctx)
	if err != nil {
		return moodPayload{}, err
	}
	indices := s.loadIndexQuotes(ctx, openMarkets)
	hint := "三市场均未开盘，已去掉实时指数，按指标+舆情分析。"
	if len(openMarkets) > 0 {
		hint = "仅开盘市场附带实时指数；休市市场只用指标和舆情动态分析。"
	}
	return moodPayload{
		OpenMarkets: openMarkets,
		Sentiment:   sentiment,
		Heat:        heats,
		Indices:     indices,
		Hint:        hint,
		Sessions:    sessions,
	}, nil
}

func (s *Service) loadLatestSentiment(ctx context.Context) (map[string]interface{}, error) {
	row := s.db.QueryRowContext(ctx, `
SELECT summary, us_score, hk_score, a_score, us_direction, hk_direction, a_direction,
       us_reason, hk_reason, a_reason, create_time, model_name
FROM sentiment_analysis WHERE status = '0' ORDER BY analysis_id DESC LIMIT 1`)
	var summary, usDir, hkDir, aDir, usReason, hkReason, aReason, model sql.NullString
	var usScore, hkScore, aScore sql.NullFloat64
	var createTime sql.NullTime
	if err := row.Scan(&summary, &usScore, &hkScore, &aScore, &usDir, &hkDir, &aDir, &usReason, &hkReason, &aReason, &createTime, &model); err == sql.ErrNoRows {
		return map[string]interface{}{}, nil
	} else if err != nil {
		return nil, err
	}
	out := map[string]interface{}{
		"summary": summary.String,
		"usScore": nullFloat(usScore), "hkScore": nullFloat(hkScore), "aScore": nullFloat(aScore),
		"usDirection": usDir.String, "hkDirection": hkDir.String, "aDirection": aDir.String,
		"usReason": usReason.String, "hkReason": hkReason.String, "aReason": aReason.String,
		"modelName": model.String,
	}
	if createTime.Valid {
		out["analyzedAt"] = formatBeijing(createTime.Time)
	}
	return out, nil
}

func (s *Service) loadLatestHeats(ctx context.Context) (map[string]map[string]interface{}, error) {
	out := map[string]map[string]interface{}{}
	for _, mkt := range marketsAll {
		row := s.db.QueryRowContext(ctx, `
SELECT trade_date, heat_score, heat_summary FROM market_heat_daily
WHERE market = ? ORDER BY trade_date DESC LIMIT 1`, mkt)
		var tradeDate sql.NullString
		var heatScore sql.NullFloat64
		var summary sql.NullString
		if err := row.Scan(&tradeDate, &heatScore, &summary); err == sql.ErrNoRows {
			continue
		} else if err != nil {
			return nil, err
		}
		out[mkt] = map[string]interface{}{
			"market": mkt, "tradeDate": tradeDate.String,
			"heatScore": nullFloat(heatScore), "heatSummary": summary.String,
		}
	}
	return out, nil
}

func (s *Service) loadIndexQuotes(ctx context.Context, openMarkets []string) []map[string]interface{} {
	items := []map[string]interface{}{}
	reader := s.influxReader()
	for _, mkt := range openMarkets {
		benches := marketBenchmarks[mkt]
		if len(benches) == 0 {
			continue
		}
		symbols := []string{}
		for _, b := range benches {
			symbols = append(symbols, b.Symbol)
		}
		grouped, err := reader.QueryLatestKlines(ctx, mkt, symbols, 2, "-60d")
		if err != nil {
			continue
		}
		for _, b := range benches {
			quote := buildQuoteFromKlines(grouped[b.Symbol])
			if quote == nil {
				continue
			}
			quote["market"] = mkt
			quote["name"] = b.Name
			quote["symbol"] = b.Symbol
			items = append(items, quote)
		}
	}
	return items
}

func buildQuoteFromKlines(bars []influx.KlineBar) map[string]interface{} {
	if len(bars) == 0 {
		return nil
	}
	last := bars[len(bars)-1]
	prev := last.Close
	if len(bars) > 1 {
		prev = bars[len(bars)-2].Close
	}
	change := 0.0
	if prev != 0 {
		change = (last.Close - prev) / prev * 100
	}
	return map[string]interface{}{
		"last": last.Close, "prevClose": prev, "changePct": change,
		"tradeDate": last.Date,
	}
}

func (s *Service) loadKlines(ctx context.Context, marketName string, symbols []string) (map[string][]factor.Bar, error) {
	reader := s.influxReader()
	grouped, err := reader.QueryKlinesMany(ctx, marketName, symbols, "-400d", 320)
	if err != nil {
		return nil, err
	}
	out := map[string][]factor.Bar{}
	for sym, bars := range grouped {
		converted := make([]factor.Bar, 0, len(bars))
		for _, b := range bars {
			converted = append(converted, factor.Bar{
				Date: b.Date, Open: b.Open, High: b.High, Low: b.Low, Close: b.Close, Volume: b.Volume,
			})
		}
		out[sym] = converted
	}
	return out, nil
}

func (s *Service) resolveInstrumentName(symbol, marketName string) string {
	symbol = strings.ToUpper(strings.TrimSpace(symbol))
	for _, inst := range factor.TargetUniverse {
		if strings.EqualFold(inst.Symbol, symbol) && inst.Market == strings.ToUpper(marketName) {
			return inst.Name
		}
	}
	return symbol
}

func (s *Service) buildAnalyzerContext(mood moodPayload) map[string]interface{} {
	indexChg := map[string]float64{}
	for _, item := range mood.Indices {
		mkt := strings.ToUpper(stringFrom(item["market"]))
		if chg, ok := item["changePct"].(float64); ok && mkt != "" && indexChg[mkt] == 0 {
			indexChg[mkt] = chg
		}
	}
	marketsCtx := map[string]interface{}{}
	for _, mkt := range marketsAll {
		open := containsString(mood.OpenMarkets, mkt)
		heat := mood.Heat[mkt]
		var heatScore interface{}
		if heat != nil {
			heatScore = heat["heatScore"]
		}
		sentField := market.SentimentField[mkt]
		marketsCtx[mkt] = map[string]interface{}{
			"open": open, "heatScore": heatScore,
			"indexChangePct": indexChg[mkt],
			"sentiment":      mood.Sentiment[sentField],
		}
	}
	return map[string]interface{}{"markets": marketsCtx, "sentiment": mood.Sentiment}
}

func (s *Service) scoreSymbolRow(symbol, name, marketName string, bars []factor.Bar, mood moodPayload) map[string]interface{} {
	res := factor.ComputeFromKlines(bars, "balanced", nil)
	if !res.OK {
		return nil
	}
	decision := factor.DecideSignal(res.Score, "balanced", nil)
	indexChg := map[string]float64{}
	for _, item := range mood.Indices {
		mkt := strings.ToUpper(stringFrom(item["market"]))
		if chg, ok := item["changePct"].(float64); ok && mkt != "" {
			indexChg[mkt] = chg
		}
	}
	heat := mood.Heat[marketName]
	var heatScore, sentRaw, idxChg *float64
	if heat != nil {
		if v, ok := heat["heatScore"].(float64); ok {
			heatScore = &v
		}
	}
	sentField := market.SentimentField[marketName]
	if v, ok := mood.Sentiment[sentField].(float64); ok {
		sentRaw = &v
	} else if v, ok := mood.Sentiment[sentField].(int); ok {
		f := float64(v)
		sentRaw = &f
	}
	opened := containsString(mood.OpenMarkets, marketName)
	if opened {
		if v, ok := indexChg[marketName]; ok {
			idxChg = &v
		}
	}
	factorTotal := res.Score.Total
	pickScore := market.CombinePickScore(&factorTotal, sentRaw, heatScore, idxChg, opened)
	reco, stance := market.RecoFromSignal(decision.Signal, pickScore)
	tags := res.Score.Tags
	if len(tags) > 6 {
		tags = tags[:6]
	}
	if opened {
		tags = append(tags, "盘中含指数")
	} else {
		tags = append(tags, "休市无指数")
	}
	metrics := map[string]interface{}{
		"rsi14": res.Metrics.Get("rsi14", 0), "macdHist": res.Metrics.Get("macdHist", 0),
		"ma20": res.Metrics.Get("ma20", 0), "volumeRatio20": res.Metrics.Get("volumeRatio20", 0),
		"return20": res.Metrics.Get("return20", 0),
	}
	return map[string]interface{}{
		"symbol": symbol, "name": name, "market": marketName,
		"price": res.Metrics.Get("latestClose", 0), "changePct": res.Metrics.Get("dayChangePercent", 0),
		"factorScore": factorTotal, "pickScore": pickScore, "signal": decision.Signal,
		"recommendation": reco, "stance": stance, "confidence": decision.Confidence,
		"reason": decision.Reason, "summary": decision.Reason,
		"indicatorReview": strings.Join(tags, "、"), "sentimentReview": stringFrom(mood.Sentiment["summary"]),
		"operationAdvice": reco, "riskWarning": "无", "tags": tags, "source": "rule", "metrics": metrics,
		"klineCount": len(bars),
	}
}

func (s *Service) enrichWithAI(ctx context.Context, rows []map[string]interface{}, contextData map[string]interface{}) (int, string) {
	models, err := s.listMarketModels(ctx)
	if err != nil || len(models) == 0 {
		return 0, "未配置可用 AI 模型"
	}
	aiCount := 0
	lastErr := ""
	for _, row := range rows {
		var used bool
		for _, model := range models {
			temp := model.Temperature
			if temp <= 0 {
				temp = 0.2
			}
			result := s.llm.AnalyzeStockPick(ctx, model.BaseURL, model.APIKey, model.ModelCode, row, contextData, temp)
			if result.OK {
				market.ApplyAIResult(row, result.Result)
				row["modelName"] = model.ModelCode
				aiCount++
				used = true
				break
			}
			lastErr = result.Error
			if result.Code == 429 || !llmGatewayFailover(result.Code) {
				break
			}
		}
		if !used && lastErr == "" {
			lastErr = "模型未返回有效 JSON"
		}
	}
	return aiCount, lastErr
}

func llmGatewayFailover(code int) bool {
	return code == 502 || code == 503 || code == 524
}

func (s *Service) listTop50(ctx context.Context, marketName, tradeDate string) ([]market.Candidate, error) {
	rows, err := s.db.QueryContext(ctx, `
SELECT symbol, name FROM market_top50_snapshot
WHERE market = ? AND trade_date = ? ORDER BY rank_no`, marketName, tradeDate)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := []market.Candidate{}
	for rows.Next() {
		var symbol, name sql.NullString
		if err := rows.Scan(&symbol, &name); err != nil {
			return nil, err
		}
		out = append(out, market.Candidate{
			Symbol: symbol.String, Name: name.String, Market: marketName, Category: "listed",
		})
	}
	return out, rows.Err()
}

func featuredForMarket(marketName string) []market.Candidate {
	out := []market.Candidate{}
	for _, inst := range factor.TargetUniverse {
		if inst.Market == marketName {
			out = append(out, market.Candidate{
				Symbol: inst.Symbol, Name: inst.Name, Market: inst.Market, Category: inst.Category,
			})
		}
	}
	return out
}

func nullFloat(v sql.NullFloat64) interface{} {
	if v.Valid {
		return v.Float64
	}
	return nil
}

func containsString(items []string, target string) bool {
	for _, item := range items {
		if item == target {
			return true
		}
	}
	return false
}

func dumpJSON(v interface{}, limit int) string {
	b, _ := json.Marshal(v)
	if len(b) > limit {
		return string(b[:limit])
	}
	return string(b)
}

func normalizeMarketReviewResult(parsed map[string]interface{}, fallback map[string]interface{}) map[string]interface{} {
	out := map[string]interface{}{}
	for k, v := range fallback {
		out[k] = v
	}
	if parsed == nil {
		return out
	}
	keys := []string{"title", "stance", "score", "summary", "index_review", "news_review", "sentiment_review", "outlook", "risk_warning", "key_points"}
	for _, key := range keys {
		if v := parsed[key]; v != nil && v != "" {
			out[key] = v
		}
	}
	stance := fmt.Sprint(out["stance"])
	if stance != "偏多" && stance != "偏空" && stance != "中性" {
		out["stance"] = fallback["stance"]
	}
	score := intFrom(out["score"])
	if score < 0 {
		score = 0
	}
	if score > 100 {
		score = 100
	}
	out["score"] = score
	return out
}

func quoteFromBars(bars []influx.KlineBar) map[string]interface{} {
	q := buildQuoteFromKlines(bars)
	if q == nil {
		return map[string]interface{}{}
	}
	change, _ := q["changePct"].(float64)
	text := fmt.Sprintf("%+.2f%%", change)
	q["changeRate"] = change
	q["changeText"] = text
	return q
}
