package store

import (
	"context"
	"crypto/sha256"
	"database/sql"
	"encoding/base64"
	"fmt"
	"strings"

	"github.com/fernet/fernet-go"
	tradeexec "github.com/lusd2904/smart-finance-platform/services/trade-exec"
)

type LongbridgeConfig struct {
	ID                   int64
	UserID               int64
	AppKey               string
	AppSecret            string
	AccessToken          string
	Region               string
	AutoTradeEnabled     bool
	DailyBuyRatio        float64
	MaxSymbolPositionPct float64
	UpdateTime           interface{}
}

func (d *DB) LoadLongbridgeCreds(ctx context.Context, userID int64, credKey, jwtSecret, appEnv string) (tradeexec.Creds, error) {
	var appKey, secret, token, region sql.NullString
	err := d.sql.QueryRowContext(ctx, `
SELECT app_key, app_secret, access_token, region
FROM quant_longbridge_config WHERE user_id = ?`, userID).Scan(&appKey, &secret, &token, &region)
	if err == sql.ErrNoRows {
		return tradeexec.Creds{UserID: int(userID), Source: "none"}, nil
	}
	if err != nil {
		return tradeexec.Creds{}, err
	}
	return tradeexec.Creds{
		UserID:      int(userID),
		AppKey:      strings.TrimSpace(appKey.String),
		AppSecret:   tradeexec.DecryptOrRaw(secret.String, credKey, jwtSecret, appEnv),
		AccessToken: tradeexec.DecryptOrRaw(token.String, credKey, jwtSecret, appEnv),
		Region:      strings.TrimSpace(region.String),
		Source:      "db",
	}, nil
}

func (d *DB) GetLongbridgeConfig(ctx context.Context, userID int64, credKey, jwtSecret, appEnv string) (LongbridgeConfig, error) {
	var id int64
	var appKey, secret, token, region, autoEnabled sql.NullString
	var ratio, pct sql.NullFloat64
	var updateTime sql.NullTime
	err := d.sql.QueryRowContext(ctx, `
SELECT id, app_key, app_secret, access_token, region, auto_trade_enabled, daily_buy_ratio, max_symbol_position_pct, update_time
FROM quant_longbridge_config WHERE user_id = ?`, userID).Scan(
		&id, &appKey, &secret, &token, &region, &autoEnabled, &ratio, &pct, &updateTime)
	if err == sql.ErrNoRows {
		return LongbridgeConfig{UserID: userID, Region: "cn", DailyBuyRatio: 0.20, MaxSymbolPositionPct: 0.10}, nil
	}
	if err != nil {
		return LongbridgeConfig{}, err
	}
	return LongbridgeConfig{
		ID:                   id,
		UserID:               userID,
		AppKey:               sqlStr(appKey),
		AppSecret:            maskSecret(tradeexec.DecryptOrRaw(secret.String, credKey, jwtSecret, appEnv)),
		AccessToken:          maskSecret(tradeexec.DecryptOrRaw(token.String, credKey, jwtSecret, appEnv)),
		Region:               defaultStr(sqlStr(region), "cn"),
		AutoTradeEnabled:     sqlStr(autoEnabled) == "1",
		DailyBuyRatio:        nullFloatDefault(ratio, 0.20),
		MaxSymbolPositionPct: nullFloatDefault(pct, 0.10),
		UpdateTime:           fmtTime(updateTime),
	}, nil
}

func sqlStr(v sql.NullString) string {
	if v.Valid {
		return v.String
	}
	return ""
}

func (d *DB) SaveLongbridgeConfig(ctx context.Context, userID int64, cfg LongbridgeConfig, credKey, jwtSecret, appEnv string) error {
	secret := cfg.AppSecret
	token := cfg.AccessToken
	if isMasked(secret) {
		row, err := d.loadRawSecrets(ctx, userID)
		if err != nil {
			return err
		}
		secret = row.secret
	} else if secret != "" {
		secret = encryptCredential(secret, credKey, jwtSecret, appEnv)
	}
	if isMasked(token) {
		row, err := d.loadRawSecrets(ctx, userID)
		if err != nil {
			return err
		}
		token = row.token
	} else if token != "" {
		token = encryptCredential(token, credKey, jwtSecret, appEnv)
	}
	region := strings.ToLower(defaultStr(cfg.Region, "cn"))
	_, err := d.sql.ExecContext(ctx, `
INSERT INTO quant_longbridge_config (user_id, app_key, app_secret, access_token, region, update_time)
VALUES (?, ?, ?, ?, ?, NOW())
ON DUPLICATE KEY UPDATE app_key=VALUES(app_key), app_secret=VALUES(app_secret),
  access_token=VALUES(access_token), region=VALUES(region), update_time=NOW()`,
		userID, cfg.AppKey, secret, token, region)
	return err
}

