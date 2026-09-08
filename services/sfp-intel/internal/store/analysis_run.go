package store

import (
	"context"
	"database/sql"
	"fmt"
	"strings"

	"github.com/lusd2904/smart-finance-platform/services/sfp-intel/internal/crypto"
	"github.com/lusd2904/smart-finance-platform/services/sfp-intel/internal/llm"
	"github.com/lusd2904/smart-finance-platform/services/sfp-intel/internal/timeutil"
)

const analyzeWindowMinutes = 10

func (s *Store) RunSentimentAnalysis(ctx context.Context) (map[string]interface{}, error) {
	cfg, err := s.GetAiConfig(ctx)
	if err != nil {
		return nil, err
	}
	model, err := s.resolveSentimentModel(ctx)
	if err != nil || model == nil {
		return nil, fmt.Errorf("请先在AI配置中填写Base URL、API Key与模型名称")
	}
	limit := cfg.MaxNewsPerRound
	if limit <= 0 || limit > 200 {
		limit = 200
	}
	rows, err := s.listUnanalyzedNews(ctx, limit, analyzeWindowMinutes)
	if err != nil {
		return nil, err
	}
	if len(rows) == 0 {
		return map[string]interface{}{
			"analyzed": 0, "analysisId": nil,
			"message": fmt.Sprintf("最近 %d 分钟内暂无待分析的舆情资讯", analyzeWindowMinutes),
		}, nil
	}
	news := make([]llm.NewsItem, 0, len(rows))
	ids := make([]int64, 0, len(rows))
	for _, r := range rows {
		content := ""
		if r.Content != nil {
			content = *r.Content
		}
		if len(content) > 800 {
			content = content[:800]
		}
		pub := ""
		if r.PubTime != nil {
			pub = r.PubTime.Format("2006-01-02 %H:%M")
		}
		news = append(news, llm.NewsItem{Source: r.Source, Title: r.Title, Content: content, PubTime: pub})
		ids = append(ids, r.NewsID)
	}
	client := llm.NewClient()
	apiKey := crypto.DecryptCredential(model.APIKey.String, s.cfg.CredentialEncryptionKey, s.cfg.JWTSecret)
	temp := 0.2
	if model.Temperature.Valid {
		temp = model.Temperature.Float64
	}
	resp := client.Analyze(ctx, model.BaseURL.String, apiKey, model.ModelCode.String, news, temp)
	modelName := model.ModelCode.String
	if resp.Code == 429 {
		return map[string]interface{}{
			"analyzed": 0, "analysisId": nil, "rateLimited": true,
			"retryAfter": resp.RetryAfter, "message": "AI 分析触发限流，请稍后再试",
		}, nil
	}
	analysisID, err := s.persistAnalysis(ctx, ids, modelName, resp)
	if err != nil {
		return nil, err
	}
	if resp.OK {
		return map[string]interface{}{"analyzed": len(ids), "analysisId": analysisID, "message": "分析成功"}, nil
	}
	return map[string]interface{}{
		"analyzed": 0, "analysisId": analysisID,
		"message": "分析失败: " + resp.Error,
	}, nil
}

func (s *Store) listUnanalyzedNews(ctx context.Context, limit int, windowMinutes int) ([]NewsRow, error) {
	rows, err := s.db.QueryContext(ctx, `
SELECT news_id, source, title, content, url, pub_time, uniq_hash, analyzed, create_time
FROM sentiment_news
WHERE analyzed = '0' AND create_time >= DATE_SUB(NOW(), INTERVAL ? MINUTE)
ORDER BY pub_time DESC LIMIT ?`, windowMinutes, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := make([]NewsRow, 0, limit)
	for rows.Next() {
		var r NewsRow
		if err := rows.Scan(&r.NewsID, &r.Source, &r.Title, &r.Content, &r.URL, &r.PubTime, &r.UniqHash, &r.Analyzed, &r.CreateTime); err != nil {
			return nil, err
		}
		out = append(out, r)
	}
	return out, rows.Err()
}

func (s *Store) persistAnalysis(ctx context.Context, newsIDs []int64, modelName string, resp llm.AnalyzeResponse) (int64, error) {
	status := "1"
	var summary, usDir, hkDir, aDir, usReason, hkReason, aReason, risk sql.NullString
	var usScore, hkScore, aScore sql.NullFloat64
	var errMsg sql.NullString
	if resp.OK && resp.Result != nil {
		status = "0"
		summary = sql.NullString{String: resp.Result.Summary, Valid: resp.Result.Summary != ""}
		usDir = sql.NullString{String: resp.Result.US.Direction, Valid: true}
		hkDir = sql.NullString{String: resp.Result.HK.Direction, Valid: true}
		aDir = sql.NullString{String: resp.Result.A.Direction, Valid: true}
		usScore = sql.NullFloat64{Float64: resp.Result.US.Score, Valid: true}
		hkScore = sql.NullFloat64{Float64: resp.Result.HK.Score, Valid: true}
		aScore = sql.NullFloat64{Float64: resp.Result.A.Score, Valid: true}
		usReason = sql.NullString{String: resp.Result.US.Reason, Valid: true}
		hkReason = sql.NullString{String: resp.Result.HK.Reason, Valid: true}
		aReason = sql.NullString{String: resp.Result.A.Reason, Valid: true}
		risk = sql.NullString{String: resp.Result.RiskEvents, Valid: true}
	} else {
		errMsg = sql.NullString{String: strings.TrimSpace(resp.Error), Valid: resp.Error != ""}
	}
	idParts := make([]string, len(newsIDs))
	for i, id := range newsIDs {
		idParts[i] = fmt.Sprintf("%d", id)
	}
	res, err := s.db.ExecContext(ctx, `
INSERT INTO sentiment_analysis
(news_count, news_ids, summary, us_direction, us_score, us_reason, hk_direction, hk_score, hk_reason,
 a_direction, a_score, a_reason, risk_events, model_name, status, error_msg, create_time)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
		len(newsIDs), strings.Join(idParts, ","), summary, usDir, usScore, usReason,
		hkDir, hkScore, hkReason, aDir, aScore, aReason, risk, modelName, status, errMsg, timeutil.NowBeijing())
	if err != nil {
		return 0, err
	}
	analysisID, _ := res.LastInsertId()
	if resp.OK {
		for _, id := range newsIDs {
			_, _ = s.db.ExecContext(ctx, `UPDATE sentiment_news SET analyzed='1' WHERE news_id=?`, id)
		}
	}
	return analysisID, nil
}
