package jobs

import (
	"context"
	"fmt"
	"strings"
)

func (s *Service) analyzeSymbol(ctx context.Context, symbol, marketName string, useAI bool, name string) (map[string]interface{}, error) {
	symbol = strings.ToUpper(strings.TrimSpace(symbol))
	marketName = strings.ToUpper(strings.TrimSpace(marketName))
	if marketName == "" {
		marketName = "US"
	}
	if symbol == "" {
		return map[string]interface{}{
			"ok": false, "available": false, "message": "标的代码不能为空", "symbol": symbol, "market": marketName,
		}, nil
	}
	if name == "" {
		name = s.resolveInstrumentName(symbol, marketName)
	}
	klines, err := s.loadKlines(ctx, marketName, []string{symbol})
	if err != nil {
		return nil, err
	}
	bars := klines[symbol]
	if len(bars) == 0 {
		return map[string]interface{}{
			"ok": false, "available": true,
			"message": fmt.Sprintf("标的 %s 暂无K线数据，请先同步", symbol),
			"symbol": symbol, "market": marketName, "name": name,
		}, nil
	}
	mood, err := s.loadMood(ctx)
	if err != nil {
		return nil, err
	}
	row := s.scoreSymbolRow(symbol, name, marketName, bars, mood)
	if row == nil {
		return map[string]interface{}{
			"ok": false, "available": true,
			"message": fmt.Sprintf("标的 %s K线不足以计算指标", symbol),
			"symbol": symbol, "market": marketName, "name": name, "klineCount": len(bars),
		}, nil
	}
	aiAvailable := false
	aiError := ""
	aiOK := false
	modelName := ""
	if useAI {
		models, err := s.listMarketModels(ctx)
		if err != nil {
			aiError = err.Error()
		} else if len(models) == 0 {
			aiError = "未配置可用 AI 模型（AI 管理 → 模型管理，适用范围选行情中心）"
		} else {
			aiAvailable = true
			contextData := s.buildAnalyzerContext(mood)
			for _, model := range models {
				temp := model.Temperature
				if temp <= 0 {
					temp = 0.2
				}
				result := s.llm.AnalyzeStockPick(ctx, model.BaseURL, model.APIKey, model.ModelCode, row, contextData, temp)
				modelName = model.ModelCode
				if result.OK {
					marketApplyAIResult(row, result.Result)
					aiOK = true
					break
				}
				aiError = result.Error
				if result.Code == 429 || !llmGatewayFailover(result.Code) {
					break
				}
			}
		}
	} else {
		aiError = "未启用 AI"
	}
	message := "分析成功"
	if useAI && !aiOK && stringFrom(row["source"]) != "ai" {
		message = fmt.Sprintf("分析失败: %s", aiError)
	}
	out := map[string]interface{}{
		"ok": true, "available": aiAvailable, "symbol": symbol, "market": marketName, "name": name,
		"price": row["price"], "changePct": row["changePct"], "factorScore": row["factorScore"],
		"pickScore": row["pickScore"], "signal": row["signal"], "recommendation": row["recommendation"],
		"stance": row["stance"], "confidence": row["confidence"], "summary": row["summary"],
		"indicatorReview": row["indicatorReview"], "sentimentReview": row["sentimentReview"],
		"operationAdvice": row["operationAdvice"], "riskWarning": row["riskWarning"],
		"tags": row["tags"], "source": row["source"], "metrics": row["metrics"],
		"reason": row["reason"], "klineCount": row["klineCount"], "message": message,
		"aiOk": aiOK,
	}
	if useAI && !aiOK {
		out["aiError"] = aiError
	}
	if stringFrom(row["source"]) == "ai" {
		out["modelName"] = modelName
	}
	return out, nil
}

func marketApplyAIResult(row map[string]interface{}, parsed map[string]interface{}) {
	if parsed == nil {
		return
	}
	row["source"] = "ai"
	if v := parsed["stance"]; v != nil && v != "" {
		row["stance"] = v
	}
	if v := parsed["recommendation"]; v != nil && v != "" {
		row["recommendation"] = v
	}
	if v := parsed["confidence"]; v != nil {
		row["confidence"] = clampConfidence(v)
	}
	if v := parsed["summary"]; v != nil && v != "" {
		row["summary"] = v
	}
	if v := parsed["indicator_review"]; v != nil && v != "" {
		row["indicatorReview"] = v
	}
	if v := parsed["sentiment_review"]; v != nil && v != "" {
		row["sentimentReview"] = v
	}
	if v := parsed["operation_advice"]; v != nil && v != "" {
		row["operationAdvice"] = v
	}
	if v := parsed["risk_warning"]; v != nil && v != "" {
		row["riskWarning"] = v
	}
}

func clampConfidence(v interface{}) int {
	n := int(intFrom(v))
	if n < 0 {
		return 0
	}
	if n > 100 {
		return 100
	}
	return n
}

func flattenPickAnalysis(data map[string]interface{}) map[string]interface{} {
	recommendation := stringFrom(data["recommendation"])
	stance := stringFrom(data["stance"])
	confidence := data["confidence"]
	flat := map[string]interface{}{
		"ok": data["ok"], "available": data["available"], "symbol": data["symbol"], "market": data["market"],
		"name": data["name"], "price": data["price"], "changePct": data["changePct"],
		"factorScore": data["factorScore"], "pickScore": data["pickScore"], "signal": data["signal"],
		"recommendation": recommendation, "stance": stance, "confidence": confidence,
		"summary": data["summary"], "indicatorReview": data["indicatorReview"],
		"sentimentReview": data["sentimentReview"], "operationAdvice": data["operationAdvice"],
		"riskWarning": data["riskWarning"], "tags": data["tags"], "source": data["source"],
		"metrics": data["metrics"], "finalDecision": recommendation, "finalConfidence": confidence,
		"trend": stance, "advice": data["operationAdvice"], "message": data["message"],
		"aiOk": data["aiOk"], "aiError": data["aiError"], "modelName": data["modelName"],
	}
	return flat
}

func (s *Service) persistSymbolAIAnalysis(ctx context.Context, data map[string]interface{}) error {
	if !boolFrom(data["ok"], false) {
		return nil
	}
	raw := dumpJSON(map[string]interface{}{
		"recommendation": data["recommendation"], "stance": data["stance"], "confidence": data["confidence"],
		"summary": data["summary"], "indicatorReview": data["indicatorReview"],
		"sentimentReview": data["sentimentReview"], "operationAdvice": data["operationAdvice"],
		"riskWarning": data["riskWarning"], "pickScore": data["pickScore"],
		"factorScore": data["factorScore"], "signal": data["signal"], "source": data["source"],
	}, 60000)
	_, err := s.db.ExecContext(ctx, `
INSERT INTO symbol_ai_analysis (
  symbol, market, price, final_decision, final_confidence, summary_text,
  indicators_json, raw_json, model_name, analysis_time
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
		stringFrom(data["symbol"]), stringFrom(data["market"]), data["price"],
		data["recommendation"], data["confidence"], stringFrom(data["summary"]),
		dumpJSON(data["metrics"], 60000), raw, data["modelName"], nowBeijing(),
	)
	return err
}
