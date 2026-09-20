package store

import (
	"context"
	"database/sql"
	"fmt"
	"strconv"
	"strings"
	"time"
)

// latestDailyManySQL reads the last N daily bars per symbol from MySQL.
// board_warmup / finance_briefings must not Flux-query Influx.
const latestDailyManySQL = `SELECT symbol, trade_date, open_price, high_price, low_price, close_price, volume
FROM (
SELECT symbol, trade_date, open_price, high_price, low_price, close_price, volume,
       ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY trade_date DESC) AS rn
FROM market_price_history_daily
WHERE market=? AND trade_date>=? AND trade_date<=? AND symbol IN (%s)
) t WHERE rn<=? ORDER BY symbol, trade_date`

type dailyBar struct {
	Date   string
	Open   float64
	High   float64
	Low    float64
	Close  float64
	Volume float64
}

type boardKlineSource interface {
	LatestDaily(ctx context.Context, market string, symbols []string, n int, start string) (map[string][]dailyBar, error)
}

type mysqlBoardKlines struct {
	db *sql.DB
}

func (m mysqlBoardKlines) LatestDaily(ctx context.Context, market string, symbols []string, n int, start string) (map[string][]dailyBar, error) {
	return queryLatestDailyMySQL(ctx, m.db, market, symbols, n, start)
}

func queryLatestDailyMySQL(ctx context.Context, db *sql.DB, market string, symbols []string, n int, start string) (map[string][]dailyBar, error) {
	out := map[string][]dailyBar{}
	if db == nil || len(symbols) == 0 {
		return out, nil
	}
	if n <= 0 {
		n = 2
	}
	mkt := strings.ToUpper(strings.TrimSpace(market))
	if mkt == "" {
		mkt = "US"
	}
	from, to := dailyWindow(start)
	cleaned := make([]string, 0, len(symbols))
	for _, raw := range symbols {
		sym := strings.TrimSpace(raw)
		if sym != "" {
			cleaned = append(cleaned, sym)
		}
	}
	const chunk = 30
	for i := 0; i < len(cleaned); i += chunk {
		end := i + chunk
		if end > len(cleaned) {
			end = len(cleaned)
		}
		part, err := scanLatestDailyChunk(ctx, db, mkt, cleaned[i:end], from, to, n)
		if err != nil {
			return nil, err
		}
		for req, bars := range part {
			out[req] = bars
		}
	}
	return out, nil
}

func scanLatestDailyChunk(ctx context.Context, db *sql.DB, market string, symbols []string, from, to string, limit int) (map[string][]dailyBar, error) {
	out := map[string][]dailyBar{}
	if len(symbols) == 0 {
		return out, nil
	}
	placeholders := strings.TrimRight(strings.Repeat("?,", len(symbols)), ",")
	query := fmt.Sprintf(latestDailyManySQL, placeholders)
	args := make([]interface{}, 0, len(symbols)+4)
	args = append(args, market, from, to)
	for _, sym := range symbols {
		args = append(args, sym)
	}
	args = append(args, limit)
	rows, err := db.QueryContext(ctx, query, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	byDB := map[string][]dailyBar{}
	for rows.Next() {
		var symbol string
		var raw interface{}
		var open, high, low, close, volume sql.NullFloat64
		if err := rows.Scan(&symbol, &raw, &open, &high, &low, &close, &volume); err != nil {
			return nil, err
		}
		byDB[symbol] = append(byDB[symbol], dailyBar{
			Date:   coerceTradeDate(raw),
			Open:   sqlNullFloat(open),
			High:   sqlNullFloat(high),
			Low:    sqlNullFloat(low),
			Close:  sqlNullFloat(close),
			Volume: sqlNullFloat(volume),
		})
	}
	if err := rows.Err(); err != nil {
		return nil, err
	}
	for _, req := range symbols {
		if bars := byDB[req]; len(bars) > 0 {
			out[req] = bars
			continue
		}
		if u := strings.ToUpper(req); u != req {
			if bars := byDB[u]; len(bars) > 0 {
				out[req] = bars
			}
		}
	}
	return out, nil
}

func dailyWindow(start string) (from, to string) {
	loc, err := time.LoadLocation("Asia/Shanghai")
	if err != nil {
		loc = time.FixedZone("CST", 8*3600)
	}
	now := time.Now().In(loc)
	to = now.Format("2006-01-02")
	fromTime := now.AddDate(0, 0, -60)
	text := strings.TrimSpace(start)
	if strings.HasPrefix(text, "-") {
		body := strings.TrimPrefix(text, "-")
		switch {
		case strings.HasSuffix(body, "y"):
			if n, err := strconv.Atoi(strings.TrimSuffix(body, "y")); err == nil && n > 0 {
				fromTime = now.AddDate(-n, 0, 0)
			}
		case strings.HasSuffix(body, "mo"):
			if n, err := strconv.Atoi(strings.TrimSuffix(body, "mo")); err == nil && n > 0 {
				fromTime = now.AddDate(0, -n, 0)
			}
		case strings.HasSuffix(body, "w"):
			if n, err := strconv.Atoi(strings.TrimSuffix(body, "w")); err == nil && n > 0 {
				fromTime = now.AddDate(0, 0, -7*n)
			}
		case strings.HasSuffix(body, "d"):
			if n, err := strconv.Atoi(strings.TrimSuffix(body, "d")); err == nil && n > 0 {
				fromTime = now.AddDate(0, 0, -n)
			}
		}
	}
	from = fromTime.Format("2006-01-02")
	return from, to
}

func coerceTradeDate(v interface{}) string {
	switch t := v.(type) {
	case time.Time:
		return t.Format("2006-01-02")
	case []byte:
		s := strings.TrimSpace(string(t))
		if len(s) >= 10 {
			return s[:10]
		}
		return s
	case string:
		s := strings.TrimSpace(t)
		if len(s) >= 10 {
			return s[:10]
		}
		return s
	default:
		return ""
	}
}

func sqlNullFloat(v sql.NullFloat64) float64 {
	if !v.Valid {
		return 0
	}
	return v.Float64
}
