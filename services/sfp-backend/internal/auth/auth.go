package auth

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"
	"strings"
	"time"

	"github.com/golang-jwt/jwt/v5"
	"github.com/redis/go-redis/v9"
	"golang.org/x/crypto/bcrypt"

	"github.com/lusd2904/smart-finance-platform/services/sfp-backend/internal/config"
	"github.com/lusd2904/smart-finance-platform/services/sfp-backend/internal/store"
)

const (
	accessTokenKey   = "access_token"
	captchaCodesKey  = "captcha_codes"
	currentUserKey   = "current_user"
	currentUserEpoch = "current_user_epoch"
	sysConfigKey     = "sys_config"
	passwordErrKey   = "password_error_count"
	accountLockKey   = "account_lock"
)

type User struct {
	UserID      int64
	UserName    string
	Admin       bool
	Permissions []string
	Roles       []string
	Payload     store.CurrentUserPayload
}

type Service struct {
	cfg   *config.Config
	redis *redis.Client
	db    *store.DB
}

func New(cfg *config.Config, rdb *redis.Client, db *store.DB) *Service {
	return &Service{cfg: cfg, redis: rdb, db: db}
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

func (s *Service) Authenticate(ctx context.Context, header string) (*User, error) {
	token, err := parseBearer(header)
	if err != nil {
		return nil, err
	}
	userID, err := s.verifySession(ctx, token)
	if err != nil {
		return nil, err
	}
	return s.loadUser(ctx, userID)
}

// VerifySession matches Python utils.ws_auth.verify_ws_session (JWT + Redis session).
func (s *Service) VerifySession(ctx context.Context, token string) error {
	_, err := s.verifySession(ctx, token)
	return err
}

func (s *Service) verifySession(ctx context.Context, token string) (int64, error) {
	token = strings.TrimSpace(token)
	if token == "" {
		return 0, errors.New("用户未登录，请先完成登录")
	}
	claims := jwt.MapClaims{}
	parsed, err := jwt.ParseWithClaims(token, claims, func(t *jwt.Token) (interface{}, error) {
		if t.Method.Alg() != s.cfg.JWTAlgorithm {
			return nil, fmt.Errorf("unexpected jwt alg %s", t.Method.Alg())
		}
		return []byte(s.cfg.JWTSecret), nil
	})
	if err != nil || !parsed.Valid {
		return 0, errors.New("用户token已失效，请重新登录")
	}
	userIDRaw, _ := claims["user_id"].(string)
	if userIDRaw == "" {
		if n, ok := claims["user_id"].(float64); ok {
			userIDRaw = fmt.Sprintf("%.0f", n)
		}
	}
	sessionID, _ := claims["session_id"].(string)
	if userIDRaw == "" {
		return 0, errors.New("用户token不合法")
	}
	userID, err := parseInt64(userIDRaw)
	if err != nil || userID <= 0 {
		return 0, errors.New("用户token不合法")
	}
	redisKey := fmt.Sprintf("%s:%d", accessTokenKey, userID)
	if s.cfg.AppSameTimeLogin && sessionID != "" {
		redisKey = fmt.Sprintf("%s:%s", accessTokenKey, sessionID)
	}
	stored, err := s.redis.Get(ctx, redisKey).Result()
	if err != nil || stored != token {
		return 0, errors.New("用户token已失效，请重新登录")
	}
	_ = s.redis.Expire(ctx, redisKey, s.cfg.JWTRedisExpire).Err()
	return userID, nil
}

func (s *Service) loadUser(ctx context.Context, userID int64) (*User, error) {
	raw, err := s.redis.Get(ctx, fmt.Sprintf("%s:%d", currentUserKey, userID)).Result()
	if err == nil {
		var cached struct {
			Epoch string                     `json:"epoch"`
			User  store.CurrentUserPayload   `json:"user"`
		}
		if json.Unmarshal([]byte(raw), &cached) == nil {
			epoch, _ := s.redis.Get(ctx, currentUserEpoch).Result()
			if epoch == "" {
				epoch = "0"
			}
			if cached.Epoch == epoch {
				return payloadToUser(userID, cached.User), nil
			}
		}
	}
	bundle, err := s.db.GetUserBundle(ctx, userID)
	if err != nil || bundle == nil {
		return nil, errors.New("用户token不合法")
	}
	payload := s.buildPayload(ctx, bundle)
	_ = s.cacheCurrentUser(ctx, userID, payload)
	return payloadToUser(userID, payload), nil
}

func (s *Service) buildPayload(ctx context.Context, b *store.UserBundle) store.CurrentUserPayload {
	perms := []string{}
	if b.IsAdmin {
		perms = []string{"*:*:*"}
	} else {
		seen := map[string]bool{}
		for _, m := range b.Menus {
			if m.Perms.Valid && m.Perms.String != "" && !seen[m.Perms.String] {
				seen[m.Perms.String] = true
				perms = append(perms, m.Perms.String)
			}
		}
	}
	roles := make([]string, len(b.Roles))
	for i, r := range b.Roles {
		roles[i] = r.RoleKey
	}
	postIDs := make([]string, len(b.Posts))
	for i, p := range b.Posts {
		postIDs[i] = fmt.Sprintf("%d", p.PostID)
	}
	roleIDs := make([]string, len(b.Roles))
	for i, r := range b.Roles {
		roleIDs[i] = fmt.Sprintf("%d", r.RoleID)
	}
	userMap := map[string]interface{}{
		"userId": b.User.UserID, "userName": b.User.UserName, "nickName": b.User.NickName,
		"avatar": b.User.Avatar, "email": b.User.Email, "phonenumber": b.User.Phonenumber,
		"sex": b.User.Sex, "postIds": strings.Join(postIDs, ","), "roleIds": strings.Join(roleIDs, ","),
	}
	if b.Dept != nil {
		userMap["deptId"] = b.Dept.DeptID
		userMap["dept"] = map[string]interface{}{"deptId": b.Dept.DeptID, "deptName": b.Dept.DeptName}
	}
	roleList := make([]map[string]interface{}, len(b.Roles))
	for i, r := range b.Roles {
		roleList[i] = map[string]interface{}{
			"roleId": r.RoleID, "roleKey": r.RoleKey, "roleName": r.RoleName,
		}
	}
	userMap["role"] = roleList
	initModify := s.configFlag(ctx, "sys.account.initPasswordModify") && !b.User.PwdUpdateDate.Valid
	expired := s.passwordExpired(ctx, b.User.PwdUpdateDate)
	return store.CurrentUserPayload{
		Permissions: perms, Roles: roles, User: userMap,
		IsDefaultModifyPwd: initModify, IsPasswordExpired: expired,
	}
}

func (s *Service) Login(ctx context.Context, userName, password, code, uuid string, captchaEnabled bool) (string, error) {
	lock, _ := s.redis.Get(ctx, fmt.Sprintf("%s:%s", accountLockKey, userName)).Result()
	if lock == userName {
		return "", errors.New("账号已锁定，请稍后再试")
	}
	if captchaEnabled {
		if err := s.checkCaptcha(ctx, uuid, code); err != nil {
			return "", err
		}
	}
	user, err := s.db.GetUserByName(ctx, userName)
	if err != nil {
		return "", err
	}
	if user == nil {
		return "", errors.New("用户不存在")
	}
	if err := bcrypt.CompareHashAndPassword([]byte(user.Password), []byte(password)); err != nil {
		key := fmt.Sprintf("%s:%s", passwordErrKey, userName)
		n, _ := s.redis.Incr(ctx, key).Result()
		if n == 1 {
			_ = s.redis.Expire(ctx, key, 10*time.Minute).Err()
		}
		if n > 5 {
			_ = s.redis.Del(ctx, key).Err()
			_ = s.redis.Set(ctx, fmt.Sprintf("%s:%s", accountLockKey, userName), userName, 10*time.Minute).Err()
			return "", errors.New("10分钟内密码已输错超过5次，账号已锁定，请10分钟后再试")
		}
		return "", errors.New("密码错误")
	}
	if user.Status == "1" {
		return "", errors.New("用户已停用")
	}
	_ = s.redis.Del(ctx, fmt.Sprintf("%s:%s", passwordErrKey, userName)).Err()

	sessionID := fmt.Sprintf("%d-%d", time.Now().UnixNano(), user.UserID)
	token, err := s.createToken(user, sessionID)
	if err != nil {
		return "", err
	}
	if s.cfg.AppSameTimeLogin {
		_ = s.redis.Set(ctx, fmt.Sprintf("%s:%s", accessTokenKey, sessionID), token, s.cfg.JWTRedisExpire).Err()
	} else {
		_ = s.redis.Set(ctx, fmt.Sprintf("%s:%d", accessTokenKey, user.UserID), token, s.cfg.JWTRedisExpire).Err()
	}
	_ = s.db.UpdateLoginDate(ctx, user.UserID)
	bundle, _ := s.db.GetUserBundle(ctx, user.UserID)
	if bundle != nil {
		payload := s.buildPayload(ctx, bundle)
		_ = s.cacheCurrentUser(ctx, user.UserID, payload)
	}
	return token, nil
}

func (s *Service) Logout(ctx context.Context, token string) error {
	claims := jwt.MapClaims{}
	parsed, err := jwt.ParseWithClaims(token, claims, func(t *jwt.Token) (interface{}, error) {
		return []byte(s.cfg.JWTSecret), nil
	}, jwt.WithoutClaimsValidation())
	if err != nil || !parsed.Valid {
		return nil
	}
	var tokenKey string
	if s.cfg.AppSameTimeLogin {
		if sid, _ := claims["session_id"].(string); sid != "" {
			tokenKey = fmt.Sprintf("%s:%s", accessTokenKey, sid)
		}
	} else {
		if uidRaw, _ := claims["user_id"].(string); uidRaw != "" {
			tokenKey = fmt.Sprintf("%s:%s", accessTokenKey, uidRaw)
		}
	}
	if tokenKey != "" {
		_ = s.redis.Del(ctx, tokenKey).Err()
	}
	if uidRaw, _ := claims["user_id"].(string); uidRaw != "" {
		if uid, err := parseInt64(uidRaw); err == nil {
			_ = s.redis.Del(ctx, fmt.Sprintf("%s:%d", currentUserKey, uid)).Err()
		}
	}
	return nil
}

func (s *Service) InvalidateAllUsers(ctx context.Context) {
	_ = s.redis.Incr(ctx, currentUserEpoch).Err()
}

func (s *Service) InvalidateUser(ctx context.Context, userID int64) {
	_ = s.redis.Del(ctx, fmt.Sprintf("%s:%d", currentUserKey, userID)).Err()
}

func (s *Service) ConfigFlag(ctx context.Context, name string, defaultOn bool) bool {
	return s.configFlag(ctx, name) || (defaultOn && !s.configExists(ctx, name))
}

func (s *Service) configExists(ctx context.Context, name string) bool {
	v, err := s.redis.Get(ctx, fmt.Sprintf("%s:%s", sysConfigKey, name)).Result()
	return err == nil && strings.TrimSpace(v) != ""
}

func (s *Service) configFlag(ctx context.Context, name string) bool {
	v, err := s.redis.Get(ctx, fmt.Sprintf("%s:%s", sysConfigKey, name)).Result()
	if err != nil {
		return false
	}
	t := strings.ToLower(strings.TrimSpace(v))
	return t == "true" || t == "1" || t == "yes" || t == "on" || t == "y"
}

func (s *Service) passwordExpired(ctx context.Context, pwdUpdate sql.NullTime) bool {
	v, err := s.redis.Get(ctx, fmt.Sprintf("%s:sys.account.passwordValidateDays", sysConfigKey)).Result()
	if err != nil || strings.TrimSpace(v) == "" {
		return false
	}
	days := 0
	fmt.Sscanf(v, "%d", &days)
	if days <= 0 {
		return false
	}
	if !pwdUpdate.Valid {
		return true
	}
	return time.Since(pwdUpdate.Time) > time.Duration(days)*24*time.Hour
}

func (s *Service) checkCaptcha(ctx context.Context, uuid, code string) error {
	v, err := s.redis.Get(ctx, fmt.Sprintf("%s:%s", captchaCodesKey, uuid)).Result()
	if err != nil {
		return errors.New("验证码已失效")
	}
	if strings.TrimSpace(code) != strings.TrimSpace(v) {
		return errors.New("验证码错误")
	}
	return nil
}

func (s *Service) StoreCaptcha(ctx context.Context, uuid, answer string) error {
	return s.redis.Set(ctx, fmt.Sprintf("%s:%s", captchaCodesKey, uuid), answer, 2*time.Minute).Err()
}

func (s *Service) createToken(user *store.SysUser, sessionID string) (string, error) {
	deptName := ""
	claims := jwt.MapClaims{
		"user_id":    fmt.Sprintf("%d", user.UserID),
		"user_name":  user.UserName,
		"dept_name":  deptName,
		"session_id": sessionID,
		"exp":        time.Now().UTC().Add(s.cfg.JWTExpire).Unix(),
	}
	return jwt.NewWithClaims(jwt.GetSigningMethod(s.cfg.JWTAlgorithm), claims).SignedString([]byte(s.cfg.JWTSecret))
}

func (s *Service) cacheCurrentUser(ctx context.Context, userID int64, payload store.CurrentUserPayload) error {
	epoch, _ := s.redis.Get(ctx, currentUserEpoch).Result()
	if epoch == "" {
		epoch = "0"
	}
	raw, err := json.Marshal(map[string]interface{}{"epoch": epoch, "user": payload})
	if err != nil {
		return err
	}
	return s.redis.Set(ctx, fmt.Sprintf("%s:%d", currentUserKey, userID), raw, s.cfg.JWTRedisExpire).Err()
}

func (u *User) HasPerm(required ...string) bool {
	if u == nil {
		return false
	}
	set := map[string]bool{}
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

func payloadToUser(userID int64, p store.CurrentUserPayload) *User {
	admin := false
	for _, r := range p.Roles {
		if r == "admin" {
			admin = true
			break
		}
	}
	userName, _ := p.User["userName"].(string)
	return &User{
		UserID: userID, UserName: userName, Admin: admin,
		Permissions: p.Permissions, Roles: p.Roles, Payload: p,
	}
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

func HashPassword(password string) (string, error) {
	b, err := bcrypt.GenerateFromPassword([]byte(password), bcrypt.DefaultCost)
	return string(b), err
}
