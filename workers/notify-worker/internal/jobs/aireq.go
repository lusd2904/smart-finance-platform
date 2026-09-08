package jobs

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"regexp"
	"strings"
	"sync"

	"github.com/lusd2904/smart-finance-platform/workers/notify-worker/internal/crypto"
)

const (
	maxReqRounds       = 3
	peerNoteLimit        = 8
	validReqPriorities   = "P0,P1,P2,P3"
)

var (
	confirmExact = map[string]bool{"确定": true, "确认": true, "同意": true, "就这样": true}
	confirmRe    = regexp.MustCompile(`(确定需求|确认需求|写入清单|总结并写入|请总结|确认落地)`)
	actionRe     = regexp.MustCompile(`\{[\s\S]*"action"\s*:\s*"upsert_requirements"[\s\S]*\}`)
)

type reqBot struct {
	BotID       int64
	ModelID     int64
	UserName    string
	DisplayName string
	IsDecider   bool
}

type reqMessage struct {
	MsgID    int64
	Role     string
	Content  string
	NickName string
}

func (s *Service) RunReqSend(ctx context.Context, payload map[string]interface{}, summarize bool) (map[string]interface{}, error) {
	userMsgID := intFrom(payload["userMsgId"])
	userID := intFrom(payload["userId"])
	userName := stringFrom(payload["userName"])
	nickName := stringFrom(payload["nickName"])
	if nickName == "" {
		nickName = userName
	}
	userRow, err := s.getReqMessage(ctx, userMsgID)
	if err != nil {
		return nil, err
	}
	if userRow == nil {
		return nil, fmt.Errorf("需求沟通消息不存在: %d", userMsgID)
	}
	text := userRow.Content
	confirmed := isConfirmText(text) || summarize
	history, err := s.listReqMessages(ctx, 0, 40)
	if err != nil {
		return nil, err
	}
	filtered := make([]reqMessage, 0, len(history))
	for _, m := range history {
		if m.MsgID == userMsgID {
			continue
		}
		filtered = append(filtered, m)
	}
	result, err := s.runReqParallelRound(ctx, filtered, fmt.Sprintf("%s: %s", nickName, text), userID, nickName, confirmed, summarize)
	if err != nil {
		return nil, err
	}
	if summarize {
		count := intFrom(result["count"])
		if count > 0 {
			result["message"] = fmt.Sprintf("已写入 %d 条需求", count)
		} else {
			result["message"] = "未解析到可写入的确定需求"
		}
	}
	return result, nil
}

func (s *Service) runReqParallelRound(ctx context.Context, history []reqMessage, userText string, createdBy int64, createdByName string, confirmed, summarize bool) (map[string]interface{}, error) {
	bots, err := s.listEnabledReqBots(ctx)
	if err != nil {
		return nil, err
	}
	if len(bots) == 0 {
		bots = []reqBot{{BotID: 0, ModelID: 0, UserName: "grok", DisplayName: "Grok", IsDecider: true}}
	}
	roundNo := inferReqRound(history)
	peerNotes := peerNotesFrom(history)
	writeNow := confirmed || summarize
	histMsgs := reqHistoryForLLM(history)

	type botReply struct {
		bot   reqBot
		reply string
	}
	replies := make([]botReply, len(bots))
	var wg sync.WaitGroup
	var mu sync.Mutex
	for i, bot := range bots {
		wg.Add(1)
		go func(idx int, bot reqBot) {
			defer wg.Done()
			conf, _ := s.resolveReqModel(ctx, bot.ModelID)
			prompt := reqSystemPrompt(bot.DisplayName, bot.IsDecider, roundNo, peerNotes, writeNow && bot.IsDecider)
			reply := ""
			if conf.BaseURL != "" && conf.APIKey != "" && conf.ModelCode != "" {
				if r, err := s.llm.ChatCompletion(ctx, conf.BaseURL, conf.APIKey, conf.ModelCode, prompt, histMsgs, userText, 0.3); err == nil {
					reply = r
				} else {
					reply = fmt.Sprintf("%s 暂时不可用：%v", bot.DisplayName, err)
				}
			} else {
				reply = fmt.Sprintf("%s 未配置可用模型，请在「AI 模型管理」补全后重试。", bot.DisplayName)
			}
			if (!bot.IsDecider || !writeNow) && len(extractRequirementPayload(reply)) > 0 {
				reply = strings.TrimSpace(actionRe.ReplaceAllString(reply, ""))
				if reply == "" {
					reply = "（已隐藏未授权的清单写入 JSON）"
				}
			}
			mu.Lock()
			replies[idx] = botReply{bot: bot, reply: reply}
			mu.Unlock()
		}(i, bot)
	}
	wg.Wait()

	aiMessages := make([]map[string]interface{}, 0, len(replies))
	written := make([]map[string]interface{}, 0)
	for _, pair := range replies {
		msg, items, err := s.appendReqAIReply(ctx, pair.reply, createdBy, createdByName, writeNow && pair.bot.IsDecider, pair.bot.UserName, pair.bot.DisplayName)
		if err != nil {
			return nil, err
		}
		aiMessages = append(aiMessages, msg)
		written = append(written, items...)
	}
	if roundNo >= maxReqRounds && !writeNow {
		notice, _, err := s.appendReqAIReply(ctx,
			fmt.Sprintf("已到默认 %d 轮。请确认后由确定者合并写入清单；更换确定者从下一轮生效。", maxReqRounds),
			createdBy, createdByName, false, "system", "系统")
		if err != nil {
			return nil, err
		}
		aiMessages = append(aiMessages, notice)
	}
	var last map[string]interface{}
	if len(aiMessages) > 0 {
		last = aiMessages[len(aiMessages)-1]
	}
	return map[string]interface{}{
		"aiMessages": aiMessages, "aiMessage": last, "requirements": written, "count": len(written),
	}, nil
}

