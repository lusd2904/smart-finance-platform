package store

import (
	"context"
	"fmt"
	"strings"
	"time"
)

const closeLookbackDays = 7

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
		mkt := market
		if mkt == "" || mkt == "ALL" {
			mkt = dayRows[0].market
		}
		closes, err := s.closeOnTradeDate(ctx, dayRows, tradeDate, mkt)
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

func (s *Service) closeOnTradeDate(ctx context.Context, dayRows []top50MissingRow, tradeDate, market string) (map[string]float64, error) {
	if len(dayRows) == 0 {
		return map[string]float64{}, nil
	}
	requested := make([]string, 0, len(dayRows))
	aliases := make([]string, 0)
	seen := map[string]struct{}{}
	for _, r := range dayRows {
		sym := strings.TrimSpace(r.symbol)
		if sym == "" {
			continue
		}
		requested = append(requested, sym)
		mkt := market
		if mkt == "" {
			mkt = r.market
		}
		for _, alias := range priceSymbolAliases(sym, mkt) {
			if _, ok := seen[alias]; ok {
				continue
			}
			seen[alias] = struct{}{}
			aliases = append(aliases, alias)
		}
	}
	if len(aliases) == 0 {
		return map[string]float64{}, nil
	}
	lookbackStart := tradeDate
	if parsed, err := time.Parse("2006-01-02", tradeDate); err == nil {
		lookbackStart = parsed.AddDate(0, 0, -closeLookbackDays).Format("2006-01-02")
	}
	placeholders := make([]string, len(aliases))
	args := make([]any, 0, len(aliases)+2)
	args = append(args, lookbackStart, tradeDate)
	for i, alias := range aliases {
		placeholders[i] = "?"
		args = append(args, alias)
	}
	q := fmt.Sprintf(`
SELECT symbol, close_price FROM market_price_history_daily
WHERE trade_date >= ? AND trade_date <= ? AND symbol IN (%s)
ORDER BY trade_date DESC`, strings.Join(placeholders, ","))
	dbRows, err := s.db.QueryContext(ctx, q, args...)
	if err != nil {
		return nil, err
	}
	defer dbRows.Close()
	found := make(map[string]float64)
	for dbRows.Next() {
		var symbol string
		var closePrice *float64
		if err := dbRows.Scan(&symbol, &closePrice); err != nil {
			return nil, err
		}
		key := strings.ToUpper(strings.TrimSpace(symbol))
		if _, exists := found[key]; exists || closePrice == nil || *closePrice <= 0 {
			continue
		}
		found[key] = *closePrice
	}
	if err := dbRows.Err(); err != nil {
		return nil, err
	}
	return mapClosesByAlias(requested, found, market), nil
}
