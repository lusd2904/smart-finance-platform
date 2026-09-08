package store

import (
	"context"
	"fmt"
	"strings"
)

type top50MissingRow struct {
	id        int64
	market    string
	tradeDate string
	symbol    string
}

// BackfillTop50Last fills null/zero last on market_top50_snapshot from market_price_history_daily.close_price.
func (s *Service) BackfillTop50Last(ctx context.Context, market string, startDate, endDate string, dryRun bool) (map[string]interface{}, error) {
	start := strings.TrimSpace(startDate)[:10]
	end := strings.TrimSpace(endDate)[:10]
	if start > end {
		return nil, fmt.Errorf("start_date %s must be <= end_date %s", start, end)
	}

	market = strings.ToUpper(strings.TrimSpace(market))
	query := `
SELECT id, market, trade_date, symbol
FROM market_top50_snapshot
WHERE trade_date >= ? AND trade_date <= ?
  AND (last IS NULL OR last = 0)`
	args := []any{start, end}
	if market != "" && market != "ALL" {
		query += ` AND market = ?`
		args = append(args, market)
	}
	query += ` ORDER BY trade_date, rank_no`

	rows, err := s.db.QueryContext(ctx, query, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	pending := make([]top50MissingRow, 0)
	byDate := make(map[string][]top50MissingRow)
	for rows.Next() {
		var r top50MissingRow
		if err := rows.Scan(&r.id, &r.market, &r.tradeDate, &r.symbol); err != nil {
			return nil, err
		}
		pending = append(pending, r)
		byDate[r.tradeDate] = append(byDate[r.tradeDate], r)
	}
	if err := rows.Err(); err != nil {
		return nil, err
	}

	patched := 0
	stillMissing := 0
	for tradeDate, dayRows := range byDate {
		closes, err := s.closeOnTradeDate(ctx, dayRows, tradeDate)
		if err != nil {
			return nil, err
		}
		for _, r := range dayRows {
			last, ok := closes[strings.ToUpper(strings.TrimSpace(r.symbol))]
			if !ok || last <= 0 {
				stillMissing++
				continue
			}
			patched++
			if dryRun {
				continue
			}
			if _, err := s.db.ExecContext(ctx, `UPDATE market_top50_snapshot SET last=? WHERE id=?`, last, r.id); err != nil {
				return nil, fmt.Errorf("patch %s %s: %w", r.symbol, tradeDate, err)
			}
		}
	}

	return map[string]interface{}{
		"startDate":    start,
		"endDate":      end,
		"market":       market,
		"dryRun":       dryRun,
		"scanned":      len(pending),
		"patched":      patched,
		"stillMissing": stillMissing,
	}, nil
}

func (s *Service) closeOnTradeDate(ctx context.Context, dayRows []top50MissingRow, tradeDate string) (map[string]float64, error) {
	if len(dayRows) == 0 {
		return map[string]float64{}, nil
	}
	placeholders := make([]string, 0, len(dayRows))
	args := make([]any, 0, len(dayRows)+1)
	args = append(args, tradeDate)
	seen := make(map[string]struct{})
	for _, r := range dayRows {
		sym := strings.TrimSpace(r.symbol)
		if sym == "" {
			continue
		}
		key := strings.ToUpper(sym)
		if _, ok := seen[key]; ok {
			continue
		}
		seen[key] = struct{}{}
		placeholders = append(placeholders, "?")
		args = append(args, sym)
	}
	if len(placeholders) == 0 {
		return map[string]float64{}, nil
	}
	q := fmt.Sprintf(`
SELECT symbol, close_price FROM market_price_history_daily
WHERE trade_date = ? AND symbol IN (%s)`, strings.Join(placeholders, ","))
	dbRows, err := s.db.QueryContext(ctx, q, args...)
	if err != nil {
		return nil, err
	}
	defer dbRows.Close()
	out := make(map[string]float64)
	for dbRows.Next() {
		var symbol string
		var closePrice *float64
		if err := dbRows.Scan(&symbol, &closePrice); err != nil {
			return nil, err
		}
		if closePrice == nil || *closePrice <= 0 {
			continue
		}
		out[strings.ToUpper(strings.TrimSpace(symbol))] = *closePrice
	}
	return out, dbRows.Err()
}
