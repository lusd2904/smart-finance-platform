package store

import (
	"context"
	"database/sql"
	"fmt"
	"strings"
	"time"

	"github.com/lusd2904/smart-finance-platform/services/sfp-intel/internal/config"
	"github.com/lusd2904/smart-finance-platform/services/sfp-intel/internal/crypto"
	"github.com/lusd2904/smart-finance-platform/services/sfp-intel/internal/ingest"
	"github.com/lusd2904/smart-finance-platform/services/sfp-intel/internal/timeutil"
)

type Store struct {
	db  *sql.DB
	cfg *config.Config
}

func New(cfg *config.Config) (*Store, error) {
	db, err := sql.Open("mysql", cfg.MySQLDSN())
	if err != nil {
		return nil, err
	}
	db.SetMaxOpenConns(12)
	db.SetMaxIdleConns(6)
	db.SetConnMaxLifetime(30 * time.Minute)
	if err := db.Ping(); err != nil {
		return nil, err
	}
	return &Store{db: db, cfg: cfg}, nil
}

func (s *Store) Close() error { return s.db.Close() }

type NewsRow struct {
	NewsID     int64      `json:"newsId"`
	Source     string     `json:"source"`
	Title      string     `json:"title"`
	Content    *string    `json:"content"`
	URL        *string    `json:"url"`
	PubTime    *time.Time `json:"pubTime"`
	UniqHash   string     `json:"uniqHash"`
	Analyzed   string     `json:"analyzed"`
	CreateTime *time.Time `json:"createTime"`
}

type NewsQuery struct {
	Source    string
	Title     string
	Analyzed  string
	BeginTime string
	EndTime   string
	PageNum   int
	PageSize  int
}

func (s *Store) ListNews(ctx context.Context, q NewsQuery) ([]NewsRow, int64, error) {
	if q.PageNum < 1 {
		q.PageNum = 1
	}
	if q.PageSize < 1 {
		q.PageSize = 10
	}
	where, args := []string{"1=1"}, []interface{}{}
	if q.Source != "" {
		where = append(where, "source = ?")
		args = append(args, q.Source)
	}
	if q.Title != "" {
		where = append(where, "title LIKE ?")
		args = append(args, "%"+q.Title+"%")
	}
	if q.Analyzed != "" {
		where = append(where, "analyzed = ?")
		args = append(args, q.Analyzed)
	}
	if q.BeginTime != "" && q.EndTime != "" {
		where = append(where, "create_time BETWEEN ? AND ?")
		args = append(args, q.BeginTime+" 00:00:00", q.EndTime+" 23:59:59")
	}
	clause := strings.Join(where, " AND ")
	var total int64
	if err := s.db.QueryRowContext(ctx, "SELECT COUNT(*) FROM sentiment_news WHERE "+clause, args...).Scan(&total); err != nil {
		return nil, 0, err
	}
	offset := (q.PageNum - 1) * q.PageSize
	rows, err := s.db.QueryContext(ctx, `
SELECT news_id, source, title, content, url, pub_time, uniq_hash, analyzed, create_time
FROM sentiment_news WHERE `+clause+` ORDER BY pub_time DESC LIMIT ? OFFSET ?`,
		append(args, q.PageSize, offset)...,
	)
	if err != nil {
		return nil, 0, err
	}
	defer rows.Close()
	out := make([]NewsRow, 0, q.PageSize)
	for rows.Next() {
		var r NewsRow
		if err := rows.Scan(&r.NewsID, &r.Source, &r.Title, &r.Content, &r.URL, &r.PubTime, &r.UniqHash, &r.Analyzed, &r.CreateTime); err != nil {
			return nil, 0, err
		}
		if r.PubTime != nil {
			t := *r.PubTime
			*r.PubTime = t
		}
		out = append(out, r)
	}
	return out, total, rows.Err()
}

func (s *Store) DeleteNews(ctx context.Context, ids []int64) error {
	if len(ids) == 0 {
		return fmt.Errorf("传入资讯id为空")
	}
	placeholders := strings.Repeat("?,", len(ids))
	placeholders = placeholders[:len(placeholders)-1]
	args := make([]interface{}, len(ids))
	for i, id := range ids {
		args[i] = id
	}
	_, err := s.db.ExecContext(ctx, "DELETE FROM sentiment_news WHERE news_id IN ("+placeholders+")", args...)
	return err
}

