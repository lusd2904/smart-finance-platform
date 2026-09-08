package store

import (
	"bytes"
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"

	_ "github.com/go-sql-driver/mysql"

	mwcfg "github.com/lusd2904/smart-finance-platform/workers/notify-worker/internal/config"
	"github.com/lusd2904/smart-finance-platform/workers/notify-worker/internal/timeutil"
)

const disclaimer = "本内容为量化策略摘要，不构成投资建议或荐股，过往表现不代表未来。交易有风险，决策请独立判断。"

type Service struct {
	db *sql.DB
}

func NewService(cfg mwcfg.Config) (*Service, error) {
	dsn := fmt.Sprintf("%s:%s@tcp(%s:%d)/%s?charset=utf8mb4&parseTime=true&loc=Local",
		cfg.MySQLUser, cfg.MySQLPassword, cfg.MySQLHost, cfg.MySQLPort, cfg.MySQLDatabase)
	db, err := sql.Open("mysql", dsn)
	if err != nil {
		return nil, err
	}
	db.SetMaxOpenConns(4)
	if err := db.Ping(); err != nil {
		return nil, err
	}
	return &Service{db: db}, nil
}

func (s *Service) Close() error { return s.db.Close() }

func (s *Service) RunFeishuPush(ctx context.Context) (map[string]interface{}, error) {
	if !timeutil.IsCNTradingDay(time.Now()) {
		return map[string]interface{}{"skipped": true, "reason": "non_trading_day"}, nil
	}
	rows, err := s.db.QueryContext(ctx, `
SELECT sub_id, user_id, personal_enabled, group_enabled, personal_webhook, group_webhook,
       push_time, timezone, last_personal_key, last_group_key
FROM plat_feishu_subscription`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	sent, silent := 0, 0
	for rows.Next() {
		var subID, userID int64
		var personalEnabled, groupEnabled string
		var personalWebhook, groupWebhook, pushTime, timezone sql.NullString
		var lastPersonalKey, lastGroupKey sql.NullString
		if err := rows.Scan(&subID, &userID, &personalEnabled, &groupEnabled, &personalWebhook, &groupWebhook, &pushTime, &timezone, &lastPersonalKey, &lastGroupKey); err != nil {
			continue
		}
		if !dueNow(pushTime.String, timezone.String, time.Now()) {
			continue
		}
		list, items, tradeDate, err := s.latestOpenList(ctx, userID)
		if err != nil || list == nil {
			silent++
			continue
		}
		card := buildCard(list, items, tradeDate)
		var lastErr string
		dayKey := tradeDate
		if personalEnabled == "1" && personalWebhook.Valid && personalWebhook.String != "" {
			key := fmt.Sprintf("%d:personal:%s", userID, dayKey)
			if lastPersonalKey.String != key {
				ok, msg := postWebhook(ctx, personalWebhook.String, card)
				if ok {
					_, _ = s.db.ExecContext(ctx, `UPDATE plat_feishu_subscription SET last_personal_key=?, update_time=NOW() WHERE sub_id=?`, key, subID)
					sent++
				} else {
					lastErr = msg
				}
			}
		}
		if groupEnabled == "1" && groupWebhook.Valid && groupWebhook.String != "" {
			key := fmt.Sprintf("%d:group:%s", userID, dayKey)
			if lastGroupKey.String != key {
				ok, msg := postWebhook(ctx, groupWebhook.String, card)
				if ok {
					_, _ = s.db.ExecContext(ctx, `UPDATE plat_feishu_subscription SET last_group_key=?, update_time=NOW() WHERE sub_id=?`, key, subID)
					sent++
				} else if lastErr == "" {
					lastErr = msg
				}
			}
		}
		if lastErr != "" {
			_, _ = s.db.ExecContext(ctx, `UPDATE plat_feishu_subscription SET last_error=?, update_time=NOW() WHERE sub_id=?`, lastErr, subID)
		}
	}
	return map[string]interface{}{"skipped": false, "sent": sent, "silent": silent}, nil
}

func (s *Service) latestOpenList(ctx context.Context, userID int64) (map[string]interface{}, []map[string]interface{}, string, error) {
	var listID int64
	var tradeDate time.Time
	var itemCount int
	var status string
	err := s.db.QueryRowContext(ctx, `
SELECT list_id, trade_date, item_count, status
FROM quant_daily_list
WHERE user_id=? AND status='open' AND item_count > 0
ORDER BY trade_date DESC LIMIT 1`, userID).Scan(&listID, &tradeDate, &itemCount, &status)
	if err == sql.ErrNoRows {
		return nil, nil, "", nil
	}
	if err != nil {
		return nil, nil, "", err
	}
	itemRows, err := s.db.QueryContext(ctx, `
SELECT symbol, market, signal, score, reason FROM quant_daily_list_item WHERE list_id=? ORDER BY score DESC`, listID)
	if err != nil {
		return nil, nil, "", err
	}
	defer itemRows.Close()
	items := []map[string]interface{}{}
	for itemRows.Next() {
		var symbol, market, signal, reason string
		var score sql.NullFloat64
		if err := itemRows.Scan(&symbol, &market, &signal, &score, &reason); err != nil {
			continue
		}
		items = append(items, map[string]interface{}{
			"symbol": symbol, "market": market, "signal": signal, "score": score.Float64, "reason": reason,
		})
	}
	list := map[string]interface{}{"tradeDate": tradeDate.Format("2006-01-02"), "itemCount": itemCount}
	return list, items, tradeDate.Format("2006-01-02"), nil
}

func buildCard(list map[string]interface{}, items []map[string]interface{}, tradeDate string) map[string]interface{} {
	lines := []string{}
	for i, item := range items {
		if i >= 12 {
			break
		}
		reason := fmt.Sprint(item["reason"])
		if len(reason) > 40 {
			reason = reason[:40]
		}
		lines = append(lines, fmt.Sprintf("%v %v  %v  评分%v  %s", item["symbol"], item["market"], item["signal"], item["score"], reason))
	}
	body := strings.Join(lines, "\n")
	if body == "" {
		body = "当日无可交易标的"
	}
	return map[string]interface{}{
		"msg_type": "interactive",
		"card": map[string]interface{}{
			"header": map[string]interface{}{"title": map[string]interface{}{"tag": "plain_text", "content": "次日策略摘要"}, "template": "blue"},
			"elements": []map[string]interface{}{
				{"tag": "div", "text": map[string]interface{}{"tag": "lark_md", "content": fmt.Sprintf("**交易日** %s  ·  %v 只", tradeDate, list["itemCount"])}},
				{"tag": "div", "text": map[string]interface{}{"tag": "lark_md", "content": body}},
				{"tag": "hr"},
				{"tag": "note", "elements": []map[string]interface{}{{"tag": "plain_text", "content": disclaimer}}},
			},
		},
	}
}

func dueNow(pushTime, timezone string, now time.Time) bool {
	local := now.In(timeutil.LocationFor(timezone))
	parts := strings.Split(pushTime, ":")
	hour, minute := 18, 30
	if len(parts) >= 2 {
		fmt.Sscan(parts[0], &hour)
		fmt.Sscan(parts[1], &minute)
	}
	return local.Hour() == hour && local.Minute() >= minute && local.Minute() < minute+5
}

func postWebhook(ctx context.Context, webhook string, payload map[string]interface{}) (bool, string) {
	raw, _ := json.Marshal(payload)
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, webhook, bytes.NewReader(raw))
	if err != nil {
		return false, err.Error()
	}
	req.Header.Set("Content-Type", "application/json")
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return false, err.Error()
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(resp.Body)
	if resp.StatusCode >= 400 {
		return false, string(body)
	}
	var data map[string]interface{}
	_ = json.Unmarshal(body, &data)
	if code, ok := data["code"].(float64); ok && int(code) != 0 {
		return false, fmt.Sprint(data["msg"])
	}
	return true, "ok"
}
