package store

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"strings"
	"time"

	"github.com/google/uuid"

	"github.com/lusd2904/smart-finance-platform/services/sfp-intel/internal/crypto"
	"github.com/lusd2904/smart-finance-platform/services/sfp-intel/internal/timeutil"
)

type ChatConfig struct {
	ChatConfigID          int64
	UserID                int64
	Temperature           *float64
	AddHistoryToContext   string
	NumHistoryRuns        int
	SystemPrompt          *string
	MetricsDefaultVisible string
	VisionEnabled         string
	ImageMaxSizeMB        *int
	CreateTime            *time.Time
	UpdateTime            *time.Time
}

type ChatSessionSummary struct {
	SessionID    string
	SessionTitle string
	UserID       int64
	CreatedAt    time.Time
	UpdatedAt    time.Time
}

type ChatMessageRow struct {
	ID               string
	Role             string
	Content          string
	ReasoningContent string
	Images           []string
	Metrics          map[string]interface{}
	FromHistory      bool
	CreatedAt        time.Time
}

type ChatSessionDetail struct {
	Summary   ChatSessionSummary
	AgentData map[string]interface{}
	SessionData map[string]interface{}
	Messages  []ChatMessageRow
}

func (s *Store) EnsureChatSchema(ctx context.Context) error {
	stmts := []string{
		`CREATE TABLE IF NOT EXISTS sfp_chat_session (
  session_id VARCHAR(64) NOT NULL,
  user_id BIGINT NOT NULL,
  title VARCHAR(200) NULL,
  agent_data JSON NULL,
  session_data JSON NULL,
  created_at DATETIME NULL,
  updated_at DATETIME NULL,
  PRIMARY KEY (session_id),
  KEY ix_sfp_chat_session_user (user_id, updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4`,
		`CREATE TABLE IF NOT EXISTS sfp_chat_message (
  message_id VARCHAR(64) NOT NULL,
  session_id VARCHAR(64) NOT NULL,
  role VARCHAR(32) NOT NULL,
  content MEDIUMTEXT NULL,
  reasoning_content MEDIUMTEXT NULL,
  images JSON NULL,
  metrics JSON NULL,
  from_history TINYINT NOT NULL DEFAULT 0,
  created_at DATETIME NULL,
  PRIMARY KEY (message_id),
  KEY ix_sfp_chat_message_session (session_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4`,
	}
	for _, stmt := range stmts {
		if _, err := s.db.ExecContext(ctx, stmt); err != nil {
			return fmt.Errorf("chat schema: %w", err)
		}
	}
	return nil
}

func (s *Store) GetChatConfig(ctx context.Context, userID int64) (*ChatConfig, error) {
	row := s.db.QueryRowContext(ctx, `
SELECT chat_config_id, user_id, temperature, add_history_to_context, num_history_runs,
       system_prompt, metrics_default_visible, vision_enabled, image_max_size_mb, create_time, update_time
FROM ai_chat_config WHERE user_id = ?`, userID)
	var cfg ChatConfig
	var temp sql.NullFloat64
	var addHist, metricsVis, vision sql.NullString
	var numHist sql.NullInt64
	var sysPrompt sql.NullString
	var imgMax sql.NullInt64
	var createTime, updateTime sql.NullTime
	err := row.Scan(&cfg.ChatConfigID, &cfg.UserID, &temp, &addHist, &numHist, &sysPrompt,
		&metricsVis, &vision, &imgMax, &createTime, &updateTime)
	if err == sql.ErrNoRows {
		return defaultChatConfig(userID), nil
	}
	if err != nil {
		return nil, err
	}
	if temp.Valid {
		v := temp.Float64
		cfg.Temperature = &v
	}
	if addHist.Valid {
		cfg.AddHistoryToContext = addHist.String
	} else {
		cfg.AddHistoryToContext = "0"
	}
	if numHist.Valid {
		cfg.NumHistoryRuns = int(numHist.Int64)
	} else {
		cfg.NumHistoryRuns = 3
	}
	if sysPrompt.Valid {
		v := sysPrompt.String
		cfg.SystemPrompt = &v
	}
	if metricsVis.Valid {
		cfg.MetricsDefaultVisible = metricsVis.String
	} else {
		cfg.MetricsDefaultVisible = "0"
	}
	if vision.Valid {
		cfg.VisionEnabled = vision.String
	} else {
		cfg.VisionEnabled = "1"
	}
	if imgMax.Valid {
		v := int(imgMax.Int64)
		cfg.ImageMaxSizeMB = &v
	}
	if createTime.Valid {
		t := createTime.Time
		cfg.CreateTime = &t
	}
	if updateTime.Valid {
		t := updateTime.Time
		cfg.UpdateTime = &t
	}
	return &cfg, nil
}

