package jobs

import (
	"context"
)

func (s *Service) RunAIAnalyze(ctx context.Context, payload map[string]interface{}) (map[string]interface{}, error) {
	symbol := stringFrom(payload["symbol"])
	marketName := stringFrom(payload["market"])
	if marketName == "" {
		marketName = "US"
	}
	analyzed, err := s.analyzeSymbol(ctx, symbol, marketName, true, "")
	if err != nil {
		return nil, err
	}
	flat := flattenPickAnalysis(analyzed)
	if !boolFrom(flat["ok"], false) {
		return flat, nil
	}
	if err := s.persistSymbolAIAnalysis(ctx, flat); err != nil {
		return nil, err
	}
	flat["result"] = map[string]interface{}{
		"recommendation": flat["recommendation"], "stance": flat["stance"], "confidence": flat["confidence"],
		"summary": flat["summary"], "indicator_review": flat["indicatorReview"],
		"sentiment_review": flat["sentimentReview"], "operation_advice": flat["operationAdvice"],
		"risk_warning": flat["riskWarning"], "pick_score": flat["pickScore"],
		"factor_score": flat["factorScore"], "signal": flat["signal"], "source": flat["source"],
	}
	return flat, nil
}
