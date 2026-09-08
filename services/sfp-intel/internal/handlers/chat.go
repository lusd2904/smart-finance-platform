package handlers

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"strings"
	"time"

	"github.com/golang-jwt/jwt/v5"
	"github.com/google/uuid"

	"github.com/lusd2904/smart-finance-platform/services/sfp-intel/internal/auth"
	"github.com/lusd2904/smart-finance-platform/services/sfp-intel/internal/crypto"
	"github.com/lusd2904/smart-finance-platform/services/sfp-intel/internal/llm"
	"github.com/lusd2904/smart-finance-platform/services/sfp-intel/internal/response"
	"github.com/lusd2904/smart-finance-platform/services/sfp-intel/internal/store"
)

const openAudience = "open-api"

func (s *Server) ChatSend(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.NotFound(w, r)
		return
	}
	user := auth.UserFrom(r.Context())
	if user == nil {
		response.Unauthorized(w, "用户未登录，请先完成登录")
		return
	}
	var req struct {
		SessionID   string   `json:"sessionId"`
		ModelID     int64    `json:"modelId"`
		Message     string   `json:"message"`
		IsReasoning *bool    `json:"isReasoning"`
		Images      []string `json:"images"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		response.Error(w, "invalid json")
		return
	}
	if req.ModelID <= 0 || strings.TrimSpace(req.Message) == "" {
		response.Error(w, "模型与消息不能为空")
		return
	}
	ctx := r.Context()
	model, err := s.Store.ResolveChatModel(ctx, req.ModelID)
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	userCfg, err := s.Store.GetChatConfig(ctx, user.UserID)
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	sessionID := strings.TrimSpace(req.SessionID)
	if sessionID == "" {
		sessionID = strings.ReplaceAll(uuid.NewString(), "-", "")
	}
	title := req.Message
	if len(title) > 20 {
		title = title[:20] + "..."
	}
	if err := s.Store.EnsureChatSession(ctx, sessionID, user.UserID, title); err != nil {
		response.Error(w, err.Error())
		return
	}
	_, _ = s.Store.AddChatMessage(ctx, sessionID, "user", req.Message, "", req.Images, nil, false)

	temperature := model.Temperature
	if userCfg.Temperature != nil {
		temperature = *userCfg.Temperature
	}
	reasoning := model.SupportReasoning == "Y"
	if req.IsReasoning != nil {
		reasoning = reasoning && *req.IsReasoning
	}
	systemPrompt := "You are a helpful AI assistant."
	if userCfg.SystemPrompt != nil && strings.TrimSpace(*userCfg.SystemPrompt) != "" {
		systemPrompt = strings.TrimSpace(*userCfg.SystemPrompt)
	}
	messages := []llm.ChatMessage{{Role: "system", Content: systemPrompt}}
	if userCfg.AddHistoryToContext == "0" {
		history, err := s.Store.ChatHistoryMessages(ctx, sessionID, userCfg.NumHistoryRuns)
		if err == nil {
			for _, h := range history {
				if h.Role == "system" {
					continue
				}
				messages = append(messages, llm.ChatMessage{Role: h.Role, Content: h.Content})
			}
		}
	}
	messages = append(messages, llm.ChatMessage{Role: "user", Content: req.Message})

	runID := strings.ReplaceAll(uuid.NewString(), "-", "")
	streamCtx, cancel := context.WithCancel(ctx)
	s.Runs.Register(runID, cancel)
	defer s.Runs.Done(runID)

	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")
	flusher, ok := w.(http.Flusher)
	if !ok {
		response.Error(w, "streaming unsupported")
		return
	}
	writeEvent := func(ev llm.StreamEvent) error {
		raw, err := json.Marshal(ev)
		if err != nil {
			return err
		}
		if _, err := fmt.Fprintf(w, "%s\n", raw); err != nil {
			return err
		}
		flusher.Flush()
		return nil
	}
	_ = writeEvent(llm.StreamEvent{Type: "meta", SessionID: sessionID})

	client := llm.NewStreamClient(300 * time.Second)
	result, err := client.StreamChat(streamCtx, llm.StreamRequest{
		BaseURL: model.BaseURL, APIKey: model.APIKey, Model: model.ModelCode,
		Temperature: temperature, MaxTokens: model.MaxTokens, Messages: messages, Reasoning: reasoning,
	}, runID, writeEvent)
	if err != nil {
		_ = writeEvent(llm.StreamEvent{Type: "error", Error: err.Error()})
		return
	}
	agentData := map[string]interface{}{
		"agentId": "chat-agent",
		"model": map[string]interface{}{
			"id": model.ModelCode, "name": model.ModelName, "provider": model.Provider,
			"temperature": temperature,
		},
	}
	_ = s.Store.TouchChatSession(ctx, sessionID, title, agentData)
	_, _ = s.Store.AddChatMessage(ctx, sessionID, "assistant", result.Content, result.Reasoning, nil, result.Metrics, false)
}

func (s *Server) ChatConfigGet(w http.ResponseWriter, r *http.Request) {
	user := auth.UserFrom(r.Context())
	cfg, err := s.Store.GetChatConfig(r.Context(), user.UserID)
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	response.Success(w, store.FormatChatConfig(cfg))
}

func (s *Server) ChatConfigSave(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPut {
		http.NotFound(w, r)
		return
	}
	user := auth.UserFrom(r.Context())
	var body map[string]interface{}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		response.Error(w, "invalid json")
		return
	}
	body["userId"] = user.UserID
	if err := s.Store.SaveChatConfig(r.Context(), user.UserID, body); err != nil {
		response.Error(w, err.Error())
		return
	}
	response.SuccessMsg(w, "保存成功", nil)
}

func (s *Server) ChatSessionList(w http.ResponseWriter, r *http.Request) {
	user := auth.UserFrom(r.Context())
	rows, err := s.Store.ListChatSessions(r.Context(), user.UserID)
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	out := make([]map[string]interface{}, 0, len(rows))
	for _, row := range rows {
		out = append(out, store.FormatChatSessionSummary(row))
	}
	response.Success(w, out)
}

func (s *Server) ChatSessionDetail(w http.ResponseWriter, r *http.Request) {
	sessionID := strings.TrimPrefix(r.URL.Path, "/ai/chat/session/")
	sessionID = strings.Trim(sessionID, "/")
	user := auth.UserFrom(r.Context())
	detail, err := s.Store.GetChatSession(r.Context(), sessionID, user.UserID)
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	response.Success(w, store.FormatChatSessionDetail(detail))
}

func (s *Server) ChatSessionDelete(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodDelete {
		http.NotFound(w, r)
		return
	}
	sessionID := strings.TrimPrefix(r.URL.Path, "/ai/chat/session/")
	sessionID = strings.Trim(sessionID, "/")
	if err := s.Store.DeleteChatSession(r.Context(), sessionID); err != nil {
		response.Error(w, err.Error())
		return
	}
	response.SuccessMsg(w, "删除成功", nil)
}

func (s *Server) ChatCancel(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.NotFound(w, r)
		return
	}
	var body struct {
		RunID string `json:"runId"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		response.Error(w, "invalid json")
		return
	}
	if !s.Runs.Cancel(body.RunID) {
		response.Error(w, "取消运行失败")
		return
	}
	response.SuccessMsg(w, "取消成功", nil)
}