func defaultChatConfig(userID int64) *ChatConfig {
	return &ChatConfig{
		UserID: userID, AddHistoryToContext: "0", NumHistoryRuns: 3,
		MetricsDefaultVisible: "0", VisionEnabled: "1",
	}
}

func (s *Store) SaveChatConfig(ctx context.Context, userID int64, body map[string]interface{}) error {
	existing, err := s.GetChatConfig(ctx, userID)
	if err != nil {
		return err
	}
	now := timeutil.NowBeijing()
	temp := existing.Temperature
	if v, ok := body["temperature"].(float64); ok {
		temp = &v
	}
	addHist := strField(body, "addHistoryToContext", existing.AddHistoryToContext)
	numHist := intField(body, "numHistoryRuns", existing.NumHistoryRuns)
	sysPrompt := strField(body, "systemPrompt", strPtr(existing.SystemPrompt))
	metricsVis := strField(body, "metricsDefaultVisible", existing.MetricsDefaultVisible)
	vision := strField(body, "visionEnabled", existing.VisionEnabled)
	imgMax := intField(body, "imageMaxSizeMb", intPtr(existing.ImageMaxSizeMB))

	if existing.ChatConfigID > 0 {
		_, err = s.db.ExecContext(ctx, `
UPDATE ai_chat_config SET temperature=?, add_history_to_context=?, num_history_runs=?,
  system_prompt=?, metrics_default_visible=?, vision_enabled=?, image_max_size_mb=?, update_time=?
WHERE user_id=?`, nullFloat(temp), addHist, numHist, nullStr(sysPrompt), metricsVis, vision, nullInt(imgMax), now, userID)
		return err
	}
	_, err = s.db.ExecContext(ctx, `
INSERT INTO ai_chat_config (user_id, temperature, add_history_to_context, num_history_runs,
  system_prompt, metrics_default_visible, vision_enabled, image_max_size_mb, create_time, update_time)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
		userID, nullFloat(temp), addHist, numHist, nullStr(sysPrompt), metricsVis, vision, nullInt(imgMax), now, now)
	return err
}

func (s *Store) ListChatSessions(ctx context.Context, userID int64) ([]ChatSessionSummary, error) {
	rows, err := s.db.QueryContext(ctx, `
SELECT session_id, title, user_id, created_at, updated_at
FROM sfp_chat_session WHERE user_id = ? ORDER BY updated_at DESC`, userID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := make([]ChatSessionSummary, 0)
	for rows.Next() {
		var item ChatSessionSummary
		var title sql.NullString
		var created, updated sql.NullTime
		if err := rows.Scan(&item.SessionID, &title, &item.UserID, &created, &updated); err != nil {
			return nil, err
		}
		if title.Valid {
			item.SessionTitle = title.String
		}
		if created.Valid {
			item.CreatedAt = created.Time
		}
		if updated.Valid {
			item.UpdatedAt = updated.Time
		}
		out = append(out, item)
	}
	return out, rows.Err()
}

func (s *Store) GetChatSession(ctx context.Context, sessionID string, userID int64) (*ChatSessionDetail, error) {
	row := s.db.QueryRowContext(ctx, `
SELECT session_id, title, user_id, agent_data, session_data, created_at, updated_at
FROM sfp_chat_session WHERE session_id = ?`, sessionID)
	var summary ChatSessionSummary
	var title sql.NullString
	var agentRaw, sessionRaw sql.NullString
	var created, updated sql.NullTime
	if err := row.Scan(&summary.SessionID, &title, &summary.UserID, &agentRaw, &sessionRaw, &created, &updated); err != nil {
		if err == sql.ErrNoRows {
			return nil, fmt.Errorf("会话不存在")
		}
		return nil, err
	}
	if userID > 0 && summary.UserID != userID {
		return nil, fmt.Errorf("会话不存在")
	}
	if title.Valid {
		summary.SessionTitle = title.String
	}
	if created.Valid {
		summary.CreatedAt = created.Time
	}
	if updated.Valid {
		summary.UpdatedAt = updated.Time
	}
	detail := &ChatSessionDetail{Summary: summary}
	if agentRaw.Valid && agentRaw.String != "" {
		_ = json.Unmarshal([]byte(agentRaw.String), &detail.AgentData)
	}
	if sessionRaw.Valid && sessionRaw.String != "" {
		_ = json.Unmarshal([]byte(sessionRaw.String), &detail.SessionData)
	}
	msgs, err := s.listChatMessages(ctx, sessionID)
	if err != nil {
		return nil, err
	}
	detail.Messages = msgs
	return detail, nil
}

func (s *Store) listChatMessages(ctx context.Context, sessionID string) ([]ChatMessageRow, error) {
	rows, err := s.db.QueryContext(ctx, `
SELECT message_id, role, content, reasoning_content, images, metrics, from_history, created_at
FROM sfp_chat_message WHERE session_id = ? ORDER BY created_at ASC`, sessionID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := make([]ChatMessageRow, 0)
	for rows.Next() {
		var m ChatMessageRow
		var content, reasoning sql.NullString
		var imagesRaw, metricsRaw sql.NullString
		var fromHist int
		var created sql.NullTime
		if err := rows.Scan(&m.ID, &m.Role, &content, &reasoning, &imagesRaw, &metricsRaw, &fromHist, &created); err != nil {
			return nil, err
		}
		if content.Valid {
			m.Content = content.String
		}
		if reasoning.Valid {
			m.ReasoningContent = reasoning.String
		}
		if imagesRaw.Valid && imagesRaw.String != "" {
			_ = json.Unmarshal([]byte(imagesRaw.String), &m.Images)
		}
		if metricsRaw.Valid && metricsRaw.String != "" {
			_ = json.Unmarshal([]byte(metricsRaw.String), &m.Metrics)
		}
		m.FromHistory = fromHist != 0
		if created.Valid {
			m.CreatedAt = created.Time
		}
		out = append(out, m)
	}
	return out, rows.Err()
}

func (s *Store) DeleteChatSession(ctx context.Context, sessionID string) error {
	tx, err := s.db.BeginTx(ctx, nil)
	if err != nil {
		return err
	}
	defer func() { _ = tx.Rollback() }()
	res, err := tx.ExecContext(ctx, "DELETE FROM sfp_chat_session WHERE session_id = ?", sessionID)
	if err != nil {
		return err
	}
	n, _ := res.RowsAffected()
	if n == 0 {
		return fmt.Errorf("删除会话失败")
	}
	if _, err := tx.ExecContext(ctx, "DELETE FROM sfp_chat_message WHERE session_id = ?", sessionID); err != nil {
		return err
	}
	return tx.Commit()
}

func (s *Store) EnsureChatSession(ctx context.Context, sessionID string, userID int64, title string) error {
	now := timeutil.NowBeijing()
	_, err := s.db.ExecContext(ctx, `
INSERT INTO sfp_chat_session (session_id, user_id, title, created_at, updated_at)
VALUES (?, ?, ?, ?, ?)
ON DUPLICATE KEY UPDATE updated_at = VALUES(updated_at)`, sessionID, userID, truncateStr(title, 200), now, now)
	return err
}

func (s *Store) TouchChatSession(ctx context.Context, sessionID, title string, agentData map[string]interface{}) error {
	now := timeutil.NowBeijing()
	agentJSON, _ := json.Marshal(agentData)
	_, err := s.db.ExecContext(ctx, `
UPDATE sfp_chat_session SET updated_at=?, title=COALESCE(NULLIF(?, ''), title), agent_data=?
WHERE session_id=?`, now, truncateStr(title, 200), string(agentJSON), sessionID)
	return err
}

func (s *Store) AddChatMessage(ctx context.Context, sessionID, role, content, reasoning string, images []string, metrics map[string]interface{}, fromHistory bool) (string, error) {
	id := strings.ReplaceAll(uuid.NewString(), "-", "")
	now := timeutil.NowBeijing()
	imgJSON, _ := json.Marshal(images)
	metricsJSON, _ := json.Marshal(metrics)
	fromHist := 0
	if fromHistory {
		fromHist = 1
	}
	_, err := s.db.ExecContext(ctx, `
INSERT INTO sfp_chat_message (message_id, session_id, role, content, reasoning_content, images, metrics, from_history, created_at)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
		id, sessionID, role, content, nullStr(reasoning), string(imgJSON), string(metricsJSON), fromHist, now)
	return id, err
}

