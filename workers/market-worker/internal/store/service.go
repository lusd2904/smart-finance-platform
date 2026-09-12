package store

import (
	"context"
	"database/sql"
	"fmt"
	"strings"
	"time"

	_ "github.com/go-sql-driver/mysql"
	"github.com/redis/go-redis/v9"

	"github.com/lusd2904/smart-finance-platform/workers/market-worker/internal/config"
	"github.com/lusd2904/smart-finance-platform/workers/market-worker/internal/influx"
	"github.com/lusd2904/smart-finance-platform/workers/market-worker/internal/kline"
)

type Instrument struct {
	Symbol   string
	Name     string
	Market   string
	Category string
	Bars     int
	LastDate sql.NullString
}

type Service struct {
	db     *sql.DB
	influx *influx.Writer
	reader *influx.Reader
	kline  *kline.Client
	rdb    *redis.Client
	cfg    config.Config
}

func NewService(cfg config.Config, writer *influx.Writer, reader *influx.Reader, klineClient *kline.Client, rdb *redis.Client) (*Service, error) {
	dsn := fmt.Sprintf("%s:%s@tcp(%s:%d)/%s?charset=utf8mb4&parseTime=true&loc=Local",
		cfg.MySQLUser, cfg.MySQLPassword, cfg.MySQLHost, cfg.MySQLPort, cfg.MySQLDatabase)
	db, err := sql.Open("mysql", dsn)
	if err != nil {
		return nil, err
	}
	db.SetMaxOpenConns(4)
	db.SetMaxIdleConns(2)
	if err := db.Ping(); err != nil {
		return nil, err
	}
	return &Service{db: db, influx: writer, reader: reader, kline: klineClient, rdb: rdb, cfg: cfg}, nil
}

func (s *Service) Close() error {
	return s.db.Close()
}

func (s *Service) SyncSymbol(ctx context.Context, symbol, market string, years int) (int, error) {
	rows, _ := s.kline.FetchReal(symbol, market, years)
	if len(rows) == 0 {
		return 0, nil
	}
	bars := toInfluxBars(rows)
	n, err := s.influx.WriteDaily(ctx, market, bars)
	if err != nil {
		return 0, err
	}
	_ = s.saveMySQL(rows)
	return n, nil
}

func (s *Service) SyncFeatured(ctx context.Context, years int) (map[string]interface{}, error) {
	targets, err := s.listUniverse(ctx, []string{"US", "CN", "HK"}, false)
	if err != nil {
		return nil, err
	}
	return s.syncTargets(ctx, targets, years, s.cfg.SymbolInterval, true)
}

func (s *Service) SyncUniverse(ctx context.Context, years int) (map[string]interface{}, error) {
	targets, err := s.listUniverse(ctx, []string{"US", "CN", "HK"}, true)
	if err != nil {
		return nil, err
	}
	interval := s.cfg.SymbolInterval
	if interval < 1.0 {
		interval = 1.5
	}
	return s.syncTargets(ctx, targets, years, interval, true)
}

func (s *Service) SyncEODMarket(ctx context.Context, market string, years int) (map[string]interface{}, error) {
	mkt := strings.ToUpper(market)
	session := eodSessionDate(mkt)
	targets, err := s.listUniverse(ctx, []string{mkt}, true)
	if err != nil {
		return nil, err
	}
	details := map[string]int{}
	skipped := []string{}
	failed := []string{}
	total := 0
	interval := s.cfg.SymbolInterval
	for i, t := range targets {
		last := ""
		if t.LastDate.Valid {
			last = t.LastDate.String
		}
		if shouldSkipEOD(last, session) {
			skipped = append(skipped, t.Symbol)
			continue
		}
		pts, err := s.SyncSymbol(ctx, t.Symbol, t.Market, years)
		details[t.Symbol] = pts
		total += pts
		if pts <= 0 || err != nil {
			failed = append(failed, t.Symbol)
		} else if interval > 0 && i < len(targets)-1 {
			time.Sleep(time.Duration(interval * float64(time.Second)))
		}
	}
	minute, err := s.SyncMinutes(ctx, mkt, interval)
	if err != nil {
		return nil, err
	}
	synced := []string{}
	for sym, pts := range details {
		if pts > 0 {
			synced = append(synced, sym)
		}
	}
	return map[string]interface{}{
		"market":      mkt,
		"sessionDate": session.Format("2006-01-02"),
		"daily": map[string]interface{}{
			"scanned":        len(targets),
			"synced_symbols": synced,
			"skipped":        skipped,
			"failed":         failed,
			"total_points":   total,
		},
		"minute": minute,
	}, nil
}