func (s *Server) ChatConsultant(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.NotFound(w, r)
		return
	}
	var body struct {
		Message string                   `json:"message"`
		History []map[string]interface{} `json:"history"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		response.Error(w, "invalid json")
		return
	}
	message := strings.TrimSpace(body.Message)
	if message == "" {
		response.Success(w, map[string]interface{}{"ok": false, "message": "请输入要咨询的问题"})
		return
	}
	model, err := s.Store.ResolveChatModelByScope(r.Context(), "chat")
	if err != nil {
		response.Success(w, map[string]interface{}{"ok": false, "message": err.Error()})
		return
	}
	msgs := []llm.ChatMessage{
		{Role: "system", Content: "你是一名资深的全球宏观与量化投资顾问。用中文给出专业、可操作的建议，并提示投资有风险。"},
	}
	for _, h := range body.History {
		if len(msgs) >= 7 {
			break
		}
		role, _ := h["role"].(string)
		content, _ := h["content"].(string)
		if role == "" {
			role = "user"
		}
		msgs = append(msgs, llm.ChatMessage{Role: role, Content: content})
	}
	msgs = append(msgs, llm.ChatMessage{Role: "user", Content: message})
	client := llm.NewStreamClient(120 * time.Second)
	reply, err := client.CompleteChat(r.Context(), llm.StreamRequest{
		BaseURL: model.BaseURL, APIKey: model.APIKey, Model: model.ModelCode,
		Temperature: model.Temperature, Messages: msgs,
	})
	if err != nil {
		response.Success(w, map[string]interface{}{"ok": false, "message": err.Error()})
		return
	}
	response.Success(w, map[string]interface{}{"ok": true, "reply": reply})
}

func (s *Server) ChatOneshot(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.NotFound(w, r)
		return
	}
	var body struct {
		Symbol string `json:"symbol"`
		Market string `json:"market"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		response.Error(w, "invalid json")
		return
	}
	symbol := strings.TrimSpace(body.Symbol)
	if symbol == "" {
		symbol = "NVDA.US"
	}
	market := strings.TrimSpace(body.Market)
	if market == "" {
		market = "US"
	}
	model, err := s.Store.ResolveChatModelByScope(r.Context(), "sentiment")
	if err != nil {
		response.Success(w, map[string]interface{}{"ok": false, "message": err.Error()})
		return
	}
	prompt := fmt.Sprintf("请对标的 %s (%s) 给出简洁的 One-Shot 技术研判，包含 score(0-100)、decision、confidence、risk_level、operation_advice 字段，输出 JSON。", symbol, market)
	client := llm.NewStreamClient(120 * time.Second)
	raw, err := client.CompleteChat(r.Context(), llm.StreamRequest{
		BaseURL: model.BaseURL, APIKey: model.APIKey, Model: model.ModelCode,
		Temperature: 0.2,
		Messages: []llm.ChatMessage{
			{Role: "system", Content: "你是量化投资总监，只输出 JSON。"},
			{Role: "user", Content: prompt},
		},
	})
	if err != nil {
		response.Success(w, map[string]interface{}{"ok": false, "message": err.Error()})
		return
	}
	var parsed map[string]interface{}
	if err := json.Unmarshal([]byte(extractJSON(raw)), &parsed); err != nil {
		response.Success(w, map[string]interface{}{"ok": false, "message": "JSON解析失败", "raw": raw})
		return
	}
	response.Success(w, map[string]interface{}{
		"ok": true, "symbol": symbol, "result": parsed, "score": parsed["score"], "raw": raw,
	})
}

