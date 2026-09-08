package jobs

import (
	"context"
	"fmt"
	"strings"

	"github.com/google/uuid"

	"github.com/lusd2904/smart-finance-platform/workers/notify-worker/internal/factor"
)

func (s *Service) RunAIBatch(ctx context.Context, payload map[string]interface{}) (map[string]interface{}, error) {
	marketName := strings.ToUpper(stringFrom(payload["market"]))
	if marketName == "" {
		marketName = "US"
	}
	symbols := stringSliceFrom(payload["symbols"])
	if len(symbols) == 0 {
		for _, inst := range factor.TargetUniverse {
			if inst.Market == marketName && !strings.HasPrefix(inst.Symbol, "^") {
				symbols = append(symbols, inst.Symbol)
			}
			if len(symbols) >= 8 {
				break
			}
		}
	}
	cycle := strings.ReplaceAll(uuid.New().String(), "-", "")[:16]
	res, err := s.db.ExecContext(ctx, `
INSERT INTO plat_ai_batch_run (cycle_id, symbols_count, success_count, status, summary, create_time)
VALUES (?, ?, 0, '0', '任务执行中', ?)`, cycle, len(symbols), nowBeijing())
	if err != nil {
		return nil, err
	}
	batchID, _ := res.LastInsertId()
	success := 0
	for _, sym := range symbols {
		itemStatus := "2"
		decision := interface{}(nil)
		confidence := interface{}(nil)
		summary := ""
		analyzed, aerr := s.analyzeSymbol(ctx, sym, marketName, true, "")
		if aerr != nil {
			summary = aerr.Error()
		} else {
			flat := flattenPickAnalysis(analyzed)
			if boolFrom(flat["ok"], false) {
				if err := s.persistSymbolAIAnalysis(ctx, flat); err == nil {
					success++
					itemStatus = "1"
					decision = flat["finalDecision"]
					confidence = flat["finalConfidence"]
					summary = stringFrom(flat["summary"])
				} else {
					summary = err.Error()
				}
			} else {
				summary = stringFrom(flat["message"])
			}
		}
		if len(summary) > 2000 {
			summary = summary[:2000]
		}
		_, _ = s.db.ExecContext(ctx, `
INSERT INTO plat_ai_batch_item (batch_id, symbol, market, decision, confidence, summary, status, create_time)
VALUES (?, ?, ?, ?, ?, ?, ?, ?)`, batchID, sym, marketName, decision, confidence, summary, itemStatus, nowBeijing())
	}
	_, err = s.db.ExecContext(ctx, `
UPDATE plat_ai_batch_run SET success_count = ?, status = '1', summary = ? WHERE batch_id = ?`,
		success, fmt.Sprintf("完成 %d/%d", success, len(symbols)), batchID)
	if err != nil {
		return nil, err
	}
	_, _ = s.RunUserNotice(ctx, map[string]interface{}{
		"user_id": 1, "title": "批量AI研判完成",
		"content": fmt.Sprintf("批次 %s 成功 %d/%d", cycle, success, len(symbols)),
		"level": "success", "category": "ai",
	})
	return map[string]interface{}{
		"batchId": batchID, "cycleId": cycle, "total": len(symbols), "success": success,
	}, nil
}

func stringSliceFrom(v interface{}) []string {
	switch arr := v.(type) {
	case []string:
		return arr
	case []interface{}:
		out := make([]string, 0, len(arr))
		for _, item := range arr {
			s := strings.TrimSpace(stringFrom(item))
			if s != "" {
				out = append(out, s)
			}
		}
		return out
	default:
		return nil
	}
}
