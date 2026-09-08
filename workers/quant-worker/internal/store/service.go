package store

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"strings"
	"time"

	_ "github.com/go-sql-driver/mysql"
	"github.com/redis/go-redis/v9"

	mwcfg "github.com/lusd2904/smart-finance-platform/workers/quant-worker/internal/config"
	mwinflux "github.com/lusd2904/smart-finance-platform/workers/quant-worker/internal/influx"
)

type targetInstrument struct {
	Symbol string
	Name   string
	Market string
}

var targetInstruments = []targetInstrument{
	{"^DJI", "道琼斯工业指数", "US"}, {"^GSPC", "标普500指数", "US"}, {"^IXIC", "纳斯达克综合指数", "US"},
	{"AAPL", "苹果", "US"}, {"MSFT", "微软", "US"}, {"GOOGL", "谷歌A", "US"}, {"AMZN", "亚马逊", "US"},
	{"NVDA", "英伟达", "US"}, {"META", "Meta", "US"}, {"TSLA", "特斯拉", "US"},
	{"0700.HK", "腾讯控股", "HK"}, {"9988.HK", "阿里巴巴-SW", "HK"}, {"3690.HK", "美团-W", "HK"},
	{"600519", "贵州茅台", "CN"}, {"000858", "五粮液", "CN"}, {"300750", "宁德时代", "CN"},
}

type Service struct {
	db     *sql.DB
	reader *mwinflux.Reader
	rdb    *redis.Client
	cfg    mwcfg.Config
}

func NewService(cfg mwcfg.Config, reader *mwinflux.Reader, rdb *redis.Client) (*Service, error) {
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
	return &Service{db: db, reader: reader, rdb: rdb, cfg: cfg}, nil
}

func (s *Service) Close() error {
	return s.db.Close()
}

func (s *Service) DB() *sql.DB {
	return s.db
}

func (s *Service) RunIndicatorRefresh(ctx context.Context) (map[string]interface{}, error) {
	byMarket := map[string][]string{}
	names := map[string]string{}
	for _, inst := range targetInstruments {
		if strings.HasPrefix(inst.Symbol, "^") {
			continue
		}
		byMarket[inst.Market] = append(byMarket[inst.Market], inst.Symbol)
		names[inst.Symbol+"|"+inst.Market] = inst.Name
	}

	board := []map[string]interface{}{}
	for market, symbols := range byMarket {
		grouped, err := s.reader.QueryLatestKlines(ctx, market, symbols, 2, "-90d")
		if err != nil {
			return nil, err
		}
		for _, symbol := range symbols {
			bars := grouped[symbol]
			var lastClose, change, changeRate, volume interface{}
			var asOf interface{}
			if len(bars) > 0 {
				last := bars[len(bars)-1]
				lastClose = last.Close
				volume = last.Volume
				asOf = last.Date
				if len(bars) > 1 && bars[len(bars)-2].Close > 0 {
					prev := bars[len(bars)-2]
					chg := last.Close - prev.Close
					change = round4(chg)
					changeRate = round4(chg / prev.Close * 100)
				}
			}
			board = append(board, map[string]interface{}{
				"symbol": symbol, "name": names[symbol+"|"+market], "market": market,
				"close": lastClose, "change": change, "changeRate": changeRate,
				"volume": volume, "asOf": asOf,
			})
		}
	}

	asOf := beijingNow()
	payload := map[string]interface{}{
		"asOf": asOf, "count": len(board), "items": board, "readModelVersion": "v2.3",
	}
	raw, _ := json.Marshal(payload)
	if _, err := s.db.ExecContext(ctx, `
INSERT INTO quant_readmodel_snapshot (snapshot_type, payload_json, create_time)
VALUES ('board', ?, NOW())`, string(raw)); err != nil {
		return nil, err
	}
	if err := putScheduledBoard(ctx, s.rdb, payload); err != nil {
		return nil, err
	}
	return map[string]interface{}{"count": len(board), "asOf": asOf}, nil
}

func round4(v float64) float64 {
	return float64(int(v*10000+0.5)) / 10000
}

func beijingNow() string {
	loc, _ := time.LoadLocation("Asia/Shanghai")
	return time.Now().In(loc).Format("2006-01-02 15:04:05")
}

func putScheduledBoard(ctx context.Context, rdb *redis.Client, payload interface{}) error {
	raw, err := json.Marshal(payload)
	if err != nil {
		return err
	}
	return rdb.Set(ctx, "readmodel:scheduled:board", raw, 15*time.Minute).Err()
}
