package store

import (
	"context"
	"database/sql"
	"fmt"
	"strings"
	"time"

	"github.com/lusd2904/smart-finance-platform/services/sfp-intel/internal/timeutil"
)

var (
	excludedReqUsernames = map[string]bool{"admin": true, "niangao": true}
	reqStatusLabels      = map[string]string{
		"pending": "待开发", "developing": "开发中", "testing": "测试中",
		"done": "已完成", "cancelled": "已取消",
	}
	validReqStatus = map[string]bool{
		"pending": true, "developing": true, "testing": true, "done": true, "cancelled": true,
	}
)

type ReqMessage struct {
	MsgID      int64
	UserID     int64
	UserName   string
	NickName   string
	Role       string
	Content    string
	CreateTime *time.Time
}

type ReqItem struct {
	ItemID        int64
	Title         string
	Detail        string
	Priority      string
	Status        string
	CreatedByName string
	Remark        string
	CreateTime    *time.Time
	UpdateTime    *time.Time
}

type ReqBot struct {
	BotID     int64
	ModelID   int64
	UserName  string
	NickName  string
	IsDecider string
	Enabled   string
	SortOrder int
}

func (s *Store) IsReqMember(userName string) bool {
	return !excludedReqUsernames[strings.ToLower(strings.TrimSpace(userName))]
}