func (s *Service) SyncMinutes(ctx context.Context, market string, interval float64) (map[string]interface{}, error) {
	targets, err := s.minuteTargets(ctx, market, 80)
	if err != nil {
		return nil, err
	}
	synced := []string{}
	failed := []string{}
	total := 0
	for i, sym := range targets {
		rows, err := s.kline.FetchMinute(sym, market)
		if err != nil || len(rows) == 0 {
			failed = append(failed, sym)
			continue
		}
		bars := minuteBarsFromRows(rows)
		var influxW minuteInfluxWriter
		if s.influx != nil {
			influxW = s.influx
		}
		n, err := writeMinutesDual(ctx, influxW, s.db, market, minuteSource(rows), bars)
		if err != nil || n == 0 {
			failed = append(failed, sym)
			continue
		}
		synced = append(synced, sym)
		total += n
		if interval > 0 && i < len(targets)-1 {
			time.Sleep(time.Duration(interval * float64(time.Second)))
		}
	}
	return map[string]interface{}{
		"market": market, "scanned": len(targets),
		"synced_symbols": synced, "failed": failed, "total_points": total,
	}, nil
}

func (s *Service) MySQLToInflux(ctx context.Context, symbol string, market string) (map[string]interface{}, error) {
	query := `SELECT symbol, market, trade_date, open_price, high_price, low_price, close_price, volume FROM market_price_history_daily`
	args := []interface{}{}
	if symbol != "" {
		query += " WHERE symbol=?"
		args = append(args, symbol)
	}
	query += " ORDER BY symbol, trade_date"
	rows, err := s.db.QueryContext(ctx, query, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	byMarket := map[string][]influx.Bar{}
	symbols := map[string]bool{}
	for rows.Next() {
		var sym, mkt string
		var tradeDate time.Time
		var open, high, low, close, volume float64
		if err := rows.Scan(&sym, &mkt, &tradeDate, &open, &high, &low, &close, &volume); err != nil {
			continue
		}
		if close <= 0 {
			continue
		}
		if mkt == "" {
			mkt = market
		}
		mkt = strings.ToUpper(mkt)
		byMarket[mkt] = append(byMarket[mkt], influx.Bar{
			Symbol: sym, TradeDate: tradeDate,
			Open: open, High: high, Low: low, Close: close, Volume: volume,
		})
		symbols[sym] = true
	}
	total := 0
	markets := []string{}
	for mkt, bars := range byMarket {
		n, err := s.influx.WriteDaily(ctx, mkt, bars)
		if err != nil {
			return nil, err
		}
		total += n
		markets = append(markets, mkt)
	}
	symList := make([]string, 0, len(symbols))
	for sym := range symbols {
		symList = append(symList, sym)
	}
	return map[string]interface{}{
		"total_points": total,
		"markets":      markets,
		"symbols":      symList,
		"message":      fmt.Sprintf("已迁移 %d 点到 Influx", total),
	}, nil
}

func (s *Service) syncTargets(ctx context.Context, targets []Instrument, years int, interval float64, skipSynced bool) (map[string]interface{}, error) {
	details := map[string]int{}
	skipped := []string{}
	failed := []string{}
	total := 0
	for i, t := range targets {
		last := ""
		if t.LastDate.Valid {
			last = t.LastDate.String
		}
		if skipSynced && shouldSkipSynced(t.Bars, last, s.cfg.SkipMinBars, s.cfg.SkipFreshDays) {
			skipped = append(skipped, t.Symbol)
			details[t.Symbol] = 0
			continue
		}
		pts, err := s.SyncSymbol(ctx, t.Symbol, t.Market, years)
		details[t.Symbol] = pts
		total += pts
		if pts <= 0 || err != nil {
			failed = append(failed, t.Symbol)
		} else if interval > 0 && i < len(targets)-1 {
			time.Sleep(time.Duration(interval * float64(time.Second)))
		}
	}
	synced := []string{}
	for sym, pts := range details {
		if pts > 0 {
			synced = append(synced, sym)
		}
	}
	return map[string]interface{}{
		"synced_symbols": synced,
		"skipped":        skipped,
		"total_points":   total,
		"details":        details,
		"failed":         failed,
		"scanned":        len(targets),
	}, nil
}

func (s *Service) listUniverse(ctx context.Context, markets []string, includeListed bool) ([]Instrument, error) {
	if len(markets) == 0 {
		markets = []string{"US", "CN", "HK"}
	}
	placeholders := strings.TrimRight(strings.Repeat("?,", len(markets)), ",")
	args := make([]interface{}, len(markets))
	for i, m := range markets {
		args[i] = strings.ToUpper(m)
	}
	query := fmt.Sprintf(`
SELECT i.symbol, i.name, i.market, i.category,
       COALESCE(p.bars, 0) AS bars, p.last_date
FROM market_instrument i
LEFT JOIN (
  SELECT symbol, COUNT(*) AS bars, MAX(trade_date) AS last_date
  FROM market_price_history_daily
  GROUP BY symbol
) p ON p.symbol = i.symbol
WHERE i.enabled='1' AND i.market IN (%s)`, placeholders)
	if !includeListed {
		query += " AND i.category <> 'listed'"
	}
	query += " ORDER BY FIELD(i.market, 'US','HK','CN'), i.symbol"
	rows, err := s.db.QueryContext(ctx, query, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []Instrument
	for rows.Next() {
		var inst Instrument
		if err := rows.Scan(&inst.Symbol, &inst.Name, &inst.Market, &inst.Category, &inst.Bars, &inst.LastDate); err != nil {
			continue
		}
		out = append(out, inst)
	}
	return out, nil
}

func (s *Service) minuteTargets(ctx context.Context, market string, cap int) ([]string, error) {
	seen := map[string]bool{}
	var out []string
	rows, err := s.db.QueryContext(ctx, `
SELECT symbol FROM market_top50_snapshot
WHERE market=? AND trade_date=(SELECT MAX(trade_date) FROM market_top50_snapshot WHERE market=?)
ORDER BY rank_no`, market, market)
	if err == nil {
		defer rows.Close()
		for rows.Next() {
			var sym string
			if err := rows.Scan(&sym); err != nil || sym == "" || seen[sym] {
				continue
			}
			seen[sym] = true
			out = append(out, sym)
		}
	}
	featured := featuredSymbols(market)
	for _, sym := range featured {
		if !seen[sym] {
			seen[sym] = true
			out = append(out, sym)
		}
	}
	if cap > 0 && len(out) > cap {
		out = out[:cap]
	}
	return out, nil
}

func featuredSymbols(market string) []string {
	// subset of TARGET_INSTRUMENTS non-index for each market
	all := map[string][]string{
		"US": {"AAPL", "MSFT", "NVDA", "TSLA", "GOOGL", "AMZN", "META"},
		"HK": {"0700.HK", "9988.HK", "3690.HK"},
		"CN": {"600519.SH", "000001.SZ"},
	}
	return all[strings.ToUpper(market)]
}

func (s *Service) saveMySQL(rows []kline.Row) int {
	if len(rows) == 0 {
		return 0
	}
	stmt := `INSERT INTO market_price_history_daily
(symbol, market, trade_date, open_price, high_price, low_price, close_price, volume, turnover, source, update_time)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, NOW())
ON DUPLICATE KEY UPDATE
market=VALUES(market), open_price=VALUES(open_price), high_price=VALUES(high_price),
low_price=VALUES(low_price), close_price=VALUES(close_price), volume=VALUES(volume),
source=VALUES(source), update_time=VALUES(update_time)`
	count := 0
	for _, r := range rows {
		_, err := s.db.Exec(stmt, r.Symbol, r.Market, r.TradeDate, r.Open, r.High, r.Low, r.Close, r.Volume, r.Source)
		if err == nil {
			count++
		}
	}
	return count
}

func toInfluxBars(rows []kline.Row) []influx.Bar {
	out := make([]influx.Bar, 0, len(rows))
	for _, r := range rows {
		ts, err := influx.ParseDate(r.TradeDate)
		if err != nil {
			continue
		}
		out = append(out, influx.Bar{
			Symbol: r.Symbol, TradeDate: ts,
			Open: r.Open, High: r.High, Low: r.Low, Close: r.Close, Volume: r.Volume,
		})
	}
	return out
}

func shouldSkipSynced(bars int, lastDate string, minBars, freshDays int) bool {
	if bars < minBars || lastDate == "" {
		return false
	}
	last, err := time.Parse("2006-01-02", lastDate[:10])
	if err != nil {
		return false
	}
	return time.Since(last) <= time.Duration(freshDays)*24*time.Hour
}

func shouldSkipEOD(lastDate string, session time.Time) bool {
	if lastDate == "" {
		return false
	}
	last, err := time.Parse("2006-01-02", lastDate[:10])
	if err != nil {
		return false
	}
	return !last.Before(session)
}

func eodSessionDate(market string) time.Time {
	locName := map[string]string{"CN": "Asia/Shanghai", "HK": "Asia/Hong_Kong", "US": "America/New_York"}[strings.ToUpper(market)]
	if locName == "" {
		locName = "America/New_York"
	}
	loc, err := time.LoadLocation(locName)
	if err != nil {
		loc = time.UTC
	}
	closeHour := map[string]int{"CN": 15, "HK": 16, "US": 16}[strings.ToUpper(market)]
	if closeHour == 0 {
		closeHour = 16
	}
	now := time.Now().In(loc)
	day := now
	if now.Hour() < closeHour || (now.Hour() == closeHour && now.Minute() < 5) {
		day = now.AddDate(0, 0, -1)
	}
	for day.Weekday() == time.Saturday || day.Weekday() == time.Sunday {
		day = day.AddDate(0, 0, -1)
	}
	y, m, d := day.Date()
	return time.Date(y, m, d, 0, 0, 0, 0, time.UTC)
}
