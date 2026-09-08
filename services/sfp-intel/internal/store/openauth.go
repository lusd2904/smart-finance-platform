package store

import (
	"context"
	"database/sql"
	"fmt"
	"strings"
	"time"

	"golang.org/x/crypto/bcrypt"

	"github.com/lusd2904/smart-finance-platform/services/sfp-intel/internal/timeutil"
)

type SysUserAuth struct {
	UserID   int64
	UserName string
	Password string
	Status   string
	DelFlag  string
}

func (s *Store) AuthenticateUser(ctx context.Context, userName, password string) (*SysUserAuth, error) {
	userName = strings.TrimSpace(userName)
	if userName == "" || password == "" {
		return nil, fmt.Errorf("用户名或密码不能为空")
	}
	row := s.db.QueryRowContext(ctx, `
SELECT user_id, user_name, password, status, del_flag
FROM sys_user WHERE user_name = ? LIMIT 1`, userName)
	var u SysUserAuth
	if err := row.Scan(&u.UserID, &u.UserName, &u.Password, &u.Status, &u.DelFlag); err != nil {
		if err == sql.ErrNoRows {
			return nil, fmt.Errorf("用户不存在/密码错误")
		}
		return nil, err
	}
	if u.DelFlag != "0" || u.Status != "0" {
		return nil, fmt.Errorf("用户不存在/密码错误")
	}
	if err := bcrypt.CompareHashAndPassword([]byte(u.Password), []byte(password)); err != nil {
		return nil, fmt.Errorf("用户不存在/密码错误")
	}
	return &u, nil
}

func ExportReqItems(ctx context.Context, st *Store, status string) (map[string]interface{}, error) {
	items, err := st.ListReqItems(ctx, status)
	if err != nil {
		return nil, err
	}
	rows := make([]map[string]interface{}, 0, len(items))
	for _, item := range items {
		rows = append(rows, FormatReqItem(item))
	}
	return map[string]interface{}{
		"exportedAt": timeutil.NowBeijingRFC(),
		"statusFilter": status,
		"items": rows,
	}, nil
}

func FormatOpenToken(token string, expiresMinutes int) map[string]interface{} {
	return map[string]interface{}{
		"token": token, "expiresIn": expiresMinutes * 60, "tokenType": "Bearer",
	}
}

func OpenTokenRedisKey(sessionID string) string {
	return "open_token:" + sessionID
}

func OpenTokenTTL() time.Duration {
	return 60 * time.Minute
}
