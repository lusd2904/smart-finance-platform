package jobs

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"strings"

	"github.com/lusd2904/smart-finance-platform/workers/notify-worker/internal/factor"
	"github.com/lusd2904/smart-finance-platform/workers/notify-worker/internal/market"
)

func (s *Service) RunStockPick(ctx context.Context, payload map[string]interface{}) (map[string]interface{}, error) {
	trigger := stringFrom(payload["trigger"])
	if trigger == "" {
		trigger = "schedule"
	}
	useAI := boolFrom(payload["useAi"], true)
	mood, err := s.loadMood(ctx)
	if err != nil {
		return nil, err
	}
	tradeDates := []string{}
	for _, heat := range mood.Heat {
		if td := stringFrom(heat["tradeDate"]); td != "" {
			tradeDates = append(tradeDates, td)
		}
	}
	tradeDate := nowBeijing().Format("2006-01-02")
	if len(tradeDates) > 0 {
		tradeDate = maxString(tradeDates)
	}
	pickID, err := s.upsertStockPickRun(ctx, tradeDate, trigger, mood, "running", "扫描中", 0, 0, 0, nil)
	if err != nil {
		return nil, err
	}
	scored := []map[string]interface{}{}
	scanned := 0
	for _, mkt := range marketsAll {
		heat := mood.Heat[mkt]
		var top50 []market.Candidate
		if heat != nil && stringFrom(heat["tradeDate"]) != "" {
			top50, err = s.listTop50(ctx, mkt, stringFrom(heat["tradeDate"]))
			if err != nil {
				return nil, err
			}
		}
		candidates := market.MergeCandidates(top50, featuredForMarket(mkt), market.CandidateCap)
		symbols := []string{}
		for _, c := range candidates {
			symbols = append(symbols, c.Symbol)
		}
		klineMap, err := s.loadKlines(ctx, mkt, symbols)
		if err != nil {
			return nil, err
		}
		var sentRaw, heatScore *float64
		if v, ok := mood.Sentiment[market.SentimentField[mkt]].(float64); ok {
			sentRaw = &v
		}
		if heat != nil {
			if v, ok := heat["heatScore"].(float64); ok {
				heatScore = &v
			}
		}
		opened := containsString(mood.OpenMarkets, mkt)
		indexChg := map[string]float64{}
		for _, item := range mood.Indices {
			if strings.ToUpper(stringFrom(item["market"])) == mkt {
				if chg, ok := item["changePct"].(float64); ok {
					indexChg[mkt] = chg
				}
			}
		}
		for _, cand := range candidates {
			scanned++
			bars := klineMap[cand.Symbol]
			res := factor.ComputeFromKlines(bars, "balanced", nil)
			if !res.OK {
				continue
			}
			decision := factor.DecideSignal(res.Score, "balanced", nil)
			var idxChg *float64
			if opened {
				if v, ok := indexChg[mkt]; ok {
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
			scored = append(scored, map[string]interface{}{
				"symbol": cand.Symbol, "name": cand.Name, "market": mkt,
				"price": res.Metrics.Get("latestClose", 0), "changePct": res.Metrics.Get("dayChangePercent", 0),
				"factorScore": factorTotal, "pickScore": pickScore, "signal": decision.Signal,
				"recommendation": reco, "stance": stance, "confidence": decision.Confidence,
				"reason": decision.Reason, "summary": decision.Reason,
				"indicatorReview": strings.Join(tags, "、"),
				"sentimentReview": stringFrom(mood.Sentiment["summary"]),
				"operationAdvice": reco, "riskWarning": "无", "tags": tags, "source": "rule",
				"metrics": map[string]interface{}{
					"rsi14": res.Metrics.Get("rsi14", 0), "macdHist": res.Metrics.Get("macdHist", 0),
					"ma20": res.Metrics.Get("ma20", 0), "volumeRatio20": res.Metrics.Get("volumeRatio20", 0),
					"return20": res.Metrics.Get("return20", 0),
				},
			})
		}
	}
	picked := market.SelectTopPicks(scored, market.PicksPerMarket)
	contextData := s.buildAnalyzerContext(mood)
	aiCount := 0
	modelName := ""
	aiError := ""
	if useAI {
		aiCount, aiError = s.enrichWithAI(ctx, picked, contextData)
		for _, row := range picked {
			if stringFrom(row["source"]) == "ai" {
				modelName = stringFrom(row["modelName"])
				break
			}
		}
	}
	if err := s.replaceStockPickItems(ctx, pickID, picked); err != nil {
		return nil, err
	}
	status := "empty"
	if len(picked) > 0 {
		if useAI && aiCount < len(picked) {
			status = "partial"
		} else {
			status = "ok"
		}
	}
	aiPart := fmt.Sprintf("AI %d/%d", aiCount, len(picked))
	if modelName != "" {
		aiPart += fmt.Sprintf("（%s）", modelName)
	}
	if useAI && aiCount == 0 && aiError != "" {
		aiPart += fmt.Sprintf("，未写入研判：%s", aiError)
	}
	message := fmt.Sprintf("%s 扫描%d只，入选%d只，%s。", mood.Hint, scanned, len(picked), aiPart)
	_, err = s.upsertStockPickRun(ctx, tradeDate, trigger, mood, status, message, scanned, len(picked), aiCount, &modelName)
	if err != nil {
		return nil, err
	}
	return s.getLatestStockPick(ctx, tradeDate)
}

func (s *Service) upsertStockPickRun(ctx context.Context, tradeDate, trigger string, mood moodPayload, status, message string, scanned, picked, aiCount int, modelName *string) (int64, error) {
	contextJSON := dumpJSON(map[string]interface{}{
		"mood": map[string]interface{}{
			"sessions": mood.Sessions, "openMarkets": mood.OpenMarkets,
			"indices": mood.Indices, "sentiment": mood.Sentiment, "hint": mood.Hint,
		},
	}, 60000)
	openMarkets := strings.Join(mood.OpenMarkets, ",")
	var existingID sql.NullInt64
	err := s.db.QueryRowContext(ctx, `SELECT pick_id FROM market_stock_pick WHERE trade_date = ? LIMIT 1`, tradeDate).Scan(&existingID)
	if err != nil && err != sql.ErrNoRows {
		return 0, err
	}
	now := nowBeijing()
	if existingID.Valid {
		_, err = s.db.ExecContext(ctx, `
UPDATE market_stock_pick SET status=?, trigger_source=?, scanned_count=?, picked_count=?, ai_count=?,
  model_name=?, open_markets=?, message=?, context_json=?, update_time=?
WHERE pick_id=?`, status, trigger, scanned, picked, aiCount, modelName, openMarkets, message, contextJSON, now, existingID.Int64)
		return existingID.Int64, err
	}
	res, err := s.db.ExecContext(ctx, `
INSERT INTO market_stock_pick (
  trade_date, status, trigger_source, scanned_count, picked_count, ai_count,
  model_name, open_markets, message, context_json, create_time, update_time
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
		tradeDate, status, trigger, scanned, picked, aiCount, modelName, openMarkets, message, contextJSON, now, now,
	)
	if err != nil {
		return 0, err
	}
	id, _ := res.LastInsertId()
	return id, nil
}

func (s *Service) replaceStockPickItems(ctx context.Context, pickID int64, picked []map[string]interface{}) error {
	_, err := s.db.ExecContext(ctx, `DELETE FROM market_stock_pick_item WHERE pick_id = ?`, pickID)
	if err != nil {
		return err
	}
	for _, row := range picked {
		tagsJSON, _ := json.Marshal(row["tags"])
		factorJSON, _ := json.Marshal(row["metrics"])
		_, err = s.db.ExecContext(ctx, `
INSERT INTO market_stock_pick_item (
  pick_id, rank_no, symbol, name, market, price, change_pct, factor_score, pick_score,
  signal, recommendation, stance, confidence, summary, indicator_review, sentiment_review,
  operation_advice, risk_warning, tags_json, source, factor_json, create_time
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
			pickID, intFrom(row["rankNo"]), row["symbol"], row["name"], row["market"],
			row["price"], row["changePct"], row["factorScore"], row["pickScore"],
			row["signal"], row["recommendation"], row["stance"], row["confidence"],
			row["summary"], row["indicatorReview"], row["sentimentReview"],
			row["operationAdvice"], row["riskWarning"], string(tagsJSON), row["source"], string(factorJSON), nowBeijing(),
		)
		if err != nil {
			return err
		}
	}
	return nil
}

func (s *Service) getLatestStockPick(ctx context.Context, tradeDate string) (map[string]interface{}, error) {
	row := s.db.QueryRowContext(ctx, `
SELECT pick_id, trade_date, status, trigger_source, scanned_count, picked_count, ai_count,
       model_name, open_markets, message, context_json, update_time
FROM market_stock_pick WHERE trade_date = ? LIMIT 1`, tradeDate)
	var pickID int64
	var status, trigger, modelName, openMarkets, message, contextJSON sql.NullString
	var tradeDay sql.NullString
	var scanned, picked, aiCount sql.NullInt64
	var updated sql.NullTime
	if err := row.Scan(&pickID, &tradeDay, &status, &trigger, &scanned, &picked, &aiCount, &modelName, &openMarkets, &message, &contextJSON, &updated); err != nil {
		return nil, err
	}
	items, err := s.listStockPickItems(ctx, pickID)
	if err != nil {
		return nil, err
	}
	openList := []string{}
	for _, part := range strings.Split(openMarkets.String, ",") {
		if p := strings.TrimSpace(part); p != "" {
			openList = append(openList, p)
		}
	}
	return map[string]interface{}{
		"pickId": pickID, "tradeDate": tradeDay.String, "status": status.String,
		"trigger": trigger.String, "scannedCount": scanned.Int64, "pickedCount": picked.Int64,
		"aiCount": aiCount.Int64, "modelName": modelName.String, "openMarkets": openList,
		"message": message.String, "items": items,
	}, nil
}

func (s *Service) listStockPickItems(ctx context.Context, pickID int64) ([]map[string]interface{}, error) {
	rows, err := s.db.QueryContext(ctx, `
SELECT item_id, rank_no, symbol, name, market, price, change_pct, factor_score, pick_score,
       signal, recommendation, stance, confidence, summary, indicator_review, sentiment_review,
       operation_advice, risk_warning, tags_json, source
FROM market_stock_pick_item WHERE pick_id = ? ORDER BY rank_no`, pickID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := []map[string]interface{}{}
	for rows.Next() {
		var itemID, rankNo sql.NullInt64
		var symbol, name, marketName, signal, reco, stance, summary, indicator, sentiment, advice, risk, tagsJSON, source sql.NullString
		var price, changePct, factorScore, pickScore sql.NullFloat64
		var confidence sql.NullInt64
		if err := rows.Scan(&itemID, &rankNo, &symbol, &name, &marketName, &price, &changePct, &factorScore, &pickScore,
			&signal, &reco, &stance, &confidence, &summary, &indicator, &sentiment, &advice, &risk, &tagsJSON, &source); err != nil {
			return nil, err
		}
		tags := []interface{}{}
		_ = json.Unmarshal([]byte(tagsJSON.String), &tags)
		out = append(out, map[string]interface{}{
			"itemId": itemID.Int64, "rankNo": rankNo.Int64, "symbol": symbol.String, "name": name.String,
			"market": marketName.String, "price": nullFloat(price), "changePct": nullFloat(changePct),
			"factorScore": nullFloat(factorScore), "pickScore": nullFloat(pickScore),
			"signal": signal.String, "recommendation": reco.String, "stance": stance.String,
			"confidence": confidence.Int64, "summary": summary.String, "indicatorReview": indicator.String,
			"sentimentReview": sentiment.String, "operationAdvice": advice.String, "riskWarning": risk.String,
			"tags": tags, "source": source.String,
		})
	}
	return out, rows.Err()
}

func maxString(items []string) string {
	if len(items) == 0 {
		return ""
	}
	best := items[0]
	for _, item := range items[1:] {
		if item > best {
			best = item
		}
	}
	return best
}
