package auth

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"strings"

	"github.com/golang-jwt/jwt/v5"
	"github.com/redis/go-redis/v9"

	"github.com/lusd2904/smart-finance-platform/services/market-read/internal/config"
)

type User struct {
	UserID      int64
	Permissions []string
}

type Authenticator struct {
	cfg   *config.Config
	redis *redis.Client
}

func New(cfg *config.Config, redis *redis.Client) *Authenticator {
	return &Authenticator{cfg: cfg, redis: redis}
}

type ctxKey int

const userKey ctxKey = 1

func WithUser(ctx context.Context, user *User) context.Context {
	return context.WithValue(ctx, userKey, user)
}

func UserFrom(ctx context.Context) *User {
	u, _ := ctx.Value(userKey).(*User)
	return u
}

func (a *Authenticator) Authenticate(ctx context.Context, header string) (*User, error) {
	token, err := parseBearer(header)
	if err != nil {
		return nil, err
	}
	claims := jwt.MapClaims{}
	parsed, err := jwt.ParseWithClaims(token, claims, func(t *jwt.Token) (interface{}, error) {
		if t.Method.Alg() != a.cfg.JWTAlgorithm {
			return nil, fmt.Errorf("unexpected jwt alg %s", t.Method.Alg())
		}
		return []byte(a.cfg.JWTSecret), nil
	})
	if err != nil || !parsed.Valid {
		return nil, errors.New("用户token已失效，请重新登录")
	}
	userIDRaw, _ := claims["user_id"].(string)
	if userIDRaw == "" {
		if n, ok := claims["user_id"].(float64); ok {
			userIDRaw = fmt.Sprintf("%.0f", n)
		}
	}
	sessionID, _ := claims["session_id"].(string)
	if userIDRaw == "" {
		return nil, errors.New("用户token不合法")
	}
	userID, err := parseInt64(userIDRaw)
	if err != nil || userID <= 0 {
		return nil, errors.New("用户token不合法")
	}

	redisKey := fmt.Sprintf("access_token:%d", userID)
	if a.cfg.AppSameTimeLogin && sessionID != "" {
		redisKey = fmt.Sprintf("access_token:%s", sessionID)
	}
	stored, err := a.redis.Get(ctx, redisKey).Result()
	if err != nil || stored != token {
		return nil, errors.New("用户token已失效，请重新登录")
	}
	_ = a.redis.Expire(ctx, redisKey, a.cfg.JWTRedisExpire).Err()

	perms, err := a.loadPermissions(ctx, userID)
	if err != nil {
		return nil, err
	}
	return &User{UserID: userID, Permissions: perms}, nil
}

func (a *Authenticator) loadPermissions(ctx context.Context, userID int64) ([]string, error) {
	raw, err := a.redis.Get(ctx, fmt.Sprintf("current_user:%d", userID)).Result()
	if err != nil {
		return nil, errors.New("用户token已失效，请重新登录")
	}
	var payload struct {
		Epoch string `json:"epoch"`
		User  struct {
			Permissions []string `json:"permissions"`
		} `json:"user"`
	}
	if err := json.Unmarshal([]byte(raw), &payload); err != nil {
		return nil, errors.New("用户token已失效，请重新登录")
	}
	epoch, err := a.redis.Get(ctx, "current_user_epoch").Result()
	if err != nil && err != redis.Nil {
		return nil, errors.New("用户token已失效，请重新登录")
	}
	if epoch == "" {
		epoch = "0"
	}
	if payload.Epoch != epoch {
		return nil, errors.New("用户token已失效，请重新登录")
	}
	return payload.User.Permissions, nil
}

func (u *User) HasPerm(required ...string) bool {
	if u == nil {
		return false
	}
	set := make(map[string]bool, len(u.Permissions))
	for _, p := range u.Permissions {
		set[p] = true
	}
	if set["*:*:*"] {
		return true
	}
	for _, need := range required {
		if set[need] {
			return true
		}
	}
	return false
}

func parseBearer(header string) (string, error) {
	h := strings.TrimSpace(header)
	if h == "" {
		return "", errors.New("用户未登录，请先完成登录")
	}
	parts := strings.SplitN(h, " ", 2)
	if len(parts) != 2 || !strings.EqualFold(parts[0], "Bearer") || strings.TrimSpace(parts[1]) == "" {
		return "", errors.New("用户token不合法")
	}
	return strings.TrimSpace(parts[1]), nil
}

func parseInt64(s string) (int64, error) {
	var n int64
	for _, ch := range s {
		if ch < '0' || ch > '9' {
			return 0, fmt.Errorf("invalid int")
		}
		n = n*10 + int64(ch-'0')
	}
	return n, nil
}
