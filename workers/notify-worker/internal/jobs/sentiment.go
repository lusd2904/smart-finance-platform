package jobs

import (
	"context"
	"database/sql"
	"fmt"
	"strings"

	"github.com/lusd2904/smart-finance-platform/workers/notify-worker/internal/crypto"
	"github.com/lusd2904/smart-finance-platform/workers/notify-worker/internal/llm"
)

const (
	analyzeWindowMinutes = 10
	maxNewsSafetyCap     = 200
)

type unanalyzedNews struct {
	NewsID  int64
	Source  string
	Title   string
	Content string
	PubTime string
}

type aiModelRow struct {
	ModelID     int64
	BaseURL     string
	APIKey      string
	ModelCode   string
	Temperature float64
	Scope       string
}

func (s *Service) RunSentimentCollect(ctx context.Context, payload map[string]interface{}) (map[string]interface{}, error) {
	pending, err := s.countPendingSentimentNews(ctx, analyzeWindowMinutes)
	if err != nil {
		return nil, err
	}
	result := map[string]interface{}{
		"fetched": pending,
		"saved":   0,
		"message": fmt.Sprintf("RSS 采集未迁移；当前依赖 X-monitor ingest。最近 %d 分钟待分析 %d 条。", analyzeWindowMinutes, pending),
	}
	if !boolFrom(payload["analyze"], false) {
		return result, nil
	}
	autoAnalyze, err := s.sentimentAutoAnalyze(ctx)
	if err != nil {
		return nil, err
	}
	if autoAnalyze != "1" {
		result["analyzed"] = 0
		result["analysisId"] = nil
		result["message"] = "自动分析未开启"
		return result, nil
	}
	analyzeResult, err := s.RunSentimentAnalyze(ctx)
	if err != nil {
		result["analyzeError"] = err.Error()
		return result, nil
	}
	for k, v := range analyzeResult {
		result[k] = v
	}
	return result, nil
}

func (s *Service) countPendingSentimentNews(ctx context.Context, windowMinutes int) (int, error) {
	var count int
	err := s.db.QueryRowContext(ctx, `
SELECT COUNT(*) FROM sentiment_news
WHERE analyzed = '0' AND pub_time >= DATE_SUB(NOW(), INTERVAL ? MINUTE)`, windowMinutes).Scan(&count)
	return count, err
}

func (s *Service) RunSentimentAnalyze(ctx context.Context) (map[string]interface{}, error) {
	candidates, err := s.listSentimentModels(ctx)
	if err != nil {
		return nil, err
	}
	if len(candidates) == 0 {
		return nil, fmt.Errorf("请先在AI配置中填写Base URL、API Key与模型名称")
	}
	maxNews, err := s.sentimentMaxNews(ctx)
	if err != nil {
		return nil, err
	}
	limit := maxNews
	if limit <= 0 || limit > maxNewsSafetyCap {
		limit = maxNewsSafetyCap
	}
	newsRows, err := s.listUnanalyzedNews(ctx, limit, analyzeWindowMinutes)
	if err != nil {
		return nil, err
	}
	if len(newsRows) == 0 {
		return map[string]interface{}{
			"analyzed": 0, "analysisId": nil,
			"message": fmt.Sprintf("最近 %d 分钟内暂无待分析的舆情资讯", analyzeWindowMinutes),
		}, nil
	}
	llmNews := make([]llm.NewsItem, 0, len(newsRows))
	newsIDs := make([]int64, 0, len(newsRows))
	for _, row := range newsRows {
		newsIDs = append(newsIDs, row.NewsID)
		llmNews = append(llmNews, llm.NewsItem{
			Source: row.Source, Title: row.Title, Content: row.Content, PubTime: row.PubTime,
		})
	}
	var aiResult llm.AnalyzeResponse
	usedModel := ""
	for _, model := range candidates {
		if model.BaseURL == "" || model.APIKey == "" || model.ModelCode == "" {
			continue
		}
		temp := model.Temperature
		if temp <= 0 {
			temp = 0.2
		}
		aiResult = s.llm.Analyze(ctx, model.BaseURL, model.APIKey, model.ModelCode, llmNews, temp)
		usedModel = model.ModelCode
		if aiResult.OK {
			break
		}
		if aiResult.Code == 429 {
			break
		}
		if !llm.GatewayFailoverCodes[aiResult.Code] {
			break
		}
	}
	if usedModel == "" {
		return nil, fmt.Errorf("未找到可用的 AI 模型配置")
	}
	if aiResult.Code == 429 {
		return map[string]interface{}{
			"analyzed": 0, "analysisId": nil, "rateLimited": true,
			"retryAfter": aiResult.RetryAfter,
			"message":    "AI 分析触发限流，请稍后再试，不要连续点击",
		}, nil
	}
	analysisID, err := s.persistAnalysis(ctx, newsIDs, usedModel, aiResult)
	if err != nil {
		return nil, err
	}
	if aiResult.OK {
		return map[string]interface{}{
			"analyzed": len(newsIDs), "analysisId": analysisID, "message": "分析成功",
		}, nil
	}
	return map[string]interface{}{
		"analyzed": 0, "analysisId": analysisID,
		"message": fmt.Sprintf("分析失败: %s", aiResult.Error),
	}, nil
}

