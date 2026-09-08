package jobs

import (
	"context"
)

func (s *Service) RunUserNotice(ctx context.Context, payload map[string]interface{}) (map[string]interface{}, error) {
	userID := intFrom(payload["user_id"])
	if userID <= 0 {
		userID = intFrom(payload["userId"])
	}
	if userID <= 0 {
		return map[string]interface{}{"skipped": true, "reason": "missing_user_id"}, nil
	}
	title := stringFrom(payload["title"])
	content := stringFrom(payload["content"])
	level := stringFrom(payload["level"])
	if level == "" {
		level = "info"
	}
	category := stringFrom(payload["category"])
	if category == "" {
		category = "system"
	}
	now := nowBeijing()
	res, err := s.db.ExecContext(ctx, `
INSERT INTO plat_notification (user_id, title, content, level, category, is_read, create_time)
VALUES (?, ?, ?, ?, ?, '0', ?)`, userID, title, content, level, category, now)
	if err != nil {
		return nil, err
	}
	id, _ := res.LastInsertId()
	return map[string]interface{}{"ok": true, "notificationId": id}, nil
}
