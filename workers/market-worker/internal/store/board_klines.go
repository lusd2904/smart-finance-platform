package store

import (
	"context"
	"database/sql"
	"strconv"
	"strings"
	"time"
)

// latestDailySQL reads the last N daily bars from the same MySQL table
// klineread uses (market_price_history_daily). board_warmup must not Flux-query Influx.
const latestDailySQL = `SELECT trade_date, open_price, high_price, low_price, close_price, volume
FROM (
SELECT trade_date, open_price, high_price, low_price, close_price, volume
FROM market_price_history_daily
WHERE symbol=? AND market=? AND trade_date>=? AND trade_date<=?
ORDER BY trade_date DESC
LIMIT ?
) t ORDER BY trade_date`

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
	for _, raw := range symbols {
		sym := strings.TrimSpace(raw)
		if sym == "" {
			continue
		}
		bars, err := scanLatestDaily(ctx, db, sym, mkt, from, to, n)
		if err != nil {
			return nil, err
		}
		if len(bars) > 0 {
			out[sym] = bars
		}
	}
	return out, nil
}

func scanLatestDaily(ctx context.Context, db *sql.DB, symbol, market, from, to string, limit int) ([]dailyBar, error) {
	rows, err := db.QueryContext(ctx, latestDailySQL, symbol, market, from, to, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []dailyBar
	for rows.Next() {
		var raw interface{}
		var open, high, low, close, volume sql.NullFloat64
		if err := rows.Scan(&raw, &open, &high, &low, &close, &volume); err != nil {
			return nil, err
		}
		out = append(out, dailyBar{
			Date:   coerceTradeDate(raw),
			Open:   sqlNullFloat(open),
			High:   sqlNullFloat(high),
			Low:    sqlNullFloat(low),
			Close:  sqlNullFloat(close),
			Volume: sqlNullFloat(volume),
		})
	}
	return out, rows.Err()
}

func dailyWindow(start string) (from, to string) {
	loc, err := time.LoadLocation("Asia/Shanghai")
	if err != nil {
		loc = time.FixedZone("CST", 8*3600)
	}
	now := time.Now().In(loc)
	to = now.Format("2006-01-02")
	days := 60
	text := strings.TrimSpace(start)
	if strings.HasPrefix(text, "-") && strings.HasSuffix(text, "d") {
		if n, err := strconv.Atoi(strings.TrimSuffix(strings.TrimPrefix(text, "-"), "d")); err == nil && n > 0 {
			days = n
		}
	}
	from = now.AddDate(0, 0, -days).Format("2006-01-02")
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
