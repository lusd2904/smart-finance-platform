package repo

import (
	"context"
	"database/sql"
	"strings"

	"github.com/lusd2904/smart-finance-platform/services/trade-exec"
)

type Repo struct {
	DB            *sql.DB
	CredentialKey string
	JWTSecret     string
	AppEnv        string
}

func (r *Repo) LoadCreds(ctx context.Context, userID int) (tradeexec.Creds, error) {
	var appKey, secret, token, region sql.NullString
	err := r.DB.QueryRowContext(ctx, `
SELECT app_key, app_secret, access_token, region
FROM quant_longbridge_config WHERE user_id = ?`, userID).Scan(&appKey, &secret, &token, &region)
	if err == sql.ErrNoRows {
		return tradeexec.Creds{UserID: userID, Source: "none"}, nil
	}
	if err != nil {
		return tradeexec.Creds{}, err
	}
	return tradeexec.Creds{
		UserID:      userID,
		AppKey:      strings.TrimSpace(appKey.String),
		AppSecret:   tradeexec.DecryptOrRaw(secret.String, r.CredentialKey, r.JWTSecret, r.AppEnv),
		AccessToken: tradeexec.DecryptOrRaw(token.String, r.CredentialKey, r.JWTSecret, r.AppEnv),
		Region:      strings.TrimSpace(region.String),
		Source:      "db",
	}, nil
}

func (r *Repo) LoadSettings(ctx context.Context, userID int) tradeexec.UserSettings {
	var appKey, token, enabled sql.NullString
	var ratio, pct sql.NullFloat64
	err := r.DB.QueryRowContext(ctx, `
SELECT app_key, access_token, auto_trade_enabled, daily_buy_ratio, max_symbol_position_pct
FROM quant_longbridge_config WHERE user_id = ?`, userID).Scan(&appKey, &token, &enabled, &ratio, &pct)
	s := tradeexec.UserSettings{
		UserID:               userID,
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

func (r *Repo) SaveAutoSettings(ctx context.Context, userID int, enabled bool, dailyBuyRatio, maxSymbolPct float64) error {
	flag := "0"
	if enabled {
		flag = "1"
	}
	_, err := r.DB.ExecContext(ctx, `
UPDATE quant_longbridge_config
SET auto_trade_enabled = ?, daily_buy_ratio = ?, max_symbol_position_pct = ?
WHERE user_id = ?`, flag, tradeexec.ClampDailyBuyRatio(dailyBuyRatio), tradeexec.ClampMaxSymbolPositionPct(maxSymbolPct), userID)
	return err
}