func reqSystemPrompt(name string, isDecider bool, roundNo int, peerNotes string, writeAllowed bool) string {
	role := fmt.Sprintf("你是需求沟通群里的 AI 成员「%s」。只讨论需求沟通，不写代码。", name)
	roundRule := fmt.Sprintf("本轮是第 %d 轮：必须点评其他 AI 的观点并回应分歧。其他成员上一轮摘要：\n%s", roundNo, peerNotes)
	if roundNo <= 1 {
		roundRule = "本轮是第 1 轮：独立判断可行性、风险、范围，不要提及其他 AI 当轮发言。"
	}
	var writeRule string
	if isDecider && writeAllowed {
		writeRule = `你是唯一清单确定者。用户已确认后，在回复末尾附加且仅附加一段 JSON（不要用 markdown 代码块）：{"action":"upsert_requirements","items":[{"title":"不超过40字","detail":"实现要点","priority":"P0|P1|P2|P3"}]}合并去重，未达成一致的不要写入。`
	} else if isDecider {
		writeRule = "你是清单确定者，但用户尚未确认，禁止输出 action JSON。"
	} else {
		writeRule = "你不是确定者，只讨论、禁止输出 upsert_requirements / action JSON。"
	}
	return fmt.Sprintf("%s\n规则：\n1. 用中文简短回复。\n2. %s\n3. %s\n4. 不要泄露密钥或编造已上线功能。", role, roundRule, writeRule)
}

func extractRequirementPayload(text string) []map[string]string {
	raw := strings.TrimSpace(text)
	match := actionRe.FindString(raw)
	if match == "" {
		return nil
	}
	start, end := strings.Index(match, "{"), strings.LastIndex(match, "}")
	if start < 0 || end <= start {
		return nil
	}
	var data map[string]interface{}
	if err := json.Unmarshal([]byte(match[start:end+1]), &data); err != nil {
		return nil
	}
	items, _ := data["items"].([]interface{})
	out := make([]map[string]string, 0)
	for _, item := range items {
		if len(out) >= 20 {
			break
		}
		m, ok := item.(map[string]interface{})
		if !ok {
			continue
		}
		title := strings.TrimSpace(stringFrom(m["title"]))
		if title == "" {
			continue
		}
		if len(title) > 200 {
			title = title[:200]
		}
		priority := strings.ToUpper(stringFrom(m["priority"]))
		if priority == "" || !strings.Contains(validReqPriorities, priority) {
			priority = "P2"
		}
		detail := strings.TrimSpace(stringFrom(m["detail"]))
		if len(detail) > 4000 {
			detail = detail[:4000]
		}
		out = append(out, map[string]string{"title": title, "detail": detail, "priority": priority})
	}
	return out
}

func isConfirmText(text string) bool {
	raw := strings.TrimSpace(text)
	if confirmExact[raw] {
		return true
	}
	return confirmRe.MatchString(raw)
}

func inferReqRound(history []reqMessage) int {
	waves := 0
	prev := ""
	for _, item := range history {
		if item.Role == "ai" && prev != "ai" {
			waves++
		}
		prev = item.Role
	}
	round := waves + 1
	if round < 1 {
		round = 1
	}
	if round > maxReqRounds {
		round = maxReqRounds
	}
	return round
}