func (s *Store) ChatHistoryMessages(ctx context.Context, sessionID string, maxRuns int) ([]ChatMessageRow, error) {
	if maxRuns <= 0 {
		maxRuns = 3
	}
	limit := maxRuns * 2
	rows, err := s.db.QueryContext(ctx, `
SELECT message_id, role, content, reasoning_content, images, metrics, from_history, created_at
FROM sfp_chat_message WHERE session_id = ? ORDER BY created_at DESC LIMIT ?`, sessionID, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	tmp := make([]ChatMessageRow, 0, limit)
	for rows.Next() {
		var m ChatMessageRow
		var content, reasoning sql.NullString
		var imagesRaw, metricsRaw sql.NullString
		var fromHist int
		var created sql.NullTime
		if err := rows.Scan(&m.ID, &m.Role, &content, &reasoning, &imagesRaw, &metricsRaw, &fromHist, &created); err != nil {
			return nil, err
		}
		if content.Valid {
			m.Content = content.String
		}
		if reasoning.Valid {
			m.ReasoningContent = reasoning.String
		}
		if imagesRaw.Valid && imagesRaw.String != "" {
			_ = json.Unmarshal([]byte(imagesRaw.String), &m.Images)
		}
		if metricsRaw.Valid && metricsRaw.String != "" {
			_ = json.Unmarshal([]byte(metricsRaw.String), &m.Metrics)
		}
		m.FromHistory = fromHist != 0
		if created.Valid {
			m.CreatedAt = created.Time
		}
		tmp = append(tmp, m)
	}
	for i, j := 0, len(tmp)-1; i < j; i, j = i+1, j-1 {
		tmp[i], tmp[j] = tmp[j], tmp[i]
	}
	return tmp, rows.Err()
}

func (s *Store) ResolveChatModel(ctx context.Context, modelID int64) (*AiModelDetail, error) {
	row := s.db.QueryRowContext(ctx, `
SELECT model_id, model_code, model_name, provider, model_sort, scope, api_key, base_url,
       model_type, max_tokens, temperature, support_reasoning, support_images, status,
       user_id, dept_id, create_by, create_time, update_by, update_time, remark
FROM ai_models WHERE model_id = ?`, modelID)
	detail, err := scanAiModelRow(row)
	if err == sql.ErrNoRows {
		return nil, fmt.Errorf("模型不存在")
	}
	if err != nil {
		return nil, err
	}
	detail.APIKey = crypto.DecryptCredential(detail.APIKeyEnc, s.cfg.CredentialEncryptionKey, s.cfg.JWTSecret)
	return detail, nil
}

func (s *Store) ResolveChatModelByScope(ctx context.Context, scope string) (*AiModelDetail, error) {
	rows, err := s.db.QueryContext(ctx, `
SELECT model_id, model_code, model_name, provider, model_sort, scope, api_key, base_url,
       model_type, max_tokens, temperature, support_reasoning, support_images, status,
       user_id, dept_id, create_by, create_time, update_by, update_time, remark
FROM ai_models WHERE status='0' ORDER BY model_sort, model_id`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var complete []AiModelDetail
	for rows.Next() {
		d, err := scanAiModelRows(rows)
		if err != nil {
			return nil, err
		}
		if d.BaseURL != "" && d.APIKeyEnc != "" && d.ModelCode != "" {
			complete = append(complete, *d)
		}
	}
	if len(complete) == 0 {
		return nil, fmt.Errorf("未配置大模型连接")
	}
	scopes := []string{scope, "global", "chat"}
	for _, sc := range scopes {
		for i := range complete {
			if complete[i].Scope == sc {
				copy := complete[i]
				copy.APIKey = crypto.DecryptCredential(copy.APIKeyEnc, s.cfg.CredentialEncryptionKey, s.cfg.JWTSecret)
				return &copy, nil
			}
		}
	}
	copy := complete[0]
	copy.APIKey = crypto.DecryptCredential(copy.APIKeyEnc, s.cfg.CredentialEncryptionKey, s.cfg.JWTSecret)
	return &copy, nil
}

func FormatChatConfig(cfg *ChatConfig) map[string]interface{} {
	out := map[string]interface{}{
		"userId": cfg.UserID, "addHistoryToContext": cfg.AddHistoryToContext,
		"numHistoryRuns": cfg.NumHistoryRuns, "metricsDefaultVisible": cfg.MetricsDefaultVisible,
		"visionEnabled": cfg.VisionEnabled,
	}
	if cfg.ChatConfigID > 0 {
		out["chatConfigId"] = cfg.ChatConfigID
	}
	if cfg.Temperature != nil {
		out["temperature"] = *cfg.Temperature
	}
	if cfg.SystemPrompt != nil {
		out["systemPrompt"] = *cfg.SystemPrompt
	}
	if cfg.ImageMaxSizeMB != nil {
		out["imageMaxSizeMb"] = *cfg.ImageMaxSizeMB
	}
	if cfg.CreateTime != nil {
		out["createTime"] = timeutil.FormatBeijing(*cfg.CreateTime)
	}
	if cfg.UpdateTime != nil {
		out["updateTime"] = timeutil.FormatBeijing(*cfg.UpdateTime)
	}
	return out
}

func FormatChatSessionSummary(s ChatSessionSummary) map[string]interface{} {
	title := s.SessionTitle
	if title == "" {
		title = "新会话"
	}
	return map[string]interface{}{
		"sessionId": s.SessionID, "sessionTitle": title,
		"userId": fmt.Sprintf("%d", s.UserID),
		"createdAt": timeutil.FormatBeijing(s.CreatedAt),
		"updatedAt": timeutil.FormatBeijing(s.UpdatedAt),
	}
}

func FormatChatSessionDetail(d *ChatSessionDetail) map[string]interface{} {
	out := FormatChatSessionSummary(d.Summary)
	out["agentId"] = "chat-agent"
	if d.AgentData != nil {
		out["agentData"] = d.AgentData
	} else {
		out["agentData"] = map[string]interface{}{"agentId": "chat-agent"}
	}
	if d.SessionData != nil {
		out["sessionData"] = d.SessionData
	} else {
		out["sessionData"] = map[string]interface{}{}
	}
	msgs := make([]map[string]interface{}, 0, len(d.Messages))
	for _, m := range d.Messages {
		item := map[string]interface{}{
			"id": m.ID, "role": m.Role, "content": m.Content,
			"fromHistory": m.FromHistory,
		}
		if m.ReasoningContent != "" {
			item["reasoningContent"] = m.ReasoningContent
		}
		if len(m.Images) > 0 {
			item["images"] = m.Images
		}
		if m.Metrics != nil {
			item["metrics"] = m.Metrics
		}
		if !m.CreatedAt.IsZero() {
			item["createdAt"] = timeutil.FormatBeijing(m.CreatedAt)
		}
		msgs = append(msgs, item)
	}
	out["messages"] = msgs
	return out
}

func truncateStr(s string, n int) string {
	if len(s) <= n {
		return s
	}
	return s[:n]
}

func strField(m map[string]interface{}, key, fallback string) string {
	if v, ok := m[key].(string); ok && v != "" {
		return v
	}
	return fallback
}

func intField(m map[string]interface{}, key string, fallback int) int {
	switch v := m[key].(type) {
	case float64:
		return int(v)
	case int:
		return v
	default:
		return fallback
	}
}

func strPtr(p *string) string {
	if p == nil {
		return ""
	}
	return *p
}

func intPtr(p *int) int {
	if p == nil {
		return 0
	}
	return *p
}

func nullStr(s string) interface{} {
	if s == "" {
		return nil
	}
	return s
}

func nullFloat(p *float64) interface{} {
	if p == nil {
		return nil
	}
	return *p
}

func nullInt(n int) interface{} {
	if n == 0 {
		return nil
	}
	return n
}
