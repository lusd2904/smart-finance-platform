package store

import (
	"context"
	"encoding/json"
	"strings"
	"time"

	tradeexec "github.com/lusd2904/smart-finance-platform/services/trade-exec"
	"github.com/lusd2904/smart-finance-platform/services/data-api/internal/longbridge"
)

var boardInstruments = []struct {
	Symbol string
	Name   string
	Market string
}{
	{"AAPL", "苹果", "US"}, {"MSFT", "微软", "US"}, {"GOOGL", "谷歌A", "US"}, {"AMZN", "亚马逊", "US"},
	{"NVDA", "英伟达", "US"}, {"META", "Meta", "US"}, {"TSLA", "特斯拉", "US"},
	{"0700.HK", "腾讯控股", "HK"}, {"9988.HK", "阿里巴巴-SW", "HK"}, {"3690.HK", "美团-W", "HK"},
	{"600519", "贵州茅台", "CN"}, {"000858", "五粮液", "CN"}, {"300750", "宁德时代", "CN"},
}

func (d *DB) RunIndicatorRefresh(ctx context.Context, influxQuery func(ctx context.Context, market string, symbols []string, limit int) (map[string][]map[string]interface{}, error)) (map[string]interface{}, error) {
	byMarket := map[string][]string{}
	names := map[string]string{}
	for _, inst := range boardInstruments {
		if strings.HasPrefix(inst.Symbol, "^") {
			continue
		}
		byMarket[inst.Market] = append(byMarket[inst.Market], inst.Symbol)
		names[inst.Symbol+"|"+inst.Market] = inst.Name
	}
	board := []map[string]interface{}{}
	for market, symbols := range byMarket {
		grouped, err := influxQuery(ctx, market, symbols, 2)
		if err != nil {
			return nil, err
		}
		for _, symbol := range symbols {
			bars := grouped[symbol]
			var lastClose, change, changeRate, volume interface{}
			var asOf interface{}
			if len(bars) > 0 {
				last := bars[len(bars)-1]
				lastClose = last["close"]
				volume = last["volume"]
				asOf = last["date"]
				if len(bars) > 1 {
					prevClose, _ := toFloat(bars[len(bars)-2]["close"])
					curClose, _ := toFloat(last["close"])
					if prevClose > 0 {
						chg := curClose - prevClose
						change = round4(chg)
						changeRate = round4(chg / prevClose * 100)
					}
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
	if _, err := d.sql.ExecContext(ctx, `
INSERT INTO quant_readmodel_snapshot (snapshot_type, payload_json, create_time)
VALUES ('board', ?, NOW())`, string(raw)); err != nil {
		return nil, err
	}
	return map[string]interface{}{"count": len(board), "asOf": asOf}, nil
}

func (d *DB) loadLongbridgeCredsForUser(ctx context.Context, userID int64) (longbridge.Creds, error) {
	credKey, jwtSecret, appEnv := tradeexec.EncryptionKeysFromEnv()
	creds, err := d.LoadLongbridgeCreds(ctx, userID, credKey, jwtSecret, appEnv)
	if err != nil {
		return longbridge.Creds{}, err
	}
	return longbridge.Creds{
		AppKey: creds.AppKey, AppSecret: creds.AppSecret, AccessToken: creds.AccessToken, Region: creds.Region,
	}, nil
}

func round4(v float64) float64 {
	return float64(int(v*10000+0.5)) / 10000
}

func toFloat(v interface{}) (float64, bool) {
	switch x := v.(type) {
	case float64:
		return x, true
	case float32:
		return float64(x), true
	case int:
		return float64(x), true
	case int64:
		return float64(x), true
	default:
		return 0, false
	}
}

func beijingNow() string {
	loc, _ := time.LoadLocation("Asia/Shanghai")
	return time.Now().In(loc).Format("2006-01-02 15:04:05")
}
