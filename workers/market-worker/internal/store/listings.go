package store

import (
	"context"
	"strings"
)

const listedCategory = "listed"

const listedFromMySQLSQL = `
SELECT DISTINCT symbol, market
FROM market_price_history_daily
WHERE symbol IS NOT NULL AND symbol <> '' AND market IS NOT NULL AND market <> ''`

func (s *Service) SyncFromInflux(ctx context.Context) (map[string]interface{}, error) {
	return s.SyncListedFromMySQL(ctx)
}

func (s *Service) SyncListedFromMySQL(ctx context.Context) (map[string]interface{}, error) {
	rows := []map[string]string{}
	fetched := map[string]int{"US": 0, "CN": 0, "HK": 0}
	if s.db != nil {
		dbRows, err := s.db.QueryContext(ctx, listedFromMySQLSQL)
		if err != nil {
			return nil, err
		}
		defer dbRows.Close()
		for dbRows.Next() {
			var symbol, market string
			if err := dbRows.Scan(&symbol, &market); err != nil {
				return nil, err
			}
			symbol = strings.TrimSpace(symbol)
			market = strings.ToUpper(strings.TrimSpace(market))
			if symbol == "" || market == "" {
				continue
			}
			fetched[market]++
			rows = append(rows, map[string]string{
				"symbol":   symbol,
				"name":     symbol,
				"market":   market,
				"category": listedCategory,
			})
		}
		if err := dbRows.Err(); err != nil {
			return nil, err
		}
	}
	upsert, err := s.upsertListedRows(ctx, rows)
	if err != nil {
		return nil, err
	}
	return map[string]interface{}{
		"fetched":  fetched,
		"upserted": upsert["fetched"],
		"affected": upsert["affected"],
		"source":   "mysql",
	}, nil
}

func (s *Service) upsertListedRows(ctx context.Context, rows []map[string]string) (map[string]int, error) {
	unique := dedupeInstruments(rows)
	if len(unique) == 0 {
		return map[string]int{"fetched": 0, "affected": 0}, nil
	}
	stmt := `
INSERT INTO market_instrument (symbol, name, market, category, enabled, create_time)
VALUES (?, ?, ?, ?, '1', NOW())
ON DUPLICATE KEY UPDATE
  name = IF(
    category = 'listed' OR category IS NULL OR category = '',
    IF(VALUES(name) IS NULL OR VALUES(name) = '', name, VALUES(name)),
    name
  ),
  market = IF(category = 'listed' OR category IS NULL OR category = '', VALUES(market), market),
  category = IF(category = 'listed' OR category IS NULL OR category = '', VALUES(category), category)`
	affected := 0
	const chunk = 400
	for i := 0; i < len(unique); i += chunk {
		end := i + chunk
		if end > len(unique) {
			end = len(unique)
		}
		for _, row := range unique[i:end] {
			name := row["name"]
			if name == "" {
				name = row["symbol"]
			}
			res, err := s.db.ExecContext(ctx, stmt, row["symbol"], name, row["market"], listedCategory)
			if err != nil {
				return nil, err
			}
			n, _ := res.RowsAffected()
			affected += int(n)
		}
	}
	return map[string]int{"fetched": len(unique), "affected": affected}, nil
}

func dedupeInstruments(rows []map[string]string) []map[string]string {
	seen := map[string]bool{}
	var out []map[string]string
	for _, row := range rows {
		sym := strings.TrimSpace(row["symbol"])
		mkt := strings.ToUpper(strings.TrimSpace(row["market"]))
		if sym == "" || mkt == "" {
			continue
		}
		key := sym + "|" + mkt
		if seen[key] {
			continue
		}
		seen[key] = true
		out = append(out, map[string]string{
			"symbol": sym,
			"name":   strings.TrimSpace(row["name"]),
			"market": mkt,
		})
	}
	return out
}
