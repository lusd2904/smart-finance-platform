package jobs

import (
	"context"
	"database/sql"
	"fmt"
	"strings"

	"github.com/lusd2904/smart-finance-platform/workers/notify-worker/internal/factor"
	"github.com/lusd2904/smart-finance-platform/workers/notify-worker/internal/llm"
)

func (s *Service) RunMarketReview(ctx context.Context, payload map[string]interface{}) (map[string]interface{}, error) {
	targets := marketsAll
	if raw := payload["markets"]; raw != nil {
		switch arr := raw.(type) {
		case []interface{}:
			targets = []string{}
			for _, item := range arr {
				mkt := strings.ToUpper(strings.TrimSpace(stringFrom(item)))
				if mkt == "US" || mkt == "HK" || mkt == "CN" {
					targets = append(targets, mkt)
				}
			}
		case []string:
			targets = arr
		}
	}
	if len(targets) == 0 {
		targets = marketsAll
	}
	items := []map[string]interface{}{}
	failed := []map[string]interface{}{}
	for _, mkt := range targets {
		result, err := s.analyzeMarketReview(ctx, mkt)
		if err != nil {
			failed = append(failed, map[string]interface{}{"market": mkt, "message": err.Error()})
			continue
		}
		if boolFrom(result["ok"], false) {
			items = append(items, result)
		} else {
			failed = append(failed, result)
		}
	}
	return map[string]interface{}{
		"ok": true, "count": len(items), "failedCount": len(failed), "aiAvailable": true,
		"items": items, "failed": failed,
		"message": fmt.Sprintf("完成 %d 个市场，失败 %d 个", len(items), len(failed)),
	}, nil
}

func (s *Service) analyzeMarketReview(ctx context.Context, marketName string) (map[string]interface{}, error) {
	marketName = strings.ToUpper(strings.TrimSpace(marketName))
	if marketLabels[marketName] == "" {
		return map[string]interface{}{"ok": false, "market": marketName, "message": fmt.Sprintf("不支持的市场: %s", marketName)}, nil
	}
	contextData, err := s.collectMarketReviewContext(ctx, marketName)
	if err != nil {
		return nil, err
	}
	fallback := llm.RuleBasedMarketReview(contextData)
	parsed := map[string]interface{}(nil)
	source := "rule"
	modelName := ""
	message := "已用指标与资讯生成兜底复盘"
	models, _ := s.listMarketModels(ctx)
	for _, model := range models {
		temp := model.Temperature
		if temp <= 0 {
			temp = 0.2
		}
		result := s.llm.AnalyzeMarketReview(ctx, model.BaseURL, model.APIKey, model.ModelCode, contextData, temp)
		if result.OK {
			parsed = result.Result
			source = "ai"
			modelName = model.ModelCode
			message = "分析成功"
			break
		}
		message = fmt.Sprintf("模型失败，已回退指标复盘: %s", result.Error)
		if result.Code == 429 || !llmGatewayFailover(result.Code) {
			break
		}
	}
	normalized := normalizeMarketReviewResult(parsed, fallback)
	reviewID, err := s.upsertMarketReview(ctx, marketName, contextData, normalized, source, modelName, parsed, fallback)
	if err != nil {
		return nil, err
	}
	return map[string]interface{}{
		"ok": true, "reviewId": reviewID, "market": marketName,
		"tradeDate": contextData["tradeDate"], "title": normalized["title"],
		"stance": normalized["stance"], "score": normalized["score"], "summary": normalized["summary"],
		"indexReview": normalized["index_review"], "newsReview": normalized["news_review"],
		"sentimentReview": normalized["sentiment_review"], "outlook": normalized["outlook"],
		"riskWarning": normalized["risk_warning"], "source": source, "modelName": modelName,
		"keyPoints": normalized["key_points"], "message": message,
	}, nil
}

func (s *Service) collectMarketReviewContext(ctx context.Context, marketName string) (map[string]interface{}, error) {
	benches := marketBenchmarks[marketName]
	symbols := []string{}
	for _, b := range benches {
		symbols = append(symbols, b.Symbol)
	}
	reader := s.influxReader()
	grouped, err := reader.QueryLatestKlines(ctx, marketName, symbols, 2, "-60d")
	if err != nil {
		return nil, err
	}
	benchmarks := []map[string]interface{}{}
	tradeDate := nowBeijing().Format("2006-%m-%d")
	for _, b := range benches {
		quote := quoteFromBars(grouped[b.Symbol])
		if td := stringFrom(quote["tradeDate"]); td != "" {
			tradeDate = td[:10]
		}
		benchmarks = append(benchmarks, map[string]interface{}{
			"symbol": b.Symbol, "name": b.Name,
			"last": quote["last"], "changeRate": quote["changeRate"], "changeText": quote["changeText"],
			"tradeDate": quote["tradeDate"],
		})
	}
	pool := []string{}
	for _, inst := range factor.TargetUniverse {
		if inst.Market == marketName && !strings.HasPrefix(inst.Symbol, "^") {
			pool = append(pool, inst.Symbol)
		}
		if len(pool) >= 24 {
			break
		}
	}
	upCount, downCount := 0, 0
	if len(pool) > 0 {
		bars, err := reader.QueryLatestKlines(ctx, marketName, pool, 2, "-60d")
		if err == nil {
			for _, sym := range pool {
				q := quoteFromBars(bars[sym])
				chg, ok := q["changeRate"].(float64)
				if !ok {
					continue
				}
				if chg > 0 {
					upCount++
				} else if chg < 0 {
					downCount++
				}
			}
		}
	}
	newsRows := s.loadFinanceBriefings(ctx, marketName, 8)
	sentimentRows := s.loadMatchingSentiment(ctx, marketName, 8)
	return map[string]interface{}{
		"market": marketName, "marketLabel": marketLabels[marketName], "tradeDate": tradeDate,
		"benchmarks": benchmarks, "upCount": upCount, "downCount": downCount,
		"sampleCount": upCount + downCount, "news": newsRows, "sentiment": sentimentRows,
	}, nil
}