func peerNotesFrom(history []reqMessage) string {
	notes := make([]string, 0, peerNoteLimit)
	for i := len(history) - 1; i >= 0 && len(notes) < peerNoteLimit; i-- {
		item := history[i]
		if item.Role != "ai" {
			if len(notes) > 0 {
				break
			}
			continue
		}
		name := item.NickName
		if name == "" {
			name = "AI"
		}
		content := item.Content
		if len(content) > 280 {
			content = content[:280]
		}
		notes = append(notes, fmt.Sprintf("- %s: %s", name, content))
	}
	for i, j := 0, len(notes)-1; i < j; i, j = i+1, j-1 {
		notes[i], notes[j] = notes[j], notes[i]
	}
	return strings.Join(notes, "\n")
}

func reqHistoryForLLM(history []reqMessage) []map[string]string {
	start := 0
	if len(history) > 16 {
		start = len(history) - 16
	}
	out := make([]map[string]string, 0, len(history)-start)
	for _, item := range history[start:] {
		out = append(out, map[string]string{"role": item.Role, "content": item.Content})
	}
	return out
}

func (s *Service) getReqMessage(ctx context.Context, msgID int64) (*reqMessage, error) {
	row := &reqMessage{}
	var nick sql.NullString
	err := s.db.QueryRowContext(ctx, `
SELECT msg_id, role, content, nick_name FROM ai_req_message WHERE msg_id=?`, msgID).
		Scan(&row.MsgID, &row.Role, &row.Content, &nick)
	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	row.NickName = nick.String
	return row, nil
}

func (s *Service) listReqMessages(ctx context.Context, afterID int64, limit int) ([]reqMessage, error) {
	if limit <= 0 {
		limit = 200
	}
	if limit > 400 {
		limit = 400
	}
	var rows *sql.Rows
	var err error
	if afterID > 0 {
		rows, err = s.db.QueryContext(ctx, `
SELECT msg_id, role, content, nick_name FROM ai_req_message
WHERE room_id=1 AND msg_id > ? ORDER BY msg_id ASC LIMIT ?`, afterID, limit)
	} else {
		rows, err = s.db.QueryContext(ctx, `
SELECT msg_id, role, content, nick_name FROM ai_req_message
WHERE room_id=1 ORDER BY msg_id DESC LIMIT ?`, limit)
	}
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := make([]reqMessage, 0)
	for rows.Next() {
		var m reqMessage
		var nick sql.NullString
		if err := rows.Scan(&m.MsgID, &m.Role, &m.Content, &nick); err != nil {
			return nil, err
		}
		m.NickName = nick.String
		out = append(out, m)
	}
	if afterID == 0 {
		for i, j := 0, len(out)-1; i < j; i, j = i+1, j-1 {
			out[i], out[j] = out[j], out[i]
		}
	}
	return out, rows.Err()
}