func (s *Store) ListReqMembers(ctx context.Context) ([]map[string]interface{}, error) {
	rows, err := s.db.QueryContext(ctx, `
SELECT user_id, user_name, nick_name FROM sys_user
WHERE del_flag='0' AND status='0' ORDER BY user_id`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := make([]map[string]interface{}, 0)
	for rows.Next() {
		var userID int64
		var userName, nickName sql.NullString
		if err := rows.Scan(&userID, &userName, &nickName); err != nil {
			return nil, err
		}
		name := userName.String
		if excludedReqUsernames[strings.ToLower(name)] {
			continue
		}
		nick := nickName.String
		if nick == "" {
			nick = name
		}
		out = append(out, map[string]interface{}{
			"userId": userID, "userName": name, "nickName": nick, "role": "user",
		})
	}
	return out, rows.Err()
}

func (s *Store) ListReqBots(ctx context.Context) ([]ReqBot, error) {
	rows, err := s.db.QueryContext(ctx, `
SELECT bot_id, model_id, user_name, nick_name, is_decider, enabled, sort_order
FROM ai_req_bot ORDER BY sort_order, bot_id`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := make([]ReqBot, 0)
	for rows.Next() {
		var b ReqBot
		var nick sql.NullString
		if err := rows.Scan(&b.BotID, &b.ModelID, &b.UserName, &nick, &b.IsDecider, &b.Enabled, &b.SortOrder); err != nil {
			return nil, err
		}
		b.NickName = nick.String
		if b.NickName == "" {
			b.NickName = b.UserName
		}
		out = append(out, b)
	}
	return out, rows.Err()
}

func (s *Store) ReplaceReqBots(ctx context.Context, bots []ReqBot) error {
	tx, err := s.db.BeginTx(ctx, nil)
	if err != nil {
		return err
	}
	defer func() { _ = tx.Rollback() }()
	if _, err := tx.ExecContext(ctx, "DELETE FROM ai_req_bot"); err != nil {
		return err
	}
	for _, b := range bots {
		if _, err := tx.ExecContext(ctx, `
INSERT INTO ai_req_bot (model_id, user_name, nick_name, is_decider, enabled, sort_order)
VALUES (?, ?, ?, ?, ?, ?)`,
			b.ModelID, b.UserName, b.NickName, b.IsDecider, b.Enabled, b.SortOrder); err != nil {
			return err
		}
	}
	return tx.Commit()
}

func (s *Store) ListReqMessages(ctx context.Context, afterID, limit int) ([]ReqMessage, error) {
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
SELECT msg_id, user_id, user_name, nick_name, role, content, create_time
FROM ai_req_message WHERE room_id=1 AND msg_id > ? ORDER BY msg_id ASC LIMIT ?`, afterID, limit)
	} else {
		rows, err = s.db.QueryContext(ctx, `
SELECT msg_id, user_id, user_name, nick_name, role, content, create_time
FROM ai_req_message WHERE room_id=1 ORDER BY msg_id DESC LIMIT ?`, limit)
	}
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := make([]ReqMessage, 0)
	for rows.Next() {
		var m ReqMessage
		var nick sql.NullString
		var created sql.NullTime
		if err := rows.Scan(&m.MsgID, &m.UserID, &m.UserName, &nick, &m.Role, &m.Content, &created); err != nil {
			return nil, err
		}
		m.NickName = nick.String
		if m.NickName == "" {
			m.NickName = m.UserName
		}
		if created.Valid {
			t := created.Time
			m.CreateTime = &t
		}
		out = append(out, m)
	}
	if afterID == 0 {
		for i, j := 0, len(out)-1; i < j; i, j = i+1, j-1 {
			out[i], out[j] = out[j], out[i]
		}
	}
	return out, rows.Err()
}

func (s *Store) AddReqMessage(ctx context.Context, userID int64, userName, nickName, role, content string) (*ReqMessage, error) {
	now := timeutil.NowBeijing()
	res, err := s.db.ExecContext(ctx, `
INSERT INTO ai_req_message (room_id, user_id, user_name, nick_name, role, content, create_time)
VALUES (1, ?, ?, ?, ?, ?, ?)`, userID, userName, nickName, role, content, now)
	if err != nil {
		return nil, err
	}
	id, _ := res.LastInsertId()
	t := now
	return &ReqMessage{
		MsgID: id, UserID: userID, UserName: userName, NickName: nickName,
		Role: role, Content: content, CreateTime: &t,
	}, nil
}

func (s *Store) CountReqMessages(ctx context.Context) (int64, error) {
	var n int64
	err := s.db.QueryRowContext(ctx, "SELECT COUNT(*) FROM ai_req_message WHERE room_id=1").Scan(&n)
	return n, err
}

func (s *Store) ListReqItems(ctx context.Context, status string) ([]ReqItem, error) {
	query := `
SELECT item_id, title, detail, priority, status, created_by_name, remark, create_time, update_time
FROM ai_req_item`
	args := []interface{}{}
	if status != "" {
		query += " WHERE status = ?"
		args = append(args, status)
	}
	query += " ORDER BY item_id DESC LIMIT 500"
	rows, err := s.db.QueryContext(ctx, query, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := make([]ReqItem, 0)
	for rows.Next() {
		var item ReqItem
		var detail, priority, createdBy, remark sql.NullString
		var created, updated sql.NullTime
		if err := rows.Scan(&item.ItemID, &item.Title, &detail, &priority, &item.Status,
			&createdBy, &remark, &created, &updated); err != nil {
			return nil, err
		}
		item.Detail = detail.String
		item.Priority = priority.String
		if item.Priority == "" {
			item.Priority = "P2"
		}
		item.CreatedByName = createdBy.String
		item.Remark = remark.String
		if created.Valid {
			t := created.Time
			item.CreateTime = &t
		}
		if updated.Valid {
			t := updated.Time
			item.UpdateTime = &t
		}
		out = append(out, item)
	}
	return out, rows.Err()
}

func (s *Store) UpdateReqItemStatus(ctx context.Context, itemID int64, status, remark string) error {
	if !validReqStatus[status] {
		return fmt.Errorf("无效状态")
	}
	now := timeutil.NowBeijing()
	res, err := s.db.ExecContext(ctx, `
UPDATE ai_req_item SET status=?, remark=?, update_time=? WHERE item_id=?`,
		status, nullStr(remark), now, itemID)
	if err != nil {
		return err
	}
	n, _ := res.RowsAffected()
	if n == 0 {
		return fmt.Errorf("需求不存在")
	}
	return nil
}

func FormatReqMessage(m ReqMessage) map[string]interface{} {
	out := map[string]interface{}{
		"msgId": m.MsgID, "userId": m.UserID, "userName": m.UserName,
		"nickName": m.NickName, "role": m.Role, "content": m.Content,
	}
	if m.CreateTime != nil {
		out["createTime"] = timeutil.FormatBeijing(*m.CreateTime)
	}
	return out
}

func FormatReqItem(item ReqItem) map[string]interface{} {
	out := map[string]interface{}{
		"id": item.ItemID, "title": item.Title, "detail": item.Detail,
		"priority": item.Priority, "status": item.Status,
		"statusLabel": reqStatusLabels[item.Status],
		"createdBy": item.CreatedByName, "remark": item.Remark,
	}
	if item.CreateTime != nil {
		out["createTime"] = timeutil.FormatBeijing(*item.CreateTime)
	}
	if item.UpdateTime != nil {
		out["updateTime"] = timeutil.FormatBeijing(*item.UpdateTime)
	}
	return out
}

func FormatReqBots(bots []ReqBot) []map[string]interface{} {
	out := make([]map[string]interface{}, 0, len(bots))
	for _, b := range bots {
		out = append(out, map[string]interface{}{
			"botId": b.BotID, "modelId": b.ModelID, "userName": b.UserName,
			"nickName": b.NickName, "isDecider": b.IsDecider, "enabled": b.Enabled,
			"sortOrder": b.SortOrder,
		})
	}
	return out
}

func FormatReqRoom(members []map[string]interface{}, bots []ReqBot) map[string]interface{} {
	all := append([]map[string]interface{}{}, members...)
	for _, b := range bots {
		if b.Enabled != "1" {
			continue
		}
		all = append(all, map[string]interface{}{
			"userId": 0, "userName": b.UserName, "nickName": b.NickName,
			"role": "ai", "isDecider": b.IsDecider == "1",
		})
	}
	return map[string]interface{}{
		"roomId": 1, "name": "需求沟通群", "members": all,
	}
}
