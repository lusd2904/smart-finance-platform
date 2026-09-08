package store

import (
	"context"
	"database/sql"
	"encoding/json"
	"strings"

	"github.com/lusd2904/smart-finance-platform/workers/quant-worker/internal/factor"
)

func (s *Service) resolveProfile(ctx context.Context, userID int, override string) string {
	raw := strings.ToLower(strings.TrimSpace(override))
	if validProfile(raw) {
		return raw
	}
	if userID <= 0 {
		return "balanced"
	}
	var code string
	err := s.db.QueryRowContext(ctx, `
SELECT profile_code FROM plat_user_strategy_bind WHERE user_id = ?`, userID).Scan(&code)
	if err != nil || !validProfile(strings.ToLower(strings.TrimSpace(code))) {
		return "balanced"
	}
	return strings.ToLower(strings.TrimSpace(code))
}

func (s *Service) loadProfileConfig(ctx context.Context, profile string, userID int) map[string]any {
	profile = factor.NormalizeProfile(profile)
	var raw sql.NullString
	if userID > 0 {
		_ = s.db.QueryRowContext(ctx, `
SELECT config_json FROM plat_strategy_profile_user
WHERE user_id = ? AND profile_code = ?`, userID, profile).Scan(&raw)
	}
	if !raw.Valid || raw.String == "" {
		_ = s.db.QueryRowContext(ctx, `
SELECT config_json FROM plat_strategy_profile WHERE profile_code = ?`, profile).Scan(&raw)
	}
	if !raw.Valid || raw.String == "" {
		return map[string]any{}
	}
	var cfg map[string]any
	if json.Unmarshal([]byte(raw.String), &cfg) != nil {
		return map[string]any{}
	}
	return cfg
}

func (s *Service) watchlistUsers(ctx context.Context) ([]int, error) {
	rows, err := s.db.QueryContext(ctx, `
SELECT DISTINCT user_id FROM market_watchlist WHERE enabled = '1' AND user_id IS NOT NULL`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := []int{}
	for rows.Next() {
		var uid int
		if err := rows.Scan(&uid); err == nil && uid > 0 {
			out = append(out, uid)
		}
	}
	return out, rows.Err()
}

type watchItem struct {
	Symbol string
	Market string
	Name   string
}

func (s *Service) enabledWatchlist(ctx context.Context, userID int) ([]watchItem, error) {
	rows, err := s.db.QueryContext(ctx, `
SELECT symbol, COALESCE(market,'US'), COALESCE(name,'')
FROM market_watchlist WHERE user_id = ? AND enabled = '1'
ORDER BY sort_order, id`, userID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := []watchItem{}
	for rows.Next() {
		var it watchItem
		if err := rows.Scan(&it.Symbol, &it.Market, &it.Name); err != nil {
			return nil, err
		}
		it.Symbol = strings.ToUpper(strings.TrimSpace(it.Symbol))
		it.Market = strings.ToUpper(strings.TrimSpace(it.Market))
		if it.Market == "" {
			it.Market = "US"
		}
		out = append(out, it)
	}
	return out, rows.Err()
}