func (s *Store) CountNews(ctx context.Context) (map[string]int64, error) {
	var total, unanalyzed, today int64
	if err := s.db.QueryRowContext(ctx, "SELECT COUNT(*) FROM sentiment_news").Scan(&total); err != nil {
		return nil, err
	}
	if err := s.db.QueryRowContext(ctx, "SELECT COUNT(*) FROM sentiment_news WHERE analyzed = '0'").Scan(&unanalyzed); err != nil {
		return nil, err
	}
	if err := s.db.QueryRowContext(ctx, "SELECT COUNT(*) FROM sentiment_news WHERE create_time >= CURDATE()").Scan(&today); err != nil {
		return nil, err
	}
	return map[string]int64{"total": total, "unanalyzed": unanalyzed, "today": today}, nil
}

func (s *Store) ExistingHashes(ctx context.Context, hashes []string) (map[string]bool, error) {
	out := make(map[string]bool)
	if len(hashes) == 0 {
		return out, nil
	}
	placeholders := strings.Repeat("?,", len(hashes))
	placeholders = placeholders[:len(placeholders)-1]
	args := make([]interface{}, len(hashes))
	for i, h := range hashes {
		args[i] = h
	}
	rows, err := s.db.QueryContext(ctx, "SELECT uniq_hash FROM sentiment_news WHERE uniq_hash IN ("+placeholders+")", args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	for rows.Next() {
		var h string
		if err := rows.Scan(&h); err != nil {
			return nil, err
		}
		out[h] = true
	}
	return out, rows.Err()
}

func (s *Store) IngestXMonitor(ctx context.Context, items []map[string]interface{}) (map[string]int, error) {
	if len(items) > ingest.BatchMax {
		return nil, fmt.Errorf("单次最多 %d 条", ingest.BatchMax)
	}
	mapped := make([]*ingest.MappedNews, 0, len(items))
	for _, raw := range items {
		if m := ingest.MapXMonitorItem(raw); m != nil {
			mapped = append(mapped, m)
		}
	}
	accepted := len(mapped)
	hashes := make([]string, 0, len(mapped))
	for _, m := range mapped {
		hashes = append(hashes, m.UniqHash)
	}
	existing, err := s.ExistingHashes(ctx, hashes)
	if err != nil {
		return nil, err
	}
	now := timeutil.NowBeijing()
	seen := make(map[string]bool)
	fresh := make([]*ingest.MappedNews, 0)
	for _, m := range mapped {
		if existing[m.UniqHash] || seen[m.UniqHash] {
			continue
		}
		seen[m.UniqHash] = true
		m.Analyzed = "0"
		m.CreateTime = now
		fresh = append(fresh, m)
	}
	if len(fresh) > 0 {
		tx, err := s.db.BeginTx(ctx, nil)
		if err != nil {
			return nil, err
		}
		stmt, err := tx.PrepareContext(ctx, `
INSERT INTO sentiment_news (source, title, content, url, pub_time, uniq_hash, analyzed, create_time)
VALUES (?, ?, ?, ?, ?, ?, ?, ?)`)
		if err != nil {
			_ = tx.Rollback()
			return nil, err
		}
		for _, m := range fresh {
			if _, err := stmt.ExecContext(ctx, m.Source, m.Title, m.Content, m.URL, m.PubTime, m.UniqHash, m.Analyzed, m.CreateTime); err != nil {
				_ = stmt.Close()
				_ = tx.Rollback()
				return nil, err
			}
		}
		_ = stmt.Close()
		if err := tx.Commit(); err != nil {
			return nil, err
		}
	}
	return map[string]int{
		"accepted": accepted,
		"inserted": len(fresh),
		"skipped":  accepted - len(fresh),
	}, nil
}

type AnalysisRow struct {
	AnalysisID  int64      `json:"analysisId"`
	NewsCount   int        `json:"newsCount"`
	NewsIDs     *string    `json:"newsIds"`
	Summary     *string    `json:"summary"`
	USDirection *string    `json:"usDirection"`
	USScore     *float64   `json:"usScore"`
	USReason    *string    `json:"usReason"`
	HKDirection *string    `json:"hkDirection"`
	HKScore     *float64   `json:"hkScore"`
	HKReason    *string    `json:"hkReason"`
	ADirection  *string    `json:"aDirection"`
	AScore      *float64   `json:"aScore"`
	AReason     *string    `json:"aReason"`
	RiskEvents  *string    `json:"riskEvents"`
	ModelName   *string    `json:"modelName"`
	Status      string     `json:"status"`
	ErrorMsg    *string    `json:"errorMsg"`
	CreateTime  *time.Time `json:"createTime"`
}

type AnalysisQuery struct {
	Status    string
	BeginTime string
	EndTime   string
	PageNum   int
	PageSize  int
}

func (s *Store) ListAnalysis(ctx context.Context, q AnalysisQuery) ([]AnalysisRow, int64, error) {
	if q.PageNum < 1 {
		q.PageNum = 1
	}
	if q.PageSize < 1 {
		q.PageSize = 10
	}
	where, args := []string{"1=1"}, []interface{}{}
	if q.Status != "" {
		where = append(where, "status = ?")
		args = append(args, q.Status)
	}
	if q.BeginTime != "" && q.EndTime != "" {
		where = append(where, "create_time BETWEEN ? AND ?")
		args = append(args, q.BeginTime+" 00:00:00", q.EndTime+" 23:59:59")
	}
	clause := strings.Join(where, " AND ")
	var total int64
	if err := s.db.QueryRowContext(ctx, "SELECT COUNT(*) FROM sentiment_analysis WHERE "+clause, args...).Scan(&total); err != nil {
		return nil, 0, err
	}
	offset := (q.PageNum - 1) * q.PageSize
	rows, err := s.db.QueryContext(ctx, `
SELECT analysis_id, news_count, news_ids, summary, us_direction, us_score, us_reason,
       hk_direction, hk_score, hk_reason, a_direction, a_score, a_reason, risk_events,
       model_name, status, error_msg, create_time
FROM sentiment_analysis WHERE `+clause+` ORDER BY create_time DESC LIMIT ? OFFSET ?`,
		append(args, q.PageSize, offset)...,
	)
	if err != nil {
		return nil, 0, err
	}
	defer rows.Close()
	out := make([]AnalysisRow, 0, q.PageSize)
	for rows.Next() {
		var r AnalysisRow
		if err := rows.Scan(
			&r.AnalysisID, &r.NewsCount, &r.NewsIDs, &r.Summary,
			&r.USDirection, &r.USScore, &r.USReason,
			&r.HKDirection, &r.HKScore, &r.HKReason,
			&r.ADirection, &r.AScore, &r.AReason,
			&r.RiskEvents, &r.ModelName, &r.Status, &r.ErrorMsg, &r.CreateTime,
		); err != nil {
			return nil, 0, err
		}
		out = append(out, r)
	}
	return out, total, rows.Err()
}

func (s *Store) GetAnalysis(ctx context.Context, id int64) (*AnalysisRow, error) {
	row := &AnalysisRow{}
	err := s.db.QueryRowContext(ctx, `
SELECT analysis_id, news_count, news_ids, summary, us_direction, us_score, us_reason,
       hk_direction, hk_score, hk_reason, a_direction, a_score, a_reason, risk_events,
       model_name, status, error_msg, create_time
FROM sentiment_analysis WHERE analysis_id = ?`, id).Scan(
		&row.AnalysisID, &row.NewsCount, &row.NewsIDs, &row.Summary,
		&row.USDirection, &row.USScore, &row.USReason,
		&row.HKDirection, &row.HKScore, &row.HKReason,
		&row.ADirection, &row.AScore, &row.AReason,
		&row.RiskEvents, &row.ModelName, &row.Status, &row.ErrorMsg, &row.CreateTime,
	)
	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	return row, nil
}

func (s *Store) LatestAnalysis(ctx context.Context) (*AnalysisRow, error) {
	row := &AnalysisRow{}
	err := s.db.QueryRowContext(ctx, `
SELECT analysis_id, news_count, news_ids, summary, us_direction, us_score, us_reason,
       hk_direction, hk_score, hk_reason, a_direction, a_score, a_reason, risk_events,
       model_name, status, error_msg, create_time
FROM sentiment_analysis WHERE status = '0' ORDER BY create_time DESC LIMIT 1`).Scan(
		&row.AnalysisID, &row.NewsCount, &row.NewsIDs, &row.Summary,
		&row.USDirection, &row.USScore, &row.USReason,
		&row.HKDirection, &row.HKScore, &row.HKReason,
		&row.ADirection, &row.AScore, &row.AReason,
		&row.RiskEvents, &row.ModelName, &row.Status, &row.ErrorMsg, &row.CreateTime,
	)
	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	return row, nil
}

func (s *Store) RecentAnalysisTrend(ctx context.Context, limit int) ([]map[string]interface{}, error) {
	if limit < 1 {
		limit = 24
	}
	rows, err := s.db.QueryContext(ctx, `
SELECT create_time, us_score, hk_score, a_score
FROM sentiment_analysis WHERE status = '0' ORDER BY create_time DESC LIMIT ?`, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	items := make([]map[string]interface{}, 0, limit)
	for rows.Next() {
		var t time.Time
		var us, hk, a sql.NullFloat64
		if err := rows.Scan(&t, &us, &hk, &a); err != nil {
			return nil, err
		}
		item := map[string]interface{}{"createTime": timeutil.FormatBeijing(t)}
		if us.Valid {
			item["usScore"] = us.Float64
		}
		if hk.Valid {
			item["hkScore"] = hk.Float64
		}
		if a.Valid {
			item["aScore"] = a.Float64
		}
		items = append(items, item)
	}
	for i, j := 0, len(items)-1; i < j; i, j = i+1, j-1 {
		items[i], items[j] = items[j], items[i]
	}
	return items, rows.Err()
}

type AiConfig struct {
	ConfigID         *int64   `json:"configId"`
	BaseURL          string   `json:"baseUrl"`
	APIKey           string   `json:"apiKey"`
	ModelName        string   `json:"modelName"`
	Temperature      float64  `json:"temperature"`
	MaxNewsPerRound  int      `json:"maxNewsPerRound"`
	AutoAnalyze      string   `json:"autoAnalyze"`
	EnabledSources   string   `json:"enabledSources"`
	UpdateBy         *string  `json:"updateBy"`
	UpdateTime       *string  `json:"updateTime"`
	ModelScope       *string  `json:"modelScope"`
	ModelID          *int64   `json:"modelId"`
}

type AiModelRow struct {
	ModelID     int64
	BaseURL     sql.NullString
	APIKey      sql.NullString
	ModelCode   sql.NullString
	Temperature sql.NullFloat64
	Scope       sql.NullString
	Status      string
	ModelSort   int
}

func (s *Store) GetAiConfig(ctx context.Context) (*AiConfig, error) {
	model, err := s.resolveSentimentModel(ctx)
	if err != nil {
		return nil, err
	}
	cfg := &AiConfig{Temperature: 0.2, MaxNewsPerRound: 200, AutoAnalyze: "1", EnabledSources: "eastmoney,sina,ths,wallstreetcn,google_news"}
	if model != nil {
		cfg.BaseURL = model.BaseURL.String
		cfg.APIKey = crypto.DecryptCredential(model.APIKey.String, s.cfg.CredentialEncryptionKey, s.cfg.JWTSecret)
		cfg.ModelName = model.ModelCode.String
		if model.Temperature.Valid {
			cfg.Temperature = model.Temperature.Float64
		}
		if model.Scope.Valid {
			scope := model.Scope.String
			cfg.ModelScope = &scope
		}
		id := model.ModelID
		cfg.ModelID = &id
	}
	row := s.db.QueryRowContext(ctx, `
SELECT config_id, max_news_per_round, auto_analyze, enabled_sources, update_by, update_time
FROM sentiment_ai_config ORDER BY config_id LIMIT 1`)
	var configID sql.NullInt64
	var maxNews sql.NullInt64
	var autoAnalyze, enabledSources sql.NullString
	var updateBy sql.NullString
	var updateTime sql.NullTime
	if err := row.Scan(&configID, &maxNews, &autoAnalyze, &enabledSources, &updateBy, &updateTime); err != nil && err != sql.ErrNoRows {
		return nil, err
	}
	if configID.Valid {
		id := configID.Int64
		cfg.ConfigID = &id
	}
	if maxNews.Valid {
		cfg.MaxNewsPerRound = int(maxNews.Int64)
	}
	if autoAnalyze.Valid {
		cfg.AutoAnalyze = autoAnalyze.String
	}
	if enabledSources.Valid {
		cfg.EnabledSources = enabledSources.String
	}
	if updateBy.Valid {
		v := updateBy.String
		cfg.UpdateBy = &v
	}
	if updateTime.Valid {
		v := timeutil.FormatBeijing(updateTime.Time)
		cfg.UpdateTime = &v
	}
	return cfg, nil
}

func (s *Store) SaveAiConfig(ctx context.Context, maxNews int, autoAnalyze, enabledSources, updateBy string) error {
	row := s.db.QueryRowContext(ctx, "SELECT config_id FROM sentiment_ai_config ORDER BY config_id LIMIT 1")
	var configID sql.NullInt64
	_ = row.Scan(&configID)
	now := timeutil.NowBeijing()
	if configID.Valid {
		_, err := s.db.ExecContext(ctx, `
UPDATE sentiment_ai_config SET max_news_per_round=?, auto_analyze=?, enabled_sources=?, update_by=?, update_time=?
WHERE config_id=?`, maxNews, autoAnalyze, enabledSources, updateBy, now, configID.Int64)
		return err
	}
	_, err := s.db.ExecContext(ctx, `
INSERT INTO sentiment_ai_config (max_news_per_round, auto_analyze, enabled_sources, update_by, update_time)
VALUES (?, ?, ?, ?, ?)`, maxNews, autoAnalyze, enabledSources, updateBy, now)
	return err
}

func (s *Store) resolveSentimentModel(ctx context.Context) (*AiModelRow, error) {
	rows, err := s.db.QueryContext(ctx, `
SELECT model_id, base_url, api_key, model_code, temperature, scope, status, model_sort
FROM ai_models WHERE status = '0' ORDER BY model_sort, model_id`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var complete []AiModelRow
	for rows.Next() {
		var r AiModelRow
		if err := rows.Scan(&r.ModelID, &r.BaseURL, &r.APIKey, &r.ModelCode, &r.Temperature, &r.Scope, &r.Status, &r.ModelSort); err != nil {
			return nil, err
		}
		if r.BaseURL.Valid && r.APIKey.Valid && r.ModelCode.Valid &&
			strings.TrimSpace(r.BaseURL.String) != "" &&
			strings.TrimSpace(r.APIKey.String) != "" &&
			strings.TrimSpace(r.ModelCode.String) != "" {
			complete = append(complete, r)
		}
	}
	if len(complete) == 0 {
		return nil, nil
	}
	return selectModelRow(complete), nil
}

func selectModelRow(models []AiModelRow) *AiModelRow {
	preferredCodes := []string{"grok-4.6", "x-ai/grok-4.6"}
	scopes := []string{"sentiment", "global", "chat"}
	for _, scope := range scopes {
		for _, m := range models {
			if m.Scope.Valid && m.Scope.String == scope {
				if scope == "sentiment" {
					for _, code := range preferredCodes {
						if m.ModelCode.Valid && m.ModelCode.String == code {
							copy := m
							return &copy
						}
					}
				}
				copy := m
				return &copy
			}
		}
	}
	for _, code := range preferredCodes {
		for _, m := range models {
			if m.ModelCode.Valid && m.ModelCode.String == code {
				copy := m
				return &copy
			}
		}
	}
	copy := models[0]
	return &copy
}

func FormatNewsRows(rows []NewsRow) []map[string]interface{} {
	out := make([]map[string]interface{}, 0, len(rows))
	for _, r := range rows {
		m := map[string]interface{}{
			"newsId": r.NewsID, "source": r.Source, "title": r.Title,
			"uniqHash": r.UniqHash, "analyzed": r.Analyzed,
		}
		if r.Content != nil {
			m["content"] = *r.Content
		}
		if r.URL != nil {
			m["url"] = *r.URL
		}
		if r.PubTime != nil {
			m["pubTime"] = timeutil.FormatBeijing(*r.PubTime)
		}
		if r.CreateTime != nil {
			m["createTime"] = timeutil.FormatBeijing(*r.CreateTime)
		}
		out = append(out, m)
	}
	return out
}

func FormatAnalysisRow(r *AnalysisRow) map[string]interface{} {
	if r == nil {
		return nil
	}
	m := map[string]interface{}{
		"analysisId": r.AnalysisID, "newsCount": r.NewsCount, "status": r.Status,
	}
	setStr := func(key string, v *string) {
		if v != nil {
			m[key] = *v
		}
	}
	setFloat := func(key string, v *float64) {
		if v != nil {
			m[key] = *v
		}
	}
	setStr("newsIds", r.NewsIDs)
	setStr("summary", r.Summary)
	setStr("usDirection", r.USDirection)
	setFloat("usScore", r.USScore)
	setStr("usReason", r.USReason)
	setStr("hkDirection", r.HKDirection)
	setFloat("hkScore", r.HKScore)
	setStr("hkReason", r.HKReason)
	setStr("aDirection", r.ADirection)
	setFloat("aScore", r.AScore)
	setStr("aReason", r.AReason)
	setStr("riskEvents", r.RiskEvents)
	setStr("modelName", r.ModelName)
	setStr("errorMsg", r.ErrorMsg)
	if r.CreateTime != nil {
		m["createTime"] = timeutil.FormatBeijing(*r.CreateTime)
	}
	return m
}

func FormatAnalysisRows(rows []AnalysisRow) []map[string]interface{} {
	out := make([]map[string]interface{}, 0, len(rows))
	for i := range rows {
		out = append(out, FormatAnalysisRow(&rows[i]))
	}
	return out
}