func (s *Service) loadFinanceBriefings(ctx context.Context, marketName string, limit int) []map[string]interface{} {
	rows, err := s.db.QueryContext(ctx, `
SELECT headline, summary, source_name FROM market_finance_briefing
WHERE market = ? ORDER BY publish_time DESC LIMIT ?`, marketName, limit)
	if err != nil {
		return []map[string]interface{}{}
	}
	defer rows.Close()
	out := []map[string]interface{}{}
	for rows.Next() {
		var headline, summary, source sql.NullString
		if err := rows.Scan(&headline, &summary, &source); err != nil {
			return out
		}
		text := summary.String
		if len(text) > 200 {
			text = text[:200]
		}
		out = append(out, map[string]interface{}{
			"headline": headline.String, "summary": text, "source": source.String,
		})
	}
	return out
}

func (s *Service) loadMatchingSentiment(ctx context.Context, marketName string, limit int) []map[string]interface{} {
	keywords := marketNewsKeywords[marketName]
	rows, err := s.db.QueryContext(ctx, `
SELECT title, source, content FROM sentiment_news ORDER BY create_time DESC LIMIT 40`)
	if err != nil {
		return []map[string]interface{}{}
	}
	defer rows.Close()
	out := []map[string]interface{}{}
	for rows.Next() {
		var title, source, content sql.NullString
		if err := rows.Scan(&title, &source, &content); err != nil {
			return out
		}
		blob := strings.ToLower(title.String + " " + content.String)
		if len(keywords) > 0 {
			matched := false
			for _, kw := range keywords {
				if strings.Contains(blob, strings.ToLower(kw)) {
					matched = true
					break
				}
			}
			if !matched {
				continue
			}
		}
		text := content.String
		if len(text) > 160 {
			text = text[:160]
		}
		out = append(out, map[string]interface{}{"title": title.String, "source": source.String, "content": text})
		if len(out) >= limit {
			break
		}
	}
	return out
}

func (s *Service) upsertMarketReview(ctx context.Context, marketName string, contextData, result map[string]interface{}, source, modelName string, parsed, fallback map[string]interface{}) (int64, error) {
	tradeDate := stringFrom(contextData["tradeDate"])
	var existingID sql.NullInt64
	err := s.db.QueryRowContext(ctx, `
SELECT review_id FROM market_daily_review WHERE market = ? AND trade_date = ? LIMIT 1`, marketName, tradeDate).Scan(&existingID)
	if err != nil && err != sql.ErrNoRows {
		return 0, err
	}
	now := nowBeijing()
	rawJSON := dumpJSON(map[string]interface{}{"parsed": parsed, "fallback": fallback}, 60000)
	if existingID.Valid {
		_, err = s.db.ExecContext(ctx, `
UPDATE market_daily_review SET title=?, stance=?, score=?, summary=?, index_review=?, news_review=?,
  sentiment_review=?, outlook=?, risk_warning=?, source=?, model_name=?, context_json=?, raw_json=?, analysis_time=?
WHERE review_id=?`,
			result["title"], result["stance"], result["score"], result["summary"],
			result["index_review"], result["news_review"], result["sentiment_review"],
			result["outlook"], result["risk_warning"], source, modelName,
			dumpJSON(contextData, 60000), rawJSON, now, existingID.Int64,
		)
		return existingID.Int64, err
	}
	res, err := s.db.ExecContext(ctx, `
INSERT INTO market_daily_review (
  market, trade_date, title, stance, score, summary, index_review, news_review,
  sentiment_review, outlook, risk_warning, source, model_name, context_json, raw_json, analysis_time, create_time
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
		marketName, tradeDate, result["title"], result["stance"], result["score"], result["summary"],
		result["index_review"], result["news_review"], result["sentiment_review"],
		result["outlook"], result["risk_warning"], source, modelName,
		dumpJSON(contextData, 60000), rawJSON, now, now,
	)
	if err != nil {
		return 0, err
	}
	id, _ := res.LastInsertId()
	return id, nil
}
