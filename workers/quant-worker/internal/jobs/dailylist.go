package jobs

import (
	"context"
	"time"

	"github.com/lusd2904/smart-finance-platform/workers/quant-worker/internal/tradeexec"
	"github.com/redis/go-redis/v9"
)

const maxScanSymbols = 80

type StrategyClient interface {
	Evaluate(ctx context.Context, profile string, userID int, targets []Target) ([]StrategySignal, error)
}

type StrategySignal struct {
	Symbol     string
	Market     string
	Signal     string
	Score      float64
	Confidence int
	Reason     string
	Price      float64
}

func RunDailyListOpen(ctx context.Context, repo *Repo, broker tradeexec.Broker, rdb *redis.Client, keys EncKeys) (map[string]interface{}, error) {
	items, err := repo.ListQueuedItems(ctx)
	if err != nil {
		return nil, err
	}
	halt := readHalt(ctx, rdb)
	haltMsg := tradeexec.HaltBlockReason(halt)
	allowed := map[int]bool{}
	var skippedUsers []int
	var done []map[string]interface{}
	now := time.Now()
	for _, it := range items {
		if !tradeexec.IsMarketSessionOpen(it.Market, now) {
			continue
		}
		if _, ok := allowed[it.UserID]; !ok {
			settings := repo.LoadSettings(ctx, it.UserID)
			allowed[it.UserID] = settings.AutoTradeEnabled
			if !settings.AutoTradeEnabled {
				skippedUsers = append(skippedUsers, it.UserID)
			}
		}
		if !allowed[it.UserID] {
			continue
		}
		creds, err := repo.LoadCreds(ctx, it.UserID, keys.CredentialKey, keys.JWTSecret, keys.AppEnv)
		if err != nil || !creds.Configured() {
			continue
		}
		outcome := placeOrQueue(ctx, repo, broker, creds, it, true, haltMsg)
		done = append(done, outcome)
	}
	return map[string]interface{}{"count": len(done), "outcomes": done, "skippedUsers": skippedUsers}, nil
}

func placeOrQueue(ctx context.Context, repo *Repo, broker tradeexec.Broker, creds tradeexec.Creds, row DailyItem, forceSubmit bool, haltMsg string) map[string]interface{} {
	if (row.Status == "submitted" || row.Status == "filled") && row.OrderID != "" {
		return map[string]interface{}{"itemId": row.ItemID, "ok": true, "idempotent": true, "message": "当日已下单", "orderId": row.OrderID}
	}
	if row.Status == "skipped" {
		msg := row.Error
		if msg == "" {
			msg = "已跳过"
		}
		return map[string]interface{}{"itemId": row.ItemID, "ok": false, "message": msg}
	}
	today := tradeexec.TodayCN(time.Time{})
	if !tradeexec.IsCNTradingDay(today) && row.Market == "CN" {
		row.Status = "skipped"
		row.Error = "非交易日禁止开仓"
		_ = repo.UpdateDailyItem(ctx, row)
		return map[string]interface{}{"itemId": row.ItemID, "ok": false, "message": row.Error}
	}
	if !forceSubmit && !tradeexec.IsMarketSessionOpen(row.Market, time.Time{}) {
		row.Status = "queued"
		row.Error = ""
		_ = repo.UpdateDailyItem(ctx, row)
		return map[string]interface{}{"itemId": row.ItemID, "ok": true, "queued": true, "message": "已排队至下一交易日开盘"}
	}
	acct, _ := broker.AccountBalance(ctx, creds)
	quoteLast := 0.0
	if row.Price <= 0 {
		quotes, _ := broker.RealtimeQuotes(ctx, creds, []string{row.Symbol}, row.Market)
		quoteLast = tradeexec.ExtractLastPrice(quotes, tradeexec.ToLongbridgeSymbol(row.Symbol, row.Market))
	}
	qty := tradeexec.SizeDailyListOrder(acct, row.Market, row.Price, quoteLast)
	if qty <= 0 {
		row.Status = "skipped"
		row.Error = "仓位不足或无法计算数量"
		_ = repo.UpdateDailyItem(ctx, row)
		return map[string]interface{}{"itemId": row.ItemID, "ok": false, "message": row.Error}
	}
	if haltMsg != "" {
		row.Status = "skipped"
		row.Error = haltMsg
		_ = repo.UpdateDailyItem(ctx, row)
		return map[string]interface{}{"itemId": row.ItemID, "ok": false, "message": haltMsg}
	}
	res := broker.SubmitOrder(ctx, creds, tradeexec.SubmitReq{
		Symbol: row.Symbol, Side: "buy", Quantity: float64(qty), OrderType: "MO", Market: row.Market,
	})
	row.Quantity = qty
	if res.OK {
		row.Status = "submitted"
		row.OrderID = res.OrderID
		row.Error = ""
	} else {
		row.Status = "rejected"
		row.Error = truncate(res.Message, 500)
		if row.Error == "" {
			row.Error = "下单失败"
		}
	}
	_ = repo.UpdateDailyItem(ctx, row)
	return map[string]interface{}{"itemId": row.ItemID, "ok": res.OK, "message": res.Message, "orderId": row.OrderID}
}