type rawSecrets struct {
	secret string
	token  string
}

func (d *DB) loadRawSecrets(ctx context.Context, userID int64) (rawSecrets, error) {
	var secret, token sql.NullString
	err := d.sql.QueryRowContext(ctx, `
SELECT app_secret, access_token FROM quant_longbridge_config WHERE user_id = ?`, userID).Scan(&secret, &token)
	if err != nil {
		return rawSecrets{}, err
	}
	return rawSecrets{secret: secret.String, token: token.String}, nil
}

func (d *DB) LoadTradeSettings(ctx context.Context, userID int64) tradeexec.UserSettings {
	var appKey, token, enabled sql.NullString
	var ratio, pct sql.NullFloat64
	err := d.sql.QueryRowContext(ctx, `
SELECT app_key, access_token, auto_trade_enabled, daily_buy_ratio, max_symbol_position_pct
FROM quant_longbridge_config WHERE user_id = ?`, userID).Scan(&appKey, &token, &enabled, &ratio, &pct)
	s := tradeexec.UserSettings{
		UserID:               int(userID),
		DailyBuyRatio:        tradeexec.ClampDailyBuyRatio(tradeexec.DailyBuyPositionRatio),
		MaxSymbolPositionPct: tradeexec.DefaultMaxSymbolPositionPct,
	}
	if err != nil {
		return s
	}
	s.HasKeys = strings.TrimSpace(appKey.String) != "" && strings.TrimSpace(token.String) != ""
	s.AutoTradeEnabled = s.HasKeys && strings.TrimSpace(enabled.String) == "1"
	if ratio.Valid {
		s.DailyBuyRatio = tradeexec.ClampDailyBuyRatio(ratio.Float64)
	}
	if pct.Valid {
		s.MaxSymbolPositionPct = tradeexec.ClampMaxSymbolPositionPct(pct.Float64)
	}
	return s
}

func (d *DB) AccountTradeReady(ctx context.Context, userID int64) (bool, string) {
	settings := d.LoadTradeSettings(ctx, userID)
	if settings.AutoTradeEnabled {
		return true, ""
	}
	var appKey, token sql.NullString
	err := d.sql.QueryRowContext(ctx, `
SELECT app_key, access_token FROM quant_longbridge_config WHERE user_id = ?`, userID).Scan(&appKey, &token)
	if err == sql.ErrNoRows || strings.TrimSpace(appKey.String) == "" || strings.TrimSpace(token.String) == "" {
		return false, "未配置长桥账户 Key，无法打开自动交易"
	}
	return false, "请先在「量化交易 / 策略配置」打开本账户自动交易"
}

func maskSecret(value string) string {
	if value == "" {
		return ""
	}
	if len(value) > 4 {
		return "****" + value[len(value)-4:]
	}
	return "****"
}

func isMasked(value string) bool {
	return strings.HasPrefix(value, "****")
}

func nullFloatDefault(v sql.NullFloat64, def float64) float64 {
	if v.Valid {
		return v.Float64
	}
	return def
}

func defaultStr(v, fallback string) string {
	if strings.TrimSpace(v) == "" {
		return fallback
	}
	return v
}

func encryptCredential(plain, credKey, jwtSecret, appEnv string) string {
	if plain == "" {
		return ""
	}
	source := strings.TrimSpace(credKey)
	if source == "" {
		if strings.EqualFold(appEnv, "prod") {
			return plain
		}
		source = strings.TrimSpace(jwtSecret)
	}
	sum := sha256.Sum256([]byte(source))
	key := base64.URLEncoding.EncodeToString(sum[:])
	k := fernet.MustDecodeKeys(key)
	tok, err := fernet.EncryptAndSign([]byte(plain), k[0])
	if err != nil {
		return plain
	}
	return string(tok)
}

func (d *DB) ToConfigModel(cfg LongbridgeConfig) map[string]interface{} {
	return map[string]interface{}{
		"id": cfg.ID, "userId": cfg.UserID, "appKey": cfg.AppKey,
		"appSecret": cfg.AppSecret, "accessToken": cfg.AccessToken, "region": cfg.Region,
		"autoTradeEnabled": cfg.AutoTradeEnabled, "dailyBuyRatio": cfg.DailyBuyRatio,
		"maxSymbolPositionPct": cfg.MaxSymbolPositionPct, "updateTime": cfg.UpdateTime,
	}
}