func extractJSON(text string) string {
	text = strings.TrimSpace(text)
	start, end := strings.Index(text, "{"), strings.LastIndex(text, "}")
	if start >= 0 && end > start {
		return text[start : end+1]
	}
	return text
}

func (s *Server) OpenToken(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.NotFound(w, r)
		return
	}
	var body struct {
		Username string `json:"username"`
		Password string `json:"password"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		response.Error(w, "invalid json")
		return
	}
	user, err := s.Store.AuthenticateUser(r.Context(), body.Username, body.Password)
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	sessionID := strings.ReplaceAll(uuid.NewString(), "-", "")
	claims := jwt.MapClaims{
		"user_id": fmt.Sprintf("%d", user.UserID), "user_name": user.UserName,
		"session_id": sessionID, "scope": "open", "aud": openAudience,
		"exp": time.Now().Add(store.OpenTokenTTL()).Unix(),
	}
	token := jwt.NewWithClaims(jwt.SigningMethodHS256, claims)
	signed, err := token.SignedString([]byte(s.Cfg.JWTSecret))
	if err != nil {
		response.Error(w, "签发失败")
		return
	}
	_ = s.Redis.Set(r.Context(), store.OpenTokenRedisKey(sessionID), signed, store.OpenTokenTTL()).Err()
	response.Success(w, store.FormatOpenToken(signed, 60))
}

func (s *Server) OpenRequirements(w http.ResponseWriter, r *http.Request) {
	if err := s.verifyOpenBearer(r); err != nil {
		response.Unauthorized(w, err.Error())
		return
	}
	status := r.URL.Query().Get("status")
	data, err := store.ExportReqItems(r.Context(), s.Store, status)
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	response.Success(w, data)
}

func (s *Server) verifyOpenBearer(r *http.Request) error {
	raw := strings.TrimSpace(r.Header.Get("Authorization"))
	if raw == "" {
		return fmt.Errorf("请先用用户名密码获取令牌")
	}
	parts := strings.SplitN(raw, " ", 2)
	if len(parts) != 2 || !strings.EqualFold(parts[0], "Bearer") {
		return fmt.Errorf("令牌不合法")
	}
	tokenStr := strings.TrimSpace(parts[1])
	claims := jwt.MapClaims{}
	parsed, err := jwt.ParseWithClaims(tokenStr, claims, func(t *jwt.Token) (interface{}, error) {
		return []byte(s.Cfg.JWTSecret), nil
	}, jwt.WithAudience(openAudience))
	if err != nil || !parsed.Valid {
		return fmt.Errorf("令牌已失效，请重新登录")
	}
	if claims["scope"] != "open" {
		return fmt.Errorf("令牌不合法")
	}
	sessionID, _ := claims["session_id"].(string)
	if sessionID != "" {
		stored, err := s.Redis.Get(r.Context(), store.OpenTokenRedisKey(sessionID)).Result()
		if err != nil || stored != tokenStr {
			return fmt.Errorf("令牌已失效，请重新登录")
		}
	}
	return nil
}

func (s *Server) decryptKey(enc string) string {
	return crypto.DecryptCredential(enc, s.Cfg.CredentialEncryptionKey, s.Cfg.JWTSecret)
}