func RunDailyListScan(ctx context.Context, repo *Repo, strategy StrategyClient, payload map[string]interface{}) (map[string]interface{}, error) {
	profile := payloadString(payload, "profile")
	userID := payloadInt(payload, "userId")
	today := tradeexec.TodayCN(time.Time{})
	if userID > 0 {
		code := repo.BoundProfile(ctx, userID, profile)
		return scanUser(ctx, repo, strategy, userID, code, today)
	}
	if !tradeexec.IsCNTradingDay(today) {
		return map[string]interface{}{"skipped": true, "reason": "non_trading_day", "message": "非交易日跳过"}, nil
	}
	users, err := repo.DistinctWatchlistUsers(ctx)
	if err != nil {
		return nil, err
	}
	var results []map[string]interface{}
	for _, uid := range users {
		code := repo.BoundProfile(ctx, uid, profile)
		one, err := scanUser(ctx, repo, strategy, uid, code, today)
		if err != nil {
			results = append(results, map[string]interface{}{"userId": uid, "error": err.Error()})
			continue
		}
		results = append(results, one)
	}
	return map[string]interface{}{"skipped": false, "userCount": len(users), "results": results}, nil
}

func scanUser(ctx context.Context, repo *Repo, strategy StrategyClient, userID int, profile string, today time.Time) (map[string]interface{}, error) {
	scanDate := today.Format("2006-01-02")
	tradeDate := tradeexec.NextCNTradingDay(today).Format("2006-01-02")
	if !tradeexec.IsCNTradingDay(today) {
		id, err := repo.UpsertDailyList(ctx, userID, scanDate, tradeDate, profile, "skipped", "非交易日，不生成可交易清单", 0)
		if err != nil {
			return nil, err
		}
		_ = repo.ReplaceDailyItems(ctx, id, nil)
		return map[string]interface{}{"listId": id, "userId": userID, "status": "skipped", "itemCount": 0}, nil
	}
	watch, err := repo.EnabledWatchlist(ctx, userID)
	if err != nil {
		return nil, err
	}
	if len(watch) > maxScanSymbols {
		watch = watch[:maxScanSymbols]
	}
	if len(watch) == 0 {
		id, err := repo.UpsertDailyList(ctx, userID, scanDate, tradeDate, profile, "empty", "自选为空，未生成清单", 0)
		if err != nil {
			return nil, err
		}
		_ = repo.ReplaceDailyItems(ctx, id, nil)
		return map[string]interface{}{"listId": id, "userId": userID, "status": "empty", "itemCount": 0}, nil
	}
	signals, err := strategy.Evaluate(ctx, profile, userID, watch)
	if err != nil {
		return nil, err
	}
	nameMap := map[string]string{}
	for _, t := range watch {
		nameMap[t.Symbol+"|"+t.Market] = t.Name
	}
	var buys []DailyItem
	for _, sig := range signals {
		if stringsToUpper(sig.Signal) != "BUY" {
			continue
		}
		symbol := stringsToUpper(sig.Symbol)
		market := stringsToUpper(sig.Market)
		if market == "" {
			market = "US"
		}
		buys = append(buys, DailyItem{
			UserID: userID, TradeDate: tradeDate, Symbol: symbol, Market: market,
			Name: nameMap[symbol+"|"+market], Signal: "BUY", Score: sig.Score,
			Confidence: sig.Confidence, Reason: sig.Reason, Status: "listed", Side: "BUY", Price: sig.Price,
		})
	}
	if len(buys) == 0 {
		id, err := repo.UpsertDailyList(ctx, userID, scanDate, tradeDate, profile, "empty", "策略无买入标的，静默不生成可交易清单", 0)
		if err != nil {
			return nil, err
		}
		_ = repo.ReplaceDailyItems(ctx, id, nil)
		return map[string]interface{}{"listId": id, "userId": userID, "status": "empty", "itemCount": 0}, nil
	}
	id, err := repo.UpsertDailyList(ctx, userID, scanDate, tradeDate, profile, "open",
		"已生成 "+itoa(len(buys))+" 只次日标的", len(buys))
	if err != nil {
		return nil, err
	}
	_ = repo.ReplaceDailyItems(ctx, id, buys)
	return map[string]interface{}{"listId": id, "userId": userID, "status": "open", "itemCount": len(buys)}, nil
}

func stringsToUpper(s string) string {
	out := make([]byte, len(s))
	for i := 0; i < len(s); i++ {
		c := s[i]
		if c >= 'a' && c <= 'z' {
			c -= 32
		}
		out[i] = c
	}
	return string(out)
}

func itoa(n int) string {
	if n == 0 {
		return "0"
	}
	var b [12]byte
	i := len(b)
	for n > 0 {
		i--
		b[i] = byte('0' + n%10)
		n /= 10
	}
	return string(b[i:])
}