func (s *Service) listEnabledReqBots(ctx context.Context) ([]reqBot, error) {
	rows, err := s.db.QueryContext(ctx, `
SELECT bot_id, model_id, display_name, is_decider
FROM ai_req_bot WHERE enabled='1' ORDER BY sort_order, bot_id`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := make([]reqBot, 0)
	hasDecider := false
	for rows.Next() {
		var b reqBot
		var display, isDecider string
		if err := rows.Scan(&b.BotID, &b.ModelID, &display, &isDecider); err != nil {
			return nil, err
		}
		b.UserName = fmt.Sprintf("bot-%d", b.BotID)
		b.DisplayName = display
		b.IsDecider = isDecider == "1"
		if b.IsDecider {
			hasDecider = true
		}
		out = append(out, b)
	}
	if len(out) > 0 && !hasDecider {
		out[0].IsDecider = true
	}
	return out, rows.Err()
}

func (s *Service) resolveReqModel(ctx context.Context, modelID int64) (aiModelRow, error) {
	if modelID <= 0 {
		return s.resolveGrokModel(ctx)
	}
	var r aiModelRow
	var baseURL, apiKey, modelCode sql.NullString
	err := s.db.QueryRowContext(ctx, `
SELECT model_id, base_url, api_key, model_code, temperature FROM ai_models WHERE model_id=?`, modelID).
		Scan(&r.ModelID, &baseURL, &apiKey, &modelCode, &r.Temperature)
	if err == sql.ErrNoRows {
		return aiModelRow{}, nil
	}
	if err != nil {
		return aiModelRow{}, err
	}
	r.BaseURL = strings.TrimSpace(baseURL.String)
	r.APIKey = crypto.DecryptCredential(strings.TrimSpace(apiKey.String), s.cfg.CredentialKey, s.cfg.JWTSecret)
	r.ModelCode = strings.TrimSpace(modelCode.String)
	return r, nil
}

func (s *Service) resolveGrokModel(ctx context.Context) (aiModelRow, error) {
	rows, err := s.db.QueryContext(ctx, `
SELECT model_id, base_url, api_key, model_code, temperature, provider, scope, model_name
FROM ai_models WHERE status='0'`)
	if err != nil {
		return aiModelRow{}, err
	}
	defer rows.Close()
	bestScore := -1
	var best aiModelRow
	for rows.Next() {
		var r aiModelRow
		var baseURL, apiKey, modelCode, provider, scope, modelName sql.NullString
		var temp sql.NullFloat64
		if err := rows.Scan(&r.ModelID, &baseURL, &apiKey, &modelCode, &temp, &provider, &scope, &modelName); err != nil {
			return aiModelRow{}, err
		}
		r.BaseURL = strings.TrimSpace(baseURL.String)
		r.APIKey = crypto.DecryptCredential(strings.TrimSpace(apiKey.String), s.cfg.CredentialKey, s.cfg.JWTSecret)
		r.ModelCode = strings.TrimSpace(modelCode.String)
		if r.BaseURL == "" || r.APIKey == "" || r.ModelCode == "" {
			continue
		}
		blob := strings.ToLower(fmt.Sprintf("%s %s %s", provider.String, r.ModelCode, modelName.String))
		score := 0
		if strings.Contains(blob, "grok") || strings.Contains(blob, "xai") {
			score += 10
		}
		if scope.String == "chat" {
			score += 2
		}
		score++
		if score > bestScore {
			bestScore = score
			best = r
		}
	}
	return best, nil
}

func (s *Service) appendReqAIReply(ctx context.Context, reply string, createdBy int64, createdByName string, writeItems bool, userName, nickName string) (map[string]interface{}, []map[string]interface{}, error) {
	now := nowBeijing()
	res, err := s.db.ExecContext(ctx, `
INSERT INTO ai_req_message (room_id, user_id, user_name, nick_name, role, content, create_time)
VALUES (1, 0, ?, ?, 'ai', ?, ?)`, userName, nickName, reply, now)
	if err != nil {
		return nil, nil, err
	}
	msgID, _ := res.LastInsertId()
	written := make([]map[string]interface{}, 0)
	if writeItems {
		for _, item := range extractRequirementPayload(reply) {
			row, err := s.upsertReqItem(ctx, item, createdBy, createdByName, msgID)
			if err != nil {
				return nil, nil, err
			}
			written = append(written, row)
		}
	}
	return map[string]interface{}{
		"msgId": msgID, "userId": 0, "userName": userName, "nickName": nickName,
		"role": "ai", "content": reply, "createTime": formatBeijing(now),
	}, written, nil
}

func (s *Service) upsertReqItem(ctx context.Context, item map[string]string, createdBy int64, createdByName string, sourceMsgID int64) (map[string]interface{}, error) {
	var existingID int64
	err := s.db.QueryRowContext(ctx, `SELECT item_id FROM ai_req_item WHERE title=? ORDER BY item_id DESC LIMIT 1`, item["title"]).Scan(&existingID)
	now := nowBeijing()
	if err == nil && existingID > 0 {
		_, err = s.db.ExecContext(ctx, `
UPDATE ai_req_item SET detail=?, priority=?, source_msg_id=?, update_time=? WHERE item_id=?`,
			item["detail"], item["priority"], sourceMsgID, now, existingID)
		if err != nil {
			return nil, err
		}
	} else if err == sql.ErrNoRows {
		res, err := s.db.ExecContext(ctx, `
INSERT INTO ai_req_item (title, detail, priority, status, source_msg_id, created_by, created_by_name, create_time, update_time)
VALUES (?, ?, ?, 'pending', ?, ?, ?, ?, ?)`,
			item["title"], item["detail"], item["priority"], sourceMsgID, createdBy, createdByName, now, now)
		if err != nil {
			return nil, err
		}
		existingID, _ = res.LastInsertId()
	} else if err != nil {
		return nil, err
	}
	return map[string]interface{}{
		"id": existingID, "title": item["title"], "detail": item["detail"], "priority": item["priority"], "status": "pending",
	}, nil
}