func (s *Service) sentimentAutoAnalyze(ctx context.Context) (string, error) {
	var auto sql.NullString
	err := s.db.QueryRowContext(ctx, `
SELECT auto_analyze FROM sentiment_ai_config ORDER BY config_id LIMIT 1`).Scan(&auto)
	if err == sql.ErrNoRows {
		return "1", nil
	}
	if err != nil {
		return "", err
	}
	if auto.Valid {
		return auto.String, nil
	}
	return "1", nil
}

func (s *Service) sentimentMaxNews(ctx context.Context) (int, error) {
	var maxNews sql.NullInt64
	err := s.db.QueryRowContext(ctx, `
SELECT max_news_per_round FROM sentiment_ai_config ORDER BY config_id LIMIT 1`).Scan(&maxNews)
	if err == sql.ErrNoRows {
		return maxNewsSafetyCap, nil
	}
	if err != nil {
		return 0, err
	}
	if maxNews.Valid {
		return int(maxNews.Int64), nil
	}
	return maxNewsSafetyCap, nil
}

func (s *Service) listUnanalyzedNews(ctx context.Context, limit int, windowMinutes int) ([]unanalyzedNews, error) {
	rows, err := s.db.QueryContext(ctx, `
SELECT news_id, source, title, COALESCE(content, ''), pub_time
FROM sentiment_news
WHERE analyzed = '0' AND pub_time >= DATE_SUB(NOW(), INTERVAL ? MINUTE)
ORDER BY pub_time DESC LIMIT ?`, windowMinutes, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := make([]unanalyzedNews, 0, limit)
	for rows.Next() {
		var row unanalyzedNews
		var pub sql.NullTime
		var content string
		if err := rows.Scan(&row.NewsID, &row.Source, &row.Title, &content, &pub); err != nil {
			return nil, err
		}
		if len(content) > 800 {
			content = content[:800]
		}
		row.Content = content
		if pub.Valid {
			row.PubTime = formatBeijing(pub.Time)
		}
		out = append(out, row)
	}
	return out, rows.Err()
}

func (s *Service) listSentimentModels(ctx context.Context) ([]aiModelRow, error) {
	rows, err := s.db.QueryContext(ctx, `
SELECT model_id, base_url, api_key, model_code, temperature, scope
FROM ai_models WHERE status = '0' ORDER BY model_sort, model_id`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	complete := make([]aiModelRow, 0)
	for rows.Next() {
		var r aiModelRow
		var baseURL, apiKey, modelCode, scope sql.NullString
		var temp sql.NullFloat64
		if err := rows.Scan(&r.ModelID, &baseURL, &apiKey, &modelCode, &temp, &scope); err != nil {
			return nil, err
		}
		r.BaseURL = strings.TrimSpace(baseURL.String)
		r.APIKey = crypto.DecryptCredential(strings.TrimSpace(apiKey.String), s.cfg.CredentialKey, s.cfg.JWTSecret)
		r.ModelCode = strings.TrimSpace(modelCode.String)
		if temp.Valid {
			r.Temperature = temp.Float64
		}
		r.Scope = scope.String
		if r.BaseURL != "" && r.APIKey != "" && r.ModelCode != "" {
			complete = append(complete, r)
		}
	}
	if len(complete) == 0 {
		return nil, nil
	}
	return orderSentimentModels(complete), nil
}

func orderSentimentModels(models []aiModelRow) []aiModelRow {
	scored := make([]struct {
		row   aiModelRow
		score int
	}, len(models))
	preferredCodes := []string{"grok-4.6", "x-ai/grok-4.6"}
	scopeRank := map[string]int{"sentiment": 30, "global": 20, "chat": 10}
	for i, m := range models {
		score := scopeRank[m.Scope]
		for j, code := range preferredCodes {
			if m.ModelCode == code {
				score += 50 - j
			}
		}
		scored[i] = struct {
			row   aiModelRow
			score int
		}{row: m, score: score}
	}
	for i := 0; i < len(scored); i++ {
		for j := i + 1; j < len(scored); j++ {
			if scored[j].score > scored[i].score {
				scored[i], scored[j] = scored[j], scored[i]
			}
		}
	}
	out := make([]aiModelRow, len(scored))
	for i, s := range scored {
		out[i] = s.row
	}
	return out
}

func (s *Service) persistAnalysis(ctx context.Context, newsIDs []int64, modelName string, aiResult llm.AnalyzeResponse) (int64, error) {
	ids := make([]string, 0, len(newsIDs))
	for _, id := range newsIDs {
		ids = append(ids, fmt.Sprintf("%d", id))
	}
	now := nowBeijing()
	status := "1"
	var summary, usDir, usReason, hkDir, hkReason, aDir, aReason, riskEvents, errMsg sql.NullString
	var usScore, hkScore, aScore sql.NullFloat64
	raw := aiResult.Raw
	if aiResult.OK && aiResult.Result != nil {
		status = "0"
		r := aiResult.Result
		summary = sql.NullString{String: r.Summary, Valid: r.Summary != ""}
		usDir = sql.NullString{String: r.US.Direction, Valid: r.US.Direction != ""}
		usReason = sql.NullString{String: r.US.Reason, Valid: r.US.Reason != ""}
		usScore = sql.NullFloat64{Float64: r.US.Score, Valid: true}
		hkDir = sql.NullString{String: r.HK.Direction, Valid: r.HK.Direction != ""}
		hkReason = sql.NullString{String: r.HK.Reason, Valid: r.HK.Reason != ""}
		hkScore = sql.NullFloat64{Float64: r.HK.Score, Valid: true}
		aDir = sql.NullString{String: r.A.Direction, Valid: r.A.Direction != ""}
		aReason = sql.NullString{String: r.A.Reason, Valid: r.A.Reason != ""}
		aScore = sql.NullFloat64{Float64: r.A.Score, Valid: true}
		riskEvents = sql.NullString{String: r.RiskEvents, Valid: r.RiskEvents != ""}
	} else {
		msg := aiResult.Error
		if len(msg) > 2000 {
			msg = msg[:2000]
		}
		errMsg = sql.NullString{String: msg, Valid: msg != ""}
	}
	res, err := s.db.ExecContext(ctx, `
INSERT INTO sentiment_analysis (
  news_count, news_ids, summary, us_direction, us_score, us_reason,
  hk_direction, hk_score, hk_reason, a_direction, a_score, a_reason,
  risk_events, model_name, status, error_msg, raw_response, create_time
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
		len(newsIDs), strings.Join(ids, ","), summary, usDir, usScore, usReason,
		hkDir, hkScore, hkReason, aDir, aScore, aReason, riskEvents, modelName, status, errMsg, raw, now,
	)
	if err != nil {
		return 0, err
	}
	analysisID, _ := res.LastInsertId()
	if aiResult.OK && len(newsIDs) > 0 {
		if err := s.markNewsAnalyzed(ctx, newsIDs); err != nil {
			return analysisID, err
		}
	}
	return analysisID, nil
}

func (s *Service) markNewsAnalyzed(ctx context.Context, newsIDs []int64) error {
	if len(newsIDs) == 0 {
		return nil
	}
	placeholders := strings.Repeat("?,", len(newsIDs))
	placeholders = placeholders[:len(placeholders)-1]
	args := make([]interface{}, len(newsIDs))
	for i, id := range newsIDs {
		args[i] = id
	}
	_, err := s.db.ExecContext(ctx, "UPDATE sentiment_news SET analyzed='1' WHERE news_id IN ("+placeholders+")", args...)
	return err
}