func (d *DB) ListConfiguredLongbridgeUsers(ctx context.Context) ([]int64, error) {
	rows, err := d.sql.QueryContext(ctx, `
SELECT user_id FROM quant_longbridge_config
WHERE app_key IS NOT NULL AND app_key != '' AND access_token IS NOT NULL AND access_token != ''`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var ids []int64
	for rows.Next() {
		var id int64
		if err := rows.Scan(&id); err != nil {
			return nil, err
		}
		ids = append(ids, id)
	}
	return ids, rows.Err()
}

func (d *DB) UpdateDailyListAuto(ctx context.Context, listID int64, enabled bool) error {
	flag := "0"
	if enabled {
		flag = "1"
	}
	_, err := d.sql.ExecContext(ctx, `UPDATE quant_daily_list SET auto_enabled = ?, update_time = NOW() WHERE list_id = ?`, flag, listID)
	return err
}

func (d *DB) SetDailyListItemAuto(ctx context.Context, listID int64, itemIDs []int64, enabled bool) error {
	flag := "0"
	if enabled {
		flag = "1"
	}
	if len(itemIDs) == 0 {
		_, err := d.sql.ExecContext(ctx, `UPDATE quant_daily_list_item SET auto_trade = ?, update_time = NOW() WHERE list_id = ?`, flag, listID)
		return err
	}
	placeholders := strings.TrimRight(strings.Repeat("?,", len(itemIDs)), ",")
	args := make([]interface{}, 0, len(itemIDs)+2)
	args = append(args, flag)
	for _, id := range itemIDs {
		args = append(args, id)
	}
	args = append(args, listID)
	_, err := d.sql.ExecContext(ctx, fmt.Sprintf(`
UPDATE quant_daily_list_item SET auto_trade = ?, update_time = NOW()
WHERE item_id IN (%s) AND list_id = ?`, placeholders), args...)
	return err
}

func (d *DB) AddQuantWatchlistSymbol(ctx context.Context, userID int64, symbol, market, note string) error {
	_, err := d.sql.ExecContext(ctx, `
INSERT INTO quant_watchlist (user_id, symbol, market, note, enabled, create_time, update_time)
VALUES (?, ?, ?, ?, '1', NOW(), NOW())
ON DUPLICATE KEY UPDATE enabled='1', note=VALUES(note), update_time=NOW()`,
		userID, strings.ToUpper(symbol), strings.ToUpper(market), note)
	return err
}

func (d *DB) GetDailyListItem(ctx context.Context, itemID, userID int64) (map[string]interface{}, error) {
	var listID int64
	var symbol, market, status, side, selected, autoTrade string
	var price sql.NullFloat64
	var orderID, errText sql.NullString
	var quantity sql.NullInt64
	err := d.sql.QueryRowContext(ctx, `
SELECT i.list_id, i.symbol, i.market, i.status, i.side, i.selected, i.auto_trade, i.price, i.order_id, i.error, i.quantity
FROM quant_daily_list_item i
JOIN quant_daily_list l ON l.list_id = i.list_id
WHERE i.item_id = ? AND l.user_id = ?`, itemID, userID).Scan(
		&listID, &symbol, &market, &status, &side, &selected, &autoTrade, &price, &orderID, &errText, &quantity)
	if err != nil {
		return nil, err
	}
	return map[string]interface{}{
		"itemId": itemID, "listId": listID, "symbol": symbol, "market": market,
		"status": status, "side": side, "selected": selected, "autoTrade": autoTrade,
		"price": nullFloat(price), "orderId": nullStr(orderID), "error": nullStr(errText),
		"quantity": nullInt(quantity),
	}, nil
}

func (d *DB) UpdateDailyListItem(ctx context.Context, itemID int64, status string, orderID, errText string, qty int) error {
	_, err := d.sql.ExecContext(ctx, `
UPDATE quant_daily_list_item SET status = ?, order_id = ?, error = ?, quantity = ?, selected = '1', update_time = NOW()
WHERE item_id = ?`, status, nullString(orderID), nullString(errText), qty, itemID)
	return err
}

func (d *DB) LatestOpenDailyListID(ctx context.Context, userID int64) (int64, string, error) {
	var listID int64
	var status string
	err := d.sql.QueryRowContext(ctx, `
SELECT list_id, status FROM quant_daily_list WHERE user_id = ? ORDER BY trade_date DESC, list_id DESC LIMIT 1`, userID).Scan(&listID, &status)
	if err == sql.ErrNoRows {
		return 0, "", fmt.Errorf("没有可交易的次日清单")
	}
	if status != "open" {
		return 0, "", fmt.Errorf("没有可交易的次日清单")
	}
	return listID, status, err
}

func nullString(s string) interface{} {
	if strings.TrimSpace(s) == "" {
		return nil
	}
	return s
}
